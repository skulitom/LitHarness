# Prose-input trial runbook

Read PREREG.md first. The commands produce experimental artifacts and never write to a book
database. Keep `LITHARNESS_ENV=test` in ordinary tests; run the live diagnostic from a normal
operator shell without setting `LITHARNESS_LIVE_PROVIDERS` for repository checks.

Prepare a new output directory and immutable source manifest:

```powershell
uv run python research/quality-measurement/prose_inputs.py prepare --out runs/ab/prose-inputs-20260905 --source-request runs/ab/chapter-rule-context-20260905/request-4.json --source-scene runs/ab/chapter-rule-context-20260905/library/marks-for-moving/chapters/Chapter1.txt
```

Convert once and inspect the notes and their source quotes before running the drafts:

```powershell
uv run python research/quality-measurement/prose_inputs.py plan --out runs/ab/prose-inputs-20260905
uv run python research/quality-measurement/prose_inputs.py draft --out runs/ab/prose-inputs-20260905
uv run python research/quality-measurement/prose_inputs.py edit --out runs/ab/prose-inputs-20260905
```

Completed calls replay from exact-request cache. A changed request, registration or script
refuses resume. An interrupted call without a recorded result refuses automatic retry. Every
call writes its request before transport, then raw response/usage and original text. Editor
patches produce separate `.scene.txt` and `.diff` artifacts; their structural checks do not
establish meaning preservation. Read all drafts and compare both edits before reporting.

Call-free verification:

```powershell
uv run pytest tests/test_prose_inputs_trial.py -q -n 0
uv run python tools/check.py handoff
```

The original 2026-09-05 conversion failed its source inspection and that run stopped before
drafting. Follow the visible amendment in PREREG.md for the continuation: use the same source
request and chapter, a new output directory `runs/ab/prose-inputs-reviewed-20260905`, and add
`--reviewed-plan runs/ab/prose-inputs-20260905/reviewed-plan.json` to `prepare`. This supplied
payload bypasses conversion; it is frozen with a hash and its source quotations are validated.
Then use `plan`, `draft` and `edit` with the new directory. Explicitly supplying source-checked
notes is a diagnostic facility, not an automatic repair or evidence of planner reliability.
