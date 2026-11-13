"""backend/osutil.py — everything that differs between macOS, Windows and Linux.

The rest of the backend calls these helpers instead of OS-specific commands
(``osascript``, ``open``, ``lsof``, process-group signals …), so the manager
runs the same on all three systems.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import webbrowser
from typing import Optional

import psutil

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

__all__ = [
    "IS_WINDOWS", "IS_MAC", "IS_LINUX", "platform_name",
    "venv_python", "venv_bin_dir", "popen_group_kwargs", "terminate_tree", "kill_pid",
    "listening_pids", "notify", "pick_folder", "PickerUnavailable",
    "open_folder", "open_terminal", "open_url", "pick_file",
]


def platform_name() -> str:
    return "windows" if IS_WINDOWS else "mac" if IS_MAC else "linux" if IS_LINUX else sys.platform


# ---------------------------------------------------------------------------
# Python virtualenv layout
# ---------------------------------------------------------------------------
def venv_bin_dir(venv: str, windows: Optional[bool] = None) -> str:
    """``<venv>/bin`` on macOS/Linux, ``<venv>\\Scripts`` on Windows."""
    win = IS_WINDOWS if windows is None else windows
    return os.path.join(venv, "Scripts") if win else os.path.join(venv, "bin")


def venv_python(venv: str, windows: Optional[bool] = None) -> str:
    win = IS_WINDOWS if windows is None else windows
    return os.path.join(venv_bin_dir(venv, win), "python.exe" if win else "python")


# ---------------------------------------------------------------------------
# processes
# ---------------------------------------------------------------------------
def popen_group_kwargs() -> dict:
    """Popen kwargs that put the child in its own process group, so the whole
    tree (shell + dev server + workers) can be stopped together."""
    if IS_WINDOWS:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP
        if not _has_console():
            # Started with pythonw (e.g. at sign-in): don't pop a console
            # window for every app; output is captured through pipes anyway.
            flags |= subprocess.CREATE_NO_WINDOW
        return {"creationflags": flags}
    return {"start_new_session": True}


def _has_console() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.kernel32.GetConsoleWindow())  # type: ignore[attr-defined]
    except Exception:
        return True


def _tree(pid: int) -> list:
    try:
        root = psutil.Process(pid)
        return [root] + root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []


def terminate_tree(proc: subprocess.Popen, timeout: float = 8.0) -> None:
    """Stop ``proc`` and everything it started: polite first, forced after
    ``timeout`` seconds."""
    pid = proc.pid
    if IS_WINDOWS:
        # cmd.exe exits before its children, so remember the tree up front.
        tree = _tree(pid)
        try:
            os.kill(pid, signal.CTRL_BREAK_EVENT)  # Ctrl+Break to the group
        except (OSError, ValueError, AttributeError):
            pass
        try:
            proc.wait(timeout=max(0.0, float(timeout)))
        except subprocess.TimeoutExpired:
            pass
        alive = [p for p in tree if _alive(p)]
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        psutil.wait_procs(alive, timeout=5.0)
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass
        return

    def signal_group(sig: int) -> None:
        try:
            os.killpg(os.getpgid(pid), sig)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    signal_group(signal.SIGTERM)
    try:
        proc.wait(timeout=max(0.0, float(timeout)))
        return
    except subprocess.TimeoutExpired:
        pass
    signal_group(signal.SIGKILL)
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        pass


def _alive(p) -> bool:
    try:
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def kill_pid(pid: int, force: bool = False) -> None:
    """Terminate (or force-kill) one process, on any OS. Errors are ignored."""
    try:
        p = psutil.Process(int(pid))
        p.kill() if force else p.terminate()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        pass


def listening_pids(port: int) -> list:
    """PIDs listening on TCP ``port``.

    macOS hides other processes' sockets from psutil without root, so use
    ``lsof`` there (and on Linux when present); otherwise psutil, which works
    on Windows and for the user's own processes on Linux.
    """
    port = int(port)
    pids: list = []
    lsof = None if IS_WINDOWS else shutil.which("lsof")
    if lsof:
        try:
            out = subprocess.check_output(
                [lsof, "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
                stderr=subprocess.DEVNULL, text=True, timeout=1.5,
            )
            for line in out.split():
                if line.strip().isdigit() and int(line) not in pids:
                    pids.append(int(line))
            return pids
        except (subprocess.SubprocessError, OSError):
            pass
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port \
                    and conn.pid and conn.pid not in pids:
                pids.append(conn.pid)
    except (psutil.AccessDenied, OSError):
        pass
    return pids


# ---------------------------------------------------------------------------
# desktop integration
# ---------------------------------------------------------------------------
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _powershell() -> Optional[str]:
    return shutil.which("powershell") or shutil.which("pwsh")


def notify(title: str, message: str) -> None:
    """Best-effort desktop notification. Text is passed as data (argv/env),
    never spliced into a script, so app names can't inject commands."""
    try:
        if IS_MAC:
            subprocess.Popen([
                "osascript",
                "-e", "on run argv",
                "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                "-e", "end run",
                title, message,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif IS_WINDOWS:
            ps = _powershell()
            if not ps:
                return
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n = New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon = [System.Drawing.SystemIcons]::Information;"
                "$n.Visible = $true;"
                "$n.ShowBalloonTip(6000, $env:LHM_TITLE, $env:LHM_MSG, 'Warning');"
                "Start-Sleep -Seconds 7; $n.Dispose()"
            )
            subprocess.Popen(
                [ps, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
                env={**os.environ, "LHM_TITLE": title, "LHM_MSG": message},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW,
            )
        else:
            exe = shutil.which("notify-send")
            if exe:
                subprocess.Popen([exe, "--", title, message],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


class PickerUnavailable(RuntimeError):
    """No native folder chooser on this system (UI falls back to its own)."""


def pick_folder(timeout: float = 300.0) -> Optional[str]:
    """Show the native "choose folder" dialog. Returns the path, None when the
    user cancels, or raises PickerUnavailable."""
    if IS_MAC:
        cmd = ["osascript", "-e", "POSIX path of (choose folder)"]
    elif IS_WINDOWS:
        ps = _powershell()
        if not ps:
            raise PickerUnavailable("PowerShell not found")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$d.Description = 'Choose the project folder';"
            "$d.ShowNewFolderButton = $false;"
            "$top = New-Object System.Windows.Forms.Form; $top.TopMost = $true;"
            "if ($d.ShowDialog($top) -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }"
        )
        cmd = [ps, "-NoProfile", "-NonInteractive", "-STA", "-Command", script]
    else:
        if shutil.which("zenity"):
            cmd = ["zenity", "--file-selection", "--directory", "--title=Choose the project folder"]
        elif shutil.which("kdialog"):
            cmd = ["kdialog", "--getexistingdirectory", os.path.expanduser("~")]
        else:
            raise PickerUnavailable("install zenity or kdialog for a native folder picker")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                             creationflags=_NO_WINDOW if IS_WINDOWS else 0)
    except subprocess.TimeoutExpired:
        return None
    except OSError as exc:
        raise PickerUnavailable(str(exc)) from exc

    chosen = (res.stdout or "").strip()
    if res.returncode == 0 and chosen and os.path.isdir(chosen):
        return chosen
    if IS_MAC and res.returncode != 0 and "-128" not in (res.stderr or ""):
        raise PickerUnavailable((res.stderr or "osascript failed").strip())
    return None  # cancelled


def pick_file(timeout: float = 300.0) -> Optional[str]:
    """Show the native "choose file" dialog (web pages and scripts first).
    Returns the path, None when cancelled, or raises PickerUnavailable."""
    if IS_MAC:
        cmd = ["osascript", "-e", 'POSIX path of (choose file with prompt "Choose a page or script to run")']
    elif IS_WINDOWS:
        ps = _powershell()
        if not ps:
            raise PickerUnavailable("PowerShell not found")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.OpenFileDialog;"
            "$d.Title = 'Choose a page or script to run';"
            "$d.Filter = 'Web pages and scripts|*.html;*.htm;*.php;*.js;*.mjs;*.cjs;*.py|All files|*.*';"
            "$top = New-Object System.Windows.Forms.Form; $top.TopMost = $true;"
            "if ($d.ShowDialog($top) -eq 'OK') { [Console]::Out.Write($d.FileName) }"
        )
        cmd = [ps, "-NoProfile", "-NonInteractive", "-STA", "-Command", script]
    else:
        if shutil.which("zenity"):
            cmd = ["zenity", "--file-selection", "--title=Choose a page or script to run",
                   "--file-filter=Web pages and scripts | *.html *.htm *.php *.js *.mjs *.cjs *.py",
                   "--file-filter=All files | *"]
        elif shutil.which("kdialog"):
            cmd = ["kdialog", "--getopenfilename", os.path.expanduser("~"),
                   "*.html *.htm *.php *.js *.mjs *.cjs *.py|Web pages and scripts"]
        else:
            raise PickerUnavailable("install zenity or kdialog for a native file picker")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                             creationflags=_NO_WINDOW if IS_WINDOWS else 0)
    except subprocess.TimeoutExpired:
        return None
    except OSError as exc:
        raise PickerUnavailable(str(exc)) from exc

    chosen = (res.stdout or "").strip()
    if res.returncode == 0 and chosen and os.path.isfile(chosen):
        return chosen
    if IS_MAC and res.returncode != 0 and "-128" not in (res.stderr or ""):
        raise PickerUnavailable((res.stderr or "osascript failed").strip())
    return None  # cancelled


