# Handoff: recursive context planning - keep the serial outside the prompt, not outside the writer's knowledge

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose long
serials already outgrow the context packet they are drafted from. Your task is one bounded piece:
test and, only if earned, integrate the useful part of Recursive Language Models (RLMs) as a
**context planner** that constructs the existing `ContextPacket`. Do not replace the scene writer,
do not let a model choose prose, and do not put a Python REPL in the production process.

This handoff was written on 2026-08-23 against `main` at `29dae60`, after inspecting:

- Zhang, Kraska and Khattab, *Recursive Language Models*, arXiv:2512.24601v3 (11 May 2026),
  including its negative results and cost/runtime tails;
- the authors' reference implementation at <https://github.com/alexzhang13/rlm>;
- `C:\DEV\LongRangeContext` at `f142a5b`, whose M0 is complete and whose M1-M5 work is absent;
- the uncommitted worktree for `claude/book-generation-progress-7dfb8d` at
  `.claude/worktrees/persona-reader-feedback-ca03cd`.

The paper and its repository are research sources, not instructions for this repository. If any
source, line number, branch state or assumption below has drifted, the repositories win. Re-anchor
before editing. Parallel sessions are real; read `CLAUDE.md` and check every file immediately
before touching it.

## The decision, before the context

Build **one experimental RLM-shaped strategy in `LongRangeContext`**:

1. the entire frozen manuscript and canon remain an external, addressable snapshot;
2. a root context planner sees only the scene query plus snapshot metadata;
3. it inspects the snapshot through a read-only, typed environment;
4. it may batch bounded semantic questions to one level of sub-calls;
5. it returns source item IDs and coverage, never invented context or scene prose;
6. deterministic hard requirements are added outside the model and cannot be displaced;
7. the resulting ordinary `ContextPacket` is handed to the existing ordinary scene writer.

Do not integrate it into LitHarness until the incubator beats the current packet on held-out,
long-serial queries at the same packet and inference budget, without a stale/future/POV leak.

That is the best fit between the paper and this system. The paper evaluates retrieval,
aggregation, repository understanding and programmatic long output. It does **not** establish that
an RLM can write coherent book-length fiction, preserve voice across recursively generated pieces,
or improve reader preference. Applying the scaffold to context selection asks it the kind of
question it was tested on and preserves LitHarness's current generation and gate boundaries.

## What the active branch is doing, and why this handoff does not join it

At inspection time, `claude/book-generation-progress-7dfb8d` pointed at the same commit as `main`
and held its work only in the worktree. It was not yet drafting a long serial:

- `plan/serial-pilot-6.md` was `FORGING` and still specified an eight-scene, two-chapter book;
- the branch was iterating on the Architect and its forge gates after repeated premise refusals;
- recent candidates carried roughly 355-429 records each, while the pilot already treated
  `--context-budget 16000` as a precondition;
- a separate comprehension battery was asking four readers to restate nine short pitches;
- no chosen Pilot 6 world and no completed `serial6.db` existed yet.

The branch matters because it supplies the next realistic **large static world** workload. It does
not supply the long manuscript horizon: eight scenes cannot reproduce the 57-82-scene dark-context
regime in stage-0 section 56.4. Do not edit its worktree, copy its mid-run files, wait on its paid
arm, or fit this design to its current candidates. After it lands, a chosen forge artifact may be
used as one frozen input in Task 0. Until then, generate an equivalent synthetic 400-record world
inside the incubator.

The comprehension work is orthogonal. It asks whether a pitch can be restated; this handoff asks
whether the drafting packet contains the right evidence. Do not merge the instruments.

## Why this exists - the measured problem in this repository

The current path is intentionally simple:

- `domain/context.py::assemble` packs premise, constraints, threads, hidden facts, ordinary facts,
  summaries and prior prose under a fixed priority order;
- `application/planner.py::packet_for` loads current summaries and state, then calls `assemble`;
- `make_plan_selector` renders the entire packet into a frozen scene-draft job payload;
- every omission is recorded, but selection is recency/priority rather than relevance;
- the writer receives no way to inspect anything that did not fit.

