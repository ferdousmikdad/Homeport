# Contributing to Homeport

Thanks for helping! Homeport aims to stay **free, local and account-less**:
no feature may require a sign-up, a paid service or sending users' data
anywhere. Optional integrations (like the AI assistant) must stay optional.

## Ways to help

- **Add a recipe** — teach Homeport a framework with one JSON file in
  [`recipes/`](recipes/README.md). The easiest first contribution.
- **Report a project it can't run** — open an issue with the folder layout
  (file names only) and the command you use to start it.
- **Teach the crash fixer** — new error patterns live in
  [`backend/diagnose.py`](backend/diagnose.py). Fixes must be predefined
  actions; never run text taken from logs or the browser.
- **Test on your OS** — Windows and Linux reports are especially valuable.

## Development

```bash
./run.sh --no-browser            # or run.bat / run.command — creates .venv
.venv/bin/python -m pytest       # tests must pass on macOS, Windows and Linux
```

- Backend: Python 3.9+, FastAPI, no build step. OS differences belong in
  `backend/osutil.py`; generated commands must work in both `sh` and
  `cmd.exe` (see `backend/detect.py`).
- Front-end: plain HTML/CSS/JS in `ui/` — no framework, no CDN, no build.
  Never use `innerHTML` with app data.
- Keep pull requests focused, add tests for behaviour changes, and describe
  what you checked by hand.

By contributing you agree your work is released under the [MIT license](LICENSE).
