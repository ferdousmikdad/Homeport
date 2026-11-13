---
title: Missing .env settings file
findings: env_missing
keywords: .env, dotenv, environment variable, is not set, undefined env, MissingEnvFile
---
When: the app needs a .env file and only .env.example exists, or an environment variable is missing.

Steps:
1. list_files the app folder. Check for .env and .env.example.
2. If .env is missing and .env.example exists: run_fix copy_env.
3. read_file .env and point out values that still look like placeholders (empty passwords, "changeme", "your-key-here", wrong database host or port).
4. For a single missing variable, update_app with env {NAME: value} if the value is obvious (for example PORT). Otherwise ask the user for the value. Never invent secrets or API keys.
5. restart_app.
