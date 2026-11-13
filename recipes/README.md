# Recipes

A recipe is a small JSON file that teaches Homeport how to run one kind of
project. Recipes are checked **before** the built-in detectors, so they can
add new frameworks or override how a known one is started.

- Shipped recipes live here, in `recipes/`. Add one with a pull request.
- Your own recipes go in `~/.homeport/recipes/` (they are picked up within
  seconds, no restart needed).

## Format

```json
{
  "name": "Hugo",
  "match": {
    "all": ["archetypes|layouts|content"],
    "any": ["hugo.toml", "config.toml"],
    "none": ["package.json"],
    "contains": {"config.toml": "baseURL"}
  },
  "requires": ["hugo"],
  "port": 1313,
  "setup": [{"unless": "node_modules", "run": "npm install"}],
  "command": "hugo server --port {port} --bind 127.0.0.1",
  "command_windows": "hugo server --port {port} --bind 127.0.0.1"
}
```

| Field | Meaning |
|---|---|
| `name` | Shown on the app card as the project type. |
| `match.all` | Every entry must exist in the project folder. `a\|b` means either; globs like `*.csproj` work. |
| `match.any` | At least one entry must exist (optional). |
| `match.none` | None of these may exist (optional). |
| `match.contains` | `{file: regex}` — the file must contain the pattern (optional). |
| `requires` | Commands that must be installed; otherwise the recipe is skipped (optional). |
| `port` | Default port. Homeport picks the next free one if it's taken. |
| `command` | How to start it. `{port}` and `{python}` (the project's own Python) are filled in. |
| `command_windows` | Optional variant for Windows (`cmd.exe` syntax). |
| `setup` | Steps run first, only when the `unless` path is missing (e.g. install dependencies). |

Test a recipe by adding a folder in Homeport (**Add app** or **Discover**):
the detected type and command appear right away.
