# Action planning diagnostic runbook

Read PREREG.md and the shared operational constraints in ../RUNBOOK.md. Inspect the process
list and atomically acquire runs/box.lock. Run handoff and commit registration before calls.
Prepare the explicit source amendment before calling the planner. All prose and source
changes remain under ignored runs; no subscription reset or direct API.

```powershell
uv run python research/quality-measurement/prose_actions.py prepare --out runs/ab/prose-actions-20260906 --source runs/ab/prose-framing-20260905/neutral-1.request.json --amendment runs/ab/prose-actions-tools/source-amendment.json
uv run python research/quality-measurement/prose_actions.py plan --out runs/ab/prose-actions-20260906
```

Read the complete proposal against the reconciled source. Record every correction and stop
on unresolved conflicts. Only then freeze the review and the two complete drafting requests.

```powershell
uv run python research/quality-measurement/prose_actions.py freeze --out runs/ab/prose-actions-20260906 --reviewed runs/ab/prose-actions-20260906/plan-source-reviewed.json --note runs/ab/prose-actions-20260906/source-review.md
uv run python research/quality-measurement/prose_actions.py draft --out runs/ab/prose-actions-20260906
```

Read every complete output, publish a local comparison and commit scoped results with hashes.
Run handoff before the results commit, push main as authorized, and release only your own lock.
