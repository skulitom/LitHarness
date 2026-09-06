# Protected reconstruction runbook

Read PREREG.md, ../BRIEF.md, ../EPISTEMIC_GOVERNANCE.md and the shared ../RUNBOOK.md. Inspect
processes, acquire runs/box.lock atomically and run no model calls alongside heavy checks.
Prepare the source file from the prior paragraph-revision manifest, preserving its complete
chapter and map. Record the common source-derived scene division and audit input exposure.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_protected_reconstruction.py prepare --out runs/ab/prose-protected-reconstruction-20260906 --source runs/ab/prose-protected-reconstruction-tools/source.json
uv run python research/quality-measurement/prose_protected_reconstruction.py run --out runs/ab/prose-protected-reconstruction-20260906
```

Commit registration and tests before prepare/model calls. Retain all outcomes. Read every
output, audit the 30 protected facts, compute registered surface counts and build a comparison
that exposes the original and all four reconstructions. Inspect it in the browser. Complete
RESULTS.md, execution.json and the overview history even on failure, then run final handoff,
commit and push main under the existing authorization. Archive only this session's lock after
its jobs complete. Source prose stays under ignored runs; derived metadata and findings commit.
