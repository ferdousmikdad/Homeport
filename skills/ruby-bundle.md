---
title: Ruby gems missing
findings: bundle
keywords: Could not find gem, Bundler::GemNotFound, bundle install, Gemfile
---
When: Bundler cannot find gems.

Steps:
1. run_fix install_bundle.
2. If it fails because of the Ruby version, read_file .ruby-version and tell the user which Ruby is needed (rbenv, asdf or rvm).
3. restart_app and get_logs.
