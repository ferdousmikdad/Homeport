"""Homeport desktop app — runs Homeport and shows it in its own window.

Used by the installers (.dmg / Setup.exe / AppImage / .deb). It:

* reuses a Homeport that's already running, otherwise starts the server
  in the background (on 7777, or the next free port);
* shows the dashboard in a native window (the system's own web engine via
  pywebview: WebKit on macOS, Edge WebView2 on Windows, GTK/Qt on Linux);
* falls back to the default browser where no native window is available;
* quits Homeport — and the apps it runs — when the window is closed.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import urllib.request

if getattr(sys, "frozen", False):
    ROOT = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as resp:
            return resp.status == 200 and b'"ok":true' in resp.read().replace(b" ", b"")
    except Exception:
        return False


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _log_to_file() -> None:
    """Windowed builds have no console: keep a log in the data folder."""
    from backend import paths

    interactive = sys.stdout is not None and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    if interactive:
        return
    os.makedirs(os.path.join(paths.DATA_DIR, "logs"), exist_ok=True)
    log = open(os.path.join(paths.DATA_DIR, "logs", "desktop.log"), "a", encoding="utf-8", buffering=1)
    sys.stdout = log
    sys.stderr = log


def main() -> int:
    _log_to_file()
    from backend import main as homeport
    from backend import osutil
    from launch import serve

    port = int(os.environ.get("HOMEPORT_PORT", "7777"))
    server_thread = None
    if not _healthy(port):
        while not _port_free(port) and port < 7900:
            port += 1  # something else holds 7777
        server_thread = threading.Thread(target=serve, args=(port,), name="homeport-server", daemon=True)
        server_thread.start()
        if not osutil.wait_for_port(port, timeout=60):
            print("Homeport's server didn't start", file=sys.stderr)
            return 1
    url = f"http://localhost:{port}/"

    try:
        import webview  # pywebview
    except Exception:
        webview = None

    shown = False
    if webview is not None:
        try:
            window = webview.create_window("Homeport", url, width=1360, height=880, min_size=(900, 600),
                                           background_color="#f3f3f4", text_select=True)
            stop_server = homeport.request_quit

            def quit_all() -> None:  # "Quit Homeport" in the dashboard closes the window too
                window.destroy()  # first: drops the page's live connection so the server stops fast
                if stop_server is not None:
                    stop_server()

            homeport.request_quit = quit_all
            webview.start()  # blocks until the window is closed
            homeport.request_quit = stop_server
            shown = True
        except Exception as exc:  # no usable web engine (e.g. minimal Linux)
            import traceback

            traceback.print_exc()
            print(f"native window unavailable ({exc}); opening the browser", file=sys.stderr)

    if not shown:
        osutil.open_url(url)
        if server_thread is not None:
            server_thread.join()  # until "Quit Homeport" in the dashboard
        return 0

    # Window closed: stop Homeport (and every app it runs) if we started it.
    if server_thread is not None and homeport.request_quit is not None:
        homeport.request_quit()
        server_thread.join(timeout=15)
    return 0


if __name__ == "__main__":
    sys.exit(main())
