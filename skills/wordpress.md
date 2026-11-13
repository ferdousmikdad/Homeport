---
title: WordPress problems
findings:
keywords: WordPress, wp-config, Error establishing a database connection, wp-admin, wp-content
---
When: a WordPress site shows "Error establishing a database connection" or other WordPress errors.

Steps:
1. Database connection error: read the database-down guide. Homeport's WordPress mode (Set up button on the app) creates the database and writes wp-config.php; suggest it if wp-config.php is missing.
2. read_file wp-config.php and check DB_NAME, DB_USER, DB_PASSWORD and DB_HOST (host must include the database app's port, e.g. 127.0.0.1:3307).
3. Links redirecting to the live site: the site's URL in the database is the live domain. Homeport's live-URL helper handles this; tell the user to use WordPress mode instead of editing the database.
4. Do not edit wp-config.php yourself; tell the user the exact line to change.
