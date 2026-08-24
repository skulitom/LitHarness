# The clarity audit: every model-facing instruction in the generation path, read against CLARITY

This is `plan/handoff-clarity-first.md` T1 — the table produced before anything changes, and
the record of what is wiped and why. Read the handoff's boundaries first; boundary 3 was
amended on the operator's correction that a forbidden-words list is a mask, not a fix:
*"we should fix the core of the issue instead of masking the consequences."*

The generation path was read module by module on 2026-08-24 (every `CompletionRequest`
construction site under `src/litharness/`, every instruction string it renders, and the
directive lane that carries forge output into downstream prompts). Three findings frame the
table: the contradiction class has exactly one family in it (never-explain), that family
appears in two modules plus one open channel (the forge's own `tone_note` emission, which
mints new members at run time); and every craft word list in the path traces to a cause that
is being removed rather than masked.

## The contradiction class (boundary 1: delete entirely)

| # | Where | The instruction | Why it goes |
|---|-------|-----------------|-------------|
| C1 | `application/architect.py:931` (`_RULES`, register rule) | "The prose this world will be written in is fast, plain, popcorn reading. … **It is never explained.**" | The direct contradiction of CLARITY ("every word … is explained where it is used"). This is the sentence the forge resolves into gnomic aphorisms, and the seed of every emitted never-explain tone note. The first two sentences of the rule survive; the final clause is deleted. |
| C2 | `application/architect.py:490` + `directives_for` (2317–2338) | The forge may emit `tone_note` directives — the 2026-08-24 forges emitted "Never explain how any of it works" | An open channel that mints contradiction-class instructions at run time, with no legality gate: `directors.legal_brief` (directors.py:136) refuses craft doctrine from the Director, and the forge's directive lane never passes through it. `tone_note` is removed from the forge schema enum and from `directives_for`'s allowed set; the surviving kinds (`constraint`, `arc_note`, `chapter_note`) are routed through `legal_brief`, so a forge-authored directive faces the same rail a Director-authored one does. Tone comes from the house or not at all. The operator's own `direct` command (cli.py:4563) is untouched — that channel is direction, not system output. |
| C3 | `application/architect.py:669` (`_RULES`, manifests rule) | "…carries `manifests_as`: one line of how it shows on the page — … **Never an explanation and never a lecture.**" | The positive specification (what is seen, heard or paid) already does the work; the never-clause is the same family as C1, reaching every `manifests_as` in every world. Clause deleted, positive form kept. |
| C4 | `application/architect.py:430` (`_PROTAGONIST.edge` description) and `:879` (premise rule) | "…written the way `manifests_as` is written: how it shows on the page, **never an explanation**" | Same family, same fix at :430. The :879 instance sits inside the premise essay, which T3 deletes whole (see P1). |
| C5 | `domain/world_brief.py:344` (`WORLD_RULES[1]`, rendered into the outline and the narrative planner) | "**Do not explain the world.** A statement says what happens, and a scene where somebody explains how the world works is a scene where nothing happens." | The first sentence instructs withholding and contradicts CLARITY head-on in the two prompts that decide what every scene is for. What the rule is actually protecting — a scene must contain an event, not only exposition — survives without the withhold instruction: "A statement says what happens. A scene whose only content is an explanation of how the world works has nothing happening in it; the world's workings reach the reader through events, priced and shown." |
| C6 | `application/outline.py:353` (milestone rules) | "Costs as well as gains: **this is a debt story**, so spending and losing are progression too." | Not never-explain, but contradiction-class all the same: it asserts a genre frame the operator refused three times out of three (stage-0 §116) into every outline of every book with a status seed. The costs-count-too principle survives; the debt frame is deleted. |

## The word-policing layer (boundary 3 as amended: delete with its cause, convert nothing)

