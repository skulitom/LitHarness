# Staging diagnostic runbook

Read PREREG.md and the parent RUNBOOK.md. Inspect processes, atomically acquire the box lock,
run handoff and commit the registration before preparation or generation. Both CLIs must
already be signed in through subscriptions. No direct API or authentication fallback.

```powershell
uv run python research/quality-measurement/prose_staging.py prepare --out runs/ab/prose-staging-20260905 --source runs/ab/prose-framing-20260905/neutral-1.request.json
uv run python research/quality-measurement/prose_staging.py plan --out runs/ab/prose-staging-20260905
```

The planner's sole invocation is stored as `planner/full-1`, retaining the Codex helper's
cache identifier. Read and validate its entire JSON proposal against the source, recording
any source-only corrections. Freeze that review before any prose generation.

```powershell
uv run python research/quality-measurement/prose_staging.py freeze --out runs/ab/prose-staging-20260905 --reviewed runs/ab/prose-staging-20260905/staging-corrected.json --note runs/ab/prose-staging-20260905/source-review.md
uv run python research/quality-measurement/prose_staging.py draft --out runs/ab/prose-staging-20260905
```

Read every draft and retain failures. Run handoff before the results commit; release only
your own lock. Do not run another CLI arm or heavy checks beside these invocations.
