---
title: PHP / Laravel setup
findings: composer, laravel_key
keywords: vendor/autoload.php, composer, artisan, No application encryption key, MissingAppKeyException, Laravel
---
When: vendor/autoload.php is missing, or Laravel says no application key.

Steps:
1. If vendor/ is missing: run_fix install_composer.
2. If .env is missing: run_fix copy_env first (see the env-file guide).
3. If the app key is missing: run_fix laravel_key.
4. restart_app and get_logs.

A database error after these steps means the database settings in .env are wrong or the database is not running: read the database-down guide.
