# Discovery/action order runbook

Read PREREG.md and the shared ../RUNBOOK.md guard-and-go constraints. Inspect processes and
atomically acquire runs/box.lock. Run handoff and commit the registration before model calls.
Freeze the explicit source amendment and dependency contract under ignored runs.

```powershell
uv run python research/quality-measurement/prose_order.py prepare --out runs/ab/prose-order-20260906 --source runs/ab/prose-framing-20260905/neutral-1.request.json --amendment runs/ab/prose-order-tools/source-amendment.json --contract runs/ab/prose-order-tools/contract.json
uv run python research/quality-measurement/prose_order.py plan --out runs/ab/prose-order-20260906
```

Read both proposals against source; record source-only corrections and stop on unresolved
conflicts or a treatment requiring redesign. Keep both raw proposals, without selection.

```powershell
uv run python research/quality-measurement/prose_order.py freeze --out runs/ab/prose-order-20260906 --reviewed runs/ab/prose-order-20260906/plans-source-reviewed.json --note runs/ab/prose-order-20260906/source-review.md
uv run python research/quality-measurement/prose_order.py draft --out runs/ab/prose-order-20260906
```

Read all drafts, build and inspect a fixed-order comparison, run handoff and commit results.
Push main as already authorized and release only the lock owned by this session.
