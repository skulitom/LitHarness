# Constraint-levels runbook

Read PREREG.md, the shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md. Inspect processes
before and after acquiring runs/box.lock; preserve unrelated untracked material. Prepare and
review runs/ab/prose-constraint-levels-tools/source.json. Confirm the source is nested, with no
ending leakage into premise or sequence leakage into ending, and no original prose in any prompt.

Run the repository handoff, then commit registration, runner and focused tests before calls.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_constraint_levels.py prepare --out runs/ab/prose-constraint-levels-20260907 --source runs/ab/prose-constraint-levels-tools/source.json
uv run python research/quality-measurement/prose_constraint_levels.py run --out runs/ab/prose-constraint-levels-20260907
```

Preparation checks ChatGPT login and freezes inputs without generating text. Inspect the
frozen requests, then dispatch exactly the six registered calls, sequentially. Do not run
sustained checks beside the model. Each logical folder retains full-1.request.json,
full-1.raw.json, full-1.result.json and full-1.txt, using the existing audited transport.
Failures stop dispatch; no source tuning or output repair. Read every complete output and
record common/ending fidelity plus original correspondence, actual lengths, plot divergence,
rule coverage and located prose defects. Verify the comparison's selectors, complete endpoints,
source expansion and responsive layout. Commit derived hashes/numbers and results only after
final handoff; push main, verify remote state, and archive the owned lock.
