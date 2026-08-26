# Context audit, 2026-08-24: what each simulated reader is shown, against what its result claims

The rule audited against is stage-0 §125's isolation boundary: every simulated-reader
elicitation carries exactly what a real reader would have at that point and nothing else —
premise-only for premise instruments; chapters 1..k−1 (as the book's own export shows them) for
a chapter-k read; the passage-so-far for a mid-chapter probe. An instrument that deliberately
reads cold may exist, but it must say so in its result and may claim only cold-reading results.

This is a census with labels, not a redesign. Verdicts:

- **correct** — the context matches the claim (premise-only for a premise instrument; a
  whole-book read from chapter 1; a population statistic or judge/channel-validity statistic
  that claims nothing about a reader's position).
- **cold-and-says-so** — reads cold and the result already carries that.
- **cold-and-silent** — presents mid-book text with no history while the claim is (at least in
  part) about a reader mid-book, and the result file never says the read was cold. The action
  column names the label added (this audit's only code change) and, where a claim would need
  real accumulated context, plans it in this table without touching code.
- **registered-frozen** — the design is pre-registered with frozen prompts/parameters. Nothing
  touched; the row records what the registration says about context and whether a future
  version would need a context amendment.

A shared fact that several rows lean on: `elicit.py` (the elicitation front-end every persona
battery uses) is built as **one passage per conversation, no history** — its own docstring
records this as deliberate, because every gate-1 manipulation is a within-passage edit and
reading cold is what isolates the edit. That defence is real for contrast claims (both sides of
a pair share the missing history) and it lives in the code, not in the result files; the labels
below move it into the results where boundary 6 requires it.

## The table

| module | what text a persona sees | what accumulated context it gets | what the result claims | verdict | action |
|---|---|---|---|---|---|
| `comprehension_battery.py` | One forged premise (~120 words), framed as "back-cover copy of a book you just picked up", to each of the four `GENRE_PANEL` readers | None — and none exists for a real browsing reader either; the premise is the whole context | First-contact comprehension: restatement agreement (deterministic Jaccard), undefined words, open questions | correct | none |
| `pitch_battery.py` | A premise and its damaged variant as a blinded, position-swapped pair (`compare_pair`), `GENRE_PANEL` | None — premise-only on both sides | Panel damage-detection on pitches (variant win rate vs the sham floor) — a validity statistic, not a reader-position claim | correct | none |
| `persona_battery.py` | One ~1,000-word scene alone (gate 0) or scene-vs-variant pair (gate 1); stage 1 "You've just read this", stage 2 keep-reading / would-stop. Scenes are mid-book units from `litharness export` dirs, fixtures, or `--published` corpus | None — one passage per conversation by `elicit.py`'s design | Gate 0 ICC and gate 1 detect/sham margins are within-passage contrasts (cold is the isolating design), but the datum is a per-passage would-stop rate — reader behaviour on a mid-book scene — and the summary never said the read was cold | cold-and-silent | Label added: summary carries `"context": "cold_read"`. Planned (table only): any future claim about a reader at scene k needs scenes 1..k−1 prepended as the book's own export shows them — `--passages` already takes a `litharness export` directory and `corpus_io.generated_scenes` yields scenes in order, so the substrate exists; the gate-1 contrast itself needs no change |
| `axiom_battery.py` | Pairs built from committed own scenes (`corpora/toll-scenes.json`) and deterministic transforms (byte-identical copies, separator swap, damage ladder, paraphrase) | None — each comparison independent | Whether the judge is a coherent preference relation (A0–A6 disqualifiers) — a judge property | correct | none |
| `chapter_endings.py` | Nobody — deterministic locator and character-level counters; no model call | n/a | Population distribution of last-paragraph descriptors | correct (no elicitation) | none |
| `comic_beats.py` | One whole chapter, paragraphs numbered, to a locator asked *where and what*, never a verdict; the strip arm is an author-frame revision call over the same chapter | None beyond the chapter — the unit is the chapter as published, which is what its census claims | Located census of levity beats by kind and position, plus instrument controls (Q3); population statistic | correct | none (committed `results/comic-beats-*.json` also pin the schema) |
| `payoff_landing.py` | A bare model (no persona) sees two 450-word excerpts — head of the scene that opened a promise, tail of the scene the ledger credits — labelled "Two passages from the same book. The second comes later", and names the settled debt | None — every scene between the two excerpts is absent, and the head/tail windows cut even the two shown scenes | Whether the ledger's claimed payoff *lands* — a claim about the book's reader at the paying scene, read through paid/mismatched/unpaid/placebo controls | cold-and-silent | Label added: report and per-response rows carry `"context": "cold_read"`. Planned (table only): the landing claim's correct context is the intervening scenes in the book's own export order — `read_scenes()` already returns all scenes in order, so a future version could show everything from the opened scene to the paying scene (or their shipped summaries); that is a new instrument version, not an edit to this one |
| `retention_distance.py` | No persona — teacher-forced forward passes: passage/matched filler + distractor + probe window | The constructed context *is* the manipulation | Memory-decay slope of prose in the model's context; mechanical population statistic | correct | none |
| `conversion_separation.py` | Nobody — CPU-only label-side study; no model call | n/a | Whether the conversion label separates prose from prose vs prose-blind baselines | correct (no elicitation) | none |
| `taste_benchmark.py` | Two matched paragraph-aligned excerpts cut from inside one chapter per story (window starts ~20% in), high- vs low-conversion, aligned/crossed strata | None — excerpt-only on both sides; the missing story context is identical across the pair | Judge–label agreement (`min` over strata) — a standing judge benchmark; no reader-position claim | correct | none |
| `taste_calibration.py` | Panel compares mid-chapter excerpts across arms (ours vs MoL, ours vs RR, MoL vs RR, RR high-vs-low, MoL vs MoL) | None | Whether the panel has taste or detects authorship — a panel property read across arms | correct | none |
| `cadence_discrimination.py` | Three placement variants of one span of committed own scenes, with `domain/discrimination.py`'s byte-frozen E6 question (name the difference; no preference leg) | None | Whether explicit payoff *placement* is nameable at all — a channel/discriminability claim | correct | none |
| `summary_reliability.py` | The shipped summariser prompt (`render_summary_prompt`) over one scene at a time, resampled | None — which matches production: the shipped call summarises a scene in isolation | Re-sample stability vs between-scene separation of the summariser; instrument reliability | correct | none |
| `world_uptake.py` | Nobody — deterministic naming-uptake counter with a wrong-world sham | n/a | Naming-uptake distribution; labelled as naming only | correct (no elicitation) | none |
| `reader_defects.py` | Blinded position-swapped pairs of one toll scene vs its interiority/stat-flatten variant; "which would you rather keep reading" | None — single scene per conversation | Whether the panel can see the two reader-named defects — a within-passage contrast (both sides share the missing history), asked in reader-behaviour vocabulary, with no cold marker in the report | cold-and-silent | Label added: report carries `"context": "cold_read"`. No semantic change needed — the contrast design is the point |
| `reader_repair.py` | Same pair frame over the em-dash arms (strip / inject / rewhitespace) on ten toll scenes | None | Whether the panel shares the human reader's taste on the one cleanly-manipulable defect — the human read the book in order; the panel reads one scene cold and the report did not say so | cold-and-silent | Label added: report carries `"context": "cold_read"` |
| `repair_generation.py` | Generation half: the writer model revises one of its own scenes; panel half: `compare_pair` of repair vs cached sober anchor, one scene, no history | None on either half | Whether a defect-aimed repair moves the panel against the placebo band — a contrast claim in reader vocabulary, silent about the cold frame | cold-and-silent | Label added: report carries `"context": "cold_read"`. `PRE_REGISTRATION`, prompts and arms untouched |
| `writer_states.py` | Retells of single scenes under state blocks; panel `compare_pair` of state retell vs sober retell | None | Whether simulated writer states reach the prose (panel contrast + mechanics deltas) | cold-and-silent | Label added: report carries `"context": "cold_read"`. `PRE_REGISTRATION`, prompts and states untouched |
| `bcr.py` (bcr.v0) | The budgeted reader sees both books' opening chunk and then every chunk it pays to fetch, sequentially, in one conversation | Accumulated within the session from chunk 1 of each book — "each choice is conditioned on everything read so far" | Budget allocation between two openings-onward reads; the claim and the context coincide | registered-frozen | none — §94/§120.5 byte-freeze; context matches claim by construction |
| `feed_core.py` / `feed_substrate.py` / `feed_session.py` / `feed_battery.py` / `feed_controls.py` (fcr.v0) | Four books entered mid-stream at section 3: per slot a deterministic skim of sections 1–2 (`RECAP`) plus one full current section; every section the reader pays to read accumulates in the transcript | Accumulated by design: skimmed story-so-far plus the session's own reads. `RECAP`, `MIDSTREAM_CHUNK` and the skim extractor are inside `PRE_REGISTRATION`, copied verbatim into every result | Costed continuation / abandonment as the revealed preference of a mid-stream feed reader | registered-frozen | none — the registration itself declares the context construction, and the claim is explicitly about a mid-stream reader with a recap, which is what a real feed gives. A version wanting true full-history entry is a new registration (fcr.v1), not an edit |
| `anticipation.py` (anticipation.v0) | The passage-so-far of one committed own scene — the paragraph boundary nearest 60% of its words — plus the byte-frozen `PROBE`, to `GENRE_PANEL` | Within-scene only; no earlier chapters, and the scenes are mid-book units | Mid-chapter anticipation (specificity, stance spread), read **only** as the destake-vs-matched contrast, which cancels the missing history | registered-frozen | none — `plan/anticipation-probe-validity.md` freezes the passage-so-far construction at scene grain. Recorded for a future version: a non-contrast claim about a reader mid-book would need prior chapters through the export path — a context amendment to the registration, not an edit |
| `affect_trajectory.py` | One whole chapter with numbered paragraphs to a register locator; the flatten arm is an author-frame rewrite call | None beyond the chapter | Register-sequence census (population statistic); scores nothing, admits nothing | correct | none |
| `promise_kinds.py` | The shipped summariser question over single scenes (constrained + open arms) | None — production call is per-scene | Distribution of reported promise kinds; a pruning observation, no bar | correct | none |
| `platform_priors.py` (D1P) | Generation only in this module: the model rewrites/extends our own scene to build blend/insert dose families; no reader is asked anything here | n/a at build time; at read time the seated budgeted reader's own accumulated-session context applies (`bcr` row) | Families built under the §104 registration; allocation claims are deferred to the registered D1P protocol | registered-frozen | none — read-side context is `bcr`'s, already correct by construction |
| `elicitation_study.py` | Protocols E1–E6 over certified pairs (B6 families, repair pairs), one pair per conversation | None | Where between representation and verdict discrimination dies — a channel property | correct | none |
| `composite_panel.py` | Layer 1 counters and layer 2 frozen readout are deterministic; layer 3 (if any Track E protocol survives) sees one pair | None | Panel v2 assembly: gate, rank, decline to prefer — a judge property | correct | none |
| `latent_crossfamily.py` | Local ollama judges see §85's certified repair pairs, both orientations | None | Positional-bias eligibility screen; win rates withheld unless the precondition passes | correct | none |
| `register_halflife.py` | No persona — a seed passage and the model's own continuations, measured mechanically | The seed is the context | How long a passage's register survives in continuations; mechanical, confound named | correct | none |
| `writer_distinctness.py` | Writer models draft from their dossiers (`ask_raw` generation); readings over the drafts are deterministic | n/a — generation-side | Roster distinctness plus the scrambled-dossier control | correct (no reader elicitation) | none |
| `voice_binding.py` | Generation: exemplar-conditioned retells and revisions over `claude -p`; scored by §85's certified path | n/a — generation-side | Dose and persistence of the demonstrated-voice lever | correct (no reader elicitation) | none |
| `world_plan_arms.py` | Outline calls, world-aware vs not; graded by `world_uptake`'s frozen counter | n/a — generation-side | P1–P3: world uptake separation of outlines | correct (no reader elicitation) | none |
| `transmission_chains.py` | Each hop's model sees only the previous hop's retell ("retell this from memory for a new reader") | None — deliberately: the loss of context between hops *is* the transmissibility quantity | What survives retelling; population claim | correct (the cold hop is the instrument, and the design says so) | none |
| `elicit.py` | Infrastructure: renders persona system prompts and the one-passage / one-pair two-turn conversation every battery above uses; no claims of its own | None — "one passage per conversation, no history", documented as deliberate in its docstring | n/a (transport + record) | correct (front-end; the cold frame is deliberate and documented in code — carrying it into results is each battery's job, done via the labels above) | none |
| `personas.py` | Frozen persona prompts and turn templates; presents nothing itself | n/a | n/a | registered-frozen (explicitly out of bounds for this task) | none |
| `force_remote.py` / `force_harness.py` / `force_gpu.py` | Transports/harness for the F-track forces; text is continued or scored, never shown to a persona | n/a | F-track mechanical claims | correct (no elicitation) | none |
| backtest `arms.py` | A frozen persona sees two blinded excerpts in one two-turn session: stage 1 names concrete differences, stage 2 emits one behavioural action from a closed schema | None beyond the excerpts — but each excerpt is the fiction's chapters 1–3 from the start (PREREG §2), identity-stripped, which is exactly what a new platform reader has at that point | Which member the persona would continue; conditional primary per PREREG §5–6 | registered-frozen | none — PREREG §2/§4 fix the excerpt construction and it matches the new-reader claim; no context amendment needed |
| backtest `blinding.py` | Nobody — strips identity/popularity markers, never reflows prose | n/a | The blinded text and its digest | registered-frozen | none |
| backtest `population.py` | Nobody — frozen personas and the reward/holdout split | n/a | n/a | registered-frozen | none |
| backtest `recognition.py` | The model sees the blinded excerpt under three frozen recall probes (title / author / continuation) | None — deliberately: the screen asks whether the model already knows the text, so cold is the question itself | Memorisation stratum assignment (`recognised` exclusion) | registered-frozen (cold by design and PREREG §3 says so) | none |
| backtest `backtest.py` / `corpus.py` / `analysis.py` | Drivers and pure arithmetic; present nothing to a model | n/a | n/a | registered-frozen | none |

## Checked and found to present nothing to a persona/model for elicitation

`ablate.py` (deterministic transforms; its model-generated variants are built elsewhere),
`authorship_tells.py` (deterministic classifier over features), `b6_benchmark.py` (fixture
admission artifact), `baseline.py` (counters), the retired craft-profile builder, `cdg_battery.py` /
`surprisal.py` / `surprisal_field.py` (mechanical scoring), `compression_progress.py`,
`context_l0_arm.py` (context-assembler census, no model), `corpus_io.py`, `corpus_leak_audit.py`,
`determinism_probe.py`, `director_distinctness.py` (directive-generation distinctness, no reader),
`elicitation_study.py`'s torch half `verdict_locus.py` and `latent_probe.py` / `latent_fixtures.py`
/ `latent_support.py` (internal-state probes, no verbal elicitation), `evaluate.py` (arithmetic),
`feedback_ablation.py` (generation-loop ablation; machine counters; its reader-side arm is
explicitly BLOCKED/UNDECIDABLE and buys nothing), `fitness_books.py`, `force_market.py` /
`force_report.py`, `named_persons.py`, `opening_counters.py`, `refuted_metrics.py`,
`register_halflife.py`'s sibling utilities, `standing.py`, `state_coverage.py`,
`system_lines.py`, `thermal_watch.py`, `world_lexicon.py`, `writer_g0.py` (calls no model).

## Labels applied (Task 2)

`"context": "cold_read"` added as a literal result field — no prompt, sampled text, parameter,
or registered constant changed — to:

- `persona_battery.py` — top level of the summary dict.
- `payoff_landing.py` — top level of the report dict and each per-response row.
- `reader_defects.py` — top level of the report dict.
- `reader_repair.py` — top level of the report dict.
- `repair_generation.py` — top level of the report dict.
- `writer_states.py` — top level of the report dict.

No test consumed those summary schemas, so no test changed. Committed files under `results/`
are untouched; the field appears in future runs' outputs only. No `"context": "accumulated"`
label was needed outside the registered-frozen instruments (`bcr`, `feed_*`), whose
registrations already carry their context construction verbatim in every result file.
