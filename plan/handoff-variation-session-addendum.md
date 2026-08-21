# Addendum to your VariationSession task: register the SYN-DIGITS calibration path

You are the agent working from `plan/handoff-variation-session.md`. This addendum gives you
a second, smaller task. **Sequencing:** finish the VariationSession deliverables first, or
bring them to a clean committed state — do not interleave this with mid-flight migration or
handler work. Every hard boundary in the original handoff still binds. This addendum adds a
registration-and-specification task; it authorizes **no new mechanism, no tables, and no
code** beyond documentation.

References checked 2026-08-21; the repo wins over this document wherever they disagree.

## What happened

A second research extraction landed: SYN-DIGITS (arXiv 2604.07513, Columbia, Apr 2026;
code at github.com/yw3453/syn-digits), a post-hoc calibration framework for LLM persona
simulations ("digital twins"). It stacks a real-human response matrix on a simulated
response matrix and treats the sim-to-real gap as a synthetic-control / matrix-completion
problem. Everything you need from it is inlined below; fetching the paper is optional.

Findings that matter here, with their numbers:

- **Individual-level calibration** (their headline): predicts real individuals' responses to
  new items from sim responses plus real responses to past items. Up to +50% correlation
  over uncalibrated sims. **Prohibited for us and unavailable anyway** — it requires
  solicited per-person human labels (scope axiom, stage-0 §95: not hired, not operator, not
  one blinded pair), and RoyalRoad exposes aggregates, never per-reader response rows.
- **Distributional calibration** (their §7): needs only *marginal distributions* per item.
  Reweight n sim personas plus K degenerate "dummy twins" (each always giving one fixed
  response, guaranteeing full support) by mirror descent on the probability simplex so
  ensemble distributions match observed marginals on past items; read the new item's
  distribution off the reweighted ensemble. 50–90% reductions in distributional divergence;
  TV and KL were the most robust training objectives; error decomposes into an irreducible
  reweighting gap plus O(sqrt(K/n)), degrading when the new item leaves the span of past
  items. **Unsolicited platform aggregates (retention, follows, rating histograms) are
  exactly marginals** — this is the candidate mechanism for connecting the simulated
  readership to the real-population settlement layer, if that flow is ever authorized.
- **The gap is structural, not informational**: handing the sim 249 ground-truth ratings
  in-context bought +16%; calibration bought +50%. Prompt enrichment does not fix sim bias.
- **Calibration is an equalizer and reorders models**: baselines spread .048–.205, calibrated
  results compressed to .204–.243; the best raw model was not the best calibrated model, and
  their fine-tuned sim went from worst raw (.048) to best calibrated (.243). Implication:
  cheap sim personas plus a correction layer may dominate expensive sims run raw.
- **Adaptive transfer = a correction that refuses**: apply the learned correction only when
  a fit diagnostic on the sim system itself says the target is in-span (train MSE below
  ~0.15 in their study), else fall back to the raw prediction. This alone doubled their
  gain (19–21% → 50%).
- **Variance retention**: sim ensembles over-concentrate; they track predicted-variance /
  true-variance ≈ 1 as an explicit health check.
- **Limitations**: structured/categorical responses only (behavioral read-on/drop fits;
  free-form text is open); calibration quality is bounded by the sim and by how well past
  items span the latent space.

## Your task: register and constrain — build nothing

### 1. Find the canonical home

Read `plan/persona-reader-validity.md`, `plan/llm-reader-engagement.md`,
`plan/machine-taste-program.md`, `plan/judge-validity-program.md`, and
`plan/force-program.md` before writing anything. First check whether a parallel session has
already registered this material (search `plan/` and the decision log for SYN-DIGITS,
synthetic control, settlement calibration, reweighting) — if so, **stop and report** instead
of duplicating. Then decide where the design belongs: a new section in the existing
canonical home for reader-sim validity, or a new companion doc (e.g.
`plan/sim-readership-calibration.md`) only if no existing doc is the right home. Counts and
designs point to canonical homes in this repo; a second home for the same question is a
defect.

### 2. Write the design registration

Whatever home you choose must record, in the house's reasons-first style:

- **The mechanism**, as summarized above, at the distributional level only.
- **The axiom analysis**: individual-level calibration is closed by §95 and by platform
  reality; distributional calibration consumes only unsolicited aggregates and solicits
  nothing from anyone.
- **The gate**: whether settlement-layer data may flow back into calibrating the simulated
  readership is an **unmade decision**. The README's "the operator ... trains, calibrates
  and selects nothing" constrains the operator; the real-population flow is a separate
  question that this registration poses and explicitly does not decide. State the trigger
  for deciding it: books live on RoyalRoad with real aggregate data accumulating.
- **Cold start**: nothing to calibrate against until published chapters have real
  aggregates; therefore post-launch only.
- **Order of operations**: calibration sits above instrument validity. Reweighting a channel
  with a known defect (e.g. the measured position bias in the verdict channel) calibrates
  noise. Instrument defect-hunting stays upstream.
- **The Goodhart caution**: the paper's guarantee is predictive, not optimization-robust. A
  reward model calibrated to aggregates and then optimized against is a proxy of a proxy;
  the §61 alpha discipline applies unchanged.
- **Binding constraints on any future sim-readership implementation** (this is the part
  future work must obey): (a) per-persona × per-item behavioral responses persist in
  matrix-completable form, so the stacked formulation is available later without re-running
  sims; (b) ensemble support coverage is checked, with degenerate always-X members
  available as the support guarantee; (c) an ensemble-concentration / variance-retention
  check is part of the readership's health reporting; (d) any learned correction ships with
  an in-span refusal diagnostic and a raw fallback — a correction that cannot refuse is not
  accepted.
- **The equalizer implication**, recorded as a decision input for the force programme's
  model-choice economics (cheap personas + correction vs expensive personas raw), not as a
  claim.

Any check you pre-register must obey the declared-bars discipline: state range, direction,
unit, and non-emptiness, and argue attainability — a bar that cannot do what it says is a
defect, not a plan.

### 3. Append the decision-log entry

Record the registration as a new § entry in `plan/stage-0-decisions.md`, in the house style
(what is being registered, why now, what is prohibited, what is gated, what triggers
revisiting, anti-scope subsection). **Check the log's head § number at write time** — it was
§103 on 2026-08-21 and parallel sessions append to this file; never assume a number from
this document. This is a second, separate entry from the VariationSession design entry your
primary task already owes.

## Hard boundaries for this addendum

- No migrations, tables, or schema changes. No calibration code, no mirror descent, no
  reweighting implementation. No new quality or craft metrics.
- Do not touch `research/quality-measurement/`, the pools/preference/judge stores, or
  provider code for this task.
- No RoyalRoad scraping, data collection, or account activity of any kind.
- Nothing that solicits judgment from anyone (§95), and no human data enters anything.
- If registration is already done by a parallel session, report and stop.

## Definition of done

1. Canonical home chosen after reading the listed docs, with the duplicate check done.
2. The design registration written there, covering every bullet in section 2.
3. The § entry appended with a correct, freshly-checked number and an anti-scope subsection.
4. No code, schema, or store changes anywhere in the diff; VariationSession work unaffected.
5. Commit messages in the house sentence style, separate from VariationSession commits.
