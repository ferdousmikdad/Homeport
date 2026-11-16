"""backend/local_https.py — open apps at https://<app>.localhost with a trusted local certificate.

Homeport makes its own small certificate authority (CA) in the data folder and
asks the system to trust it once (macOS: a Keychain password prompt; Windows:
a certificate-store prompt; Linux: the steps are shown). A second listener then
speaks HTTPS in front of the same named-URL proxy as http://<app>.localhost, so
the apps keep running on plain HTTP and need no changes.

* The CA can only vouch for ``localhost`` names (an X.509 name constraint), and
  its private key never leaves the data folder (mode 600).
* Browsers don't accept a ``*.localhost`` wildcard, so every ``<app>.localhost``
  name gets its own certificate, made the first time it's visited.

    GET    /api/https          -> status (see status())
    POST   /api/https/setup    -> create the CA if needed, start HTTPS, ask the system to trust it
    POST   /api/https/trust    -> ask the system to trust the CA again
    DELETE /api/https          -> stop HTTPS, forget the CA in the system, delete it
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime
import ipaddress
import os
import re
import shutil
import socket
import ssl
import subprocess
import threading
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from . import osutil, paths

router = APIRouter()

CA_NAME = "Homeport Local CA"
DEFAULT_PORT = 7443
LEAF_DAYS = 397  # Apple refuses longer-lived server certificates from user-added roots
_HOST_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)?localhost$")

asgi_app: Any = None  # set by main.py: the app the HTTPS listener serves

_lock = threading.RLock()
_leaf: dict[str, ssl.SSLContext] = {}
_trusted: Optional[bool] = None  # cached system answer; None = not checked yet
_server: Any = None  # uvicorn.Server
_task: Optional[asyncio.Task] = None
port: Optional[int] = None


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------
def _dir() -> str:
    return os.path.join(paths.DATA_DIR, "https")


def _ca_files() -> tuple[str, str]:
    d = _dir()
    return os.path.join(d, "ca-key.pem"), os.path.join(d, "ca.pem")


def available() -> bool:
    try:
        import cryptography  # noqa: F401
        return True
    except Exception:
        return False


def has_ca() -> bool:
    key, pem = _ca_files()
    return os.path.isfile(key) and os.path.isfile(pem)


def _write_private(path: str, data: bytes) -> None:
    """Write a file only this user can read (private keys)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


# ---------------------------------------------------------------------------
# certificates
# ---------------------------------------------------------------------------
def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def create_ca() -> None:
    """Make the CA (once). Its key is EC P-256 and it may only sign localhost names."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    with _lock:
        if has_ca():
            return
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, CA_NAME),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Homeport (this computer only)"),
        ])
        now = _now()
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                         content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            # Only names under localhost. (No IP-address constraint: LibreSSL — used by
            # macOS's curl and some Pythons — rejects certificates that have one.)
            .add_extension(x509.NameConstraints(permitted_subtrees=[x509.DNSName("localhost")],
                                                excluded_subtrees=None), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256())
        )
        key_path, pem_path = _ca_files()
        _write_private(key_path, key.private_bytes(serialization.Encoding.PEM,
                                                   serialization.PrivateFormat.PKCS8,
                                                   serialization.NoEncryption()))
        with open(pem_path, "wb") as fh:
            fh.write(cert.public_bytes(serialization.Encoding.PEM))
        _leaf.clear()


def _load_ca():
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    key_path, pem_path = _ca_files()
    with open(key_path, "rb") as fh:
        key = serialization.load_pem_private_key(fh.read(), password=None)
    with open(pem_path, "rb") as fh:
        cert = x509.load_pem_x509_certificate(fh.read())
    return key, cert


def ca_fingerprint() -> Optional[str]:
    """SHA-1 of the CA certificate, in the form the OS tools use (upper-case hex)."""
    if not has_ca():
        return None
    from cryptography.hazmat.primitives import hashes

    _, cert = _load_ca()
    return cert.fingerprint(hashes.SHA1()).hex().upper()


def leaf_pem(hostname: str) -> bytes:
    """A server certificate + key (PEM) for one localhost name, signed by the CA."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    ca_key, ca_cert = _load_ca()
    key = ec.generate_private_key(ec.SECP256R1())
    names: list = [x509.DNSName(hostname)]
    if hostname == "localhost":
        names += [x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.IPAddress(ipaddress.ip_address("::1"))]
    now = _now()
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=LEAF_DAYS))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=False, key_cert_sign=False,
                                     crl_sign=False, content_commitment=False, data_encipherment=False,
                                     key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    return (key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption())
            + cert.public_bytes(serialization.Encoding.PEM))


