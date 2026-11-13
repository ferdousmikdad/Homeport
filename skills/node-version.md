---
title: Wrong Node.js version
findings:
keywords: Unsupported engine, requires Node, engines, node version, SyntaxError: Unexpected token, ERR_REQUIRE_ESM, structuredClone is not defined, fetch is not defined
---
When: errors mention an unsupported engine, a required Node version, or modern syntax failing on old Node.

Steps:
1. read_file package.json and look at "engines". Also look for .nvmrc or .node-version with list_files / read_file.
2. Compare with the Node version shown in the logs (if any).
3. You cannot install Node. Tell the user which version the project needs and how to get it: nodejs.org, or `nvm install <version>` / `fnm use`.
4. If the project uses .nvmrc and the user has nvm, suggest the command `nvm use && npm run dev` and offer to set it with update_app (command).
