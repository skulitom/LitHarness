# Batch exploration retains recurring story structures

Generating several premises together produced visibly different alternatives within a
response. Ordinary batches already did this. The explicit contrast instruction and the
video's representative-sample wording have no clear additional benefit in these two blocks.
Recurring structures remain across batches, and the selected expansions retain several of
the familiar care, rescue, transport and institutional-conflict patterns.

Random selection followed by expansion is mechanically workable: both selected contrast
premises retained their central identities and power mechanisms. This is a candidate
exploration lead, not evidence that the repetition problem or literary quality is solved.

## Registered comparison and integrity

[Protocol](RUNBOOK.md), [registration](registration.json), [evidence](evidence.json),
[source boundaries](SOURCES.md), [claim record](claim.json).
Registration was committed as `6a7b978` before model dispatch, after repository handoff checks.
Generation used a frozen committed source snapshot at `d4ebdb5`, excluding unrelated local
precision changes. No production source or model default changed in this experiment.

All fourteen calls completed: ten premise-array responses and four prespecified expansions.
There are fifty short premises, ranging from 98 to 109 whitespace-delimited words, and
four full three-field discovery plans. Every array has the requested count, every expansion
passes the existing discovery validation, and every complete output was read. Recorded
usage is 73,031 tokens. There are fourteen distinct native sessions and output texts, no
frozen-file drift, no transport stop, no retries and no replaced responses.

Each block uses one fresh 2,048-bit integer converted by the production v3 Base64 encoder.
Both independent selection draws happened to choose zero-based index 1: the second premise.
Those choices were committed before dispatch and were not rerolled. The same index is
retained for every batch in its block. Singles select their only item. No model ranks the
alternatives and no observed content changes the selection.

The audit checks identical non-system request fields and launch configuration across the
premise arms, exact captured prefixes, separate sessions, precommitted selection and source
hashes. All four expansion requests match the unchanged discovery renderer with only the
selected premise as its brief. An initial offline comparison reported a false mismatch
because JSON stores the empty tools tuple as an array. The audit now compares the renderer's
JSON representation; the only original mismatch was `()` versus `[]`. A regression test
also verifies that this normalization still rejects a changed premise. No generation or
registered request was altered to resolve that diagnostic error.

Raw prose is retained in the local
[reading copy](../../../runs/invention-contrast-20260911/TREATMENTS.md) and call receipts.
The [inventory](INVENTORY.md) accounts for every short premise; each slot and index maps to
an exact text hash and selection flag in evidence.json.

## What changed in the short premises

The new single-premise baseline names Nessa Vale and Inez Vale. One is a lost-property
clerk resolving ownership on a continent of missing objects; the other is a claims adjuster
restoring a collapsed transit platform through insurance necromancy. Neither names Mara,
and the first does not specify an aquatic world. Thus this baseline does not reproduce the
earlier exact-name concentration or an all-water short-premise pattern. The shorter task and
its revised wording differ from the previous experiment. Batching cannot receive credit
for changes already present in these controls.

The ordinary batches contain, among other alternatives, a ferry that becomes a dungeon,
an undertaker carrying dead people's obligations, food-based resistance, a distributed bee
body, dragon inheritance, a ghost orchestra, and settlements inside a giant animal. The
contrast batches likewise span a resurrection clinic, oxygen-credit fraud, a quest-generating
theater, a migrating apiary, a substitute salt god and an astronaut inside his own body.
These are concrete variations, not merely a set of different character names.

Yet the batches repeatedly draw from an overlapping menu. Examples retained in full:

| Items | Concrete overlap and difference |
| --- | --- |
| batch-2 item 1; representative-2 item 1 | Both use Mara Venn as a surveyor/cartographer whose geographic edits rescue people, cause water-related harm and expose deliberately erased territory. One is a drowned walking city; the other a frontier. |
| representative-2 item 6; placebo-2 item 6 | Both begin at an Antarctic station, transfer heat to save a colleague, freeze the fuel supply, scale toward global thermal management and discover a dangerous heat source under the ice. The occupations and final threat differ. |
| contrast-1 item 4; contrast-2 item 2 | Both use an Apiarist whose scout-bee senses uncover a settlement's concealed harm and whose colony's specializations drive further community survival. One rides a stone giant; the other travels among sky islands. |
| batch-1 item 5; placebo-2 item 3 | Both translate a stenographer's correction into a reality-changing legal edit, save someone and create responsibility for that person or community. Their jurisdictions and continuing cases differ. |
| representative-2 item 5; placebo-1 item 5 | Both feature a teenage wheelchair athlete who sacrifices a competitive result to save another participant, gains cooperative abilities, and threatens a rigged tournament. One uses golems; the other races for breathable air. |

