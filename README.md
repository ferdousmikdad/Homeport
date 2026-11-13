# Homeport

**The home for every local project you run.** Start, stop, watch and share all
your dev servers — Laravel, PHP, Node, Python, Rails, Go, Rust, Java, .NET,
Docker, static sites and more — from one page in your browser.

Free and open source (MIT). Runs on **macOS, Windows and Linux**.
**No account, no sign-up, no cloud, nothing to pay** — everything runs on
your own computer.

---

## Why Homeport

Most tools cover one slice: a PHP stack, a Node process manager, a tunnel.
Homeport works with the projects you already have, whatever they're built with.

| | |
|---|---|
| 🔍 **Finds how to run anything** | Point it at a folder and it works out the start command — framework, package manager, virtualenv, free port, missing installs. |
| 🧭 **Discover projects** | Pick your `~/Projects` folder; every project inside is detected and added in one click. |
| 🏷️ **Named URLs** | Open apps at `http://blog.localhost:7777` instead of remembering ports. No hosts-file edits — every browser resolves `*.localhost` to your computer. Live reload keeps working. |
| 📱 **Phone preview + QR** | One switch puts an app on your Wi-Fi; scan the QR code to open it on your phone. |
| 🌍 **Public links, safely** | Share a running app on a free `https://…trycloudflare.com` link (no account). Add a **password** and an **auto-expiry** so nothing stays open by accident. Leftover `localhost` links in pages are fixed on the fly, so any framework works for visitors. |
| ⌨️ **Command palette** | Press **⌘K / Ctrl+K** and type: “stop api”, “logs blog”, “share portfolio”, “add redis”. Every action, keyboard-first. |
| 🗄️ **Databases & services** | PostgreSQL, MySQL/MariaDB, Redis, MongoDB and Mailpit as one-click apps — using the server already on your computer, or Docker. Copy the connection URL or ready-made `.env` lines. |
| 📝 **WordPress mode** | Drop in a WordPress site (even a copy of a live one), click **Set up**: database, `wp-config.php` and a live-URL helper are done for you. Import the `.sql` backup and it works on localhost, phones and share links. |
| 🧱 **Workspaces** | Group apps (API + frontend + worker) and start them as one — in your order, each waiting until the previous is up. |
| 🩺 **Crash fixer** | When an app stops, **Why?** reads the log and explains it in plain words — port in use, missing packages, no `.env`, tool not installed, database down — with one-click fixes. Works offline. |
| 🌿 **Git on every card** | Branch, uncommitted changes, commits to pull — and **Pull & restart**. |
| 🧩 **Community recipes** | Teach Homeport a new framework with a small JSON file — no code. See [`recipes/`](recipes/README.md). |
| 🤖 **Optional AI assistant** | If you already use [Claude Code](https://claude.com/claude-code), a chat bubble can diagnose and fix apps for you. Not required for anything else. |

Plus: live CPU / memory / uptime, persistent logs with search, auto-restart on
crash, start at login, port-conflict detection, drag-and-drop organising,
categories, light & dark themes.

## Quick start

**Nothing to install first.** Download or clone this repository, then:

| System  | Start Homeport |
|---------|----------------|
| macOS   | Double-click **`run.command`** (or open `Homeport.app`) |
| Windows | Double-click **`run.bat`** |
| Linux   | Run **`./run.sh`** |

The first start sets everything up by itself (needs internet once, usually
under a minute), then opens <http://localhost:7777>:

1. If this computer has **Python 3.9+**, Homeport uses it.
2. If not, it downloads a **private copy of Python** (via
   [uv](https://github.com/astral-sh/uv)) into the hidden `.runtime/` folder
   here — nothing is installed system-wide and no admin rights are needed.
3. It installs its few Python libraries into `.venv/` in this folder.

After that, starting is instant; libraries are only reinstalled when
`requirements.txt` changes. Deleting the folder removes everything.

Options: `--port 8000`, `--no-browser` (e.g. `./run.sh --port 8000`).
Your own projects still use their own tools (Node, PHP, …) from your system.

### Start at login

| System  | Install | Remove |
|---------|---------|--------|
| macOS   | `scripts/install_autostart.sh` | `scripts/uninstall_autostart.sh` |
| Windows | `scripts\install_autostart_windows.bat` | `scripts\uninstall_autostart_windows.bat` |
| Linux   | `scripts/install_autostart_linux.sh` | `scripts/uninstall_autostart_linux.sh` |

## Privacy & cost

- Homeport only listens on `127.0.0.1` — other devices can't reach the
  dashboard. **Phone preview** exposes just the one app you choose, on your
  local network, until you switch it off or the app stops.
- Public links use Cloudflare's free, account-less Quick Tunnels via the
  open-source `cloudflared` tool, downloaded on first use. Protected links
  ask for your password before anything reaches your app (only a salted
  hash is kept).
- No telemetry, no analytics, no account. Your app list stays in
  `data/apps.json` on your machine.

## Per-system notes

- **Folder picker**: native dialog on macOS and Windows; on Linux `zenity`
  or `kdialog` if installed, otherwise the built-in browser.
- **Crash notifications**: Notification Center (macOS), tray balloon
  (Windows), `notify-send` (Linux).
- Commands Homeport suggests use your system's shell syntax (`cmd` on
  Windows, `sh` elsewhere). You can always edit them.

## Contributing

Bug reports, recipes and pull requests are very welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). Adding support for a new framework is
often just one JSON file in [`recipes/`](recipes/README.md).

```bash
.venv/bin/python -m pytest          # macOS / Linux
.venv\Scripts\python.exe -m pytest  # Windows
```

## License

[MIT](LICENSE) © The Homeport contributors
