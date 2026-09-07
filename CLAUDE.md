# Claude Code sessions in LitHarness

Read [AGENTS.md](AGENTS.md) for repository instructions and
[CONTRIBUTING.md](CONTRIBUTING.md) for setup and validation. This file adds only Claude
transport and shared-machine guidance; it is not a book-writing prompt.

## Find the current surface

- [README.md](README.md) describes supported operator commands.
- [Research navigation](research/quality-measurement/README.md) routes current tasks;
  [RESEARCH.md](RESEARCH.md) indexes results by question. Read the current arm's registration
  and RUNBOOK before executing it, not the historical root RUNBOOK in full.
- Search `PLAN.md` and `plan/stage-0-decisions.md` only for decisions relevant to the task.
  Historical instructions and completed handoffs are not an active backlog.
- Use the MCP read profile or the `debug-book` skill for book evidence. The diagnostic fence
  and scope of operator-authorized isolated research are defined in AGENTS.md.

## Keep session context out of model transports

`src/litharness/providers/cli.py` and the `CLI_HARDENING` tuples in
`research/quality-measurement/elicit.py` and `force_remote.py` pass both
`--setting-sources user` and the `claudeMdExcludes` setting on `claude -p` calls. Preserve
both when adding a call site: `--system-prompt` alone does not exclude project context,
and `--bare` breaks subscription login. The opt-in marker test in `tests/test_providers.py`
checks isolation; rerun it after a Claude CLI upgrade with authorization for live quota.

## Production editorial authority

`house.CLARITY` is the floor. A qualified reader mechanism may supply an objective signal
through a scoped editorial intervention; provisional role essays, including `house.READER`,
rank below both. Author locks constrain feasible interventions, not quality votes.

Raw reader answers stay out of drafting and planning. `application/editorial.py` keeps
versioned observations inert until their mechanism is qualified. Its controller records
`satisfy`, `defer`, `subvert`, `refuse`, or `challenge_lock`; only `satisfy` and `subvert` may
submit a scoped machine directive. Listing observations have no renderer or revision path
back to the writer. Operator diagnostics and real-reader behavior do not bypass these gates.

The existing operator-curated exemplar shelf (`application/exemplars.py`, `--exemplars`)
is a separate controlled surface: keep its openings ignored, never quote them into output,
and never reuse exposed material to measure a book that saw it. Measurement corpora remain
outside generation. The leak gate is not permission to import corpus material.

## Share the box

One sustained job at a time across sessions, including CPU-heavy tests, type checks, corpus
passes, GPU work and model arms. Check both the process list and `runs/box.lock`, acquire the
lock atomically, and announce start/end. Follow the shared
[guard-and-go procedure](research/quality-measurement/RUNBOOK.md#guard-and-go-how-several-sessions-share-one-box).
Do not run validation beside a model arm: CLI calls have lost responses under combined load,
and CPU/GPU overlap has shut down this workstation.

GPU arms also require the owning runbook's governor and `thermal_watch.py` sidecar; a GPU
temperature limit alone does not protect against combined CPU load. RoyalRoad parquet and
torch/GPU work use `C:/DEV/MirrorBench/.venv`; package work and reads of
`research/quality-measurement/corpora/toll.db` use `uv run python`. Preserve each arm's cache
rules. Do not share a cache between running processes or edit a request mid-run; retain
transport failures before interpreting results.

On this Windows host, terminate owned processes by PID in PowerShell and verify they ended;
`pkill -f` has returned success without stopping them. Preserve other sessions' work and use
the canonical `tools/check.py handoff` command from CONTRIBUTING.md when the box is free.
