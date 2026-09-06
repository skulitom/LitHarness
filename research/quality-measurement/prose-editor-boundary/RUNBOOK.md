# Editor-boundary runbook

Read PREREG.md, the shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md. Inspect processes,
acquire runs/box.lock, and keep sustained checks separate from the single sequential CLI job.
Preserve unrelated untracked working material. No production imports or direct model API.

Prepare the ignored fixture using runs/ab/prose-editor-boundary-tools/prepare_source.py and
read source-review.md and all source units before registration. Confirm the static prompt
really lacks optional contents, including in global notes and timing references. The original
chapter remains audit-only; scene fixtures are local author-created material. Do not tune a
fixture after seeing any dependent output.

```powershell
uv run python tools/check.py handoff
# Commit registration, runner and tests before prepare/calls.
uv run python research/quality-measurement/prose_editor_boundary.py prepare --out runs/ab/prose-editor-boundary-20260906 --source runs/ab/prose-editor-boundary-tools/source.json
uv run python research/quality-measurement/prose_editor_boundary.py run --out runs/ab/prose-editor-boundary-20260906 --until selector
# Read the selector. Preserve valid decisions; invalid schema skips dependent drafts.
uv run python research/quality-measurement/prose_editor_boundary.py run --out runs/ab/prose-editor-boundary-20260906
```

The runner reuses completed exact requests, never redraws failures, freezes code/source hashes,
and stops before the next call at the combined token limit. All model calls are subscription
CLI only. Keep raw streams and intermediate passages. Inspect all outputs and actual prompt
equality, source containment, literals, semantics and usage before reporting. Build comparison
pages and inspect their layout, selectors, source expansion, endpoints and browser console.
Record every result and any deviation; run final handoff and push the session-owned files.
