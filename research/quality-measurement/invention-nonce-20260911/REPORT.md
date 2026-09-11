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

## Registered follow-up

[Protocol](FORMAT.md), [registration](format-registration.json). The follow-up retains the
first short prefix and compares the native constraint, identical submitted JSON instructions
without native enforcement, and a brief undivided plain-text premise request. This tests
remaining format controls; it is not a new setting seed or a production prompt change.

Rebuild the initial evidence without model calls:

```bash
uv run python research/quality-measurement/invention-nonce-20260911/audit.py
```
