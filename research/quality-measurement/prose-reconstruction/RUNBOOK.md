# Full-context and reconstruction runbook

Read PREREG.md and the parent quality-measurement RUNBOOK.md before running. Check the process
list and acquire `runs/box.lock` atomically for a sustained check or live arm; release only the
lock you acquired. Do not run repository-wide tests alongside paid CLI calls.

```powershell
uv run python research/quality-measurement/prose_reconstruction.py prepare --out runs/ab/prose-reconstruction-20260905 --source-request runs/ab/prose-inputs-reviewed-20260905/plain_factual-1.request.json --source-manifest runs/ab/prose-inputs-reviewed-20260905/manifest.json
uv run python research/quality-measurement/prose_reconstruction.py compile --out runs/ab/prose-reconstruction-20260905
```

Inspect the changed units against their sources before drafting. Preserve a correction payload
and source rationale if needed, then freeze it before any dependent output exists:

```powershell
uv run python research/quality-measurement/prose_reconstruction.py freeze --out runs/ab/prose-reconstruction-20260905 --target context --reviewed runs/ab/prose-reconstruction-20260905/context-corrected.json --note runs/ab/prose-reconstruction-20260905/context-review.md
uv run python research/quality-measurement/prose_reconstruction.py draft --out runs/ab/prose-reconstruction-20260905
uv run python research/quality-measurement/prose_reconstruction.py extract --out runs/ab/prose-reconstruction-20260905
```

Inspect both extracted ledgers against the complete original texts. The same `freeze` command
accepts targets `meaning-original` and `meaning-literal`, with their respective correction files.
It refuses changes after the corresponding reconstruction request exists. Then:

```powershell
uv run python research/quality-measurement/prose_reconstruction.py rewrite --out runs/ab/prose-reconstruction-20260905
```

Retain every raw response, read all drafts and both reconstructions, and record losses as well
as surviving defects. Requests replay only from their exact cache. The helper's test-environment
guard prevents fresh provider calls in tests. No command writes a production database.

```powershell
uv run pytest tests/test_prose_reconstruction_trial.py -q -n 0
uv run python tools/check.py handoff
```
