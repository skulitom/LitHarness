# Verbalized sampling at initial invention

The operator requested continued solution search. The prior representative-sample wording
experiment did not request probabilities; it was not verbalized sampling (VS). This pilot
tests an adaptation of VS at first invention and whether departures carry through the
unchanged discovery expansion. It is isolated research, not a production selection policy.

## Conditions and units

Use two fresh 2048-bit random integers transformed through the existing Base64 seed v3.
All four conditions in a block receive the same opaque prefix; blocks receive different
prefixes. Matching within a block is an experimental control. No authored world seed,
previous story, dossier, simulated reader answer or literature prose enters generation.

Each condition returns six 80-120 word LitRPG premises with the same underlying task:

- batch: the previous ordinary batch request, array of strings.
- format: array of objects containing text and a numeric probability placeholder of 0.0.
- full: that object schema, with estimates for possible responses relative to the full
  response space, without normalizing the estimates over the six returned objects.
- tail: full plus a request for responses estimated below 0.10 probability.

Exact bytes are in run.py and frozen request hashes. Format versus batch checks a schema
and metadata-instruction effect; full versus format compares estimation against a fixed
placeholder with the same schema. Tail versus full isolates the added tail instruction.
Format is a treatment, not a proven inert placebo. Wording length is not matched. These
comparisons do not identify a latent probability mechanism or calibrate the estimates.

Order is batch, format, full, tail for block 1 and the reverse for block 2. Then expand
one item from each batch in reverse call order. Before any model response, draw a separate
2048-bit integer per block and use the registered PRNG to choose one of six positions
uniformly, independently of the prefix draw and response contents. Share that position
across arms within the block. This is random positional selection, never a model choice.
Retain all items. Do not rank, reject, reroll or reweight by content or estimated probability.
Even estimates outside the requested range do not change selection or expansion eligibility.
Non-finite/non-numeric metadata or malformed story shape is a structural failure, recorded
without replacement; skip only its dependent expansion. Audit probability compliance
separately. Do not call low stated probabilities evidence of rare outputs or training OOD.

All expansions receive only the preselected story text via unchanged discovery.render_request,
third person, with no writer, history, probability field, VS instruction or extra seed prefix.
Eight invention calls and eight expansions are the full planned inventory. Two seed blocks
are the independent prompt units; six items in one response are dependent. There is no
within-condition repeat or full-book generation, and no expansion comparison with a shared
premise, so differences combine premise changes with stochastic expansion variation.

## Inspection and decision rule

Do not read new generated prose until every slot finishes or an operational stop fires.
Audit frozen hashes, captured requests, launch configuration, sessions, all first outputs,
selection provenance, probability values and word counts. Counts of words and literal
repetition are descriptive, not quality scores. Inspect all 48 planned premises and all
eight expansions; record bounded paraphrases tied to item identifiers and receipt hashes.

Compare initiating actions, consequential power use, advancement, continuing pursuit and
conflict. Specifically examine previously recurring occupational/support-power stories,
rescue-to-service obligations, community/infrastructure control and ancestral repair, while
also recording departures and other repeated structures. A place/name swap is not a plot
departure. Water alone is not a failure; it can belong to a different story mechanism.

A feasibility lead must show causal/plot departures beyond both batch and format controls
in both blocks, with its two preselected expansions preserving those departures rather
than reverting to the familiar causal structure. If controls show comparable departures,
if an apparent benefit is limited to one block, or if its expansions converge again,
the proposed consistent carry-through lead fails this pilot. Full and tail are separate
hypotheses; report the complete comparison, not just the more favorable arm. If structure
or transport loss prevents the comparison, report it incomplete. This is qualitative
artifact inspection, not a qualified novelty rate, literary-quality claim, calibrated
probability estimate, general VS refutation or proven cause of model repetition.

## Frozen execution and recovery boundaries

Use the existing source snapshot d4ebdb5 and exact native Codex binary from the contrast
experiment, requested gpt-6-astra at medium effort. Subscription transport only; no tools,
API keys, paid fallback, reset credits, retries, rerolls, hidden resume or live-provider flag.
The task and CLI references expose no verified temperature/seed control for this transport;
backend sampling remains unreported. This is an adapted task test, not a paper replication.

Freeze this protocol, runner, audit, tests, literature snapshots, dependency lock, binary,
source and prepared invention requests. Commit registration and pass handoff before calls.
Hold runs/box.lock after checking processes. Run one sustained job at a time. After the
thermal shutdown, set PYTEST_XDIST_AUTO_NUM_WORKERS=1 for every handoff check. Local checks
and model calls run sequentially. Progress, receipts and new manifests use flush/fsync and
atomic replacement; this reduces write-loss risk without guaranteeing power-loss survival
of the native transport's own files. Preserve ambiguous slots; no automatic restart.

Stop before a call at 16 attempts or 120,000 recorded tokens; the in-flight call may exceed
the ceiling. Unknown usage, transport/auth/quota failure or frozen-file drift stops the run.
Invention requests retain 3,200 maximum output tokens and expansions the renderer's 2,400,
both with 600-second timeouts. Native enforcement/capture limitations remain reportable.
Raw prose and traces stay in runs/invention-verbalized-20260911. Commit only code, identifiers,
hashes, derived controls and bounded findings. Rebuild with:

```powershell
uv run python research/quality-measurement/invention-verbalized-20260911/run.py prepare
# After registration commit, handoff success, and while holding the shared lock:
uv run python research/quality-measurement/invention-verbalized-20260911/run.py run
uv run python research/quality-measurement/invention-verbalized-20260911/audit.py
```

Pass final one-worker handoff, preserve unrelated work, release this task's lock and push
under the operator's existing instruction. Experimental prompts remain outside production.
