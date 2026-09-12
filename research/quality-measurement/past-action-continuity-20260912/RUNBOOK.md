# Past-action continuity in a fresh chapter

The operator requested a fresh chapter, complete reading, published-opening comparison,
then a fix/regenerate loop. The first production draw and cold reading are retained under
`runs/fresh-chapter-review-20260912/`. This is an isolated authoring experiment, not a reader
metric, candidate selector, production feedback role or claim of audience enjoyment.

## Located defect and conjecture

The accepted scene 4 introduces a cooperating character's prior responsibility for a fault
after that character helped investigate it without mentioning that responsibility. Searching
the actual generation responses locates this past action first in scene 4. The earlier prose
was present in the writer request. The plan supplied the supply conflict but did not assign
the past action. This establishes provenance, not the sole cause of the model's choice.

CONJECTURE: explicitly checking invented past actions against earlier behavior will prevent
this unexplained withholding in this continuation without suppressing motivated secrets.
Use the exact additional instruction in run.py. No character, water, nursery, maintenance,
published-book example, reader verdict or dossier explanation enters that instruction.

## Frozen comparison

Six sequential calls: baseline continuation control then treatment; motivated-secret control
then treatment; baseline treatment repeat then control repeat. The four continuation calls
reuse the exact system and prompt from the original scene-4 provider trace, except the
treatment inserts one paragraph after the original first system paragraph. The manufactured
secret case is a boundary control, not an independent natural story or transfer test. Its
author direction requires the culprit's prior action and gives an established reason for
silence. Neither arm may remove that fact, make the culprit innocent, or expose the secret
to the pursuer prematurely. It tests overcorrection, not literary quality.

Use gpt-6-astra, medium effort, native subscription Codex, free text, default profile,
4096 output tokens, 600-second timeout, fresh ephemeral sessions. Repeats have identical
request bytes; no new story seed is added mid-book. No tool use, model fallback, retries,
quota reset, API keys, live-provider tests, automatic selection or implicit resume.
Ceilings: six attempted calls and 150000 recorded tokens, checked before dispatch; one
in-flight call can overrun. Stop on unknown usage, failure or frozen-file drift. Retain
every result and failure. Freeze registration, source, requests and native binary before
dispatch; run one-worker handoff and commit registration first. Hold the existing root
task's shared-box lock and keep sustained checks separate from generation.

## Reading and decision rule

Read every output completely in registered order. For each continuation locate whether
it adds prior responsibility/knowledge that leaves earlier cooperative behavior unexplained,
and whether it preserves the repair, independent supply conflict, new diversion, renewed
contact and need for physical rescue. Record passages and objections, not word matches as
semantic labels. Check both secret outputs preserve the specified cause and motivation.

Support is limited to this known continuation only if the fault recurs in at least one fresh
unchanged control, neither treatment recurrence has it, both treatments retain the required
events, and neither boundary-control output loses the authorized secret. Any missing
contrast is inconclusive; a treatment failure or secret loss kills this candidate under
this rule. Close reading is unblinded editorial assessment, not a qualified LLM measure.
Repeats are not independent stories and prompt-length effects are not isolated.

If supported, install only the tested continuation instruction and verify its actual routing
through the production planner. Assemble the first treatment (chosen now, before outputs)
with the unchanged first three scenes as an explicitly experimental revised chapter and
read it end to end. It is not an accepted revision of the production database. Retain both
versions; do not claim a better whole book or general resolution of repetition. If killed
or inconclusive, record that outcome without presenting the instruction as a proven fix.

The fresh discovery also returns to reed-family nurseries. Record that transfer failure
beside the earlier two-source life-scope finding; do not erase or generalize that narrow
result. The present continuation experiment cannot test invention diversity.

## Commands

```powershell
uv run python research/quality-measurement/past-action-continuity-20260912/run.py prepare
# One-worker handoff; commit registration before the next command.
uv run python research/quality-measurement/past-action-continuity-20260912/run.py run
uv run python research/quality-measurement/past-action-continuity-20260912/run.py audit
```

Raw prose stays under ignored runs. Commit derived hashes, usage, controls and located
observations only. Keep comparator text and digests entirely outside generation.
