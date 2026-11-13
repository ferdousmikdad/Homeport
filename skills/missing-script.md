---
title: npm script does not exist
findings: missing_script
keywords: Missing script, npm ERR! Missing script, npm error Missing script
---
When: npm says "Missing script: <name>".

Steps:
1. read_file package.json and list the names under "scripts".
2. Pick the script that starts a development server: usually "dev", then "start", then "serve".
3. update_app the command to `npm run <script>` (or pnpm/yarn/bun if the project uses that lock file), then restart_app.