The failure is already measured at the real intended scale. Stage-0 section 47 found that a
900-word target binds the 6,000-token default at scene 5 and retains three prior scenes. Section
56.4 then added one accepted status record per scene and measured:

| serial length | full prior prose | summaries | facts | prior scenes present in no form |
|---:|---:|---:|---:|---:|
| 30 | 3 | 19 | 29 | 7 |
| 57 | 2 | 22 | 56 | 32 |
| 82 | 2 | 12 | 81 | 67 |
| 120 | 1 | 10 | 119 | 108 |

A large forged world makes the budget tight earlier, but it is not the growing term. Pilot 2's
world held roughly flat while open promises grew and prose disappeared. `world-architect.md`
section 5.1 therefore already says the first cheap fix is a ledger policy, not a world retriever.
Keep that conclusion: this handoff does not excuse an unbounded promise ledger. Recursive context
planning addresses the broader case after deterministic pruning and hard reservations have done
their work.

## What the paper contributes, and what is refused

| Research observation | Keep here | Refuse here |
|---|---|---|
| Long input lives as an environment object rather than in the root model's history | an immutable `ContextSnapshot` and symbolic item handles | copying the full serial into a larger prompt |
| A root model probes, decomposes and stores intermediate values | a typed context program and persisted evidence buffers | arbitrary host Python or mutable access to the book store |
| Depth 0 often helps; depth 1 helps most on information-dense tasks | separate externalisation-only and depth-1 arms | assuming recursion is the source of every gain |
| Programmatic sub-calls can apply one semantic transformation across many chunks | batched structured semantic reads over source IDs | one call per fact, scene or line |
| First decomposition strongly affects performance | one LitHarness-specific decomposition contract, frozen by version | the paper's generic prompt pasted unchanged across models |
| Higher depth can propagate syntax errors and perform worse | maximum recursion depth exactly 1 | depth 2+, recursive scene generation, training an RLM now |
| `FINAL()` / `FINAL_VAR()` is brittle | schema-validated `ContextPlan` returned through the provider contract | tag parsing as a workflow boundary |
| Sequential sub-calls create extreme runtime tails | batch aggressively; expose a concurrency cap; keep it at 1 on this box | parallel `claude -p` calls on a machine known to fail under load |
| Cost is comparable at the median and long-tailed at the 95th percentile | operation ceilings, per-call usage, p50/p95 reporting, early stop | approving the design from an average cost alone |

The official package's default local environment executes generated Python in the host process and
its own README says not to use that for production. Do not add `rlms` as a LitHarness runtime
dependency. A pinned, isolated adapter may be used in the incubator as a fidelity check, but the
promotion candidate is the narrow typed environment below.

## Hard boundaries

These are not preferences. Work that breaks one is worse than work not done.

1. **The scene writer stays one call over one ordinary frozen prompt.** No RLM writes, stitches,
   critiques or selects the scene. `make_scene_draft_handler` and the draft/gate/accept path remain
   unchanged until the context strategy has separately promoted.
2. **No paid call inside `make_plan_selector`.** Work selection is currently deterministic and
   durable. If the candidate promotes, the selector enqueues a `context_plan` job; a handler owns
   the paid calls, budget pre-flight, retry record and settlement before it enqueues `scene_draft`.
3. **Hard eligibility is deterministic and happens before the model.** Wrong book or branch,
   future story position, stale revision, explicit exclusion and POV-invisible knowledge never
   enter the environment's eligible set. A semantic worker cannot rescue an ineligible item.
4. **Hard packet content cannot be displaced.** Premise, author-locked constraints, target scene
   statement, current POV/knowledge rules, all undisclosed claims the writer must honour, and the
   configured exact-local-prose floor are pinned outside the model. The planner allocates only
   the remaining soft budget.
