# Event-activated attention runbook

Read this registration, shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md. Inspect processes,
atomically take runs/box.lock and inspect again. Preserve unrelated files. Prepare and review
the unchanged source and explicit opening availability under runs/ab/prose-attention-events-tools.
Run handoff and commit registration, runner and tests before any call.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_attention_events.py prepare --out runs/ab/prose-attention-events-20260907 --source runs/ab/prose-attention-events-tools/source.json
uv run python research/quality-measurement/prose_attention_events.py initial --out runs/ab/prose-attention-events-20260907
```

Read the initial state against its four supplied facts before continuing. It is a compatible
rendering possibility, not new biography or canon. Then generate the one update proposal.

```powershell
uv run python research/quality-measurement/prose_attention_events.py updates --out runs/ab/prose-attention-events-20260907
```

Read all twelve updates at their activation points. Stop on structural or material semantic
failure with no repair/redraw. Write temporal-review.json only after checking initial and
updated states; bind both text hashes and reviewed_activations including opening. This is an
agent source review, not user approval or a quality judgment.

```powershell
uv run python research/quality-measurement/prose_attention_events.py freeze --out runs/ab/prose-attention-events-20260907 --review runs/ab/prose-attention-events-20260907/temporal-review.json
uv run python research/quality-measurement/prose_attention_events.py draft --out runs/ab/prose-attention-events-20260907
```

Inspect frozen writer requests for equality except rendering_mode before drafting. Run calls
sequentially without sustained checks alongside. Read every complete chapter, with all source
units and activation transitions audited. Retain partial/stopped outcomes as such. Build and
browser-check comparison, update results/claim/history to OBSERVED only. Final handoff, exact-file
commit/push, remote verification and owned-lock archival complete the run.
