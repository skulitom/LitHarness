# Conflicting-objectives runbook

Read PREREG.md and the shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md. Inspect
processes before and after acquiring runs/box.lock. Preserve unrelated work. Prepare the local
fixture and read every source unit plus source-review.md before registration. Commit the
registration, source-free runner and tests after the required handoff checker, before calls.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_conflicting_objectives.py prepare --out runs/ab/prose-conflicting-objectives-20260906 --source runs/ab/prose-conflicting-objectives-tools/source.json
uv run python research/quality-measurement/prose_conflicting_objectives.py run --out runs/ab/prose-conflicting-objectives-20260906
```

Preparation verifies subscription login without generating text. Inspect both actual frozen
requests before dispatch: only the objective differs, all 42 units and obligations remain,
and original prose is absent. Run exactly the registered four calls, sequentially. Retain
failures and stop; no retries, fallback or source revision after output inspection. Read every
complete passage, record all source audits and local interaction observations, generate the
comparison and derived execution record, and verify the browser controls and layout. Run final
handoff separately from generation, stage only session-owned files, commit/push main and archive
the owned lock. No production code imports this experiment.