5. **The model returns references, not canon.** Every selected line already exists as an eligible
   exact item or a fresh, versioned derived summary. Free text from a root or sub-call never enters
   the packet. Unknown IDs, duplicate IDs, over-budget plans and references outside the snapshot
   are refusals.
6. **Containment is structural, not a sentence in the prompt.** The context planner receives a
   frozen `ContextSnapshot`, not a store. It has no manuscript/plan writer, directive inbox,
   decision repository, gate, reader feedback, candidate prose, corpus signal or tool that can
   mutate the book. It may select eligible source IDs for query-relevance reason codes and nothing
   else; it cannot write an instruction, change authority, accept/refuse a scene, or learn from the
   draft it shapes. The strategy is version-frozen for the run. This is the containment required
   by stage-0 sections 61(5), 91, 105.1 and 107.5 for a model that selects among candidates.
7. **No silent fallback.** In an RLM arm, a timeout, shape failure, exhausted budget or invalid
   plan parks the context job and names why. It does not quietly run the baseline. The existing
   baseline remains the default strategy until promotion and is byte-identical when selected.
8. **Depth is one.** A root may call a semantic worker. A semantic worker may not call another
   model, execute tools, or return a program. More depth is a new experiment, not a parameter an
   operator can accidentally turn up.
9. **One provider call in flight on this machine.** The executor may expose
   `max_concurrent_subcalls`, but the LitHarness/Claude CLI binding sets it to 1. Batch related
   items into each sub-call; do not fight the box discipline recorded in `CLAUDE.md`.
10. **The plan is frozen and replayable.** Snapshot digest, strategy/prompt versions, root turns,
   sub-call inputs and outputs, item reads, selected/rejected IDs, usage and stop reason survive.
   A retry reuses content-addressed call results and may not spend twice on the same request.
11. **No model ranks prose or worlds.** This chooses evidence for a drafting packet, under a gold
    retrieval protocol. It does not touch `forge --pick`, plan-search candidate selection,
    reader/persona verdicts, Director direction or repair licensing.
12. **RS1 still holds.** No Royal Road, Mother of Learning, review text, corpus digest or
    corpus-derived example crosses to the generation side. Long-context test books are synthetic,
    contract fixtures or this system's own generated prose.
13. **No quality claim.** Correct evidence retrieval is necessary and insufficient. A packet that
    remembers scene 3 may still produce bad prose. Do not call recall, coverage, cost or a clean
    continuity counter reader preference.
14. **No fitted bar.** Run the four attainability checks first: range at the real n, direction,
    independent unit, non-empty subgroup. Correctness invariants may remain absolute; performance
    thresholds are pre-registered only after Task 0 shows the quantity can attain them.
15. **Promotion is from the incubator API, never a source copy.** Follow LongRangeContext's
    section 21 contract: versioned library/API, schemas, migration notes, license inventory,
    frozen splits, reproducible commands, latency/cost envelope and compatibility suite.

## The proposed abstraction

Keep the production-facing return type `ContextPacket`. Add these concepts in the incubator first;
their names may change, but their responsibilities may not collapse.

```text
ContextQuery
    book/branch/revision + target scene + story cutoff + POV
    target scene statement + referenced entities/threads + hard requirements
    packet token budget + operation inference budget

ContextSnapshot
    immutable manifest of eligible, versioned ContextItems
    exact prose, state, promises, plans, fresh summaries, hierarchy
    source IDs, token counts, authority, story position, visibility, hashes

ContextEnvironment (read-only)
    manifest()
    inspect(ids)
    recent_scenes(n)
    lexical_search(terms, limit)
    state(subjects/predicates/position)
    open_promises(subjects/due_window)
    summaries(level/subjects/threads)
    semantic_batch(ids, question) -> EvidenceRows

ContextProgram / trajectory
    root actions, named buffers, sub-call results and exact item reads

ContextPlan
    pinned IDs + selected soft IDs + rejected IDs/reasons
    coverage claims + tokens by class + snapshot/strategy digests

deterministic pack(ContextSnapshot, ContextPlan) -> ContextPacket
```

