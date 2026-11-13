---
title: Unknown crash: how to investigate
findings: unknown
keywords: error, exception, traceback, fatal, failed, crashed
---
When: diagnose found no known cause.

Steps:
1. get_logs with 150 lines. Find the FIRST error line, not the last: later lines are often follow-up noise.
2. Read the stack trace: the first line that points to the project's own files (not node_modules, site-packages or vendor) is usually the cause.
3. read_file that file around the reported line.
4. Explain the cause in one or two plain sentences. If the fix is a code change, show the exact change and let the user make it. Only use action tools for configuration (port, command, env) or the predefined fixes.
5. If nothing is clear, say so honestly and list what you checked.