| # | Where | The rule or list | The cause, and why deletion is safe |
|---|-------|------------------|-------------------------------------|
| W1 | `application/architect.py:706–712` (ladder rule) | "**The words `ladder` and `rung` are this schema's and never the book's** — and so is `standing` …" — an in-prompt lexical ban, plus the two worked examples of the ban firing | Cause: the premise is written inside the schema call, where ladder/rung/standing are the ambient machinery vocabulary (three of eight unfollowable terms on *Wake the Jar* were `standing`). After T3 the premise call never sees the schema, so there is nothing to ban. The positive clauses survive ("a reader meets it as whatever THIS world calls its ordered standings"; "Name the rung this world names, in this world's own language"); the ban sentences are deleted. Schema echo, if it ever recurs, arrives as unexplained vocabulary and the comprehension screen quotes it. |
| W2 | `application/architect.py:1099–1146` (`_ADMINISTRATION` frozenset, `_administration_in`, `_administration_rate`, `_administration_complaints`, gate check 7, the `include_subject` parameter) | 80-odd administrative words scanned over the premise; refusal on a hit | Cause: the module's own rule text steered worlds toward debt and paperwork — fixed in the rules themselves (§116; the "place people live in" rule, which survives as a positive principle). The scan is the scar: narrowed for measured false positives three times (`franchise`, `like in`, `court`), which is what a mask does under load. Deleted with its helpers and its gate check. The operator reads every premise that passes the comprehension screen and picks by hand; a debt-framed premise cannot reach a book unseen. |
| W3 | `application/architect.py:730–732` (domain rule) | "the domain's technical vocabulary never reaches the page — a reader learns none of its words and needs none" | Borderline: it is phrased as a ban but the positive form is in the same sentence ("What somebody can do is said in plain words a reader could repeat after one read"). The ban clause is deleted; the positive clause carries the rule. Unexplained trade jargon is exactly what the comprehension screen quotes (`mordant` was the operator's own example). |
| W4 | `application/architect.py:1059–1074` (`_BORROWED`) | Comparison-to-external-work syntax scan | **Kept.** A containment rail, not a craft rule: RS1/C3 forbid naming real works, and the guard's own docstring refuses to become a title deny-list for §97.3's reason. The one scan the amended boundary 3 names as surviving. |

## The premise-as-prose split (boundary 4; T3)

| # | Where | What moves |
|---|-------|-----------|
| P1 | `application/architect.py:860–905` (the premise essay inside the protagonist rule), `_WORLD.required` premise field (:505), `worlds_from` premise checks (:1217, :1266), `premise_names_protagonist` (:1296) | The premise leaves the world call entirely. The world schema drops `premise`; the ~45-line premise essay is deleted (its clarity content is the house rules' job, carried by the premise call by construction). A new `render_premise_request(candidate, …)` asks the flagship model for one paragraph of plain prose — who this person was, what happened to them, what they can do here that nobody else can, what they are heading toward, about 200 words — with the house rules in the system message and the world as context, no schema, no JSON. Deterministic post-checks on the paragraph: non-empty; names the protagonist (the existing membership check, now run on the returned text); `_BORROWED` clean. A failed check re-runs the same request once, fresh — never with reader or gate findings in the prompt (§97.1) — then marks the candidate failed. `bundle_for` (:2583) takes the paragraph as a parameter instead of reading `candidate.raw`; forge.json's shape downstream (`--pick`, `directives.json`, the comprehension battery's `--forge` reader) is unchanged. |

## The comprehension gate (boundary 5; T4)

| # | What | Design |
|---|------|--------|
| G1 | New `application/comprehension.py` + wiring in `cmd_forge` | Four genre readers restate the premise and quote every word they were never given (`undefined_words`) and every question they expect the book to answer (`open_questions`); pass = zero undefined words across all four; open questions are reported and never gated. The readers are **title-free** derivations of the research panel's four roles (climber / stranger / regular / mechanism — `reads_for` and `drops_on` only): the research personas' anchor lists name real published works, and a generation-side module may not carry named works (§97.3, the `_BORROWED` docstring's own boundary). Calls go through the provider registry like every other generation call — the same pinned production-tier provider that forges the world, which is the operator's requirement ("Opus 5 must produce and understand the premises") satisfied by construction — and are refused in test env by the same registry rails. A candidate whose premise fails the screen gets one fresh premise regeneration and one re-screen; still failing, it is marked and `--pick` refuses it by index, naming the screen as the reason. No `--no-screen` flag exists. Results land in forge.json beside each candidate; screen spend is recorded as its own decision row. The research battery (`research/quality-measurement/comprehension_battery.py`) is untouched: it is the measuring stick for T6's before/after, and its panel and model stay frozen for comparability. |

## Reviewed and clean (for the record)

- `application/planner.py` (writer prompt, :421): house rules + mechanics; no contradiction-class content. The status/standing blocks instruct movement of declared numbers, not vagueness.
- `application/outline.py` system (:399) and rule list: clean apart from C6.
- `application/narrative_planner.py` (:204): mechanical edit rules; carries `WORLD_RULES`, so C5's fix reaches it for free.
- `application/director.py` (:153): clean, and already refuses prose-craft direction in its own instruction text; Director output passes `legal_brief`.
- `application/summarize.py`, `repair.py`, `judge_panel.py`, `variation.py`, `plan_search.py`, `handlers.py`: no reader-facing prose instruction in the contradiction class (grep over the family's vocabulary; the only hits in `src/litharness` are the table rows above).
- `domain/house.py`: the constitution itself, now carrying the book-generation session's second pass (absorbed at 85adedf).

## What is deliberately not touched

The declarative world-shape rules (consequences in three domains, visible forms, costs on the
page, countable lowest-first ladders, capability inventories, mysteries with recorded answers,
relationship edges) stay as they are: they instruct what a world *declares*, not how prose
reads, each encodes a measured correction, and none contradicts CLARITY. Wholesale rewriting
them under this handoff would be an unmeasured regression risk in the name of tidiness; T6's
re-forge measures the changes that were made, and a later entry can take up the essays
separately if their length itself proves to be a defect.

Live databases (`serial.db`'s stored tone notes among them) are records of books already
written and are not edited; the purge closes the channel, it does not rewrite history.
