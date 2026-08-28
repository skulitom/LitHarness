# Claude-specific session and transport rules

Read [AGENTS.md](AGENTS.md) completely before changing this repository. It is the shared guide
for architecture, evidence boundaries, test tiers, dirty-checkout safety, and document routing.
This file contains only rules specific to Claude sessions and this machine.

This file is **not** part of any book-production prompt. `providers/cli.py` and the two research
`CLI_HARDENING` tuples (`research/quality-measurement/elicit.py`, `force_remote.py`) pass
`--setting-sources user` and a `claudeMdExcludes` setting on every `claude -p` call. The opt-in
live test in `tests/test_providers.py` proves a marker `CLAUDE.md` in the working directory does
not reach the model. Re-run that test after a Claude CLI upgrade. Any new `claude -p` call site
must carry the same two controls: `--system-prompt` does not exclude this file, while `--bare`
prevents the subscription login from loading.

## Claude session helpers

- For questions about why a scene or book emerged as it did, use the local
  `.claude/skills/debug-book/` procedure before opening databases by hand. Nothing its dossier
  reveals may become a prompt, directive, finding, or plan item.
- Do not create or switch worktrees unless the operator explicitly requests it. Inspect the
  shared checkout immediately before every edit and stage only your changes.
- When editing the append-only decision ledger, check the highest section number already present
  before choosing another. A committed entry owns its number; an uncommitted collision must be
  renumbered.

## Running model or research work on this box

- `claude -p` fails under total machine load, not merely its own concurrency. A failed call can
  still return while leaving unanswered cells. Do not run the full suite, mypy, a GPU job, or
  another sustained CPU task beside a paid arm, pilot loop, or Architect run. One CLI arm at a
  time, and inspect `transport_failures` before interpreting verdicts.
- The machine has hard-shut-down under combined CPU and GPU load even while the GPU governor held
  its temperature target. Run only one sustained job at a time; CPU simulations count. Every GPU
  arm runs beside the existing `thermal_watch.py` sidecar.
- `pkill -f` is unreliable here. Stop a process by PID from PowerShell and verify it is gone.
  Long paid arms use `force_remote.SingleRun` PID locks; do not bypass them.
- RoyalRoad parquet or torch/GPU work uses the MirrorBench interpreter at
  `C:/DEV/MirrorBench/.venv`. Package code and `corpora/toll.db` use `uv run python`.
- Replay caches key on the digest of system text, messages, model, and transport. Reuse a prior
  raw JSONL cache for identical requests instead of buying the same call twice. A background
  process buffers stdout; its cache file is the progress indicator.

Before handing off ordinary code, use `uv run python tools/check.py handoff`. Do not run that
sustained command while a model or research arm is active.
