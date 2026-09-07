# Quality research: where to start

Use this page to find the relevant record. Read the linked source for its evidence and
rules; the full research archive is not an onboarding checklist.

| Task | Start here |
| --- | --- |
| Diagnose a generated chapter | [Debug-book workflow](../../.claude/skills/debug-book/SKILL.md): identify the actual manuscript, frozen request, job-bound plan and raw/accepted stages. |
| Continue Chapter 1 prose work | [Forensic audit](prose-chapter-one-forensics/RESULTS.md), then [Recall clarification results](prose-recall-clarification/RESULTS.md), its registration and runbook. |
| Check what an earlier prose experiment established | [Chapter 1 experiment history](../../RESEARCH.md#451-chapter-1-prose-experiment-history), then that experiment's registration, results and deviations. |
| Propose a quality measure | [BRIEF.md](BRIEF.md) owns the failed-proxy ledger; [EPISTEMIC_GOVERNANCE.md](EPISTEMIC_GOVERNANCE.md) owns claim states and evidence requirements. |
| Work on reader perception or qualification | [Reader architecture programme](../../plan/reader-architecture-program.md). |
| Run an existing experiment | That arm's `RUNBOOK.md`; use the shared [box-lock procedure](RUNBOOK.md#guard-and-go-how-several-sessions-share-one-box) for sustained work. |
| Change implementation or run repository checks | [CONTRIBUTING.md](../../CONTRIBUTING.md). |

## Reading the archive

`RESEARCH.md` is the cross-question results index. `BRIEF.md` is the refutation ledger.
The root research `RUNBOOK.md` records historical reproduction commands as well as shared
machine-operation rules; its older experiments are not prerequisites for a new arm.
`plan/stage-0-decisions.md` preserves decisions and reversals. Search these documents for
the current question and read the surrounding entry, rather than loading them in full.

An experiment's `PREREG.md` states what was fixed before calls; `RESULTS.md` states what
happened; `DEVIATIONS.md` qualifies delivery; execution/validation files pin artifacts and
checks. A later scope correction belongs beside the results without rewriting registration.
Folder names and a confident summary do not establish success or production qualification.

Raw requests, generated prose, comparisons and scratch scripts live under ignored `runs/`.
Committed records point to their identities; a fresh clone may not contain those local
artifacts. Keep retained evidence and unrelated ongoing work when cleaning up. Historical
runners stay at their recorded paths; new runner infrastructure should use explicit shared
helpers without changing already-frozen dependencies during an experiment.
