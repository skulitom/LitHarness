# Subscription Codex diagnostic runbook

Read PREREG.md and the parent RUNBOOK.md. Inspect live processes and atomically acquire
`runs/box.lock` before sustained checks or generation. Run one arm at a time and keep heavy
tests separate from provider calls. Release only your own lock after work completes.

Before first generation, run `uv run python tools/check.py handoff` and commit registration,
runner and call-free controls. The prepare phase makes no generation call and requires an
existing ChatGPT login. It never falls back to an API key.

```powershell
uv run python research/quality-measurement/prose_codex.py prepare --out runs/ab/prose-codex-20260905 --full runs/ab/prose-framing-20260905/neutral-1.request.json --focused runs/ab/prose-framing-20260905/focused-1.request.json
uv run python research/quality-measurement/prose_codex.py draft --out runs/ab/prose-codex-20260905
```

Read all outputs and failures. Full system/prompt strings, argv, CLI events, usage and input
hashes remain with the local artifacts. No result writes a manuscript or production state.
Run handoff before the final results commit.
