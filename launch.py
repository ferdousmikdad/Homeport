"""Start Homeport and open it in the browser (macOS, Windows, Linux).

Run by run.command (macOS), run.sh (Linux/macOS) and run.bat (Windows) after
they have prepared the .venv; can also be run directly:

    .venv/bin/python launch.py            # macOS / Linux
    .venv\\Scripts\\python.exe launch.py    # Windows

Options: --port N (default 7777, or $LHM_PORT), --no-browser.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def _already_running(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "api/health", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Homeport")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LHM_PORT", "7777")))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    os.chdir(HERE)
    sys.path.insert(0, HERE)

    from backend import paths

    # Started without a console (pythonw on Windows, login items): log to a file.
    if sys.stdout is None or sys.stderr is None:
        os.makedirs(os.path.join(paths.DATA_DIR, "logs"), exist_ok=True)
        log = open(os.path.join(paths.DATA_DIR, "logs", "server.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    url = f"http://localhost:{args.port}/"

    from backend import osutil

    if _already_running(url):
        print(f"Homeport is already running at {url}")
        if not args.no_browser:
            osutil.open_url(url)
        return 0

    if not args.no_browser:
        def open_when_ready() -> None:
            if osutil.wait_for_port(args.port, timeout=30):
                try:
                    osutil.open_url(url)
                except Exception:
                    pass

        threading.Thread(target=open_when_ready, daemon=True).start()

    print(f"Homeport is running at {url}  (press Ctrl+C to stop)", flush=True)
    serve(args.port)
    return 0


def serve(port: int) -> None:
    """Run the server until Ctrl+C or "Quit Homeport" (shared with the desktop app)."""
    import uvicorn

    from backend import main as homeport

    # Open dashboard tabs keep a live-update stream open forever; don't let
    # them block quitting (Ctrl+C / closing the window / logout).
    config = uvicorn.Config(homeport.app, host="127.0.0.1", port=port, log_level="warning",
                            timeout_graceful_shutdown=3)
    server = uvicorn.Server(config)
    homeport.request_quit = lambda: setattr(server, "should_exit", True)
    server.run()


if __name__ == "__main__":
    sys.exit(main())
