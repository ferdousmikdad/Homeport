---
title: App killed (out of memory)
findings: killed
keywords: exit code 137, Killed, out of memory, JavaScript heap out of memory, OOM, MemoryError
---
When: exit code 137, "Killed", or "JavaScript heap out of memory".

Steps:
1. For Node "heap out of memory": update_app env {NODE_OPTIONS: "--max-old-space-size=4096"}, then restart_app.
2. Otherwise check how many apps are running with list_apps. Suggest stopping ones the user does not need.
3. Docker containers: Docker Desktop's memory limit may be too low; tell the user where to raise it (Settings → Resources).
