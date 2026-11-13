"""backend/tunnels.py — share a running local app on a public https link.

Uses Cloudflare Quick Tunnels (``cloudflared tunnel --url``): free, no account,
random ``https://<words>.trycloudflare.com`` address that changes each time.

Safe sharing:
* **password** — the tunnel then points at Homeport's own proxy, which asks
  for the password before forwarding to the app (see backend/proxy.py);
* **expiry** — the link shuts itself down after the chosen time.

The Host header is rewritten so dev servers that only accept localhost
(Vite, Django …) still answer.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import platform
import re
import secrets
import subprocess
import tarfile
import threading
import time
from collections import deque
from typing import Optional

from . import osutil, shellenv

__all__ = ["TunnelManager", "CloudflaredMissing"]

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(_PROJECT_ROOT, "bin")

_QUICK_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


class CloudflaredMissing(RuntimeError):
    pass


def _release_asset(system: Optional[str] = None, machine: Optional[str] = None) -> str:
    """Name of the official cloudflared release file for this OS/CPU."""
    system = (system or osutil.platform_name()).lower()
    machine = (machine or platform.machine()).lower()
    arm64 = machine in ("arm64", "aarch64")
    if system == "mac":
        return f"cloudflared-darwin-{'arm64' if arm64 else 'amd64'}.tgz"
    if system == "windows":
        # Windows on ARM runs the amd64 build through emulation.
        return "cloudflared-windows-386.exe" if machine in ("x86", "i386", "i686") else "cloudflared-windows-amd64.exe"
    if machine.startswith("armv7") or machine == "armv6l":
        return "cloudflared-linux-arm"
    return f"cloudflared-linux-{'arm64' if arm64 else 'amd64'}"


_EXE = "cloudflared.exe" if os.name == "nt" else "cloudflared"


SHARE_HOST_SUFFIX = ".share.localhost"


class _Share:
    def __init__(self, app_id: str, port: int, password: Optional[str], expires_at: Optional[float]):
        self.app_id = app_id
        self.port = port
        self.status = "starting"  # starting | live | error
        self.url: Optional[str] = None
        self.error: Optional[str] = None
        self.started_at = time.time()
        self.expires_at = expires_at
        self.lines: deque = deque(maxlen=60)
        self.proc: Optional[subprocess.Popen] = None
        self.checking = False
        # password: only a salted hash is kept; the cookie secret is per share
        self.salt = secrets.token_hex(16)
        self.pw_hash = _hash_pw(password, self.salt) if password else None
        self.secret = secrets.token_hex(32)

    def public(self) -> dict:
        return {
            "mode": "quick",
            "status": self.status,
            "url": self.url,
            "error": self.error,
            "port": self.port,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "protected": self.pw_hash is not None,
        }


def _hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), 120_000).hex()


class TunnelManager:
    """Start/stop one tunnel per app; thread-safe."""

    def __init__(self):
        self._lock = threading.RLock()
        self._shares: dict = {}

    # ------------------------------------------------------------------
    # cloudflared binary
    # ------------------------------------------------------------------
    def binary(self) -> Optional[str]:
        local = os.path.join(BIN_DIR, _EXE)
        if os.path.isfile(local) and (osutil.IS_WINDOWS or os.access(local, os.X_OK)):
            return local
        return shellenv.which("cloudflared")

    def version(self) -> Optional[str]:
        exe = self.binary()
        if not exe:
            return None
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        match = re.search(r"version\s+(\S+)", out.stdout + out.stderr)
        return match.group(1) if match else "unknown"

    def install(self) -> str:
        """Download the official cloudflared release from GitHub into bin/."""
        import httpx

        asset = _release_asset()
        url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"
        with httpx.Client(follow_redirects=True, timeout=180) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.content
        os.makedirs(BIN_DIR, exist_ok=True)
        if asset.endswith(".tgz"):
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                member = next((m for m in tar.getmembers()
                               if m.isfile() and os.path.basename(m.name) == "cloudflared"), None)
                if member is None:
                    raise RuntimeError("cloudflared binary not found in the download")
                data = tar.extractfile(member).read()
        target = os.path.join(BIN_DIR, _EXE)
        tmp = target + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, 0o755)
        os.replace(tmp, target)
        return target

    def status(self) -> dict:
        return {"cloudflared": bool(self.binary()), "version": self.version()}

    # ------------------------------------------------------------------
    # sharing
    # ------------------------------------------------------------------
    def get(self, app_id: str) -> Optional[dict]:
        with self._lock:
            share = self._shares.get(app_id)
            if share is None:
                return None
            if share.proc and share.proc.poll() is not None and share.status != "error":
                share.status = "error"
                tail = " | ".join(list(share.lines)[-3:])
                share.error = f"tunnel exited (code {share.proc.returncode}). {tail}".strip()
            return share.public()

    def is_sharing(self, app_id: str) -> bool:
        with self._lock:
            return app_id in self._shares

    def start(self, app_id: str, port: int, *, manager_port: int = 7777,
              password: Optional[str] = None, expires_minutes: Optional[float] = None) -> dict:
        """Open a Quick Tunnel to the app. With a password, the tunnel goes
        through Homeport's proxy (``<id>.share.localhost``), which asks for it."""
        exe = self._require_binary()
        password = (password or "").strip() or None
        if password is not None and len(password) < 4:
            raise ValueError("use a password of at least 4 characters")
        expires_at = None
        if expires_minutes:
            minutes = float(expires_minutes)
            if not (1 <= minutes <= 7 * 24 * 60):
                raise ValueError("expiry must be between 1 minute and 7 days")
            expires_at = time.time() + minutes * 60
        self.stop(app_id)

        share = _Share(app_id, int(port), password, expires_at)
        if password:
            origin = f"http://localhost:{int(manager_port)}"
            host = f"{app_id}{SHARE_HOST_SUFFIX}"
        else:
            origin = f"http://localhost:{int(port)}"
            host = f"localhost:{int(port)}"
        cmd = [exe, "tunnel", "--no-autoupdate", "--http-host-header", host, "--url", origin]

        share.proc = self._spawn(cmd)
        with self._lock:
            self._shares[app_id] = share
        threading.Thread(target=self._read, args=(share,), daemon=True).start()
        return share.public()

    def stop(self, app_id: str) -> bool:
        with self._lock:
            share = self._shares.pop(app_id, None)
        if share is None:
            return False
        proc = share.proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        return True

    def shutdown(self) -> None:
        for app_id in list(self._shares):
            self.stop(app_id)

    def stop_expired(self) -> list:
        """Stop shares whose time is up; returns their app ids."""
        now = time.time()
        with self._lock:
            due = [a for a, s in self._shares.items() if s.expires_at and s.expires_at <= now]
        for app_id in due:
            self.stop(app_id)
        return due

    # password check used by the proxy ----------------------------------
    def auth_info(self, app_id: str) -> Optional[tuple]:
        """(salt, pw_hash, secret, port) for a password-protected share."""
        with self._lock:
            share = self._shares.get(app_id)
            if share is None or share.pw_hash is None:
                return None
            return share.salt, share.pw_hash, share.secret, share.port

    def check_password(self, app_id: str, password: str) -> bool:
        info = self.auth_info(app_id)
        if info is None:
            return False
        salt, pw_hash, _secret, _port = info
        return hmac.compare_digest(_hash_pw(password or "", salt), pw_hash)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _spawn(self, cmd: list) -> subprocess.Popen:
        return subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env={**os.environ, "PATH": shellenv.user_path()},
            **osutil.popen_group_kwargs(),
        )

    def _require_binary(self) -> str:
        exe = self.binary()
        if not exe:
            raise CloudflaredMissing("cloudflared is not installed — use Share settings → Install")
        return exe

    def _read(self, share: _Share) -> None:
        proc = share.proc
        if proc is None or proc.stdout is None:
            return
        for raw in proc.stdout:
            line = raw.rstrip()
            share.lines.append(line)
            if share.status == "starting":
                match = _QUICK_URL.search(line)
                if match and "api.trycloudflare.com" not in match.group(0):
                    share.url = match.group(0)
                if share.url and "Registered tunnel connection" in line and not share.checking:
                    share.checking = True
                    threading.Thread(target=self._go_live_when_resolvable, args=(share,),
                                     daemon=True).start()
        proc.wait()

    def _go_live_when_resolvable(self, share: _Share, timeout: float = 45.0) -> None:
        """Mark the share live once its hostname resolves publicly.

        Cloudflare reports the tunnel connected a few seconds before the new
        hostname exists in DNS; opening the link in that window makes the
        Mac cache "not found". Ask Cloudflare's DNS-over-HTTPS (not the local
        resolver) so the local cache is never poisoned.
        """
        import httpx

        host = (share.url or "").split("://", 1)[-1].split("/", 1)[0]
        deadline = time.time() + timeout
        while time.time() < deadline and share.proc and share.proc.poll() is None:
            try:
                resp = httpx.get(
                    "https://cloudflare-dns.com/dns-query",
                    params={"name": host, "type": "A"},
                    headers={"accept": "application/dns-json"},
                    timeout=5,
                )
                if resp.status_code == 200 and resp.json().get("Answer"):
                    time.sleep(1.0)
                    break
            except Exception:
                pass
            time.sleep(1.5)
        if share.status == "starting":
            share.status = "live"