`semantic_batch` returns a schema such as `(item_id, relevant, reason_code, claims)` and never a
replacement passage. The root is instructed to orchestrate, not to write: probe the manifest,
name a decomposition, batch semantic work, verify coverage, finalize IDs. The environment owns
loops, validation, accounting and storage. It exposes no filesystem, network, process, clock,
database handle or arbitrary import.

## Task 0 - re-anchor and freeze the experiment before a provider call

Do this in a new results note under `C:\DEV\LongRangeContext\docs\` or `benchmarks\reports\`.
Nothing in this task calls a model.

1. Record current LitHarness and LongRangeContext commits, worktrees and dirty files. Confirm the
   active Pilot 6 branch has either landed or remains out of scope. Do not read numbers from a
   mid-write database.
2. Reproduce stage-0 section 56.4 from the current `context.assemble`, including 30, 57, 82 and
   120 scenes, exact token budget, summary policy and one-record-per-scene density. Record selected
   IDs as well as section counts so a future arm can be compared item for item.
3. Add a second workload with roughly 400 static world records and the same 57/82-scene horizons.
   Use a landed Pilot 6 forge artifact if one is stable; otherwise generate the records
   deterministically. This is configuration pressure plus narrative growth, the branch's real
   shape without depending on its current run.
4. Add a third workload reproducing Pilot 2's growing promise ledger. Before invoking an RLM,
   implement or import the deterministic ledger policy separately and report how much pressure it
   removes. The recursive strategy competes against the corrected baseline, not against a known
   unbounded list.
5. Freeze query families by information density:
   - **located callback:** a scene plan names one early person, object, fact or promise;
   - **linear coverage:** the scene depends on a character/thread history spread across the book;
   - **continuity pair:** two distant items must be kept together to avoid a contradiction.
     This is a stress test, not a claim that every draft query is quadratic.
6. For each query, freeze mandatory items or accepted substitutes, forbidden items, and the reason
   from exact synthetic construction or the existing GoldContextSuite. Do not solicit a new human
   panel. Run the project's no-human scope against any LongRangeContext M0 labels before reusing
   them; generated exact answers are safer than adding annotations.
7. Run the four attainability checks at 57 and 82 scenes: metric range, correct direction under a
   planted improvement/damage, independent book count, and non-empty query-family subgroups.
   Pre-register kill conditions only after these tables exist. Do not weaken an absolute
   stale/future/POV prohibition.
8. Freeze a cost envelope in units already governed by LitHarness: invocations, prompt tokens,
   output tokens, wall time and projected USD per `context_plan`. Report p50 and p95. The ceiling
   must fit inside the book's existing daily/operation policy rather than living as a second hidden
   budget.

Deliverable: `rlm-context-baseline.json` plus a human-readable report containing the exact commands,
fixture digests, query manifest and pre-registration. If Task 0 cannot produce reliable labels at
book grain, stop: a model choosing context without a grader repeats the reason retrieval was left
unbuilt in `world-architect.md` section 5.1.

## Task 1 - build the external context environment in LongRangeContext

All work stays in `C:\DEV\LongRangeContext`.

1. Add an immutable snapshot builder from the incubator's `BenchmarkBook` / shared contract
   artifacts. Filter book, branch, story cutoff, revision, exclusions and POV before exposing the
   environment. Assert the environment cannot enumerate a forbidden item even by exact ID.
2. Give every item content hash, source revision, authority, token count, hierarchy position and
   kind. Fresh summaries remain `DERIVED`; they never outrank exact canon.
3. Implement the read-only typed methods above. Deterministic methods return source items.
   `semantic_batch` is the only model seam and sits behind a provider-neutral protocol. No module
   in the domain/retrieval layer imports a provider.
4. Add a deterministic `pack` that first reserves pinned classes, validates every selected ID,
   deduplicates, applies the same counter, enforces the token limit and records every rejection.
   The root cannot change render text, authority, order key or visibility.
5. Add content-addressed request caching over `(model, system, messages, schema, strategy version,
   snapshot digest)`. Cache hits retain provenance and cost zero new invocations. A clean rebuild
   and a replay must select byte-identical item IDs.
6. Add adversarial items whose prose contains instructions such as calling tools, changing the
   query, returning a final answer or reading another branch. They are manuscript text, never
   executable instruction. Pin that the environment exposes only their text under source framing
   and that no action can widen eligibility.

Deliverable: an environment usable by the existing recent-window and TF-IDF baselines before any
RLM strategy is added. That parity matters: otherwise a later gain can come from a different
candidate universe rather than from recursive planning.

## Task 2 - add exactly two RLM-shaped arms

Use the same frontier model for root and semantic worker in the first controlled comparison. A
cheaper worker is a later cost ablation; changing model and scaffold together makes the cause
unreadable.

### R0 - external environment, no sub-calls

The root sees query, manifest metadata and typed deterministic actions. It may search, inspect,
maintain buffers and finalize a `ContextPlan`; it may not call `semantic_batch`. This isolates the
paper's strongest architectural move - externalising the prompt - from recursion.

### R1 - one level of batched semantic sub-calls

R1 adds `semantic_batch`. Batch related candidate IDs up to the worker's safe request size. The
worker returns structured relevance/claim rows; it cannot call the environment or another model.
The root may consume those rows and finalize IDs.

Both arms must:

- use a schema-validated action/result protocol instead of `FINAL()` tags;
- persist every root turn and observation as an append-only trajectory;
- show the root only bounded metadata about large observations, leaving large buffers external;
- refuse after the configured iteration, invocation, token, cost or wall-time ceiling;
- record unused buffers and repeated work, because the paper's failed trajectories often computed
  a correct answer and then discarded it;
- default to one in-flight call on this machine;
- make prompt/decomposition examples versioned and specific to `draft_scene` context planning.

If you use the official `rlms` package as a fidelity arm, pin a release/commit and run it only in a
Docker or equivalent isolated environment over a serialized snapshot with no repository mount and
no secrets. It is not the promotion implementation and is not imported by LitHarness.

## Task 3 - run the ablation that decides whether any of this survives

Compare at identical packet token budget and report total inference overhead separately:

| arm | meaning |
|---|---|
| L0 | current LitHarness fixed-priority packet with its current summaries |
| L1 | LongRangeContext recent-window baseline over the same eligible universe |
| L2 | LongRangeContext TF-IDF baseline over the same eligible universe |
| R0 | external environment and symbolic root, no semantic sub-calls |
| R1 | R0 plus one level of batched semantic sub-calls |

Do not add depth 2, embeddings, a learned reranker, query-focused rewriting or a second model to
this first matrix. Five arms are enough to answer whether the paper adds anything beyond the two
baselines already present.

Report per book and query family:

- mandatory recall and acceptable-substitute recall;
- forbidden, POV, future and stale selection counts;
- selected useful/mandatory items per 1,000 packet tokens;
- dark prior scenes and uncovered declared requirements;
- exact duplication/redundancy in the packet;
- root turns, sub-calls, cache hits, total input/output tokens, p50/p95 wall time and projected cost;
- failure/timeout/invalid-plan rate;
- first-decomposition category and whether the trajectory later discarded a valid buffer.

Correctness rails are absolute: no forbidden/stale/future/POV item and no displaced hard pin. For
performance, use Task 0's pre-registered intervals and book-resampled uncertainty. A scene is not
an independent book. R1 does not promote merely because it beats L0 on the development fixtures;
it must beat the strongest simple baseline at equal packet budget on held-out 57/82-scene books,
and the benefit must survive when total context-planning inference cost is included.

Run one downstream generation check only after retrieval passes: fixed provider/model/profile,
same target beat, same sampler, one draft per arm over this system's own unmemorised synthetic
serials. Plant mechanically checkable obligations - use the right distant fact, preserve a secret,
avoid an obsolete fact, settle the named promise - and grade with existing deterministic
extractors/gates. Do not ask which prose is better and do not turn the result into a craft gate.

Kill the candidate if any of the following occurs on held-out:

- a forbidden/stale/future/POV leak;
- a hard-pinned item is omitted or rewritten;
- gains disappear against corrected L0/L1/L2 at equal budget;
- the planner is constant, selects effectively everything, or merely restates TF-IDF order;
- more than the pre-registered cost/timeout envelope is required for the gain;
- the only downstream gain comes from changing the generator prompt beyond packet contents;
- trajectory replay cannot reproduce the selected IDs without a fresh model call.

A null is a completed result. Record it in LongRangeContext and stop; do not integrate a clever
scaffold because the paper's unrelated benchmarks were positive.

## Task 4 - only after promotion, add a durable context-plan job to LitHarness

Do not begin this task until LongRangeContext's promotion package exists.

### Choreography

```text
plan selector
  -> enqueue context_plan(book, branch, revision, beat, plan_epoch, strategy_version)

