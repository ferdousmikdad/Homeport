---
title: Permission denied
findings: permission
keywords: Permission denied, EACCES, EPERM, operation not permitted
---
When: the log says Permission denied, EACCES or EPERM.

Steps:
1. If it mentions a port below 1024 (80, 443): ports under 1024 need admin rights. update_app to a port like 8080 or 3000, then restart_app.
2. If it mentions a file or folder: tell the user the path and suggest fixing its permissions (or that the folder belongs to another user). Do not suggest running as root/sudo.
3. EACCES on a script (./run.sh): the file is not executable. Tell the user to run `chmod +x <file>`, or update_app the command to `sh <file>`.
