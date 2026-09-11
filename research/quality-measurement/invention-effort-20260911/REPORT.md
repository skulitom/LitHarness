# Low invention effort retains recurring structures

Changing initial invention from medium to low reasoning effort did not remove the observed
repetition. Both settings produced overlapping rescue, support and institutional-conflict
structures, including closely matched premises within all three fixed-prefix pairs. The
selected plans retained distinct central powers while reintroducing familiar surrounding
material. This does not support changing the production effort default as a repetition fix.

[Protocol](RUNBOOK.md), [registration](registration.json), [evidence](evidence.json),
[complete premise inventory](INVENTORY.md), [claim record](claim.json).

## Execution and requested controls

Registration was committed as `c073a71` before model dispatch. The experiment reused the
previous frozen committed source at `d4ebdb5`, with fresh 2,048-bit Base64 prefixes and the
same native binary. The only intended launch change within each premise pair was low versus
medium model_reasoning_effort. Every expansion used normal medium effort.

All twelve calls completed with valid shapes: six arrays containing thirty-six premises and
six prespecified discovery expansions. Premises range from 98 to 106 whitespace-delimited
words. Recorded usage was 65,327 tokens. Every first response
was retained and read after completion. There were twelve distinct sessions and output texts,
no retries or replacement selections, no operational stop and no frozen-file drift. All
recorded request, effort, selection and expansion-provenance controls pass.

Preselection chose one-based positions 1, 5 and 5 for the three pairs. Both efforts in a pair
used the same position, without inspecting content. The expansion renderer received only the
selected premise, third person, no writer or additional prefix. No model ranked candidates.

The captured application and transport input fields are identical within every pair; launch
configuration is identical after removing only model_reasoning_effort. Reported reasoning
usage is lower in each low-effort call:

| Block | Low reasoning tokens | Medium reasoning tokens | Low input tokens | Medium input tokens |
| --- | ---: | ---: | ---: | ---: |
| 1 | 35 | 219 | 4,143 | 4,143 |
| 2 | 26 | 93 | 4,150 | 4,152 |
| 3 | 33 | 47 | 4,155 | 4,153 |

The two-token input differences in the latter pairs remain unexplained by the captured
fields. Capture does not expose the entire backend request or resolved model/sampling
distribution. These controls establish what was requested and locally recorded, not perfect
identity of all hidden context or a causal account of the backend.

## Repetition is still visible before expansion

The strongest evidence is concrete overlap, not a water-word count:

| Pair | Low effort | Medium effort | Overlap and difference |
| --- | --- | --- | --- |
| Block 1, item 1 | Mara Venn, municipal surveyor, moves a prison boundary and frees a child | Mara Venn, locksmith, moves a locked state from a cell into a knight and frees a child | Same name and professional boundary manipulation initiating child rescue; consequences diverge into territorial liability versus disabled winter defense. |
| Block 2, item 1 | Ferry captain protects a sinking tower in dungeon oceans and inherits harbor fees | Lifeguard protects a drowning child in dungeon oceans and inherits sanctuary upkeep | Maritime jurisdiction becomes rescue power, then a growing settlement obligation; the occupations, immediate targets and names differ. |
| Block 3, item 1 | Mara Venn repairs a giant's artery, gains residential property and maintenance debt, and risks waking the inhabited body | Mara Venn disables a sacrificial structure, saves workers but interrupts water, and risks destroying homes by freeing their foundation | Occupational infrastructure power, immediate rescue, governing responsibility and an inhabited-support dilemma recur. The medical and inspection mechanisms differ. |

Other items preserve useful variety: testimony can resurrect a ferryman, discarded timelines
can organize a return, and appraised weapons can reveal captive people. That variety coexists
with recurring menus. In particular, low-2 item 4 and medium-1 item 3 both develop restorative
growth that awakens the large body containing civilization. Both efforts also repeatedly
generate food adaptations whose survival benefits create obligations or behavioral harm.

No claim of zero variation or identical outputs is warranted. Conversely, the repeated
structures in low effort directly defeat the simple expectation that less reasoning would
remove this family in the registered draws. The experiment does not estimate an average
diversity effect from three independent pairs.

## What expansion adds

| Source | Preserved central premise | Added surrounding material |
| --- | --- | --- |
| low-1 item 1 | Boundary Clerk, prison annexation and search for a missing survey team | Makes the child an estuary sovereign; introduces flooded family-history chambers, water-dependent nurseries, a drainage-yard opening and negotiated route maintenance. |
| medium-1 item 1 | Threshold Thief, imprisoned child and an immobilized winter defender | Introduces ceramic lintel people, slow-time nurseries and an ancestral nursery-door repair needed to restore the knight; later power use again requires preserving others' boundaries. |
| low-2 item 5 | Crumb Accountant, stolen miner rations and debt against future children | Develops shared kitchens, ceramic oven people, restored delivery roads and support for a flooded village. Food ownership remains the main opening problem. |
| medium-2 item 5 | Restoration, a wounded soldier's portrait and suppressed imperial history | Develops a ferry agreement, restored wet steps, leaking water, painted waterways and disputed travel/toll rights. Painting and evidence remain central. |
| low-3 item 5 | Consensual summoning by correspondence, a locksmith and freed prisoners | Makes the locksmith responsible for flood doors; her absence damages household supplies. Escape uses canal contacts and a grain barge, then develops local maintenance and emergency crews. |
| medium-3 item 5 | Fermenter, cold-resistant refugees and inherited pack behavior | Adds meltwater cultivation, intelligent lichen seeking ancestral nurseries, guild farms and damaged breeding grounds; the food-adaptation problem stays central. |

All selected identities survive: these are not six interchangeable flood-engineering plans.
The expansions nevertheless repeatedly add nursery protection, repaired infrastructure,
water-linked routes and community obligations. The low-effort selections do not provide an
escape from that repertoire. Water appearing as a secondary example in Pavel's food plan is
not equivalent to water being its main setting; the distinction matters.

## Decision and remaining uncertainty

Keep low effort out of production as a proposed repetition cure. The opaque Base64 default
remains as requested, but neither its presence nor reduced reasoning demonstrates unique
story families or distance from training data. This result narrows the list of simple fixes;
it does not identify alignment, hidden context or model priors as the proved root cause.

Random batch selection remains mechanically usable for exploring alternatives, with limited
survival of premise differences through expansion. These results provide no new reason to
declare it sufficient. Further experiments should address the repeated source repertoire
and downstream additions separately, and require concrete plot differences to survive
expansion. More nonce length or effort-only trials are not the next useful direction on this
evidence. No full novels, reader response or literary quality were measured.

Rebuild the audit without model calls:

```bash
uv run python research/quality-measurement/invention-effort-20260911/audit.py
```

The local [reading copy](../../../runs/invention-effort-20260911/TREATMENTS.md) contains every
first response. Focused regression tests protect effort assignment, precommitted selection,
JSON request comparison and rejection of configuration drift beyond effort. Both handoff
checks passed, including 4,934 tests, 20 skips, lint, types, coverage, wheel build and the
corpus-history audit. The final checker result is retained in
[handoff-final.log](../../../runs/invention-effort-20260911/handoff-final.log).
