# Original production scene obligation diagnostic

Read this arm's PREREG.md and the shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md.
Inspect processes, acquire runs/box.lock atomically and inspect processes again. Keep one
subscription model call at a time and separate every call from sustained validation.

Prepare source.json with the ignored prepare_source.py; read input-audit.md and all four
exact cuts plus their surviving witnesses. Validate that the control matches the archived
request and the scene_trace hashes. Run handoff and commit runner/tests/registration before
freezing the manifest and starting generation.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_production_obligations.py prepare --out runs/ab/prose-production-obligations-20260907 --source runs/ab/prose-production-obligations-tools/source.json
uv run python research/quality-measurement/prose_production_obligations.py draft --out runs/ab/prose-production-obligations-20260907 --slot control-1
```

Inspect that slot's retained transport before starting single-1, single-2 and control-2.
The runner enforces fixed ordering and stops on failed/incomplete slots or an internal
sampling retry. A changed frozen input/code file is a stop, never an in-place repair.
If only part of the registration completes, retain and report the incomplete comparison.

Read all completed scenes in full, retaining paragraph locations and adverse findings.
Expose each output and its exact input in the local comparison. Record hashes and all
reported usage fields, without double-counting reasoning or cached input. Update results,
claim and RESEARCH.md; validate the claim, run final handoff and commit/push owned files.
Archive only this task's owned lock after checks and calls are complete.
