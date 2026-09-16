# Connected chapter experiences: a bounded authoring demonstration

Read BRIEF.md, EPISTEMIC_GOVERNANCE.md, the reader-architecture programme, and the
planning-material-20260916 RUNBOOK and result before running this arm. The operator
authorized making the next milestone a demonstrated sequence of connected chapter
experiences. This is isolated authoring research, not reader qualification or a quality gate.

## Question and design

What intended experiences actually occur across three successive chapters, and how do
their consequences change subsequent activity, possibilities, personal responses and choices?
Compare the ordinary and opt-in structured workflows at production revision 79f4da7.
A uses ordinary concept invention; B adds only `concept --planning-material` to the same
operator commands. This changes invention, its output representation and downstream
rendering together. It is a whole-workflow observation, not a format-only causal test.

Two fixed premises in inputs.json, each with one first-draw concept per workflow:
case 1 is a fresh magical-repair/outlaw-racing premise; case 2 repeats the original courier
premise from the earlier experiments. No prior concept, world, prose or diagnostic is
supplied. The fresh premise expressly keeps early learning useful and the power's origin
unresolved. Neither promise is a validated pleasure measure. Both versions share verbatim
author wording and a sealed concept seed, but independently invent their story and world.
A seed is a sampling label, not proof of equal provider randomness. No matched-concept claim.

Both use halloran, third person, six one-scene chapters planned, 1,400 target words per scene.
Draft the first three chapters of all four books. Preserve this already-used layout to avoid
introducing another workflow difference; its limited length is a limitation of the demonstration.
Continuation follows each version's own accepted prose. No new outline is intentionally requested.
This tests three chapters of an opening arc, not arc completion, a whole book or long-serial endurance.

## Preparation and execution

Check for sustained LitHarness jobs and acquire runs/box.lock exclusively. Preserve unrelated
checkout changes. Freeze identical production archives, isolated interpreters using installed
dependencies, uv.lock, native executable, runner, tests and reused recorder/auditor sources.
No worktrees. Before spending, test phase limits, actual concept CLI request construction,
third-chapter progression and two continuation scene IDs with billing disabled. Prepare and
commit/push the registration before any live call. The runner checks committed bytes at dispatch.

Use ordinary concept, new, architect seed and world accept. Alternate A/B order across cases
and phases, as sealed in registration.json. Draft chapter one, drain its existing queue, grow
at scene-1, accept the world, draft chapter two, drain, grow at scene-2, accept, draft chapter
three, drain. A drain runs only while pending work exists. One live provider call at a time.
Keep all first outputs and ordinary policy attempts, including failures. No manual story repair,
redraw, candidate ranking, selective continuation or feedback from post-run readings.

Use the existing native gpt-6-astra/medium transport with ephemeral sessions, memory and project
instructions disabled. Only ordinary scoped world tools during seed/grow; invention, outlining
and drafting remain tool-free. No corpus/exemplar material, web, publication, fallback, reset or
purchase. Do not run sustained checks beside generation or enable live providers during tests.

## Limits and stops

140 provider calls including health probes, 2,500,000 recorded Usage.total tokens, 10,800 seconds
from first dispatch, 40 calls per book, 20 ticks per phase. An admitted call may cross a ceiling;
report actual usage. Failed/interrupted provider calls, unknown usage, frozen-input mismatch or
global ceilings stop further dispatch. Operational exits, parked/poisoned work, no_work before
target, book ceiling or phase cap stop that book. Never silently resume an interrupted run.
Keep partial outputs and reasons. Release only this task's lock after work finishes.

## Readout and milestone

Do not inspect generated narrative until all books complete or stop. Then read every generated
concept/discovery, complete outline, reached chapter, narrative attempt and raw/accepted
difference. Use the debug-book CLI workflow for job-bound plans and frozen writer requests.
Report transport controls, author/experience retention, structured projection, store attribution,
usage, retries and missing material before interpreting the prose.

For each of the four sequences, make a located account of:

1. What the protagonist wants and actually attempts in each chapter.
2. What succeeds, fails, is discovered or changes the available possibilities.
3. What remains consequential in the following chapter, with locations at both ends.
4. How the character responds and what becomes newly desirable or necessary.
5. What repeats, resets, is contradicted, gets deferred, or exists only in a plan.

Show both chapter transitions in every reached three-chapter sequence. Keep material links
distinct from mere repeated names or recap. Do not require a reward in every chapter, resolve
future material early, or count a planned event as enacted. Missing and ambiguous links stay
visible. A quoted promise or a story's assertion that it learned something is insufficient by
itself to establish changed subsequent action. No scalar connection/enjoyment score or pass rate.

The deliverable is all four reading copies plus a complete, located comparison, including
negative cases and the limits of the reading. If any book stops short, the four-sequence milestone
is incomplete; do not replace it or declare it achieved through surviving examples. Completing
the package does not establish that every sequence is connected or pleasurable. Two premises,
one draw per workflow, a familiar case, independent invention and divergent histories preclude
a general benefit, causal estimate or popularity claim. Claim status can advance to OBSERVED only.

Keep source material, stores, requests, prose and detailed narrative notes under ignored runs/.
Commit identifiers, hashes, numerical controls and methodological conclusions. No production
defaults change and no diagnostic becomes a production editorial instruction. Any next intervention
needs its own explicit scope and registration. Run the canonical handoff checker before both
registration commit and completed-result handoff.

## Commands

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/connected-chapters-20260916/run.py prepare
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/connected-chapters-20260916/claim.json
# Commit and push before:
uv run python research/quality-measurement/connected-chapters-20260916/run.py run
uv run python research/quality-measurement/connected-chapters-20260916/run.py audit
```
