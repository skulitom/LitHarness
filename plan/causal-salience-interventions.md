# Scene interventions and serial-length controls

**Status: model-independent engineering implemented, 2026-08-27. No model was called and no arm
was registered.** This note refines the causal-salience battery in
`reader-perception-research.md`; it does not license a production reader or a consistency claim.
`litharness reader-evidence-audit` now executes the census, validates current-revision spans,
classifies distance rungs, and writes a prose-free manifest, unlabeled public packets, and the
private scoring key separately.

## Decision

LitHarness should treat the **open-ended serial** as the canonical work and a volume as a derived
release package. The default package is 50 globally numbered chapters, adjustable for a natural
40-60 chapter break. It does not mint another book, reset state, imply an ending, or reduce the
consistency obligation to one prompt window. Each volume may have its own cover set.

The first ecological battery does not synthesize all five proposed defect families merely
because the domain vocabulary can describe them. It admits only transformations whose semantic
relation and edited prose spans are independently present in structured, accepted records. The
state family currently has a deterministic sibling generator; the other four have strict
admission contracts and remain unavailable to a model until their transformations are frozen.

## What the stored records can certify

| Requested family | Existing substrate | Admission now |
| --- | --- | --- |
| Causal contradiction | Accepted or author-locked `StateRecord`s, ordered objective facts, evidence spans, and declared finite/opposite predicate domains | **Implemented narrowly.** The census admits repeated allowlisted states with two unique, digest-valid spans; the generator substitutes the later value and creates a matched case-only sham. It never infers antonyms. |
| Event consequence deletion | Reified `CHANGE` records with `actor`, `precondition`, `caused_by`, `effect`, `consumes`, and `produces` roles plus evidence | **Admission implemented; transformation still family-specific.** The census accepts only a unique effect plus a span-backed causal role and reports every missing role/span. |
| Progression deflation | Declared standing ladders/comparators and reified changes carrying `consumes`, `produces`, `precondition`, or `effect` | **Admission implemented for explicit gain/cost changes.** Both `consumes` and `produces` must have current exact spans. There is still no invented general progression schedule. |
| Character-cause substitution | Accepted character wants, ties, standing, capabilities, and reified causal roles | **Explicit causes implemented.** Character sheets expose reified actor/performed-by, caused-by, and effect links with evidence completeness. A free-text `wants` field is never inferred to be a cause. |
| Promise displacement | Scheduled promise windows with opened/due/paid positions | **Evidence path implemented.** Promise opening and payment can carry optional exact scene spans. Historical/unlocated rows stay usable but the census refuses them as hidden keys. |

This is deliberately stricter than semantic plausibility. The state and character builders only
consume accepted canon, but accepted vocabulary is not the same as a located intervention. The
call-free census counts records satisfying all five conditions:

1. accepted or author-locked authority;
2. a declared relation whose values make the damage mechanically decidable;
3. every keyed side has an evidence span whose digest still matches the source revision;
4. the target text occurs uniquely and the edit changes only the intended span;
5. clean, damaged, and surface-control siblings can be made at a matched edit dose.

If any count is zero, the family is unavailable; a model must not fill the missing key. Character
and promise schemas can now retain the required evidence, but coverage exists only where a
particular book actually contains complete current spans.

## Scene-level intervention contract

An ecological item is one source scene plus mechanically derived siblings and a hidden key. The
key contains source revision and group IDs, the relation kind, before/after values, exact anchor
and suspect spans, transformation implementation ID, and expected downstream inconsistency. The
reader sees none of it.

Each semantic intervention needs three siblings:

- **clean:** unchanged source prose;
- **damaged:** exactly one keyed relation is broken;
- **sham:** the same edit size and position distribution without changing that relation.

Code validates source hashes, unique quotes, relation membership, and edit boundaries before an
item enters the battery. The response remains a top-one suspect span plus an incompatible anchor
and relation; listing the entire scene does not pass. Report each mechanism independently, with
false accusation on clean and sham siblings beside detection.

