# Homeport (formerly Localhost Manager) — original build spec

> Historical design notes from the first versions. The code and README are now the source of truth.

Run with: `.venv/bin/python -m uvicorn backend.main:app --port 7777`. Python 3.14, deps in requirements.txt (fastapi, uvicorn, psutil, httpx, pytest). No other deps. UI is static HTML/JS/CSS in `ui/`, no build step, no CDN.
Only edit the files you own. Do not touch others' files. Do not run `git commit`.

## Data model (JSON, `data/apps.json` = list of AppConfig)
AppConfig: `{id: str(slug of name, unique), name: str, path: str(abs dir), command: str(shell cmd run with cwd=path), port: int|null, health_url: str|null, auto_restart: bool, env: {str:str}}`

AppState (runtime, returned by API, not persisted):
`{id, name, path, command, port, health_url, auto_restart, status, pid: int|null, started_at: float|null (epoch), uptime_s: float|null, cpu_percent: float|null, mem_mb: float|null, detected_port: int|null, healthy: bool|null, restarts: int, last_exit_code: int|null, last_error: str|null}`
status ∈ `"stopped" | "starting" | "running" | "crashed"`.
- stopped: user stopped it or never started. crashed: process exited without a user stop. starting: process alive, port not yet open (max 30s, then "running" anyway if alive). running: alive and (no port configured/detected, or port open).

## Module contracts

### backend/procman.py  (owner: worker A)
```python
class ProcessManager:
    def __init__(self, log_lines: int = 1000): ...
    def start(self, cfg: dict) -> int            # spawn `cfg["command"]` via shell, cwd=cfg["path"], env=os.environ+cfg["env"], new session/process group (start_new_session=True), stdout+stderr merged -> ring buffer. Returns pid. Raises ValueError if already running or path missing.
    def stop(self, app_id: str, timeout: float = 8.0) -> bool   # SIGTERM whole process group, SIGKILL after timeout; marks as user-stopped. False if not running.
    def restart(self, cfg: dict) -> int
    def is_running(self, app_id: str) -> bool
    def info(self, app_id: str) -> dict   # {pid, started_at, exit_code, user_stopped, running}
    def logs(self, app_id: str, tail: int = 200) -> list[str]
    def pid(self, app_id: str) -> int | None
    def shutdown(self) -> None            # stop everything (called on manager exit)
```
Log reading uses a background thread per app. Thread-safe.

### backend/monitor.py  (owner: worker B)
```python
def process_tree_stats(pid: int) -> dict         # {cpu_percent, mem_mb} summed over pid + children (psutil); {} if gone
def listening_ports(pid: int) -> list[int]       # TCP LISTEN ports of pid + descendants
def port_open(port: int, host="127.0.0.1", timeout=0.5) -> bool
async def http_healthy(url: str, timeout=2.0) -> bool   # httpx GET, True if status < 500
def compute_status(cfg: dict, info: dict, port_ok: bool|None, now: float, grace: float = 30.0) -> str   # pure fn, implements status rules above
def should_auto_restart(cfg: dict, info: dict, restarts_in_window: int) -> bool   # only if cfg.auto_restart, status crashed (not user_stopped), and < 5 restarts per 5 minutes
def detect_command(path: str) -> dict   # {"command": str|None, "port": int|None}. Look for, in order: run.py, launch.py, server.py, app.py, main.py (-> "python3 <file>"), package.json "dev"/"start" script (-> "npm run <x>"), *.command (-> "bash '<file>'"). Port: regex-scan README/source for "localhost:NNNN" / "port NNNN" / "PORT = NNNN", else None.
```

### backend/registry.py + backend/main.py  (owner: worker C; start after A and B exist)
registry.py: `Registry(path="data/apps.json")` with `list()`, `get(id)`, `add(cfg)`, `update(id, patch)`, `remove(id)`; atomic write (tmp+rename); slug ids; duplicate name -> ValueError.
main.py: FastAPI app. Background asyncio task ticks every 1s: for each app builds AppState using procman+monitor, handles auto-restart, caches states, pushes to SSE subscribers. On startup, apps are NOT auto-started. On shutdown calls procman.shutdown(). Serves `ui/` at `/` (StaticFiles html=True).
Routes (all JSON):
- `GET /api/apps` -> list[AppState]
- `POST /api/apps` body `{name, path, command?, port?, health_url?, auto_restart?, env?}` -> AppState. If command missing, use detect_command(path). 400 if path is not a directory.
- `PATCH /api/apps/{id}` partial AppConfig -> AppState. `DELETE /api/apps/{id}` -> `{ok:true}` (stops it first).
- `POST /api/apps/{id}/start|stop|restart` -> AppState. 404 unknown id, 409 start when already running.
- `GET /api/apps/{id}/logs?tail=200` -> `{lines: [str]}`
- `GET /api/detect?path=...` -> `{command, port}`
- `GET /api/events` -> SSE, each event `data: <json list[AppState]>\n\n`, sent every second and immediately on connect.
- `GET /api/health` -> `{ok:true}`

