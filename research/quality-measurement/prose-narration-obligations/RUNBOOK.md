# Narration obligations runbook

Read PREREG.md, BRIEF.md, EPISTEMIC_GOVERNANCE.md and the shared RUNBOOK.md. Inspect processes
and acquire the box lock before sustained checks. All four calls are sequential and isolated
from heavy checks. Preserve unrelated working material; stage exact session-owned files.

Build the local source with runs/ab/prose-narration-obligations-tools/prepare_source.py. Review
its 42 units against all thirty original compound facts and freeze source-review.md before
any outputs. The two writer inputs must differ only in their required_narration arrays; the
original and paragraph coordinates must not reach either writer. Read the source manually:
schema coverage does not certify semantic equivalence.

```powershell
uv run python tools/check.py handoff
# Commit registration and controls before prepare/calls.
uv run python research/quality-measurement/prose_narration_obligations.py prepare --out runs/ab/prose-narration-obligations-20260906 --source runs/ab/prose-narration-obligations-tools/source.json
uv run python research/quality-measurement/prose_narration_obligations.py run --out runs/ab/prose-narration-obligations-20260906
```

Keep failures. No retries, replacements or repair of literal or semantic defects. The wrapper
checks combined usage including separate reasoning before dispatch; Codex enforces four request
files and exact replay identity. Read all four complete chapters and audit all 42 units in each.
Optional non-narration, contradicted truth and omitted required events are different outcomes.

Build a comparison retaining every draw, original, actual source and condition labels. Inspect
layout, selectors, source expansion, endpoint and console in the browser. Save readings, hashes,
usage and deterministic rebuild provenance, then finish RESULTS.md, execution.json, claim record
and RESEARCH.md history. Run handoff, commit/push main, and archive only this session's lock.
