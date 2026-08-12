# Build spec: the LitRPG deterministic rules pack

**Status: BUILT AND GREEN.** ContinuityEvaluation 20 → 42 tests passing; the six
checks reproduce the litrpg gold set exactly, with span-level equality.
**Home:** `C:\DEV\ContinuityEvaluation` (see PLAN.md §8.4 for why here, not a new
package).
**Precondition:** ~~`git init` litharness-contracts~~ — done, commit `858901a`.

## 0. As built

| | |
|---|---|
| Detectors | `src/continuity_evaluation/detectors/rules/` — `ledger_gold`, `stat_ceiling`, `level_monotonic`, `skill_acquisition`, `quest_transition`, `ghost_item`, plus `common.py` |
| Translator | `PREDICATE_TRANSLATIONS` table in `runner/run.py`; allowlist, `note` not projected |
| Fixture gate | `run.py` now derives the expected fixture id from the plan's own path instead of the literal `"mystery"`; facts schema `const` → `enum` |
| Configs | `configs/litrpg-evaluation-plan.json`, `benchmarks/corpora/litrpg-evaluation-state.json` (deliberately empty sidecar — no hand-authored ground truth) |
| Gates | `tests/integration/test_litrpg_rules.py` (14), parameterized `test_slice_gates.py` (5), parameterized `test_reproducibility.py` (6) |
| Result | 6 findings, one per detector; 0 errors, 0 abstentions; byte-identical across runs |

Two things the build changed relative to this spec, both because a test failed and
the test was right:

1. **`rule_or_critic_id` is not part of the grading identity.** Mystery's gold cites
   `location.exclusive.v0` while the repo ships `location.exclusive.v1`, so including
   rule id in the exact-set tuple failed on *mystery*, not litrpg. Identity is
   `(category, subtype, primary_span)`; the litrpg rule-id alignment is asserted
   separately, where it is actually a property of that family.
2. **The ledger mutation test had to repair the event, not the status block.** Setting
   scene-3 gold to 20 does *not* silence the detector, because the fixture's scene-4
   and scene-5 blocks also carry 15 — a value that follows from the planted defect. So
   a block-only edit just moves the mismatch downstream. Raising the toll from 5 to 10
   repairs the whole chain. That the first attempt failed is the mutation test earning
   its place on its first run.

Everything below is a verified fact about files on disk, not a design preference.
The point of writing it down is that four of these facts are non-obvious and each
one, if missed, produces a green gate that proves nothing.

## 1. The exact gold target

Eight findings in `fixtures/golden/litrpg/findings.json` — six `open` defects to
detect, two `accepted_intentional` controls to leave alone.

| finding_id | category | subtype | rule_or_critic_id | severity |
|---|---|---|---|---|
| f-gold-ledger | `world_rule` | `resource_conservation` | `ledger.gold.v0` | major |
| f-skill-before-acq | `causality` | `use_before_acquisition` | `causality.acquisition.v0` | major |
| f-hp-over-max | `world_rule` | `stat_ceiling` | `stats.ceiling.v0` | major |
| f-level-regression | `physical_state` | `level_regression` | `stats.level_monotonic.v0` | critical |
| f-quest-early-complete | `promise_payoff` | `thread_state` | `thread.transition.v0` | major |
| f-silver-key-ghost | `inventory` | `ghost_item` | `inventory.ghost.v0` | major |
| f-control-flavor | `style` | `unreliable_system_text` | `style.flavor.v0` | info |
| f-control-status-repetition | `repetition` | `intentional_format` | `repetition.format.v0` | info |

