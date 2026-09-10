# Creative seeding pilot

The operator asked to try seeding generations to obtain unique, out-of-distribution
generations. Here "out of distribution" means escaping the repeated invention family
observed in [the preceding diagnosis](../invention-cause-20260910/REPORT.md). We cannot
measure distance from a model's training distribution or certify global originality. This
is an authorized experiment in authoring inputs, not a quality metric or candidate selector.

## Mechanism and controls

The production Codex and Claude CLI adapters do not forward CompletionRequest.sampler as
native temperature/seed arguments. Do not label a seed in unused metadata a sampling change.
Test a seed that controls the actual author brief instead.

tools/invention_seed.py has a versioned, explicitly authored adventure palette: eight options
each for protagonist, world, opening engine, power and personal pursuit. SHA-256 derives an
offset and coprime stride through the Cartesian product. For one seed label, different deck
positions have distinct ingredient combinations. Different seed labels can overlap. Repeating
the same label and position reproduces the brief, not necessarily the model's text. This
finite palette is a methodological constraint, not a representative distribution of fiction
or a permanent production ontology. No generated candidate is ranked, filtered or redrawn.

Use seed label `20260910-invention-seed-pilot`, positions 0, 1 and 2, selected before any calls.
Retain every packet. No reroll after reading packet ingredients or model outputs. Each selected
ingredient is a positive creative input; the brief contains no previous stories, recurring
names, diagnostic descriptions, thematic blacklist or third-party material. It does not
prescribe the protagonist's name, so name changes alone cannot establish the desired effect.

Three conditions use the exact frozen production discovery system and schema, third-person
narration, gpt-6-astra at medium reasoning, 2,400 requested output tokens and 600-second timeout:

- **control:** empty author brief, three fresh first responses.
- **nonce:** the same empty-brief request plus a reproducibly derived opaque hexadecimal
  identifier and an instruction to use it to vary the invention, three fresh responses.
  This is an input perturbation, not a native sampling seed.
- **ingredients:** render each selected packet through the existing author-brief input,
  two fresh first responses per packet. No names are seeded. Repeats are separated in time.

Order: control-1, nonce-1, ingredients-0-a, ingredients-1-a, control-2, nonce-2,
ingredients-2-a, ingredients-0-b, nonce-3, ingredients-1-b, ingredients-2-b, control-3.
The nonce condition is not token-length matched to ingredients, so this pilot compares
practical methods, not an isolated semantic-content effect at fixed prompt length.

## Bounds and integrity

Use the preceding baseline's isolated source/interpreter (revision
d5ccb9ec7a244e8a573a0c26612373672d3c2bd7) and native Codex binary. Freeze this document, runner,
seed tool, packets, prepared requests, source files and binary before dispatch. Commit the
registration before model calls. No database, writer, exemplar, reader or downstream book
stage is opened. Capture complete requests, native receipts, first responses and usage.

Own runs/box.lock after checking processes. One sustained check or generation job at a time.
Stop after twelve completion attempts or 160,000 recorded tokens, checked before dispatch;
an in-flight call can exceed the bound. Auth/transport/quota failure, unknown usage or frozen
file drift stops remaining slots. Retain recoverable failed native usage separately. No
implicit resume, retries, fallback, API keys, usage resets or live-provider test flag. Native
internal behavior is not assumed to be single-pass merely because complete is called once.
Validate all outputs with Discovery.from_invention and retain validation failures without
redraw. Read story outputs only after the batch completes or an operational stop fires.

## Inspection and interpretation

Use the generation trace tool to verify application/transport differences, equal inputs for
each repeated packet, distinct sessions and output hashes. Then read every complete treatment.
Describe each first response's protagonist, world, central action and power. Compare the
two responses for each packet and the three packets with one another. Locate concrete output
passages realizing or contradicting the supplied ingredients. These are inspectable input
adherence observations, not reader judgments or quality labels.

Call the input mechanism promising only if the three packet pairs retain recognizably
different protagonists, settings and central conflicts through those supplied ingredients.
Merely renaming a familiar repair scenario does not meet that practical aim. Report ignored
or collapsed ingredients, mismatched repeats and any remaining repetitive structures. An
opaque identifier might work, fail or merely vary names; retain that result equally. No
statistical novelty threshold, comparison with training data, book-quality claim or model
ranking follows from this small pilot. No response is chosen for further generation here.

Keep full input/output prose and logs under runs/invention-seeding-20260910. Commit code,
registration, hashes and bounded conclusions. The reusable seed tool creates optional brief
files for the existing concept --brief-file interface; it does not alter production defaults.
