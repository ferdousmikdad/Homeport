# Skills for the local AI assistant

Each `.md` file here is a short, step-by-step guide that Homeport hands to the
**local AI model** (Ollama) when it works on a problem. Small local models
follow a written plan much better than they invent one, so a good guide is
what makes them useful.

How a guide is picked:

* `findings:`: the crash-fixer finding ids it covers (see `backend/diagnose.py`,
  e.g. `port_in_use`, `node_modules`, `database_down`). When the assistant
  diagnoses an app, the guides for its findings are attached automatically.
* `keywords:`: comma-separated words matched against the question and the
  app's log, to pick guides for problems the crash fixer doesn't know.

The model can also open any guide by name with its `read_skill` tool.

Write guides in plain, short steps. Name only the assistant's tools:
`list_apps`, `diagnose`, `get_logs`, `check_port`, `list_files`, `read_file`,
`read_skill`, `run_fix` (install_node, install_python, install_composer,
copy_env, laravel_key, install_bundle), `update_app` (port, command, env),
`start_app`, `stop_app`, `restart_app`. Every change a tool makes is shown to the user
for approval first.
