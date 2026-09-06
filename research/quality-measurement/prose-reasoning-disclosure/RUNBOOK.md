# Reasoning and disclosure runbook

Read PREREG.md and the shared research governance/runbook. Inspect processes and acquire the
box lock atomically. Keep all sixteen potential generations sequential and separate from
heavy checks. Stage only this session's files; preserve unrelated research output.

Prepare the ignored source.json from the protected-reconstruction manifest. Arm A reuses its
full request exactly. Arm B partitions the thirty facts and ten literals, applying only the
two source-review clarifications registered in PREREG.md and scoping notes before release.
Freeze source-review.md beside source.json. The runner validates coverage, ordering and
literal multiplicity; reading must additionally inspect information leakage through prose.

```powershell
uv run python tools/check.py handoff
# Commit registration and controls before prepare or calls.
uv run python research/quality-measurement/prose_reasoning_disclosure.py prepare --out runs/ab/prose-reasoning-disclosure-20260906 --source runs/ab/prose-reasoning-disclosure-tools/source.json
uv run python research/quality-measurement/prose_reasoning_disclosure.py reasoning --out runs/ab/prose-reasoning-disclosure-20260906
uv run python research/quality-measurement/prose_reasoning_disclosure.py disclosure --out runs/ab/prose-reasoning-disclosure-20260906
```

Any failed request stops new dispatch; keep raw data and report the stop. The budget guard
includes both arms and separate reasoning tokens. Every later installment receives its own
unrevised earlier prose, with the actual request serving as the dependency record. Audit these
links deterministically after completion. Do not repair a bad installment before continuation.

Read every installment and assembled chapter, audit thirty facts per chapter, report registered
counts and create comparisons for both arms. Inspect browser layout, selectors and console.
Complete derived execution metadata, claim records, RESULTS.md and the overview history. Run
final handoff, commit and push main under the standing authorization. Archive only the owned
box lock after its jobs finish. Other proposed ideas in IDEAS.md are unrun conjectures.
