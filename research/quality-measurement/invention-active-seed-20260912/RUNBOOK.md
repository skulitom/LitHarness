# Active use of an opaque generation prefix

The operator authorized the next experiment proposed by the full-plan-history report:
ask the model to use the externally generated number-to-Base64 prefix during invention.
This is an isolated prompt experiment, not a production change or an authored world seed.

## Registered comparison

Use the frozen source d4ebdb5 and native Codex binary from the preceding experiments,
requesting gpt-6-astra at medium effort through subscription authentication. Keep the
six-premise, 80-120-word task, final schema, user prompt and transport identical across arms.
No prior story, book database, exemplar, corpus, reader answer or diagnosis enters a request.

Draw two fresh 2048-bit integers once and transform them through the existing v3 Base64
renderer. Draw two separate selection integers before outputs. Use each prefix in all
three arms and both repeats of its block. The exact system strings are frozen in run.py:

- passive: the unchanged earlier batch request with its opaque prefix at the start.
- diverse: passive plus the common diversity instruction, TASK_USE and FINAL_ONLY.
- active: identical to diverse except SEED_USE replaces TASK_USE, explicitly directing
  creative decisions toward the exact prefix contents.

The active/diverse contrast changes one sentence. It is not exactly matched in length,
tokenization or interpretation. Passive/diverse bundles diversity wording and extra text.
All arms contain the seed; there is no no-seed or model-generated-seed arm. No sampling
parameter, model effort, output schema or additional reasoning field changes. Do not ask
for an explicit reasoning transcript or seed explanation. All returned final material,
including unsolicited seed artifacts or invalid answers, remains in the receipts.

The committed sequence contains twelve invention calls:

1. Block 1, repeat 1: passive, diverse, active.
2. Block 2, repeat 1: diverse, active, passive.
3. Block 1, repeat 2: active, diverse, passive.
4. Block 2, repeat 2: passive, active, diverse.

Repeat 2 reverses each block's condition order. Repeat requests must be byte-identical
at the captured application and transport boundaries. Calls use fresh sessions. Stable
stories for a repeated seed are not automatically a failure: freshness is sought across
fresh seeds. Repeats test whether apparent between-seed and between-arm differences hold
under another draw. Neither sessions nor items within a batch are independent seed units.

After all twelve batches, expand one preselected position from each repeat-1 batch using
unchanged discovery.render_request, third person. The local PRNG maps the separate
selection integer to one of six positions uniformly before generation; the same position
applies to all arms of a block. Process those six sources in reverse invention order.
Expansions receive only their exact selected premise, not the seed, treatment instruction,
other candidates or history. Repeat-2 batches are retained and inspected but not expanded.
No candidate is ranked, rejected or selected for its contents. No reroll or replacement.

## Inspection and decision rule

Inspect no new prose until all slots finish or an operational stop fires. Retain and read
all seventy-two premises and all six completed expansions, including inconvenient cases.
Tie bounded paraphrases to the receipt and individual text hashes. Inspect protagonist,
setting, initiating action, consequential power use, advancement and continuing pursuit.
Compare active with both controls in each block/repeat and compare active across the two
seeds. Look for the known professional/support-power, rescue-to-obligation, community
repair, nursery and inherited-infrastructure patterns, but also record new repeated
families and departures in the controls. These patterns are inspection questions only;
their wording and old outputs never enter generation.

Active seed use is a feasibility lead only if causal plot departures beyond both controls
appear in both blocks and both repeats, do not converge on another cross-seed family, and
survive both preselected active expansions. A differing name, body, occupation or absence
of water is insufficient. Differences also present in diverse cannot be credited to
active seed use. A single favorable item or output is insufficient. Expansion must retain
the supplied central story; a replacement is not a successful preservation of a departure.
Distinguish recurrence already present in a premise from newly added plan material.
An invalid/missing required comparison cannot count as success.

This is unblinded qualitative artifact inspection, not a qualified semantic metric or
literary-quality measure. Word counts and literal equality are descriptive controls only.
Two seeds, dependent batch items, single expansions of repeat-1 positions, instruction
length and unreported backend behavior limit inference. No observed difference proves
the model used all seed characters, identifies a sampler, calibrates training OOD distance,
establishes a population novelty rate or authorizes production feedback. This adaptation
does not test every component of String Seed of Thought; see SOURCES.md.

## Execution and persistence

Freeze the scripts, tests, protocol, source references, renderer, provider, binary, draws
and prepared requests. Run the repository handoff check and commit registration before
dispatch. Preserve unrelated edits and stage only this experiment's files. Hold the
task-owned runs/box.lock after checking processes. Use one worker for every handoff and
set OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and MKL_NUM_THREADS to 1. Sustained checks and
model calls run sequentially. Do not set LITHARNESS_LIVE_PROVIDERS.

The ceiling is eighteen attempts or 120,000 recorded tokens, checked before each call;
an in-flight call may exceed the token stop. Requested limits remain 3,200 output tokens
for invention, 2,400 for expansion and 600 seconds per call. Unknown usage, frozen-file
drift, transport failure or authentication/quota failure stops the run. An invalid first
batch skips its scheduled expansion without substitute; all other registered slots remain.
Use no API keys, paid fallback, resets, retries or implicit resume. Interrupted/ambiguous
slots remain preserved; restarting the script is not an authorized continuation method.
Atomic flushed receipts record each attempt before dispatch and after completion.

```powershell
uv run python research/quality-measurement/invention-active-seed-20260912/run.py prepare
# Run handoff and commit registration before the following command:
uv run python research/quality-measurement/invention-active-seed-20260912/run.py run
uv run python research/quality-measurement/invention-active-seed-20260912/audit.py
```

The audit is offline and checks all first responses, source lineage, prefix rendering,
captured effective system including the schema instruction, native schema, prompt,
repeat/arm/seed comparisons, frozen files, sessions, usage and structural validation.
Raw prose and traces stay in runs/invention-active-seed-20260912; commit derived controls,
hashes and bounded observations. Pass final one-worker handoff, push under the operator's
existing authorization and release only this task's lock.
