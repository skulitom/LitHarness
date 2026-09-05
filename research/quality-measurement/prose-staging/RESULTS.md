# Staging diagnostic: stopped on unresolved source conflicts

The registered source planner completed one Codex CLI invocation using ChatGPT subscription
quota. It produced seven staging steps covering all twelve required action IDs and reported
two source conflicts. Every step and both conflicts were read against the source. No corrections
were made and no payload was approved for drafting. The actual freeze command refused the
unresolved payload before creating its frozen review or any of the four Claude requests.

This is the registration's conditional stop, not an efficacy result. The four prose conditions
were not generated. No claim can be made about whether staged planning changes their prose.
The planner is not a qualified conflict detector and this case supplies no false-positive rate.
See [PREREG.md](PREREG.md), [RUNBOOK.md](RUNBOOK.md), and [execution.json](execution.json).

## Source findings and their limits

The current action list starts Kellow walking with the register; a separate first-ability
description places him standing when the private scheme appears. The priced item is movement
from the seat, and the endpoint requires his movement to earn the first mark. The source gives
neither a seated interval nor an explicit eligibility interpretation for the standing invigilator.
Treating any movement as eligible, or adding a seated state, would resolve an authoring decision
silently. A broader locational meaning is possible; the finding is an unresolved requirement,
not a formal proof that every reading of the wording is impossible.

The source's current snapshot has rank 1 and pace 1, while pace's cost is six marks banked and
spent at a closing bell and the opening ends with the first payment of one mark. The unresolved
question is acquisition origin. Possessions may precede page one, so automatically setting all
initial abilities to zero would be an unjustified general fix. This opening needs an explicit
origin/exception or a reconciled starting state. The source packet supplies neither origin.

The pre-existing seed record was located in the earlier chapter diagnostic's preserved
starting world: `rec-wda03d69147c97ea0404adbd1`, an accepted-canon `status_snapshot` with no
story position and no evidence entries. It already contains those initial values. The earlier
run imported seed records from `runs/ab/pilot25/draw3/serial.db` before generating its chapter.
Thus the value is in the source, not a new invention by the current Codex drafts. No active
production call to the older `starting_sheet` helper was found, so that helper is not identified
as the origin merely because it also builds nonzero starting values. No existing database,
canon record or narrative was changed.

## What the proposal itself did

The planner grouped reading, understanding, approach, withdrawal and outline into one interval.
It also prohibited questions, intervention and second reading, which is stricter than the source
action list independently requires. Its lookup step discouraged naming by referring to later
accounting material. These are additional planning decisions requiring review; source-ID coverage
does not establish semantic fidelity. The proposed notes add limited new action/response staging.
Their JSON structure alone is not evidence that the intended mechanism has been realized.

The useful next conjecture is a source-reconciliation stage before event staging and prose.
This result does not license a production gate or automatic source repair. Any future test must
also distinguish actual contradictions from legitimate prior acquisitions and declared exceptions.
The generic prototype remains isolated research code and contains no story-specific production
rule, example dialogue, reader ranking, or raw-feedback path.

## Execution

Registration and controls were committed at `cffcaf5` before the planner invocation. It requested
`gpt-6-astra` at high reasoning through Codex CLI 0.153.0. The envelope has no independently resolved
model field. Wall time was 84.4 seconds; usage was 15932 input tokens (2688 cached, already a
subset), 1911 output tokens, and 823 separately reported reasoning-output tokens. A conservative
sum including the separate reasoning field is 18666. Dollar cost is unavailable. Claude auth
was checked as a first-party subscription, but no Claude generation occurred in this trial.

Raw request, CLI events, proposal, full source review, unchanged unresolved payload and freeze
refusal remain under ignored `runs/ab/prose-staging-20260905/`. The execution record contains
their hashes, the seed-record identity and the local rebuild command. The pre-call handoff
passed 3991 tests, with 19 skipped and 88.76% coverage; lint, types, build and corpus-history
audit passed. The final handoff repeated those results: 3991 passed, 19 skipped, 88.76%
coverage, with lint, types, build and corpus-history audit also passing.
