# Research note: teach and test salience before asking for quality

**Status: direction note, 2026-08-27. No model calls were made for this work.** This note
narrows `reader-architecture-program.md`; it does not register an arm, license a reader, or
change production.

## Conclusion

The next useful asset is not another reader prompt, a larger council, or an activation lens in
isolation. It is a **causal salience battery**: stories with one hidden, controlled defect whose
location and downstream consequence are known to code. Every candidate cognitive architecture
can then be tested on the same question: did it locate the most consequential injected damage,
and did it reconstruct what that damage broke?

This changes the search from *which reader sounds discerning?* to *which system learns or exposes
the right internal distinction?* It also gives multi-agent analysis and representation probes a
shared target instead of letting either define quality by its own outputs.

## Why this is the bottleneck

The repository's result is more specific than “LLM judges are noisy.” The reader can separate the
registered follower gradient, yet its paired screen prefers LitHarness listings to the operator's
summits 24/24. It is reading a stable signal; it is attending to the wrong one.

Recent primary research points to **salience and representation structure**, not prompt wording:

- [Help Me Write a Story](https://aclanthology.org/2025.acl-long.1254/) finds that models often
  give specific, correct feedback while missing the biggest intentionally introduced writing
  problem. Its best correctness readings are materially above its error-localisation readings.
- [Style over Story](https://aclanthology.org/2026.findings-acl.1361/) finds a stable model
  preference for style over event and character (style selection rate ratio 1.78 against event);
  quality-focused instructions do not remove that style preference. This is a plausible external
  explanation for a polished generated listing beating a stronger story.
- [Beyond Correctness](https://arxiv.org/abs/2510.14616) removes grammar, factuality, and length
  cues from writing pairs. Direct sequence reward models and zero-shot judges fall near chance,
  while generative reward models with intermediate reasoning reach 81.8% on its human-labelled
  benchmark. The transferable result is architectural: direct classification loses the subjective
  signal that a generative intermediate representation can carry.
- [CoKe](https://aclanthology.org/2025.gem-1.31/) finds that sampling more free-form rationales can
  optimise for fluent-looking explanations rather than correct story ratings; a constrained
  keyword intermediate representation performs better. More debate text is therefore not evidence
  of more perception.
- [Finding Flawed Fictions](https://arxiv.org/abs/2504.11900) supplies the closest usable
  construction: synthesize a defect, retain the two contradictory evidence spans as the key, and
  score localisation rather than prose persuasiveness. Frontier performance degrades with story
  length, so long-form capability must be measured rather than inherited from a blurb result.
- [Prover-Verifier Games](https://arxiv.org/abs/2407.13692) shows that adversarial training can make
  reasoning more checkable when correctness is externally verifiable. Literary quality has no such
  verifier; the hidden intervention key is what creates one for a bounded capability.
- [Iterative Dual-Model Alignment](https://aclanthology.org/2026.acl-long.648/) improves a trained
  story evaluator by coupling a classifier to a label-blind structured explainer. Its supervision is
  human engagement data and therefore inadmissible here, but the separation of explanation from
  decision is an architecture worth testing against admissible keys.
- [LLM evaluators recognise and favour their own generations](https://arxiv.org/abs/2404.13076),
  which preserves the need for a generator-family firewall even when authorship is hidden.
- [Discovering Latent Knowledge](https://arxiv.org/abs/2212.03827) shows that activations can
  contain distinctions a model does not reliably say, so a lens remains a real candidate. But
  [control-task research on probes](https://aclanthology.org/D19-1275/) shows that probe accuracy
  alone can mean the probe learned the task. Held-out intervention families and shuffled-label
  controls are therefore prerequisites, not follow-up polish.

The papers that train high-performing story evaluators use human preference labels. That route is
outside LitHarness's scope axiom. Their value here is the architectural evidence—specialisation and
structured intermediate reasoning help—not their supervision source.

## Proposed mechanism: Causal Salience Reader

The battery contains clean/damaged siblings generated from LitHarness's own unmemorised scenes.
Each damage family has a machine-held key:

1. **Event consequence deletion** — remove the act that changes the scene while preserving its
   setup and surface register; key the missing state transition and its source span.
2. **Character-cause substitution** — preserve the outcome but replace the motive or choice that
   makes it belong to this character; key the incompatible motive and later consequence.
3. **Progression deflation** — preserve the gain and system vocabulary but remove its cost or
   dramatic consequence; key the gain/cost relation.
4. **Promise displacement** — preserve the same events but move or replace the payoff so the
   registered debt no longer lands; key the opened promise and expected paying event.
5. **Causal contradiction** — negate an established fact later, following the FlawedFictions
   construction; key both evidence spans.
6. **Surface-only control** — matched changes to names, layout, length, and diction that should not
   dominate the story-level families.

Admission is strict: the semantic change must be guaranteed by an explicit stored relation or by a
mechanical edit whose before/after spans are known. A model-generated corruption cannot certify
its own key. If an intervention needs subjective confirmation to establish what it changed, it is
not yet battery material.

The initial reader mechanism has three model behaviours and no model verdict:

1. A **tracker** emits a small causal state: event, actor, motive, consequence, debt opened/paid.
2. A **locator** gets a fixed budget and returns its single most consequential suspect span plus the
   downstream state it cannot reconcile. Top-one is deliberate: a flood of correct trivia does not
   pass the salience problem identified in the feedback study.
3. A **challenger** tries to reconstruct a coherent causal chain using only quoted spans. This is not
   a vote. Code checks quotation location, overlap with the hidden intervention, the keyed relation,
   and whether the untouched sibling was falsely accused.

Candidate architectures may implement those behaviours with one model, independent agents,
iterative Alpha/Beta-style refinement, or internal probes. The scorer and held-out battery do not
change between candidates.

### Implemented substrate (not an experiment)

`research/quality-measurement/causal_salience.py` now freezes the hidden-key, reader-claim, and
item-score contracts and exercises them without a model. Its fixtures are controlled-language
mechanism tests only: allowlisted binary states are contradicted after an explicit no-change
statement, while matched controls alter whitespace and preserve every non-whitespace codepoint.
Development and holdout use different contradiction renderers and different surface transforms;
source groups cannot cross the split. Quotes are bounded, must locate uniquely, and the top-one
suspect and anchor must overlap both hidden spans before an exact causal relation earns detection.

Perfect, random, criticism-flooding, and style-only fake readers establish the scorer's operating
characteristics. The manifest and registration are digest-pinned by tests, results contain no
outside prose, and the report explicitly carries no promotion bar. Run the free diagnostic with:

```bash
uv run python research/quality-measurement/causal_salience.py --selftest
```

This substrate does not establish ecological validity. Before a model arm, replace or extend the
toy fixtures with unmemorised LitHarness scenes whose answer keys are certified by existing state,
event, or promise relations; do not loosen admission to accept model-authored damage at face value.

## The first arm, when a model path is available

Do not begin with training. Compare mechanisms on a small, frozen battery first:

- same clean/damaged sibling groups for every mechanism;
- variants blinded and position balanced;
- one top-one localisation per scene, with abstention available;
- reports by damage family, never only pooled;
- untouched siblings, surface-only edits, entity renames, and layout changes in the same pass;
- held-out books **and held-out transformation implementations**, so a reader cannot learn an edit
  fingerprint;
- long-context rungs, because short-text success does not license scene or book reading;
- the follower gradient only after the causal battery is readable; LitHarness text only after that.

No numerical bar should be registered until the attainable ranges at the real item and book counts
have been simulated. The registered directions are enough for now: injected damage should be
located more often than shams; story-level families must not be eclipsed by surface controls; and
the known-bad LitHarness target must not again look cleaner than the market.

## Kill conditions

- **Style shortcut:** surface damage is found while event, character, progression, or payoff damage
  is missed at comparable dose.
- **Criticism flood:** recall rises only by flagging clean siblings.
- **Wrong salience:** the injected defect appears somewhere in a long list but not in the top-one
  response.
- **Edit fingerprint:** performance collapses on a held-out implementation of the same damage.
- **Memorisation:** entity renaming or using unmemorised LitHarness scenes removes the effect.
- **Explanation theatre:** free-text rationale length or fluency rises without localisation gain.
- **Probe illusion:** an activation probe fits the target labels but has no selectivity over
  shuffled-label controls or fails on held-out intervention implementations.
- **No transfer:** the battery is passed but the follower gradient or the operator's fixed acceptance
  target remains inverted. Then the battery taught bounded defect recognition, not readership.

## Scope boundary and order

The narrow substrate now exists: battery generator, hidden keys, deterministic scorer, frozen
splits, and call-free fixtures. It does **not** add a production reader, train a model, run a
council, or inspect activations. From here:

1. compare single-pass structured generation with a tracker/locator/challenger architecture;
2. independently test whether an activation probe recovers the same keyed distinctions when the
   verbal channel succeeds **or fails**, with probe controls in the same pass;
3. only if a frozen verbal or representation-level mechanism has signal, consider synthetic-data
   fine-tuning;
4. only after transfer survives may any output become reader direction.

This order keeps the lens direction alive without making it a separate research programme: the
same causal labels test whether registered defect distinctions exist in activations and whether the
decoder can express them.
