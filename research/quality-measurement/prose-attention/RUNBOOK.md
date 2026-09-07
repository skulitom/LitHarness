# Attention diagnostic runbook

Read PREREG.md, shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md. Check processes before
and after atomically acquiring runs/box.lock. Preserve unrelated work. Prepare and review the
unchanged chapter map and six-interval partition under runs/ab/prose-attention-tools.

Run handoff and commit registration, runner and tests before any generation.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_attention.py prepare --out runs/ab/prose-attention-20260907 --source runs/ab/prose-attention-tools/source.json
uv run python research/quality-measurement/prose_attention.py trace --out runs/ab/prose-attention-20260907
```

Read the complete proposed trace against each source interval. Stop on structural failure,
unsupported new facts/motives or future-knowledge leakage. Retain it without repair or retry.
For a compatible proposal, write a hash-bound trace-review.json with reviewed_phases, source
compatibility, future-knowledge and no-new-canon checks, including the interpretive limits.
This is an agent source review, not a human approval or quality judgment.

```powershell
uv run python research/quality-measurement/prose_attention.py freeze --out runs/ab/prose-attention-20260907 --review runs/ab/prose-attention-20260907/trace-review.json
uv run python research/quality-measurement/prose_attention.py draft --out runs/ab/prose-attention-20260907
```

Inspect frozen writer equality except rendering_mode before drafting. Do not run sustained
checks beside model calls. Read every complete chapter and record all 42 source correspondences,
six interval realizations and located defects. Build and browser-check the full comparison.
Update results, claim and RESEARCH history to OBSERVED only, including stopped outcomes.
Final handoff before commit/push; verify remote main and archive only the owned lock.
