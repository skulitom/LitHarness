# Source contract diagnostic

Read PREREG.md, the shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md. Inspect competing
processes, acquire runs/box.lock atomically and inspect again. Preserve unrelated changes.

Prepare the ignored lossless partitions, then read the full source and each proposed split.
Keep all original bytes and source authority. The ignored source-review.md records both
selected and deliberately unsplit annotations. Run handoff and commit the generic runner,
tests, registration and literature note before any generation call.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_source_contract.py prepare --out runs/ab/prose-source-contract-20260907 --source runs/ab/prose-source-contract-tools/source.json
uv run python research/quality-measurement/prose_source_contract.py draft --out runs/ab/prose-source-contract-20260907
```

Before draft, inspect all four exact request types and verify only the registered differences.
Keep every call sequential and separate from sustained tests/builds. On failure, stop without
retry or prompt repair. Keep malformed output and length misses as observed outcomes.

Read every whole chapter, locate all source units and the registered diagnostic locations,
record adverse and uncertain findings, then browser-check every retained output and its exact
inputs. Update RESULTS.md, execution.json, claim.json and RESEARCH.md. Validate the claim,
run final handoff, commit/push owned files and verify the remote head. Archive only this
session's owned lock when done. Source and generated prose remain under ignored runs.