def _context_for(hostname: str) -> ssl.SSLContext:
    """A TLS server context for one name (cached; certificates live in the data folder)."""
    with _lock:
        ctx = _leaf.get(hostname)
        if ctx is not None:
            return ctx
        path = os.path.join(_dir(), "hosts", hostname + ".pem")
        fresh = False
        if os.path.isfile(path):
            try:
                from cryptography import x509
                with open(path, "rb") as fh:
                    cert = x509.load_pem_x509_certificate(fh.read())
                fresh = cert.not_valid_after_utc - _now() > datetime.timedelta(days=30)
            except Exception:
                fresh = False
        if not fresh:
            _write_private(path, leaf_pem(hostname))
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(path)
        _leaf[hostname] = ctx
        return ctx


def server_context() -> ssl.SSLContext:
    """The listener's context: localhost by default, each <app>.localhost by SNI."""
    base = _context_for("localhost")

    def pick(sock: ssl.SSLObject, server_name: Optional[str], _ctx: ssl.SSLContext) -> None:
        name = (server_name or "").strip().lower().rstrip(".")
        if name and name != "localhost" and _HOST_RE.match(name):
            try:
                sock.context = _context_for(name)
            except Exception:
                pass  # fall back to the localhost certificate; the browser says why
        return None

    base.sni_callback = pick
    return base


# ---------------------------------------------------------------------------
# system trust
# ---------------------------------------------------------------------------
def _mac_keychain() -> str:
    return os.path.expanduser("~/Library/Keychains/login.keychain-db")


