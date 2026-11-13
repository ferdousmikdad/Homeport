---
title: Tool not installed
findings: missing_tool
keywords: command not found, is not recognized as an internal or external command, ENOENT, not installed
---
When: the start command needs a program (php, composer, python, go, cargo, ruby, docker, ...) that is not installed or not on PATH.

Steps:
1. Name the missing program from the log.
2. You cannot install system programs. Tell the user where to get it: PHP via Laravel Herd or php.net, Node from nodejs.org, Python from python.org, Go from go.dev, Rust from rustup.rs, Docker Desktop from docker.com.
3. If a different command would work with what is installed (for example `python3` instead of `python`, or `npx vite` instead of `vite`), offer update_app with the new command.
4. After they install it, the user may need to restart Homeport so it sees the new PATH.
