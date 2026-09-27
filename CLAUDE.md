# Claude Code sessions in LitHarness

Read [AGENTS.md](AGENTS.md) first. This file adds only what a Claude session on this box needs.

- Every model call goes through `litharness.transport`. It runs Codex from an empty temporary
  directory outside any git tree, with user config, project docs, tools and API keys cut off.
  After any Codex CLI upgrade, run `python -m litharness canary`; `new` and `next` refuse to spend
  until the installed version has passed it.
- Share the box: one sustained job at a time across sessions (model calls, heavy tests, GPU work).
  Check the process list and `runs/box.lock` in the main checkout, take the lock with an atomic
  `mkdir` plus a `holder` line, announce start and end. `new`, `next` and `canary` take it
  themselves. The unit suite is not sustained load.
- On Windows, stop owned processes by PID in PowerShell and verify they ended.
- Data stays outside the tree (`$LITHARNESS_HOME`, default `~/LitHarness-data`). Third-party prose
  never enters the tree, and no exemplar text is quoted into output.
- The operator's read is the only quality gate. Simulated readers and model judges do not measure
  the objective; do not propose them as gates.
- Subagents run on Opus with capped fan-out; log what a cap dropped.
- Push after every green commit (GitHub is the backup). Never `--force`.
