---
title: Python packages missing
findings: python_deps
keywords: ModuleNotFoundError, No module named, ImportError, pip install, venv, virtualenv
---
When: "ModuleNotFoundError: No module named ..." or diagnose reports python_deps.

Steps:
1. list_files the app folder: look for requirements.txt, pyproject.toml, uv.lock and a .venv / venv folder.
2. run_fix with action install_python (creates .venv if needed and installs requirements into it).
3. Check the start command uses the project's environment (.venv). If it calls plain `python` while a .venv exists, update_app the command to use the venv's python.
4. restart_app and get_logs.

If one module is still missing after install, it is probably not listed in requirements.txt. Tell the user the package name to add.
