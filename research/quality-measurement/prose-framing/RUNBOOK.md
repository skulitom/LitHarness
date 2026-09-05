# Framing trial runbook

Read PREREG.md and the parent RUNBOOK.md. Inspect processes and atomically acquire
`runs/box.lock` before a sustained check or live arm. Run them sequentially, and release only
your own lock. Commit registration and call-free controls before prepare and paid calls.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_framing.py prepare --out runs/ab/prose-framing-20260905 --source runs/ab/prose-inputs-reviewed-20260905/plain_factual-1.request.json
uv run python research/quality-measurement/prose_framing.py select --out runs/ab/prose-framing-20260905
```

Read every selected and omitted source unit. Save the reviewed decision payload and a source
review note, including every correction, before drafting. No new context prose is written.

```powershell
uv run python research/quality-measurement/prose_framing.py freeze --out runs/ab/prose-framing-20260905 --reviewed runs/ab/prose-framing-20260905/selection-corrected.json --note runs/ab/prose-framing-20260905/selection-review.md
uv run python research/quality-measurement/prose_framing.py draft --out runs/ab/prose-framing-20260905
```

Read all eight scenes and retain every request, response, usage envelope and failure. Cache
identity includes full transport argv; changing a mode cannot reuse a different treatment.
No command writes a production database. Run handoff before the final results commit.
