# Generic outline-role removal: fixed-story comparison

Read BRIEF.md, EPISTEMIC_GOVERNANCE.md and the preceding
chapter-coverage-20260915/RUNBOOK.md. The operator approved testing the first proposed fix
alone on the same two concepts, one chapter per version. This isolated authoring experiment
does not qualify a reader mechanism or authorize model ranking or selection.

## Question and contrast

Does removing generic preassigned scene-role labels and the instruction to respect them
change the opening coverage the outline plans and the first chapter actually enacts?
The preceding experiment located explicit deferral, but does not establish its cause.
The two known cases are diagnostic units; one draw per version is not an unseen transfer
test and cannot establish a systematic effect separately from sampling variation.

A is the production code at 89527c3, which includes chapter coverage. B is the committed
implementation identified in registration.json. The only model-input change is removal of
each scene's dramatic_function field and the exact generic role instruction. The outline
profile changes from planner.outline.v5 to v6 for attribution. The policy digest also advances.
Keep chapter coordinates, output schema, all other instructions, concepts, author briefs,
world state, word budget, provider settings and writer input machinery unchanged. Internal
beat functions and chronology remain; author instructions are never removed by text matching.
No additional instruction about early rewards is added in B.

## Common initial state

Copy the preceding trial's frozen initial-stores/B2.db and B4.db, plus their saved concepts,
into each arm's separate local book directory. Both arms of a case therefore start from
byte-identical SQLite files, with the original experience-B2 or experience-B4 identity.
Retain separate immutable starting copies and record source hashes. Refuse stores containing
drafted prose. The original premises and titles are identifiers for these same stories.

Archive both committed source versions and use isolated runtimes sharing the same installed
dependencies, with source paths verified. On additional database copies, invoke the ordinary
selector and outline handler through a recording provider that refuses generation.
LITHARNESS_ENV=test enforces offline preparation. A's request must exactly equal the preceding
B preflight request. B may differ only in the two removed prompt components and profile.
Freeze preparation, dependencies, source archives, recorder, audit helpers, tests and runtime
executable. Commit and push registration before any live call. Never overwrite a prepared or
dispatched root; retain failed offline preparation if correction is necessary.

## Production and limits

Generate all four fresh six-chapter outlines and only their first chapter. Each chapter has
one scene and a 1,400-word target. Use halloran, third person and the existing signed-in native
gpt-6-astra / medium provider. The only phases are chapter1 and drain1. Drain ordinary queued
evaluation and summary work after drafting; never tick an empty queue or generate chapter two.
No invention, world seeding, world growth, listing or publication calls belong in this trial.
Order chapter1 as A2, B2, B4, A4; reverse arms within each case for drain1. Run one call at a time.

Use the original unchanged recording transport and corrected continuation auditor, frozen by
hash. Sessions are ephemeral, with user/project instructions, memory and web search disabled.
Every request in this experiment is tool-free. No fallback, reset, credit purchase or manual
world repair. Preserve first outputs and any ordinary policy retries; no story replacement.

Ceilings: 40 provider calls including health probes, 600,000 recorded Usage.total tokens,
10 calls per book, one hour after dispatch, and 20 ticks per phase. An admitted call may cross
a ceiling; report actual totals. Stop a book on a terminal job, operational exit, no_work before
its target or phase cap. A provider/transport failure, unknown usage, frozen-input mismatch
or global ceiling stops further calls. Do not silently resume an interrupted run.

The original scheduler assumes a two-chapter completion target in its final status; this
wrapper normalizes completion to one accepted chapter with an empty queue and no terminal
job. It never adds a phase or call to reach the old target. Tests cover that boundary and the
rejection of unregistered commands. Audit additionally checks the one-chapter ceiling at
every step, the registered phases and absence of tool allowances.

The task continues ownership of the existing machine lock, updating its holder after verifying
that no prior sustained job remains. Hold it through checks and generation. Do not run sustained
checks beside native generation, and never set LITHARNESS_LIVE_PROVIDERS for offline checks.

## Reading and reporting

Wait until every book completes or stops before reading new narrative output. Read all four
outlines and every reached draft, including ordinary retries. Read raw writer output separately
where the accepted version differs; deterministic dash/markup cleanup is not a narrative redraw.
Trace every scene brief through the stored job plan to the exact writer input, and retain all
coverage records. Report incomplete books and failed controls without replacement generation.

Locate the proposed activity, practical use, consequence, character response and subsequent
choice in each outline and draft. Distinguish a planned later payoff from one enacted in the
opening. Include strengths and omissions in both arms and any loss of response caused by dense
staging. Do not require all future commitments to close in chapter one or impose the same
reward cycle on every chapter. The primary independent units are the two source stories.

No enjoyment score, preference vote, winner, quality-effect threshold or popularity claim is
registered. Located editorial readings remain interpretations, not validated reader labels.
No reader notes or dossiers enter production inputs. The claim may become OBSERVED only.
Keep prose, requests, stores, reading notes and report under ignored runs/beat-labels-20260915;
commit identifiers, hashes, numbers, controls and methodological conclusions.

## Commands

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/beat-labels-20260915/run.py prepare
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/beat-labels-20260915/claim.json
# Commit and push the registration, runner, tests and source revisions, then:
uv run python research/quality-measurement/beat-labels-20260915/run.py run
uv run python research/quality-measurement/beat-labels-20260915/run.py audit
```
