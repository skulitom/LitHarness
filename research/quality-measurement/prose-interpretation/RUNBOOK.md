# Prescribed interpretation runbook

Read PREREG.md and the shared ../RUNBOOK.md guard-and-go rules. Inspect processes, atomically
acquire runs/box.lock, then run handoff and commit registration before calls. Freeze the
occurrence-checked amendment and complete source review under ignored runs first.

```powershell
uv run python research/quality-measurement/prose_interpretation.py prepare --out runs/ab/prose-interpretation-20260906 --source runs/ab/prose-order-20260906/drafts/focused-1.request.json --amendment runs/ab/prose-interpretation-tools/amendment.json --note runs/ab/prose-interpretation-tools/source-review.md
uv run python research/quality-measurement/prose_interpretation.py draft --out runs/ab/prose-interpretation-20260906
```

Read every complete output. Retain the raw envelopes and report usage, paragraph locations,
scope limits and any failure. Build and inspect a comparison containing all four drafts;
run handoff, commit results, push main as authorized, and release only this session's lock.
