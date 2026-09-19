# A complete first-volume trial

The operator authorized work on the release blockers after an assessment of the unfinished
volume pilot, short current-pipeline demonstrations and unqualified reader mechanisms.
This is one bounded authoring and operational trial, not reader qualification or a comparison.
Read AGENTS.md, CONTRIBUTING.md, BRIEF.md, EPISTEMIC_GOVERNANCE.md, the reader-architecture
programme and connected-chapters-20260916/RESULTS.md before execution.

## Fixed scope

One fresh premise in inputs.json, one ordinary structured concept invocation, halloran,
third person, 24 one-scene chapters at 2200 requested words, four six-chapter arcs. Use
production commit 6c3bda417a994724a34355ae18e9561003223bc8, including the actor-state,
development-accounting and reader-fact changes. Unrelated uncommitted precision changes
are excluded from the frozen archive. No worktree is created. The working title is fixed
for identification, not selected by a model. The supplied author brief requests a volume
conclusion while leaving the wider serial open. Word count is a resource estimate, not
an acceptance criterion or quality measure.

Create the book with six scenes. Seed and accept its world, draft each chapter, and drain
its existing queue. Grow and accept the world after chapters 3, 6, 9, 12, 15, 18 and 21.
After chapters 6, 12 and 18, extend the same store by exactly one arc. Request no extra
chapter after 24. Preserve the original concept, all accepted history, ordinary retries,
proposals and failures. No replacement book, candidate ranking, manual story repair,
diagnostic feedback, or reader-directed revision. Read generated narrative only after
the run completes or stops. Structural completion does not establish that the ending works.

## Reproducibility and resource limits

Freeze production source, migrations, dependency lock, native executable, runner, its
reused recorder/transport auditor, tests, author brief and random invention seed before
dispatch. Register and commit the exact artifacts before any live call. A frozen runtime
imports the archived production source; native world-tool children use that runtime too.
The parent verifies the registration commit and the provider boundary verifies frozen bytes.

Use the existing native Codex provider, gpt-6-astra at medium effort, with ephemeral sessions,
memory and project instructions disabled. Only ordinary scoped world tools may be used by
the Architect. No corpus, exemplar, web, publication, fallback, reset or purchase.

Ceilings: 300 provider calls including health probes, 8,000,000 recorded Usage.total tokens,
14,400 seconds from first dispatch, 20 ticks per phase. A call admitted below a ceiling may
cross it; report actual use and refuse the next call. These are subscription usage records,
not dollar charges. The ceiling is deliberately above the short demonstration's world cost;
it is not an estimate that a book must consume that amount.

Stop on failed/interrupted provider calls, unknown usage, changed frozen input, operational
fault, terminal job, open exception, loss/change of an accepted scene, unexpected scene count,
idle tick before the requested chapter, phase exhaustion, or a global ceiling. A stopped run
cannot resume implicitly. Preserve its receipts and partial manuscript. A new continuation
requires an explicit amendment before dispatch. Never extend a partial or undrained arc.

Check relevant processes and acquire runs/box.lock atomically before sustained checks or
generation. One sustained job at a time; no tests beside generation. Release only this
task's lock. Use the repository handoff checker before registration commit and final handoff.

## Readout

Report operational controls before narrative interpretation: actual chapters and words,
three extension boundaries, immutable earlier chapters, job/decision attribution, source
and transport isolation, receipt chain, actual tokens/calls/time, retries and stop reasons.
The audit must not silently promote a partial run to a complete volume. Check the original
author brief and structured source in every outline; report omitted material separately
from transmitted material. Save all chapter dossiers, outlines and writer inputs locally.

Read the complete reached manuscript, concept, outlines, rejected narrative attempts and
any raw/accepted changes. Record locations for the central objective, consequential character
choices, progression uses/costs, earlier events affecting later arcs, deferred developments,
necessary reader facts, contradictions/resets, closing action and its aftermath. Planned,
mentioned and enacted events remain distinct. Report missing and ambiguous evidence.

This produces a candidate and a located defect inventory, not a quality score, release
approval, a causal benefit of the recent changes or a reader mechanism licence. No
diagnostic observation enters production. One book cannot supply independent held-out
books or qualify a reader; the reader blocker remains explicitly open. A later controlled
reader arm needs its own registration and substrate admission.

Keep prose, stores, prompts and detailed readings under ignored runs/. Commit identifiers,
hashes, numerical controls and methodological conclusions. Claim status is REGISTERED
before execution and at most OBSERVED afterward.

## Commands

```powershell
uv run pytest tests/test_full_book_trial.py -n 0
uv run python tools/check.py handoff
uv run python research/quality-measurement/full-book-trial-20260919/run.py prepare
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/full-book-trial-20260919/claim.json
# Commit the registration, runner and tests before:
uv run python research/quality-measurement/full-book-trial-20260919/run.py run
uv run python research/quality-measurement/full-book-trial-20260919/run.py audit
```
