# GitHub integration

Homeport works with the projects on your computer. Most of them live on
GitHub, so Homeport can connect to GitHub to make the everyday loop shorter:
get a repo running, see whether it builds, review changes and turn feedback
into issues — without leaving Homeport.

It stays true to Homeport's promise: **optional, no Homeport account, nothing
in the cloud.** Homeport talks only to GitHub (`api.github.com`,
`github.com`), and the GitHub login stays on your computer.

---

## 1. Connecting

Settings → **GitHub** shows whether Homeport is connected and as whom.
There are three ways to connect; Homeport uses the first one that works.

| Way | What the user does | When it's used |
|---|---|---|
| **Sign in with GitHub** | Click *Connect*, a short code appears, GitHub opens in the browser, enter the code, done. | The normal way. Uses GitHub's *device flow* (the same sign-in GitHub CLI and VS Code use). No password or secret is typed into Homeport. Needs Homeport's public OAuth app ID (see §6). |
| **GitHub CLI** | Nothing, if `gh auth login` was done before. | If the `gh` command is installed and logged in, Homeport borrows its login (`gh auth token`). Shown as "Connected through GitHub CLI". |
| **Personal access token** | Paste a token. | Fallback for GitHub Enterprise or locked-down setups. Needs the `repo` scope for private repos. |

**Disconnect** deletes the login Homeport saved. A GitHub CLI login is
untouched (Homeport only reads it).

**Where the login is stored:** `<data dir>/github.json`, readable only by
the user (file mode `600`). It's never sent anywhere but GitHub, never
logged, and never shown in the UI or the API (the status only says *who* is
connected). The data folder is in `.gitignore`.

**Scopes asked for:** `repo` (clone and read private repos, CI status,
pull requests) and `read:user` (show who's connected). Nothing that can
delete repos or change settings.

---

## 2. Phase 1 — available now

### 2.1 Add from GitHub

Sidebar → Tools → **Add from GitHub** (also in ⌘K).

1. A list of your repos, most recently updated first, with search. Private
   repos are marked. Not connected? Paste any public repo URL instead.
2. Pick one. Homeport shows where it will go: `<projects folder>/<repo name>`.
   The projects folder is a setting (Settings → GitHub), defaulting to
   `~/Projects` (or `~/Developer` / `~/Code` if one of those exists).
3. **Clone & add** → `git clone` → Homeport detects how to run it (like *Add
   app*), adds it, and starts it if *Start after adding* is ticked.

Rules:
- Only `https://github.com/<owner>/<repo>` URLs or `owner/repo` names.
- Never clones into a folder that already exists and isn't empty.
- Private repos clone with the GitHub login. The login is passed to git for
  that one command through the environment (`GIT_CONFIG_*`), never written
  to the repo's `.git/config` or to the command line.
- *Pull & restart* on a card uses the same login for github.com remotes, so
  private repos keep updating.

### 2.2 GitHub on the card

For apps whose `origin` remote is on github.com:

- The branch in the card's subtitle shows the **CI result** of the latest
  commit on that branch: ✓ passed, ✗ failed, ● running. Hover for details,
  click to open the run on GitHub.
- ⋯ menu → **Open on GitHub** and **Pull requests (N)**.

Without a login, the card still gets *Open on GitHub* (read from the remote);
CI and pull requests need a login.

Numbers are cached for 2 minutes per repo and refreshed in the background,
so the dashboard never waits on GitHub, and a busy dashboard stays far below
GitHub's rate limits (5,000 requests per hour when logged in).

### 2.3 API (Homeport's own, local)

| Method | Path | |
|---|---|---|
| GET | `/api/github/status` | `{connected, source: "homeport"\|"gh"\|null, user: {login, name, avatar_url}, device_flow, gh_installed, projects_dir}` |
| POST | `/api/github/device/start` | starts the sign-in → `{user_code, verification_uri, interval, expires_in}` |
| POST | `/api/github/device/poll` | → `{status: "pending"\|"slow_down"\|"done"\|"expired"\|"denied", user?}` |
| POST | `/api/github/token` | `{token}` → checks it with GitHub, then saves it |
| POST | `/api/github/disconnect` | deletes Homeport's saved login |
| GET | `/api/github/repos?q=` | your repos (name, owner, private, description, language, updated, default branch) |
| POST | `/api/github/clone` | `{repo, name?, start?}` → clones, adds the app, starts it; returns the app |

App state gets `github: {repo, url, ci, ci_url, prs}` (or `null`).

---

## 3. Phase 2 — reviewing changes

- **Preview a pull request.** *Preview PR #42* runs that branch next to your
  own copy, on its own port, using a git **worktree** (a second checkout
  that shares the repo; your working folder is never touched). Removing the
  preview removes the worktree.
- **Share the preview on the PR.** One click posts the public share link
  (and, if feedback is on, how to leave comments) as a comment on the PR.

## 4. Phase 3 — closing the loop

- **Feedback → issue.** Each visitor comment gets *Create issue*: title from
  the comment, body with the page, screen size, the reply thread and a link
  back. The comment remembers the issue and links to it.
- **Crash → issue.** *Report as issue* on a crashed app, with the crash
  fixer's explanation and the last log lines (you see and can edit the text
  first — logs can contain secrets).
- **Auto-update.** *Keep up to date* on a card: Homeport checks GitHub every
  few minutes and runs *Pull & restart* when the branch has new commits
  (only fast-forward pulls, never over local changes).

---

## 5. Safety rules

- GitHub is never contacted unless the user connects or pastes a URL.
- The token never leaves the computer except in requests to GitHub.
- Homeport never pushes, never force-anything, never deletes anything on
  GitHub. Writes (Phase 2/3: comments, issues) only happen on a click, and
  show what will be posted.
- Clones and pulls are fast-forward only and never overwrite local work.

## 6. One-time setup for the maintainer (Sign in with GitHub)

The device flow needs a GitHub **OAuth App** (free):

1. GitHub → Settings → Developer settings → OAuth Apps → **New OAuth App**.
2. Name: *Homeport*, homepage: `https://homeport.ferdousmikdad.com`,
   callback URL: the same (unused by the device flow).
3. Tick **Enable Device Flow**, save, copy the **Client ID** (it's public —
   there is no secret in the device flow).
4. Put it in `backend/github.py` (`CLIENT_ID`), or set the environment
   variable `HOMEPORT_GITHUB_CLIENT_ID`.

Until then, *Sign in with GitHub* is hidden and GitHub CLI / token work.
