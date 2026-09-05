# Deletion-only runbook

Read PREREG.md and the parent RUNBOOK.md. Inspect processes and atomically acquire
`runs/box.lock` before sustained checks or live calls. Do not run them together; release only
your own lock. A current owner may retain its lock while finishing the preceding arm.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_subtraction.py prepare --out runs/ab/prose-subtraction-20260905 --source runs/ab/prose-reconstruction-20260905
uv run python research/quality-measurement/prose_subtraction.py run --out runs/ab/prose-subtraction-20260905
```

Commit registration and controls before prepare/live calls. The two named outputs are fixed.
The runner retains rejected responses and continues to the other independent position.
Replays use the exact request cache; requests missing a response cannot silently replay.
Read complete sources, edits and cut records. No generated prose is committed or promoted.
