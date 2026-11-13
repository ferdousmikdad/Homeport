---
title: Database not running
findings: database_down
keywords: ECONNREFUSED, Connection refused, SQLSTATE, 5432, 3306, 6379, 27017, could not connect to server, database
---
When: the app cannot connect to PostgreSQL, MySQL, Redis or MongoDB.

Steps:
1. list_apps: is there a database app (PostgreSQL, MySQL, Redis, MongoDB) in Homeport? If it is stopped, start_app it, then restart_app the crashed app.
2. If none exists, tell the user to click "Add service" in the crash dialog (or Add → Services) to add the database in one click.
3. Compare the port in the app's .env (DB_PORT, DATABASE_URL, REDIS_URL) with the database app's port. If they differ, tell the user which line to change. Do not edit .env yourself.
4. "Access denied" or "password authentication failed" means wrong credentials in .env, not a stopped database.
