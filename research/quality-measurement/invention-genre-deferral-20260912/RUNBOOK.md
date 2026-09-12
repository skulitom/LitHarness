# Deferring the genre cue until a pursuit exists

The operator authorized continued work on story quality and creativity on 2026-09-12.
This isolated experiment tests an upstream generation procedure. It does not introduce
a quality score, reader intervention, model selector or production policy.

## Hypothesis and comparison

Conjecture: asking for a character's pursuit and consequential actions before specifying
LitRPG may produce different causal stories which can retain that identity when genre
mechanics, detailed planning and opening prose are added. The immediate prior experiment
did not establish consistent benefit from explicitly using the opaque prefix. Its outputs
and diagnoses never enter these requests. SOURCES.md separates local history from the
limited related literature; that literature does not establish this hypothesis.

Use the frozen source d4ebdb5, native CLI binary and subscription-only provider from the
previous experiments, requesting gpt-6-astra at medium effort. Draw two fresh 2048-bit
integers, transform them with the unchanged v3 Base64 renderer, and draw two independent
selection integers before any completion. This remains the operator's opaque number seed,
not an authored world palette. Each block shares its prefix across arms and repeats to
control the comparison; the two blocks have different fresh seeds.

Both arms ask for six 80-120-word premises naming a protagonist, setting, desire, obstacle,
chosen consequential action, result and further pursuit. Only the first task sentence differs:

- early: explicitly requests original LitRPG in portal fantasy, isekai or system apocalypse.
- late: requests original story premises with no genre specified.

The remaining system text, user task, schema, limits and transport are identical. The late
arm does not prohibit speculative fiction. Genre omission broadens the permitted content;
it does not guarantee ordinary-world premises. Length/tokenization also differ. This is
a genre-cue timing comparison within a common new pursuit task, not a comparison against
the unchanged production invention prompt, and not a separate test of pursuit wording.

Freeze exact text, renderer, tests, draws, references, provider and requests before calls.
The initial order is early-1-1, late-1-1, late-2-1, early-2-1, late-1-2, early-1-2,
early-2-2, late-2-2. Thus each block reverses arm order in its second repeat. Repeated
requests must match at both captured application and effective transport boundaries.
Every call starts a fresh session. Repeated-seed stability is not itself a freshness defect.

## Preselected story chains

A local PRNG maps each independent selection integer to one of six positions before outputs.
Use the same position for both arms of that block. Only repeat 1 supplies chains. Keep all
repeat-2 responses for inspection; do not replace a selected item based on its contents.

After all eight batches, process four chains in reverse repeat-1 invention order. Complete
each entire stage across the four sources before starting the next stage:

1. Adapt the exact selected premise to an 80-120-word LitRPG premise, preserving its central
   desire, relationships, chosen action and consequence while integrating consequential
   power use and progression. Both arms get exactly the same instruction, including the
   already genre-aware early sources. This controls for the extra rewriting call.
2. Expand the exact adapted premise using unchanged discovery.render_request, third person.
3. Draft a 1200-1600-word opening chapter using only the exact preceding world/opening/growth
   object and the common research drafting instruction in run.py. This is a standalone
   prose feasibility test, not the production writer, full-book loop or editorial workflow.

Later stages receive only the immediate source. They receive no arm label, earlier source,
other candidate, old story, diagnostic, corpus text, generated critique or source article.
They have no separate seed prefix; the fresh initial story seed reaches them through their
source material, as in the preceding expansion experiments. No reasoning transcript or
quality verdict is requested. All first outputs, including invalid or inconvenient ones,
are retained. Invalid parents skip descendants without replacement.

## Inspection and decision boundary

Read no generated prose until all scheduled calls finish or an operational stop occurs.
Then read all 48 initial premises, all four adaptations, four plans and four opening drafts.
Record bounded paraphrases located by receipt, item/field/paragraph and text hash. Distinguish
new additions from inherited source features at each transition.

Compare desires, obstacles, initiating actions, consequences and continuing pursuits across
arms, seeds and repeats. Record repeated causal families and counterexamples in both arms;
names, occupations, unusual bodies or the absence of water are not sufficient departures.
Check whether genre adaptation retains its source's causal identity and provides usable
power growth. Check whether planning retains it and whether the opening actually enacts
the chosen action and power consequences. Record missing/contradictory source promises,
unmotivated substitutions, explanatory restatement and concrete counterexamples. These
are located inspection questions, not numerical craft measures or a literary-quality bar.

Genre deferral is a repeatable feasibility lead only if causal departures beyond the early
control appear in both seeds and repeats, do not merely converge on a different repeated
family, and survive both selected late chains through adaptation, plan and opening. Genre
failure or replacing the original pursuit is not successful preservation. A missing required
comparison prevents a positive conclusion. A single favorable story does not pass this rule.

Two seeds are the independent seed units; six dependent items are not six independent trials.
Later stages have one draw per selected source, so any prose contrast also changes source
content and cannot isolate writing quality or a downstream causal effect. Inspection is
unblinded and not a qualified semantic instrument. Do not infer training-distribution OOD,
population novelty, reader enjoyment, whole-book quality or production readiness. The claim
stays OBSERVED unless independent evidence qualifies a stronger statement. No selection,
accepted manuscript change or production feedback follows from this experiment.

## Operation and verification

Read CONTRIBUTING.md, BRIEF.md, EPISTEMIC_GOVERNANCE.md and the parent RUNBOOK box-lock
section. Check processes, then acquire runs/box.lock atomically with this task as owner.
Run one subscription CLI call at a time. Handoff checks use one worker with OMP_NUM_THREADS,
OPENBLAS_NUM_THREADS and MKL_NUM_THREADS set to 1; never overlap sustained checks with calls.
Use no API keys, billing fallback, quota reset, live-provider flag, reroll or implicit resume.

Ceilings: twenty attempts and 150000 recorded tokens, checked before dispatch. An in-flight
call may overrun the latter. Every request has a 600-second timeout. Output limits are 3200
for batches, 1000 for adaptation, 2400 for discovery and 4200 for chapter prose. Unknown usage,
frozen-file drift, transport failure or authentication/quota failure stops the sequence.
Record start and final receipts atomically with flush/fsync, full request, usage, session
trace and immediate source hashes. An interruption remains preserved and is not a retry.

Run handoff and commit registration before dispatch. Run the offline audit after completion
or operational stop, then final handoff before committing results and pushing the exact own
commit under existing operator authorization. Preserve unrelated work and release only the
owned lock. Raw generated material stays under the ignored run root; commit hashes, derived
transport controls and located observations, never corpus or generated chapter text.

```powershell
uv run python research/quality-measurement/invention-genre-deferral-20260912/run.py prepare
# One-worker handoff and registration commit precede dispatch.
uv run python research/quality-measurement/invention-genre-deferral-20260912/run.py run
uv run python research/quality-measurement/invention-genre-deferral-20260912/audit.py
```
