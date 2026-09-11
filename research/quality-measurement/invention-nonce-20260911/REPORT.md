# Base64 integer preprompts: repetition persists

The operator clarified that seeding means a long random integer encoded as Base64 and used
as a preprompt. The production default now implements that method as `invention-seed.v3`.
The earlier authored ingredient/world seeds addressed a different interpretation and remain
available explicitly under v1/v2. This change is the operator's input policy, not a claim
that random prefixes produce original stories.

## Exact implementation

Each new `concept` invocation draws 2,048 random bits with `secrets.randbits`. The integer's
unsigned big-endian representation, padded to at least 256 bytes, becomes standard Base64.
The exact prefix and two newlines precede the invention system message. No invented setting,
character, plot instruction or instruction to interpret the random bytes accompanies it.

The receipt retains the decimal integer, version, index, prefix and hash before the first
call when `--out` is used. Development retries preserve the invention; later production
stages retain the receipt as provenance without reintroducing the prefix. Decimal seeds at
index 0 encode that exact integer; named labels and alternate indices use deterministic
SHAKE-256 derivation for replay. This does not set a native sampler seed.

[Tests](../../../tests/test_default_invention_seed.py) check exact integer round-trips,
placement, fresh default draws, version replay, retries, failure receipts, author-brief
separation and downstream metadata boundaries. The trace debugger also distinguishes native
output-schema enforcement from JSONL event logging, including unknown flags in old traces.

## Registered prefix comparison

[Protocol](RUNBOOK.md), [registration](registration.json), [audit](evidence.json).
Implementation and registration were committed as `635b258` before dispatch. The frozen
snapshot excludes unrelated uncommitted precision work. The prepared format-only experiment
was not dispatched when the operator clarified the requested seeding method; its preparation
is retained under ignored `runs/invention-format-20260911/`.

There are two unseeded controls, two independent 2,048-bit prefixes, two independent
8,192-bit prefixes, and one repeat of the first prefix at each size. All integers were drawn
once and retained. The prefixes contain 344 and 1,368 characters respectively. Every prepared
and captured system differs from its control only by the prefix. User prompt, schema,
parameters and native configuration match. Repeat requests are byte-identical.

All eight calls completed and parsed successfully, using 48,353 recorded tokens. There are
eight distinct native sessions and output texts, no frozen-file drift, and no retries or
replacements. Every complete output was read; literal searches only locate passages.

| Slot | Protagonist and situation | First and later power purpose |
| --- | --- | --- |
| control-1 | Mara, bus mechanic, stranded coach in a tidal shell-road basin | Repair a nursery sluice, transfer her mother to safety, then develop shared load support and recover a route home. |
| control-2 | Nell, canal mechanic, houseboat in suspended waterways | Stabilize a cradle, reach her sister, then develop persistent anchors and restore transport. |
| short-1 | Mara, wheelchair-using lift mechanic, terraced city beneath an overhead sea | Repair a nursery cradle, redirect her chair's load, then develop bridges and accessible routes. |
| short-2 | Mara, carpenter, cottage and father on a tidal flat | Free a hatchery barge, brace a gangway, then distribute loads and investigate old transport anchors. |
| long-1 | Mara, upholsterer, brother trapped beside elevated canals and drowned orchards | Rescue a reed intelligence, anchor a cabin, then move archives and develop crossing support. |
| long-2 | Mara, lock mechanic, dog trapped in a canal station | Repair a gate, bind a ladder, then develop load inspection and restore canal connections. |
| repeat-long-1 | Mara, railway worker, missing brother on a tidal shell coast | Gain bodily anchoring while repairing a crossing, then develop cooperative load sharing and temporary spans. |
| repeat-short-1 | Mara, lift mechanic, father in a cradle above suspended reservoirs | Brace machinery, gain load sight, then develop transfers, temporary spans and portal supports. |

Both controls and all six prefixed responses retain the aquatic repair/support family.
All prefixed responses name Mara; the unseeded controls use Mara and Nell. The initial
long-prefix treatment still introduces drowned orchards. This is not a claim that water,
professional expertise or caregiving is inherently a defect; it records their recurrence
across these unspecified inventions despite the intended input perturbation.

Both repeated prefixes produce different text and different immediate situations. The long
repeat changes an upholsterer rescuing her brother into a railway worker searching for him.
The short repeat changes a wheelchair-using mechanic into a mechanic rescuing her father.
The broader family persists. Thus input replay is exact, output replay is not established,
and distinct text hashes do not demonstrate distinct story families.

