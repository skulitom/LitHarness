# Prospective attention diagnostic

Read PREREG.md, shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md. Inspect competing
processes, acquire runs/box.lock atomically, inspect again. Preserve unrelated checkout work.
Prepare the unchanged source and three before_ids in the ignored tools directory; review
the four opening-known IDs and all three prefix cutoffs, including the reviewed planner_units
view without timing annotations or future hints in earlier fact text. Run handoff and commit registration,
generic runner and tests before model dispatch.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_prospective_attention.py prepare --out runs/ab/prose-prospective-attention-20260907 --source runs/ab/prose-prospective-attention-tools/source.json
uv run python research/quality-measurement/prose_prospective_attention.py derive --out runs/ab/prose-prospective-attention-20260907
```

Read each entire proposal and actual prefix input. On structural or material compatibility
failure, retain and stop without repair/redraw. A passing temporal-review.json binds
text_sha256 (all three call names to their text hashes), reviewed_before_ids in order,
source_compatible, knowledge_timing, no_new_canon, and all_prefix_inputs_read. Record concrete
semantic observations beside those booleans. Tentative guesses are not asserted source facts.

```powershell
uv run python research/quality-measurement/prose_prospective_attention.py freeze --out runs/ab/prose-prospective-attention-20260907 --review runs/ab/prose-prospective-attention-20260907/temporal-review.json
uv run python research/quality-measurement/prose_prospective_attention.py draft --out runs/ab/prose-prospective-attention-20260907
```

Verify exact writer equality except prospective_attention before drafting. Keep calls
sequential and separate from sustained tests/builds. Read every chapter in full, record source
and attention correspondences with adverse/uncertain findings, and browser-check the retained
comparison. Update results, claim and RESEARCH.md with observed evidence and limits. Final
handoff, exact-file commit/push, remote verification and owned-lock archival complete the run.
