---
title: Port already in use
findings: port_in_use
keywords: EADDRINUSE, address already in use, port is already, already allocated, socket address
---
When: the log says the port is in use, or diagnose reports port_in_use.

Steps:
1. Call check_port with the app's port to see which program holds it.
2. If the holder is another Homeport app, the two apps share a port. Give this app a different free port with update_app (port, and the port in the command if the command contains one), then restart_app.
3. If the holder is an old copy of this same app (same folder or same command), call start_app with stop_port_blocker=true.
4. If the holder is an unrelated program (a database, Docker, a system service), do NOT stop it. Change this app's port with update_app instead.

Tell the user which program had the port and what you changed.