This batch does not show that either tested prefix length removes the repetition. It cannot
estimate a novelty rate, establish a general effect of length, infer training-distribution
distance or reveal backend sampling parameters. No response was ranked, developed into a
book, used as reader feedback or accepted into production state. The default remains the
operator-requested random-prefix method, with its limitation made explicit.

All source prose is retained in the local
[reading copy](../../../runs/invention-nonce-20260911/TREATMENTS.md) and complete receipts.

## Fixed-prefix format comparison

[Protocol](FORMAT.md), [registration](format-registration.json), [audit](format-evidence.json).
The follow-up was committed as `9530671` before dispatch. It retains the first short prefix
and compares the native constraint, identical submitted JSON instructions without native
enforcement, and a brief undivided plain-text premise request. This tests remaining format
controls; it is not a new setting seed or a production prompt change.

All six calls completed in separate native sessions with distinct output texts, using
32,621 recorded tokens. The four structured outputs pass the original schema and discovery
validation; the two free-premise outputs pass a non-empty text check, not production plan
validation. No frozen files drifted, operational stops occurred or responses were replaced.
Every full response was read. Across the two registered batches, there were 14 calls and
80,974 recorded tokens.

The audit verifies that both native requests equal the initial short-1 request and that all
prepared and captured systems start with its exact prefix. Non-format request fields match.
Within each native/prompt-json pair, captured system and user text are identical; the schema
and its native flag differ, and the remaining launch configuration is equal. Both prompt-json
and free-premise omit native schema enforcement and share launch configuration. JSONL event
logging remains enabled in every arm; it does not prescribe the final story format.

| Slot | Protagonist and situation | First and later power purpose |
| --- | --- | --- |
| native-1 | Mara, apprentice stonemason, brother missing after a flood into a tilted shell city | Build a nursery-cart passage, gain anchoring, then develop shared routes while investigating a return door. |
| prompt-json-1 | Rhea, lift mechanic, father trapped in a carriage above suspended canals | Brace a walkway without crushing a living gate's young, then develop load sight and distributed support for transport and return. |
| free-premise-1 | Mara Venn, piano mover, city suspended above an ocean | Choose Porter to lift a beam during a rescue; carrying others' burdens grows into moving an entire district to safety. |
| free-premise-2 | Mara Venn, ferrykeeper, flooded city and dead passengers | Deliver a dead child home to earn a level, hull repair and sounding power; restore a submerged hospital while confronting a seawall powered by souls. |
| prompt-json-2 | Nell, locksmith, missing father in a drowned country inside a tree | Repair a nursery flood shutter and gain temporary bracing, then develop load sight and distributed supports without draining inhabited waterways. |
| native-2 | Mara, ferry mechanic, missing mother among shell cities and suspended seas | Brace a nursery pipe, gain load sight, then develop temporary bearings and stabilize shared transit. |

The native controls reproduce the earlier family. Removing native JSON enforcement changes
the names to Rhea and Nell on these draws but retains the aquatic repair/support structure.
Removing the JSON instructions and detailed production task still yields two Mara Venn
stories centered on water, transport and rescue. The porter treatment also retains load
support and community evacuation. The ghost-ferry treatment introduces a different death
and soul economy; it is a counterexample to any claim that format changes leave every
story mechanism unchanged. It does not repeat the same first-scene mechanical repair plot.

These responses show that neither native JSON enforcement nor the detailed production
task and three-field plan are necessary for the observed repetition on these draws. They
do not establish that format has no effect. The plain-text contrast changes several prompt
features and length together, and two responses per arm cannot estimate their causal weights.

The repetition is already present in the first isolated provider completions. These calls
do not use a book store, previous manuscripts, candidate selection or downstream development.
The remaining explanation lies within the retained minimal request and provider/model
generation path; the receipts cannot distinguish model tendencies from unobserved backend
context or sampling. They also do not independently verify the backend-resolved model.
The cause remains unresolved, and a fresh Base64 prefix is not a demonstrated remedy.

Complete follow-up prose and receipts remain in the local
[reading copy](../../../runs/invention-nonce-20260911/format/TREATMENTS.md).

Rebuild both evidence files without model calls:

```bash
uv run python research/quality-measurement/invention-nonce-20260911/audit.py
uv run python research/quality-measurement/invention-nonce-20260911/phase2_audit.py
```

`uv run python tools/check.py handoff` passed after the final audit changes. The local
[validation log](../../../runs/invention-nonce-20260911/handoff-final.log) retains lint,
type checks, regression tests, coverage, wheel build and corpus-history audit results.