context_plan handler
  -> stale-head and standing pre-flight
  -> budget pre-flight for the entire root/sub-call envelope
  -> build frozen snapshot
  -> execute/replay bounded context program
  -> validate and persist ContextPlan + trajectory + usage
  -> render ordinary ContextPacket and ordinary scene prompt
  -> enqueue scene_draft with the frozen prompt and context provenance

scene_draft handler
  -> unchanged
```

1. Add a narrow application port implemented by a LitHarness adapter over the versioned
   LongRangeContext API. `application` imports neither its concrete package internals nor a
   provider. Keep the existing `assemble` behind a baseline implementation. The handler may read
   the store to build the frozen snapshot; the planner runtime receives only that snapshot and
   query, so its protocol has no store capability to grow into a write path.
2. Add `CONTEXT_PLAN` as a durable job kind and handler. Its stable identity includes book,
   branch, target logical ID, plan epoch, base revision, snapshot digest and strategy version. A
   second tick converges; a changed base or epoch is a different unit.
3. Count `context_plan` among a book's one draft in flight. Do not enqueue scene drafting beside
   it. Check the head before the first paid call and again before committing the plan; a moved head
   discards the result with a decision rather than forking the book.
4. Use the existing provider/budget vocabulary. Pre-flight the maximum envelope before the first
   call, record actual usage for every root/sub-call, and park rather than silently exceed daily or
   operation ceilings. A cache replay records cache provenance and no new spend.
5. Persist an immutable plan/trajectory artifact keyed by digest. The scene job payload gains:
   `context_strategy`, `context_snapshot_digest`, `context_plan_digest`, selected source IDs and
   hashes, rejected IDs/reasons, tokens by section and trajectory reference. It already carries the
   frozen rendered prompt; preserve that replay behavior.
6. An invalid/timeout provider answer is a failed context unit, not an empty packet. No baseline
   fallback inside the RLM strategy. The operator can deliberately re-enqueue under the baseline
   as a new policy decision if they accept the change.
7. Default configuration remains the current baseline and must render byte-identically. The RLM
   strategy is opt-in through recorded policy until a later production decision; changing the
   default is not part of this handoff.
8. Extend `debug-book` / `blame --json` so an operator can answer: which snapshot was read, which
   items were inspected, which were selected/rejected, what each sub-call returned, what it cost,
   and whether the scene used a baseline or recursive plan. Do not make a trajectory that exists
   only in a log file.
9. Test architecture boundaries, stale-base refusal, crash/replay convergence, budget refusal,
   invalid IDs, hidden/POV rails, no-fallback behavior, byte-identical baseline, selected-source
   persistence and cache reuse before any live pilot.

Do not add these calls to `packet_for` or `make_plan_selector` directly. A selector that can spend
money and crash between sub-calls has no durable unit, no decision, no budget settlement and no
honest replay.

## Task 5 - one long-serial pilot, not Pilot 6 retrofitted

Pilot 6 is an eight-scene read and is not changed. Create a later pilot only after Task 4, with a
length that crosses the measured boundary: at least the existing 57-scene synthetic/own-generated
substrate, or a continuation copied from a stable store. Never mutate an accepted pilot database.

Pre-register:

- the exact source revision, world artifact, scene count and packet budget;
- baseline and recursive arms, provider/model/profile and sampler identity;
- hard obligations planted at early, middle and late positions;
- context-plan ceilings and stop rules;
- packet metrics, deterministic continuity outcomes and cost/latency summaries;
- the statement that no reader preference or prose-quality claim is licensed.

Run baseline first on a copy, recursive strategy on another copy, one paid arm at a time. Keep both
databases, trajectories, prompts and decisions. A result is the retrieval/continuity/cost table,
including nulls and failures; it is not a hand-selected scene excerpt.

## Out of scope, named so you do not drift into it

- Editing, waiting on, picking for, or completing `claude/book-generation-progress-7dfb8d`.
- Changing Pilot 6's Architect, forge rules, pitch battery, comprehension battery or reader panel.
- Replacing `application/planner.py::render_prompt` or `make_scene_draft_handler` with the RLM
  library.
- Asking sub-models to draft scene chunks and stitching them into fiction.
- Arbitrary Python, shell, filesystem, network or database access in a model-controlled REPL.
- Recursion depth above 1; RLM fine-tuning or reinforcement learning.
- A new embedding stack, learned reranker or summarization policy in the same experiment.
- A model selecting worlds, scene-plan alternatives, repairs or prose candidates.
- Letting summaries become canon, losing source hashes, or serving a stale summary diagnostically
  without the caller explicitly opting in.
- Treating the promise-ledger pressure as a retrieval problem before implementing its own policy.
- Any human panel, operator labels, Royal Road labels or corpus text on the generation side.
- Any claim that the paper's benchmark improvements transfer to fiction quality.

## Deliverables

1. Task 0's frozen manifests, pre-registration, fixture digests and reproduced baseline numbers.
2. LongRangeContext's immutable environment, deterministic packer, cache and adversarial tests.
3. R0 and R1 plus complete trajectory artifacts and the five-arm evaluation report.
4. A promotion/no-promotion decision in LongRangeContext. A null stops here and is a valid handoff.
5. Only on promotion: a versioned LongRangeContext package and compatibility suite.
6. Only then: LitHarness's durable `context_plan` job, adapter, persistence/migration, operator
   provenance surface and tests, with the existing baseline byte-identical.
7. One later long-serial pilot at the measured horizon, with both databases and all cost/context
   artifacts retained.
8. A stage-0 entry at the next free number, in the house form: measured first, what shipped, what
   was refused, no quality claim, no fitted bar, anti-scope. Re-run the cross-worktree number check
   immediately before writing it.
9. Your own commits only. In each repository run its full prescribed checks, including
   `uv run pytest`, Ruff, mypy and `git diff --check` for LitHarness, with no full suite while a
   paid arm is running on the box.

## Stop conditions

Stop and write the result instead of engineering around it if:

- exact, book-grain mandatory/forbidden labels cannot be produced without new human judgment;
- deterministic ledger pruning removes the measured pressure and R0/R1 have no remaining target;
- R0/R1 cannot beat the simple baselines at equal packet budget on held-out long books;
- the gain requires model-authored free text to enter the packet;
- the only implementable runtime is an unsandboxed host REPL;
- the context step cannot be made durable, budgeted and replayable before it spends;
- one-provider-call-at-a-time makes the pre-registered cost/latency envelope unattainable;
- promoting the API requires copying experimental internals into LitHarness.

The successful outcome is not “LitHarness uses RLMs.” It is: **at scene 82, the writer receives
the distant evidence the current packet loses, no forbidden knowledge, under a recorded budget,
and the system can show exactly how that packet was assembled.** If recursive planning is not the
cheapest method that earns that sentence, do not ship it.