def open_folder(path: str) -> None:
    """Show a folder in Finder / Explorer / the Linux file manager."""
    if IS_WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]
    elif IS_MAC:
        subprocess.run(["open", path], check=True)
    else:
        subprocess.run(["xdg-open", path], check=True)


def open_terminal(path: str) -> None:
    """Open a terminal window in ``path``."""
    if IS_MAC:
        subprocess.run(["open", "-a", "Terminal", path], check=True)
        return
    if IS_WINDOWS:
        wt = shutil.which("wt")
        if wt:
            subprocess.Popen([wt, "-d", path])
        else:
            subprocess.Popen(["cmd.exe", "/K", "cd", "/d", path],
                             creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        return
    candidates = (
        ("gnome-terminal", ["--working-directory", path]),
        ("kgx", ["--working-directory", path]),
        ("konsole", ["--workdir", path]),
        ("xfce4-terminal", ["--working-directory", path]),
        ("alacritty", ["--working-directory", path]),
        ("kitty", ["--directory", path]),
        ("tilix", ["--working-directory", path]),
        ("x-terminal-emulator", []),  # Debian alias: flags vary, so rely on cwd
        ("xterm", []),
    )
    for exe, args in candidates:
        found = shutil.which(exe)
        if found:
            subprocess.Popen([found, *args], cwd=path)
            return
    raise RuntimeError("no terminal emulator found")


def open_url(url: str) -> None:
    if not webbrowser.open(url):
        raise RuntimeError("no web browser available")


def wait_for_port(port: int, timeout: float = 20.0) -> bool:
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False
