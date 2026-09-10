# Automatic seeding: implementation and experiment

New `concept` invocations now create a fresh creative seed by default. The versioned seed
supplies five ingredients plus a first magical success and further growth tied to the
opening activity. This is the operator's requested authoring policy. The experiment found
useful control of those actions, with recurring settings and support abilities still present.
It does not establish that the underlying concentration of model choices has been removed.

## Default behavior

The implementation is in [invention.py](../../../src/litharness/domain/invention.py), composed
by `cmd_concept` and passed to the discovery renderer. A new UUID is allocated once per
invocation, before the first call. `--seed LABEL --seed-index N` reproduces the input at that
version; `--no-seed` is an explicit control. Model output is not reproducible by guarantee.
Distinct deck positions for one label have different ingredient combinations; different
labels can overlap in the finite palette. No global uniqueness claim follows from a fresh ID.

The seed label never enters the generation prompt. The selected creative material does.
The prompt gives explicit author directions precedence over conflicting suggestions. The
original author brief remains separate. A successful concept retains the seed, version,
position, exact creative input and its hash in `concept.json`; `--out` also writes the receipt
before the first call, preserving it when that call fails. Development retries reuse the
same invention. JSON stdout remains valid; the seed notice goes to stderr.

The model cannot replace the caller's receipt during development. Quantity editing and
outline/world/listing projections use the realized story rather than the raw seed receipt.
Older concepts without seed metadata remain readable. The standalone experimental seed tool
retains its original version for the preceding pilot; it is not imported by production.

[Regression tests](../../../tests/test_default_invention_seed.py) exercise default freshness,
explicit replay, retry stability, invalid-input refusal before store creation, failure
receipts, stored metadata, legacy reads and downstream projections. These tests establish
software behavior and prompt construction, not model adherence or literary quality.

## Registered comparison

[Protocol](RUNBOOK.md), [registration](registration.json), [audit](evidence.json).
The production change and registration were committed as `df97723` before dispatch. The
snapshot uses the recorded committed base plus the four owned production changes. Unrelated
uncommitted precision edits were excluded from the generation snapshot.

Three UUID labels were drawn once, with no ingredient reroll. Each supplied two first-response
requests: ingredients alone, and the same ingredients with the default activity guidance.
Cases 0 and 2 from the default arm were then developed, selected before observing outputs.
All eight attempts completed, using 55,649 recorded tokens, in eight separate native sessions.
Outputs have distinct hashes; prepared requests and frozen files match. Within each discovery
pair, system, schema, other parameters and normalized native configuration match; the prompt
changes by the registered activity addition. No response was ranked, replaced or redrawn.

Every structured response passed its corresponding parser. Both development records have
`discovery_preserved: true` and `seed_preserved: true`, with no reserved machinery names.
Both still require the production precision stage. These local development artifacts have
not been edited, accepted into a book or drafted as chapters.

All source prose is retained in the local
[reading copy](../../../runs/automatic-seeding-20260910/TREATMENTS.md) and individual receipts
under `runs/automatic-seeding-20260910/calls/`. The following observations refer to those
receipts' complete `result.parsed` fields, not keyword classifications or reader scores.

| Case and fixed ingredients | Ingredients-only response | Default activity guidance |
| --- | --- | --- |
| 0: defeated warlord, mirror desert, competitive hunt, injury-bound advancement, unwilling companion rescue | Varek loses the hunt. Aftergrip helps him climb out and hold a shutter; later work centers on recovering memory plates and learning mirror maintenance. | Saren uses Passage Wake to locate and trap the quarry, obtaining passage. Further tracking senses support another capture, then an opponent exploits them to create false trails. |
| 1: smuggler, forest on migrating beasts, race, creatures made from witnessed lies, humiliation of a rival | Sera's summoned elk reaches the destination but obeys a promise to carry anyone, including a pursuer. Later development concerns controlling creatures' obligations and recovering testimony. This is already an active race, not a repair opening. | Ressa's summoned stag obeys a false claim about running straight past a predator, giving her a dangerous route to the court. A later flexible creature supports another race; rivals respond by removing available body material. |
| 2: human in a hunted monster body, layered glacier, competitive hunt, stolen shadows commanded by their owners, pursuit of a crown | Mara Venn uses human shadow hands to operate an inspection grille, then a cooperating shadow braces against a current. Further power supports access, handling objects and carrying others. | Mara arranges a shadow's owner-commanded movement to trigger a basket capturing its owner, earning entry and protection. Later shadow tracking enables another capture; a rival then exploits owner commands to create a false trail. |

The activity additions produce the specified first success and a concrete further success
in all three examples. They do not make the ingredients-only arm uniformly unsuccessful;
case 1 already supplies the race and its complication. The two hunt comparisons show a
clearer shift from access/support uses toward capturing quarry. This is input steering of
prescribed action, not independent invention of that difference.

## Development and remaining repetition

`development-0` retains Saren's trap, tracking powers and later courier capture. Its arc
continues into Ilyen's challenge to forced dispersal. However, the high-level capability
description returns to holding a damaged mirror open for a migrating community.

`development-2` retains Mara's basket capture, roadkeeper hunt and countered tracking
technique. It also emphasizes climbing routes and braced crossings in its upper capabilities.
The preserved opening is an application guarantee; the later development fields were read
separately and are not treated as guaranteed by that equality check.

The world material still converges in places. Both default hunting treatments introduce
drowned-orchard realms; water, maintenance marks, closed routes, administrative permissions
and dependent communities recur. The glacier control again uses Mara Venn, and Vey reappears
as a world name. The default glacier treatment eventually offers shadow bridges and supports.
Such passages remain in the record even where the central activity follows the seed.

The result supports a practical, limited conclusion: default seeding supplies varied inputs,
and the activity extension can keep early and later magical uses connected to those inputs.
It does not demonstrate an unbiased generator, globally unique stories, distance from the
training distribution or reader appeal. Only three distinct ingredient combinations were
tested, neither arm is matched for prompt length, and no chapters were generated. Native
receipts do not reveal every backend instruction or resolved sampling parameter.

Rebuild the integrity report without a provider or book store:

```bash
uv run python research/quality-measurement/automatic-seeding-20260910/audit.py
```

The final repository handoff log is retained at
`runs/automatic-seeding-20260910/handoff-final.log`.