So the litrpg plan's `categories` are
`["world_rule", "causality", "physical_state", "promise_payoff", "inventory"]` —
disjoint from the mystery plan's `["location", "inventory", "physical_state",
"timeline", "knowledge"]` except for two shared members.

## 2. Four non-obvious facts that make this tractable

**(a) Evidence spans come free — do not hardcode them.** Every one of the six gold
findings' `primary_span` is exactly the triggering record's own evidence span. So a
detector that calls `span(request, triggering_record)` matches gold automatically,
and the span-verification in `resolve_evidence` (which re-hashes the excerpt from
scene text and rejects a mismatch) becomes free correctness insurance. The trigger
record per finding:

| finding | trigger record | order key |
|---|---|---|
| f-gold-ledger | `rec-s3-status` | s3 |
| f-skill-before-acq | `rec-ev-shadowstep-use` | s3 |
| f-hp-over-max | `rec-s4-status` | s4 |
| f-level-regression | `rec-s5-status` | s5 |
| f-quest-early-complete | `rec-s5-quest-completed` | s5 |
| f-silver-key-ghost | `rec-ev-silver-key` | s4 |

**(b) Emit no supporting evidence.** The existing gate asserts
`correct_evidence / total_evidence == 1.0` over `[primary_span, *supporting_evidence]`
of every matched finding. Some gold *supporting* spans are prose-only — the
`[INVENTORY]` and `[SKILLS]` blocks — with no corresponding state record, so a
detector that helpfully adds its own supporting spans will drive precision below
1.0 and fail. With `supporting=()` the emitted set is `{primary}`, which is always
in the expected set. Add supporting spans only if the fixture's own supporting
spans become record-derivable.

**(c) The answer-key leak is already closed here.** `StateRecord.note` carries the
finding id for five of the six defects. CE's `_build_corpus` projects each record
onto a fixed field list (`record_id`, `subject_id`, `predicate`, `value`, `scope`,
`status`, `valid_from`, `valid_to`, `resource_kind`, `evidence`) that does not
include `note`. Preserve that; add a test asserting no detector module references
`note`.

**(d) Detectors read the corpus, not `state.json`.** So carrying the game
predicates through `_build_corpus`'s translator is the actual enabling step, and it
must be done without perturbing the mystery corpus (§4).

## 3. Record shapes

`status_snapshot` assertions (subject `rook`, one per scene s1..s6) carry
`{level, hp, hp_max, mp, mp_max, gold}`. The event vocabulary, complete:

| predicate | value | order key |
|---|---|---|
| `purchased` | `{item: storm_lantern, cost_gold: 20}` | s2 |
| `paid` | `{amount_gold: 5}` | s3 |
| `used_skill` | `{skill: shadowstep}` | s3 |
| `consumed` | `{item: red_potion}` | s4 |
| `leveled_up` | `{to_level: 4}` | s4 |
| `used_item` | `{item: silver_key}` | s4 |
| `acquired_skill` | `{skill: shadowstep, level: 1}` | s5 |
| `paid` | `{amount_gold: 15}` | s6 |
| `quest_completed` | `{quest: the_toll_gate}` | s6 |

Plus a `quest_status` assertion on subject `quest_toll_gate` at s5, a
`thread_status` record, and two `author_locked` `world_rule` records:
`rule_hp_ceiling` = `"hp_current <= hp_max"` (mechanically interpretable) and
`rule_level_monotonic` = `"level never decreases except on death"` (English prose —
so this one needs a rule_id→semantics map; the "drive thresholds from the data"
mitigation is only half available).

Snapshot trajectory: gold 45 → 25 → **15** → 15 → 15 → 0; level 3 → 3 → 3 → 4 →
**3** → 4; hp 24 → 24 → 22 → **34** → 27 → 27 (hp_max 30 throughout).

## 4. The six checks

Only `ledger.gold.v0` is a fold. The other five are record scans — which is why
CE's `DeterministicDetector` protocol hosts them naturally.

1. **`ledger.gold.v0`** — fold `purchased.cost_gold` and `paid.amount_gold` across
   order keys, compare to each snapshot's `gold`, and **resync to the asserted
   value after reporting** (PLAN.md §8.2). Pure carry-forward yields four findings
   where gold has one, and its spurious s6 divergence collides with control
   `f-control-status-repetition`'s span, failing the control clause.
2. **`stats.ceiling.v0`** — intra-snapshot `hp > hp_max`. No simulation.
3. **`stats.level_monotonic.v0`** — consecutive snapshots, level decreased, no
   death event present.
4. **`causality.acquisition.v0`** — `used_skill` at an order key earlier than the
   matching `acquired_skill`.
5. **`thread.transition.v0`** — `quest_status: completed` asserted at an order key
   earlier than the matching `quest_completed` event.
6. **`inventory.ghost.v0`** — `used_item` with no acquisition record. **Must be
   scoped to `used_item` only**, because `consumed red_potion` also has no
   acquisition record and is *not* a labeled defect. That leaves a population of
   exactly one, so this detector is near-tautological and needs the mutation test
   (§5) to mean anything. Escalate the `consumed`-vs-`used_item` asymmetry to
   litharness-contracts as a fixture inconsistency rather than silently living
   with it.

Do **not** simulate `hp/mp/hp_max/mp_max`: no record carries a delta for them, and
the snapshots move for prose-only reasons.

## 5. The gate

Parameterize `tests/integration/test_slice_gates.py` off its hardcoded
`len(required) == 5`, `len(controls) == 3`, `len(artifact["findings"]) == 5`, and
its `DETERMINISTIC` category set. Then, per PLAN.md §8.3, add what the existing
gate does not cover:

- **Exact-set equality** on `(category, subtype, rule_or_critic_id, primary_span)`
  — the existing total-count assertion is a good precision gate but does not pin
  identity.
- **Mutation matrix** — perturb the corpus in memory and require the named
  detector to go *silent*: s3 gold → 20 (`ledger.gold`), s4 hp → 30
  (`stats.ceiling`), s5 level → 4 (`stats.level_monotonic`), move
  `rec-ev-shadowstep-acq` to s1 (`causality.acquisition`), move
  `rec-s5-quest-completed` to s6 (`thread.transition`). Then the inverse on a
  conforming step and require a new finding. Without this, three of six checks
  have a fixture population of one and zero negative examples.
- **Cross-fixture silence** — run the litrpg detectors against the mystery corpus
  and require zero findings. Mystery has no `status_snapshot`, `gold` or `level`
  predicate anywhere, so this is a genuine (if weak) precision check where the two
  designated controls are not.
- **No-`note` assertion** — grep the detector modules.

## 6. Backward-compatibility constraints

The mystery run is currently green and must stay byte-identical:

- `input_digest` is computed from the **raw** artifacts, not the corpus, so
  carrying extra predicates through the translator cannot move it.
- `run_id` derives from `digest(plan)` + corpus hash + selected detector ids, so
  leaving the mystery plan and raw fixtures untouched keeps it stable.
- Keep the translator **allowlist-based**: map the three existing mystery
  predicates plus the game predicates, and continue to drop the rest. A translator
  that carries *everything* through would add mystery records the existing
  detectors ignore — harmless to findings, but it perturbs the corpus for no gain.
- The fixture gate at `run.py:43` should compare against the fixture id declared in
  the plan rather than the literal `"mystery"`, and the schema's
  `contract_fixture_id` `const` becomes an `enum`.
- Fix `CONTRACT_SCHEMAS.samefile("C:/DEV/litharness-contracts/schemas")` in
  `tests/contract/test_schemas.py` while in there — it hardcodes an absolute path
  and makes the suite machine-bound.

## 7. What this does and does not close

Three of §8.3's four promotion clauses. The fourth — validation of model-written
(not templated) chapters — needs generation, which needs Stage 0. Report it as
three of four.
