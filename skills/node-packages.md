---
title: Node packages missing
findings: node_modules
keywords: Cannot find module, ERR_MODULE_NOT_FOUND, Cannot find package, node_modules, vite: not found, next: not found, ENOENT
---
When: "Cannot find module", "<tool>: command not found" for vite/next/nuxt/etc., or diagnose reports node_modules.

Steps:
1. list_files on the app folder. Confirm package.json exists and node_modules is missing or incomplete.
2. run_fix with action install_node (it picks npm, pnpm, yarn or bun from the lock file).
3. restart_app and get_logs to confirm it starts.

If install fails with "engine" or "Unsupported engine", read the node-version guide.
