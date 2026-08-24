# Handoff: clarity is the constitution — contradictory rules out, comprehension wired in, readers given the reader's context

You are working in `C:\DEV\LitHarness`. The operator issued this directive on 2026-08-24 after
reading four forged premises and finding manufactured nonsense in them ("cancelling is packing
done with sound"), and after the diagnosis located the cause in the system rather than the
model: the premise is written as one field of a ~38KB structured world call, under rule-essays
that contradict each other, with banned-word lists that force coinage soup, and with no
read-back before a person sees it. The flagship model can write a coherent paragraph; the
pipeline never asks it to.

The operator's words, which this handoff exists to execute: *"We need the comprehension to be
wired. We need Opus 5 to produce and understand the premises. We shouldn't hardcode
contradictory rules, but use general systems instead. We shouldn't be codifying rules which
break the text. Rules should never contradict each other. Clarity is top priority and anything
in the project that doesn't abide by this or hinders this should be wiped completely. Simulated
readers should have access to all the required context — if they are reading chapter 2 they
should know what happened in chapter 1; if they are reading the premise hook, that's all they
need to know."*

## Boundaries first — these bind every task below

1. **Clarity is constitutional.** `domain/house.py`'s CLARITY rule outranks every other
   writing instruction in the system. Any rule, tone note, directive, or prompt fragment
   anywhere in the generation path that contradicts it — anything that tells a model to
   withhold explanation, stay mysterious about mechanics, compress past followability, or use
   a term before a reader has met it — is **deleted entirely**: no dead code, no
   commented-out relic, no deprecation flag, no "kept for reference". The stage-0 entry
   recording the removal is the only trace (the ledger stays append-only; the working system
   carries nothing). The first known member of this class is the forge's own emitted
   `tone_note` "Never explain how any of it works" — it directly contradicts CLARITY and is
   why the model resolves the tension with gnomic aphorisms.

2. **Rules are non-contradictory by construction, not by review.** One canonical home for
   writing instructions (`domain/house.py`); every prompt-rendering path draws from it and
   none restates it. Add a test that renders every model-facing prompt in the generation path
   and asserts none contains an instruction from the contradiction class (never-explain,
   stay-vague, "do not define"). A contradiction that can be written again will be.

3. **General systems over hardcoded rules — and a word list is not a general system.**
   (Amended 2026-08-24 on the operator's correction: *"forbidden-words list sounds like a hack
   solution to an underlying problem... we should fix the core of the issue instead of masking
   the consequences."* The first version of this boundary converted in-prompt word bans into
   post-generation word scans; that keeps the mask and moves it.) Replace rule-essays with two
   layers: a small set of short principles (house.py), and **measured outcome gates** (the
   comprehension screen) that check the result instead of micromanaging the text. Every
   word-policing rule and every craft word list is **deleted together with its cause**: the
   schema-vocabulary bans exist because the premise is written inside the schema call — after
   boundary 4 the premise call never sees the schema, and there is nothing to ban; the
   administration word scan exists because the old rule text itself steered worlds toward
   debt and paperwork (fixed in the rules, stage-0 §116) — the scan is the scar, it has been
   narrowed for false positives three times, and it goes. Unexplained vocabulary of every
   kind is caught by the comprehension screen, which is blind to which list a word would
   have been on. The only deterministic scans that survive are **containment rails, never
   craft**: the borrowed-work guard stays because RS1/C3 forbid naming real works, and that
   is a leak boundary rather than a style rule.

4. **Prose is written as prose.** Any paragraph a reader will read — the premise above all —
   gets its own dedicated call: world mechanics are forged as data first; then the premise is
   written as a paragraph, by the flagship production model, with only the house rules and
   the world as context. No JSON cell ever again carries reader-facing prose as a side effect
   of a schema call.

5. **Comprehension is wired, not optional.** The pipeline gate: forge world → write premise
   prose → run the comprehension screen (`comprehension_battery`'s confusion half, the four
   genre readers, **on the production-tier model** — the operator's requirement is that the
   model that produces the premises is also shown to understand them) → a premise passes only
   at **zero undefined words across all four readers**. `open_questions` are reported beside
   it and never gated — a pitch that leaves questions it plans to answer is working. A failed
   premise is **refused and re-forged**, not rewritten from the readers' quotes — feeding a
   reader's findings back into a prompt is the contamination §97.1 exists to stop, and
   refusal needs no such channel. No premise reaches the operator unscreened, ever.

6. **Readers get the reader's context.** Every simulated-reader elicitation carries exactly
   what a real reader would have at that point and nothing else: premise-only for premise
   instruments; chapters 1 through k−1 (as the book's own export would show them) for a
   chapter-k read; the passage-so-far for a mid-chapter probe. An instrument that
   deliberately reads cold may exist, but it must say so in its result and may claim only
   cold-reading results. Audit every instrument against this rule; the known offender class
   is the isolated mid-book excerpt presented with no history while the claim is about a
   reader mid-book.

7. **Standing axioms untouched.** No human judgment solicited (§95); nothing diagnosed from
   a book's record feeds a prompt (§97.1); no model ranks or selects among premises — the
   comprehension gate refuses on a deterministic count, and the operator's pick remains the
   only selection. RS1 holds.

8. **Coordination before edits.** The book-generation session
   (`claude/book-generation-progress-7dfb8d`, worktree `persona-reader-feedback-ca03cd`)
   holds an uncommitted second clarity pass in `domain/house.py` and active pilot work. Check
   that worktree's state first; land or absorb their pass before touching shared modules, and
   do not stomp their uncommitted work under any circumstances.

## Tasks, in order

- **T1 — the audit.** Enumerate every model-facing instruction in the generation path: the
  Architect's `_RULES`, every directive kind the forge emits (`tone_note` first), the
  outline, planner, and writer prompts, and `domain/house.py`. For each: does it contradict
  CLARITY, does it police words rather than outcomes, does it micromanage text a gate could
  check instead. Produce the table before changing anything; the table is the record of what
  was wiped and why.

- **T2 — the purge.** Delete every contradiction-class instruction per boundary 1. Collapse
  what remains of the rule-essays into short principles; delete every word-policing rule and
  every craft word list together with its cause per boundary 3 — nothing is converted into a
  post-generation word scan. The forge stops emitting tone directives that can contradict
  house rules — tone comes from the house or not at all.

- **T3 — the premise-as-prose split.** Two-call forge: the world-data call (schema, no
  reader-facing prose), then the premise call (flagship model, house rules, world as
  context, output is one paragraph of plain prose). The pick flow is unchanged — a person
  chooses; no model ranks.

- **T4 — wire the gate.** The forge command runs the comprehension screen on every new
  premise automatically, production-tier readers, zero-undefined to pass, results stored
  beside the forge output. A `--no-screen` escape hatch does not exist.

- **T5 — the context sweep.** Audit every reader-sim instrument's context construction
  against boundary 6; fix chapter-grain instruments to carry accumulated context through the
  book's own export path; label the deliberately-cold ones in their results.

- **T6 — the record.** Stage-0 entry in house form: what the audit found, what was wiped
  (each named), what replaced it, and the measured before/after — the four premises of
  2026-08-24 (0/4, 1/4, 2/4, 4/4 readers confused) are the baseline; re-forge under the new
  pipeline and run the same screen for the after. Tests per boundary 2. Every wiped rule's
  name grepped through the ledger and `tests/` so no citation dangles.

## Out of scope

Taste, preference, and excitement instruments (the backtest programme owns that question);
any change to the reader/judge loop's registered pools; any human-facing process. Nothing
here decides what a good story is — it decides that a reader can follow the words, which is
the floor under every other question this project asks.