The literal name Elias also appears in a contrast premise. The transcript's names and
examples were absent from the captured prompts. This observation is not a validation of
the video's causal explanation or an instruction to prohibit particular names.

## The video wording does not separate from its controls here

The representative arm adds exactly "Use a representative sample." The placebo adds
"Return the requested output." Both additions have four words and twenty-eight characters,
although tokenization may differ and a neutral instruction need not be behaviorally inert.

Representative batches include meaningful variations such as a reincarnated wrestler-beetle,
a crab carrying a reef community and a wheelchair athlete in a golem tournament. Placebo
batches also include a beetle gardener, an oyster carrying testimony, a wheelchair racer and
a cook whose adaptations divide a population. The closely matching Antarctic plots above
are particularly strong evidence that the representative wording does not remove recurrent
story structures in this trial. Both kinds of batch still often connect occupational power,
rescue, cooperation and opposition to a controlling institution.

This is not an estimate of a zero effect. There are two independent blocks per arm, no
quality score, and six alternatives within one response are correlated. The result provides
no clear incremental benefit to credit to the phrase. It does not measure a representative
population, recover a pre-alignment distribution or establish training-data distance.

## What survived expansion

Only the prespecified single and contrast selections were expanded. Representative and
placebo selections remain recorded but were not developed; their downstream behavior is
unknown in this experiment.

| Source | Selected premise | Expanded behavior |
| --- | --- | --- |
| single-1, item 1 | Nessa's ownership-return power on the continent of missing objects | Adds a guild sluice flood, a bridge rescue, glass-bodied nurseries and shared light infrastructure. The ownership mechanic remains, with a strongly aquatic repair/support opening. |
| contrast-1, item 2 | Salma's births and inherited monster memories at resurrection checkpoints | Keeps childbirth, memory separation and the clinic as the central problem. Adds marsh peoples, excluded nurseries, refugees and a company-controlled resurrection network. It does not become a flood-engineering opening. |
| contrast-2, item 2 | Elias's Apiarist colony among migrating sky islands | Keeps scout senses, the predatory orchard and specialized bee castes. Develops the escape into a seedwood barge, bridges, navigation beacons, mobile nurseries, pollination agreements and worker votes. |
| single-2, item 1 | Inez's Insurance Necromancer restoring transit assets | Develops a tidal station archipelago, platform rescue, structural damage, load-bearing nests and disputed maintenance liability. The legal resurrection mechanic remains. |

The two contrast selections retain different central activities from the controls: neonatal
memory care and hive development. However, Elias's expansion again centers heavily on
transport, communal refuge, infrastructure and nursery care. Salma's introduces another
marsh people with nurseries, although the principal medical conflict stays intact. The
registered survival check therefore finds preserved premise identity alongside continued
reuse of familiar surrounding structures. It does not support an unqualified cure.

## Practical implication and limits

Keep batching as an experimental way to expose choices. This trial gives no reason to add
the representative-sample phrase as a production default, and no clear evidence that the
explicit contrast sentence improves on asking for several premises. Random selection
prevents a preference-ranking model from deciding which candidate proceeds; it does not
make the candidate distribution broad by itself.

The failure to repeat Mara in the short single baseline, the use of only two blocks, both
draws selecting the same list position, and overlapping plot structures limit stronger
conclusions. Batch generation also produces more text than a single premise, so this is not
an equal-token efficiency comparison. Full novels, reader experience and literary quality
were not tested. The claim record remains OBSERVED rather than a production qualification.

Rebuild the evidence without model calls:

```bash
uv run python research/quality-measurement/invention-contrast-20260911/audit.py
```

The final `uv run python tools/check.py handoff` passed. Its local
[log](../../../runs/invention-contrast-20260911/handoff-final.log) records lint, type checks,
regressions, coverage, wheel build and the corpus-history audit. Focused tests cover
preselection, exact text preservation, malformed arrays, prompt differences and persisted
request comparison without making model calls.