def _run(cmd: list[str], timeout: float = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def is_trusted(refresh: bool = False) -> Optional[bool]:
    """Does the system trust the CA? None where Homeport can't tell (Linux)."""
    global _trusted
    if not has_ca():
        return False
    if _trusted is not None and not refresh:
        return _trusted
    result: Optional[bool] = None
    try:
        if osutil.IS_MAC:
            # verify a localhost certificate the way a browser would
            path = os.path.join(_dir(), "hosts", "localhost.pem")
            if not os.path.isfile(path):
                _context_for("localhost")
            res = _run(["security", "verify-cert", "-c", path, "-p", "ssl", "-s", "localhost", "-q"], timeout=20)
            result = res.returncode == 0
        elif osutil.IS_WINDOWS:
            fp = ca_fingerprint()
            res = _run(["certutil", "-user", "-verifystore", "Root", fp or ""], timeout=20)
            result = res.returncode == 0
    except Exception:
        result = None
    _trusted = result
    return result


def trust() -> dict:
    """Ask the system to trust the CA. The OS shows its own prompt; nothing is trusted silently."""
    global _trusted
    _, pem = _ca_files()
    if osutil.IS_MAC:
        res = _run(["security", "add-trusted-cert", "-r", "trustRoot", "-p", "ssl", "-k", _mac_keychain(), pem])
    elif osutil.IS_WINDOWS:
        res = _run(["certutil", "-user", "-addstore", "Root", pem])
    else:
        _trusted = None
        return {"ok": False, "manual": True, "steps": linux_steps()}
    _trusted = None
    ok = res.returncode == 0 and bool(is_trusted(refresh=True))
    detail = (res.stderr or res.stdout or "").strip()[-300:]
    return {"ok": ok, "manual": False, "detail": None if ok else (detail or "the system didn't trust the certificate")}


def linux_steps() -> list[str]:
    _, pem = _ca_files()
    return [
        f"Chrome / Chromium: Settings → Privacy and security → Security → Manage certificates → Authorities → Import {pem} and tick “Trust this certificate for identifying websites”.",
        f"Firefox: Settings → Privacy & Security → Certificates → View Certificates → Authorities → Import {pem}.",
        f"Command-line tools (curl, Node): sudo cp {pem} /usr/local/share/ca-certificates/homeport.crt && sudo update-ca-certificates",
    ]


def untrust() -> None:
    """Best effort: make the system forget the CA (the OS may ask again)."""
    if not has_ca():
        return
    _, pem = _ca_files()
    fp = ca_fingerprint()
    with contextlib.suppress(Exception):
        if osutil.IS_MAC:
            _run(["security", "remove-trusted-cert", pem])
            if fp:
                _run(["security", "delete-certificate", "-Z", fp, _mac_keychain()])
        elif osutil.IS_WINDOWS and fp:
            _run(["certutil", "-user", "-delstore", "Root", fp])


# ---------------------------------------------------------------------------
# the HTTPS listener
# ---------------------------------------------------------------------------
def _free_port(start: int) -> Optional[int]:
    for p in range(start, start + 60):
        with socket.socket() as s:
            if os.name != "nt":
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # same rule as uvicorn
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return None


def running() -> bool:
    return _task is not None and not _task.done() and port is not None


async def start() -> Optional[int]:
    """Start serving HTTPS (once the CA exists). Returns the port."""
    global _server, _task, port
    if running():
        return port
    if asgi_app is None or not has_ca() or not available():
        return None
    import uvicorn

    chosen = _free_port(int(os.environ.get("HOMEPORT_HTTPS_PORT") or DEFAULT_PORT))
    if chosen is None:
        return None

    class _Server(uvicorn.Server):
        # The main server owns Ctrl+C and signals; this one just follows it.
        @contextlib.contextmanager
        def capture_signals(self):
            yield

        def install_signal_handlers(self) -> None:  # older uvicorn
            return None

    config = uvicorn.Config(asgi_app, host="127.0.0.1", port=chosen, log_level="warning",
                            lifespan="off", timeout_graceful_shutdown=2)
    config.load()
    config.ssl = await asyncio.to_thread(server_context)
    _server = _Server(config)
    _task = asyncio.create_task(_server.serve())
    port = chosen
    for _ in range(50):  # up to ~5 s for the socket to open
        if _server.started or _task.done():
            break
        await asyncio.sleep(0.1)
    if _task.done():
        port = None
        return None
    return port


async def stop() -> None:
    global _server, _task, port
    if _server is not None:
        _server.should_exit = True
    if _task is not None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(_task, timeout=5)
    _server = _task = None
    port = None


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------
def wants_https(cfg: dict, default: Optional[bool]) -> bool:
    """An app opens over HTTPS when its own switch says so, else the Settings default."""
    own = cfg.get("https")
    return own if isinstance(own, bool) else bool(default)


def app_url(app_id: str, cfg: dict, default: Optional[bool], http_port: int, page: str = "/") -> str:
    if running() and wants_https(cfg, default):
        return f"https://{app_id}.localhost:{port}{page}"
    return f"http://{app_id}.localhost:{http_port}{page}"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def status() -> dict:
    from . import app_settings

    ok = available()
    return {
        "available": ok,
        "ready": ok and has_ca(),
        "trusted": is_trusted() if ok and has_ca() else False,
        "running": running(),
        "port": port if running() else None,
        "default": bool(app_settings.load().get("https_default")),
        "platform": osutil.platform_name(),
        "ca_path": _ca_files()[1] if has_ca() else None,
        "steps": linux_steps() if has_ca() and not (osutil.IS_MAC or osutil.IS_WINDOWS) else None,
    }


@router.get("/api/https")
async def get_status() -> dict:
    return await asyncio.to_thread(status)


@router.post("/api/https/setup")
async def setup() -> dict:
    if not available():
        raise HTTPException(status_code=503, detail="this Homeport build can't make certificates (the cryptography package is missing)")
    await asyncio.to_thread(create_ca)
    if await start() is None:
        raise HTTPException(status_code=500, detail="couldn't start HTTPS — no free port from 7443")
    result = await asyncio.to_thread(trust)
    out = await asyncio.to_thread(status)
    out["trust"] = result
    return out


@router.post("/api/https/trust")
async def trust_again() -> dict:
    if not has_ca():
        raise HTTPException(status_code=409, detail="set up HTTPS first")
    result = await asyncio.to_thread(trust)
    out = await asyncio.to_thread(status)
    out["trust"] = result
    return out


@router.delete("/api/https")
async def remove() -> dict:
    global _trusted
    await stop()
    await asyncio.to_thread(untrust)
    with _lock:
        _leaf.clear()
        shutil.rmtree(_dir(), ignore_errors=True)
    _trusted = None
    return await asyncio.to_thread(status)
