"""backend/lan.py — "open on your phone": expose one running app on the Wi-Fi.

Dev servers usually listen on 127.0.0.1 only, so a phone on the same network
can't reach them. While Wi-Fi preview is on for an app, a tiny TCP forwarder
listens on all interfaces (LAN) and passes bytes to the app's local port.
Raw TCP keeps everything working — HTTP, WebSockets, live reload.

Only the chosen app is exposed (never the Homeport dashboard), and only until
it is switched off or the app stops.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import socket
from typing import Optional

import psutil

__all__ = ["LanGateways", "lan_ip"]

_FIRST_PORT = 18000


def lan_ip() -> Optional[str]:
    """This computer's address on the local network (no packets are sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET address: picks the default route
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    for addrs in psutil.net_if_addrs().values():
        for a in addrs:
            if a.family == socket.AF_INET:
                try:
                    if ipaddress.ip_address(a.address).is_private and not a.address.startswith("127."):
                        return a.address
                except ValueError:
                    continue
    return None


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError, asyncio.CancelledError):
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


class LanGateways:
    """One forwarder per app; must be used from the server's event loop."""

    def __init__(self):
        self._servers: dict = {}  # app_id -> (server, lan_port, target_port)

    def info(self, app_id: str) -> Optional[dict]:
        entry = self._servers.get(app_id)
        if entry is None:
            return None
        _server, lan_port, target = entry
        ip = lan_ip()
        return {
            "ip": ip,
            "port": lan_port,
            "target_port": target,
            "url": f"http://{ip}:{lan_port}/" if ip else None,
        }

    def is_on(self, app_id: str) -> bool:
        return app_id in self._servers

    async def start(self, app_id: str, target_port: int) -> dict:
        if lan_ip() is None:
            raise RuntimeError("this computer isn't connected to a local network")
        await self.stop(app_id)

        async def handle(reader, writer):
            try:
                up_reader, up_writer = await asyncio.wait_for(
                    asyncio.open_connection("localhost", target_port), timeout=5)
            except (OSError, asyncio.TimeoutError):
                writer.close()
                return
            await asyncio.gather(_pipe(reader, up_writer), _pipe(up_reader, writer))

        server = None
        port = _FIRST_PORT
        while server is None and port < _FIRST_PORT + 200:
            try:
                server = await asyncio.start_server(handle, host="0.0.0.0", port=port)
            except OSError:
                port += 1
        if server is None:
            raise RuntimeError("no free port for Wi-Fi preview")
        self._servers[app_id] = (server, port, int(target_port))
        return self.info(app_id)

    async def stop(self, app_id: str) -> bool:
        entry = self._servers.pop(app_id, None)
        if entry is None:
            return False
        server = entry[0]
        server.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(server.wait_closed(), timeout=2)
        return True

    async def stop_all(self) -> None:
        for app_id in list(self._servers):
            await self.stop(app_id)