Minimal changes are preferable, but minimality is not permission to make an unnatural sentence.
The [TimeTravel counterfactual task](https://aclanthology.org/D19-1509/) formalises minimal story
revision, while [PASTA](https://aclanthology.org/2023.tacl-1.73/) shows that a local perturbation can
require necessary downstream state changes. LitHarness should therefore record both edit dose and
the exact causal consequence being tested, and reject edits that accidentally break grammar,
voice, or unrelated facts.

## Edit-fingerprint controls

The scorer must not reward recognition of the corruption tool.

- Split by whole source book/world **and** by transformation implementation. A renderer, deletion
  template, or substitution lexicon used in development cannot appear in holdout.
- Match token delta, sentence count, punctuation, whitespace, edit position, and anchor distance
  between damage and sham. Run a deterministic shallow-feature classifier before any LLM arm; if
  those features separate the labels, reject the batch.
- Create multiple implementations of each semantic relation: deletion, neutral restatement, and
  downstream incompatibility where the record permits them. Results must transfer across them.
- Include nonce entity renames and same-book donor wording so names, author idiolect, or an imported
  sentence cannot become the label.
- Keep source and sibling texts blinded and position-balanced. Do not reveal family names, edit
  counts, or whether an item is clean.

This follows the lesson of [SWAG adversarial filtering](https://aclanthology.org/D18-1009): dataset
construction artifacts can make a nominal reasoning task separable by unintended stylistic cues.
LitHarness does not need a model-based filter; a deterministic surface audit is a stronger first
gate because it cannot certify its own semantic intervention.

## Memorisation controls

Primary scored material should be fresh LitHarness-owned scenes created after the selected
reader's training cutoff. Public story benchmarks are diagnostics, not promotion evidence.

- Hold out complete books/worlds, not random scenes, so recurring names and rules cannot leak.
- Preserve the relation graph while replacing entities, quantities, and system labels with nonce
  equivalents. Report original and relabelled results separately.
- Keep author/generator model families out of the measurement pool where possible; existing
  generator-family firewalls still apply because evaluator self-preference can survive concealed
  authorship.
- Store source creation time, content digest, generator family, transformation ID, and every split
  assignment in the manifest.
- Do not count paraphrase as decontamination. [Rephrasing benchmark questions can bypass common
  contamination checks](https://arxiv.org/abs/2311.04850); genuinely new worlds plus graph-preserving
  relabelling are the safer control.

## Long-context and 40-60 chapter controls

A nominal context-window size is not a consistency result. Entity tracking degrades on longer and
unseen-operation splits ([Entity Tracking](https://aclanthology.org/2023.acl-long.213/)); evidence
in the middle of a prompt is often used less reliably
([Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/)). NoLiMa further removes easy lexical
overlap, and RULER adds multi-hop tracing and aggregation rather than needle retrieval alone
([NoLiMa](https://arxiv.org/abs/2502.05167), [RULER](https://arxiv.org/abs/2404.06654)).

Use nested rungs rather than a single full-book score:

1. adjacent scene/chapter;
2. local arc;
3. half-volume;
4. full 40-60 chapter release volume;
5. cross-volume;
6. growing serial prefix.

At every rung, balance anchors and defects at start, middle, and end, including middle-to-middle
pairs, and sample anchor-target distance on a roughly logarithmic scale. Include three task forms:
direct state lookup, multi-hop causal tracing, and aggregation over repeated changes. Add low lexical
overlap items where a concrete event must be connected to a differently worded state. Report by
distance, position, task form, and intervention family; a pooled average can conceal the precise
failure mode.

Novel-length tests must also cover plot order, storyworld location, and time, not only entity facts.
The recent [ConStory-Bench](https://aclanthology.org/2026.findings-acl.410/) uses exact evidence
grounding across factual, temporal, spatial, and narrative consistency categories, while the
novel-oriented [TLDM benchmark](https://aclanthology.org/2026.latechclfl-1.28/) explicitly separates
plot, storyworld, and time. These are useful task shapes, not substitutes for fresh LitHarness data.

Production consistency uses the durable ledger as memory, not repeatedly stuffing the whole
serial into one prompt. Before accepting a new chapter, assemble:

- the recent raw-text window;
- retrieved, span-backed state/event/character/progression records from the entire serial;
- only open cross-volume promises carrying current exact evidence spans;
- a small fixed set of cross-volume sentinels chosen before drafting the target chapter.

The check scope grows with the serial even when the prompt does not. The audit now reports the six
distance rungs independently, and qualification evidence must attest full-volume, cross-volume,
and growing-prefix controls. A release manifest still records `verified: false` until an actual
qualified mechanism runs on that serial; engineering coverage is not an empirical certificate.

## Derived release-volume and cover pipeline

`litharness library` now emits `book-library/<book>/volumes/VolumeN/` with a reading copy, global
chapter fragments, and a manifest. The default window is 50 chapters; `--volume-chapters` changes
packaging without changing manuscript identity. The whole-serial copy remains canonical, and a
short final folder is an in-progress volume rather than an inferred finale.

`litharness cover --volume N` routes an independent cover set to that volume's `covers/` folder and
records the release number alongside the same book, branch, and revision IDs. The library publisher
preserves those assets. This work prepares the path only; no cover was generated. Royal Road's
[volume documentation](https://www.royalroad.com/support/knowledgebase/83) says chapters belong to
one volume and that volumes organise the fiction page and covers without reordering the fiction,
which is why LitHarness keeps global numbering and does not create volume-local canon.

## Model-independent work is complete

Run `litharness reader-evidence-audit --out generated/reader-audit` on any existing book. It makes
no model call, registers no arm, and does not qualify a mechanism. It emits the aggregate census
and prose-free manifest in `evidence-audit.json`, blinded prose in `battery.public.json`, and
labels, source evidence, and scoring keys only in `battery.private.json`. The remaining step is
empirical: combine whole-book groups into frozen
development and holdout sets, register attainable bars, run a candidate reader through the public
packets, and produce the closed qualification artifact. Under the current constraint, that run is
deliberately not attempted and no local model or Claude CLI is required by the repository.