### ui/  (owner: worker D) — files: `ui/index.html`, `ui/app.js`, `ui/style.css`, plus `ui/mock_server.py` (stdlib-only mock of the API above on port 7778 with 3 fake apps, so UI can be built independently).
Dark, clean dashboard. Header with title + "Add app" button + summary counts (running/stopped/crashed). Grid of cards: name, status badge (green running, grey stopped, red crashed, amber starting), port link (opens http://localhost:PORT), uptime (live-ticking h:mm:ss), CPU %, mem MB, restarts, buttons Start / Stop / Restart (disabled appropriately), "Logs" (drawer with tail, auto-refresh 2s), auto-restart toggle, delete (confirm). Add-app modal: name, path (on path blur call /api/detect and prefill command+port), command, port, health_url. Use EventSource `/api/events` with fallback to polling `/api/apps` every 2s; relative URLs only (API base can be overridden by `?api=http://localhost:7778`). Escape all text (no innerHTML with user data). Works at phone width.

### tests/  (owner: worker E, last) — pytest for procman (use `sleep`/tiny python http servers), monitor pure functions, and API via FastAPI TestClient. Finish with `tests/smoke_real_apps.md`: result of registering the 3 apps in a local folder of sample apps through the API and starting/stopping each (clean up afterwards; never leave them running).

---
# SPEC v2 (addendum — overrides v1 where they conflict)

## Reported bugs (user, real usage) — must be root-caused with the real apps, not guessed
1. Every app the user adds shows "crashed" / cannot run. Reproduce with the 3 apps in a local folder of sample apps (insight-studio, opus-watch, prompt-scheduler). Read each app's README/launcher to learn its real start command, port flag, venv/deps, and whether it daemonizes/detaches (e.g. opus-watch `launch.py` detaches; use a foreground entry such as `panel.py --no-open` if one exists). Known: port 8795 is held by an UNRELATED user app (other project) — never kill it; pick a free port if the app accepts `--port`/env, else surface a clear conflict message. Prefer the app's own `.venv/bin/python` or `venv/bin/python` when present (detect_command must do this). Likely culprit candidates: wrong python/deps, detached launchers, port conflicts, env.
2. No way to edit an added app. 3. Logs not visible / not working. 4. Path must be chosen with a folder-browse button, not pasted.

## New config/state fields
AppConfig adds: `autostart: bool=false` (start when manager boots), `notify: bool=true` (macOS notification on crash via `osascript -e 'display notification ...'`).
AppState adds: `port_conflict: {pid:int, command:str, cwd:str|null}|null`, and `last_error` must always be filled on crash (exit code + last 3 log lines).

## Logs (persistent)
procman appends every app's merged output to `data/logs/<id>.log` (rotate at 5 MB to `.log.1`), with `[manager] <ISO time> started pid=N cmd=...` / `[manager] <ISO time> exited code=N (stopped by user|crashed)` marker lines. `GET /api/apps/{id}/logs?tail=500` reads from the FILE tail (so history survives manager restarts and works while stopped). `DELETE /api/apps/{id}/logs` clears. `GET /api/apps/{id}/logs/download` returns the file as attachment.

## New/changed routes
- `PATCH /api/apps/{id}` — edit name, path, command, port, health_url, auto_restart, autostart, notify, env. Editing a running app returns state with a `needs_restart` hint (UI offers "Restart now").
- `GET /api/browse?path=` -> `{path, parent|null, entries:[{name, path, looks_like_app:bool}]}` directories only, no hidden dirs, sorted; default path = home dir. `looks_like_app` = detect_command finds a command.
- `POST /api/pick-folder` -> `{path: str|null}` opens the native macOS folder chooser via `osascript -e 'POSIX path of (choose folder)'` (null if cancelled/unavailable). UI: "Browse…" button calls this first, falls back to the in-page `/api/browse` picker if it returns an error.
- `POST /api/apps/start-all`, `POST /api/apps/stop-all` -> list[AppState] (only touches registered apps).
- `POST /api/apps/{id}/open` body `{target: "browser"|"finder"|"terminal"}` using macOS `open` (terminal = `open -a Terminal <path>`).
- Start with a configured/detected port already used by a process NOT managed by us -> `409 {detail:{error:"port_in_use", pid, command, cwd}}`. `POST /api/apps/{id}/start?kill_conflict=1` terminates ONLY that pid (UI asks for explicit confirmation showing pid/command/cwd first).
- On manager startup: start all apps with `autostart`. On crash with `notify`: macOS notification once per crash.
- Every error response is JSON `{detail: str|obj}`; UI shows it in a toast — never fail silently.

## UI v2 requirements
Edit button on each card (same modal as Add, prefilled; saves via PATCH; "Restart now" prompt if running). Path field has a **Browse…** button (native picker, fallback in-page folder browser with breadcrumbs, "Select this folder"); on pick, call `/api/detect` and prefill command/port. Log drawer: shows persistent log, auto-scroll toggle, search/filter box, Clear, Download, wrap toggle, highlights `[manager]` lines and lines containing error/traceback in red; visible even when stopped; shows exit code + last_error banner when crashed. Header: Start all / Stop all, search box, status filter chips (All/Running/Stopped/Crashed). Card extras: Open in browser, Open folder, Open terminal, port-conflict warning with "Kill process & start" confirm dialog, autostart + auto-restart + notify toggles in the edit modal. Toast system for all errors/successes. Keep `ui/mock_server.py` in sync with the new routes.

## Seed data (keep it)
`data/apps.json` must contain the 3 real apps registered with working commands/ports (verified running). `.gitignore` must exclude `data/logs/` but NOT `data/apps.json`.

---
# SPEC v3 (addendum) — organizing apps

- AppConfig/AppState add `category: str = ""` (trimmed; "" = uncategorized). Settable on `POST /api/apps` and `PATCH /api/apps/{id}`.
- Registry order is the user's manual order. `POST /api/apps/reorder` body `{ids: [str]}` -> list[AppState]; unknown ids are ignored, unlisted apps keep their relative order after the listed ones.
- `POST /api/pick-folder` returns `{path: null}` when the user cancels and `501` when the native picker is unavailable (UI then falls back to the in-page browser).
- UI: search, status, category filter, sort (manual/drag, name, folder path, folder created/modified, status, port, memory), group-by-category, grid/list layout, light/dark theme. View prefs are per-browser (localStorage). Dragging a card onto another category group (with Group on) moves it into that category.

---
# SPEC v4 (addendum) — AI assistant

- `backend/ai_routes.py` runs the local `claude` CLI (`claude -p --output-format stream-json`) with the user's logged-in Claude account, cwd = project root. Nothing runs unless the user sends a message; a run is killed on Stop or when the client disconnects. One run at a time (409).
- `GET /api/ai/status` -> `{available, cli, version, busy}`. `POST /api/ai/stop` -> `{stopped}`.
- `POST /api/ai/ask` body `{prompt, model?, session_id?, mode: "act"|"ask"}` -> SSE of `{type: session|text|tool|tool_result|done|error, ...}`. `session_id` resumes the conversation. `act` = full permissions; `ask` = read-only tools.
- System prompt includes a compact snapshot of all apps (and apps sharing a port) and tells the model to change apps only through this HTTP API.
- UI: "Ask AI" header button / ⌘J opens a side panel with model picker (Sonnet/Opus/Haiku/account default/custom id), Act/Ask-only toggle, New chat, Stop, and a "Reload page" button after it edits `ui/` files.

# SPEC v5 (addendum) — local AI assistant (Ollama)

- Optional, offline alternative to Claude Code. `backend/local_ai.py` talks to Ollama (`$OLLAMA_HOST`, default `http://127.0.0.1:11434`). Nothing runs in the background: a model answers only when the user sends a message, and Ollama unloads it `KEEP_ALIVE` (5 min) after the last answer. Homeport's own download size doesn't change; Ollama (~0.5–2 GB) and one model (~1–5 GB) are separate downloads, only for users who turn it on.
- `GET /api/local-ai/status` -> `{installed, running, version, url, models[], catalog[], recommended, ram_gb, disk_free_gb, download_url, busy, pulling}`. `catalog` is a curated list (Qwen3 4B default, Qwen2.5-Coder 7B, Qwen3 8B, Llama 3.2 3B, Qwen2.5-Coder 1.5B, Gemma 3 4B) with size and memory needs.
- `POST /api/local-ai/start` starts Ollama if installed (the macOS app, else `ollama serve`). `POST /api/local-ai/pull {model}` starts a background download on the server (one at a time, 409); progress is `status.pull = {model, status, completed, total, active, done, error, cancelled}`; `POST /api/local-ai/pull/cancel`. The first finished download becomes the selected model. `POST /api/local-ai/delete {model}` (clears the selection if it was that model).
- `POST /api/local-ai/ask {prompt, model, session_id?, mode, app_id?}` -> SSE of the Claude events plus `delta` (streamed text), `status` and `confirm {id, name, summary}`. Conversations are kept in memory (last 10). One run at a time (409). `POST /api/local-ai/stop`.
- Tools (Ollama tool calling): read-only `list_apps, diagnose, get_logs, check_port, list_files, read_file, read_skill`; in Act mode also `run_fix` (only the crash fixer's named fixes), `update_app` (port/command/env), `start_app` (optionally stopping the port blocker), `stop_app`, `restart_app`. Tools call Homeport's own API in-process. Every action tool waits for `POST /api/local-ai/confirm {id, approve}`; declined or unanswered (10 min) = not run. Files are read only inside the app's folder. No shell access.
- Skills: `skills/*.md` (bundled like `recipes/`), short step-by-step guides with `findings:` (crash-fixer ids) and `keywords:`. Up to 2 matching guides go into the system prompt; `diagnose` results include the guides for their findings; any guide can be opened with `read_skill`. With `app_id` (from the crash dialog's "Ask AI to fix"), the app's findings and log tail are added up front.
- Models without tool support (Gemma 3, or Ollama answering "does not support tools") get advice-only mode. Qwen3 runs with `think: false` for speed; `<think>` blocks are hidden.
- Settings (`backend/app_settings.py`): `GET/PATCH /api/settings` -> `{ai_provider: "claude"|"local"|null, local_model}` stored in `<data dir>/settings.json`, shared by every window. With no `ai_provider`, the UI uses Claude Code when installed, else the local model.
- UI: **Settings** in the sidebar (and ⌘K) opens a dialog: AI assistant choice (Claude Code / Local model with their status), Ollama status with Download / Start, the model list (download with progress and Cancel, Use, Remove, memory warning), this computer's memory / free disk / space used by models, and the list of fix guides. While a download runs, the sidebar's Settings item shows its percentage and a toast reports the result; it keeps going if the dialog or page is closed.
- Chat panel: AI picker and a quick local-model picker; "Models" opens Settings. When the local model isn't ready, the chat shows a short card with "Open Settings". The Ask AI button is always shown. Action requests show an Allow / Don't allow card. The crash dialog's "Ask AI to fix" is always shown.

# SPEC v6 (addendum) — visitor feedback on share links

- Share option `feedback` (POST /api/apps/{id}/share body; `PATCH /api/apps/{id}/share {feedback}` changes a live share without a new link). Share state has `feedback`.
- `backend/proxy.py`: on `<id>.share.localhost` with feedback on, HTML pages (full documents only, not fragments) get `<script src="/__homeport/fb.js" data-mode="visitor">`. `/__homeport/fb*` is handled by Homeport and never reaches the app: `GET fb.js` (the widget, `backend/feedback_widget.js`), `POST fb` (store a note; 16 KB max; 30 notes per visitor IP per 10 min, IP from `cf-connecting-ip`). `GET fb/list?page=` (comments on a page, drawn as pins like Figma comments: visitors get only open comments with id, time, message, name, page and position; the owner gets everything plus `can_manage`). Owner-only paths answer 404 on share hosts. Pages on share hosts (and in review mode) are sent with `Cache-Control: no-cache` and no validators, and conditional request headers are dropped, so turning feedback on/off shows on the next reload.
- Review mode (owner, named URL `<id>.localhost` only): `GET /__homeport/fb/review?on=1|0&to=/path&pin=<id>` sets/clears the `homeport_review` cookie and redirects (to `to#homeport-fb=<id>`; `to` must be a local path). With the cookie, pages get the widget in `review` mode: numbered pins, a list (also of general notes), Resolve/Reopen, Add note, Exit review. `GET /__homeport/fb/list?page=`, `POST /__homeport/fb/<id> {status}`.
- `backend/feedback.py`: notes in `<data dir>/feedback/<app id>.json` (max 1000 per app; oldest resolved dropped first). A note: message (≤2000), name (≤60), page, url, title, position (CSS selector + offset in the element, plus page x-fraction/y as fallback), viewport size, user agent, status open|resolved, source share|local. Deleted with the app. App state has `feedback_open`.
- Dashboard API: `GET /api/apps/{id}/feedback`, `PATCH .../feedback/{fid} {status}`, `DELETE .../feedback/{fid}`, `DELETE .../feedback?status=resolved`.
- `POST /api/apps/{id}/open`: target `app` takes an optional `path` (a local path of the app); new target `share` opens the public link. Used by the desktop app, whose web view can't open browser tabs.
- UI: share dialog checkbox "Let visitors leave feedback" (remembered); share bar "Feedback on/off" switch; 💬 count chip on the card; Feedback dialog (Open/Resolved/All, Show on page, Resolve/Reopen, Delete, Delete resolved, View with / without feedback; refreshes every 5 s). Card menu starts with Open, Copy link, Feedback…; menus open toward the side with more room and scroll if needed.

- Widget: pins and the open comment / the comment being written are placed every animation frame from their anchor (element + offset, page coordinates as fallback), so they move with scrolling (also inside scrollable areas) and layout changes. After posting, the comment stays as a pin (blue = yours). Toolbar: `N comments` (list, incl. general comments), Hide/Show (remembered), Comment; review mode adds Show resolved, Exit review, Resolve/Reopen. Comments refresh every 15 s.

# SPEC v7 (addendum) — Figma-style comments, macOS-style Settings

- Comments widget (`backend/feedback_widget.js`) works like Figma comments: dark floating toolbar (Add comment `C`, Comments panel with open count, show/hide, and in review mode Show resolved / Exit review); comment mode with a comment cursor (click anywhere, Esc to exit, the page still scrolls); pins are avatar bubbles (initials, colour per name, pointed corner on the spot) that preview on hover; a click opens the thread card (messages, Reply box with a round send button, ✓ resolve for the owner); the Comments panel lists every comment on the page. Enter sends, Shift+Enter makes a new line. The visitor's name is asked once and remembered.
- Replies (threads): `POST /__homeport/fb/<id>/reply {message, name?}` on share links (open comments only, rate limited) and on the owner's named URL; `POST /api/apps/{id}/feedback/{fid}/reply` from the dashboard. Up to 100 replies per comment. Visitors get replies with id, time, message and name only.
- Feedback dialog in the dashboard shows each thread and has a reply box (your name comes from Settings → Sharing & Feedback).
- Settings uses the app's own look (line icons, pill nav, grouped lists, × close on the right). Sections: General (theme System/Light/Dark, open apps when they start, keyboard shortcuts), AI assistant (assistant, default mode, Claude or local model, status), Local AI (Ollama status, memory, disk), Models (download/use/remove, progress also on the nav item and the sidebar), Sharing & feedback (default link expiry, feedback on by default, your name on replies), Fix guides, About (address, data folder with Open folder, license, links). `GET /api/about`, `POST /api/about/open-data`.
- Sidebar order: app filters, Categories, Tools (Discover projects, Databases & services), then Settings at the bottom above the Homeport card; the ? icon opens Homeport's docs.

- Cards (grid view) are simpler: name + feedback count (line icon), subtitle "status · uptime · branch" (CPU, memory, uptime and restarts in the status tooltip), the app's address on its own line, sharing as one line ("Shared · time left · password" + Copy) whose menu holds the full link, Visitor feedback on/off, View feedback, QR code and Stop sharing. Buttons: stopped = Logs + Start; running = Share + Logs + Stop + Open. The list view keeps stats, path and type.

# SPEC v8 (addendum) — GitHub integration, phase 1

See `docs/GITHUB.md` for the full design. `backend/github.py`: connect (device flow when `CLIENT_ID` / `HOMEPORT_GITHUB_CLIENT_ID` is set, GitHub CLI login, or a pasted token saved in `<data dir>/github.json` mode 600), `/api/github/{status,device/start,device/poll,token,disconnect,repos,clone}`, setting `projects_dir`. App state `github: {repo, url, ci, ci_url, prs}` (cached 2 min per repo/branch, background refresh; CI and PRs only when connected). *Pull & restart* uses the login for https github.com remotes via `GIT_CONFIG_*` env (never written to disk). UI: sidebar Tools → Add from GitHub (also ⌘K), Settings → GitHub, card branch shows ✓/✗/● CI (click opens the run), ⋯ → Open on GitHub / Pull requests (N).
