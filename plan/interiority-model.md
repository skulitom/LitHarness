# Interiority, both sides: the character's felt state and the reader who inhabits it

**Status: DESIGN, 2026-08-21.** Not built. Claims marked ✅ were run against this repository;
❌ marks a measured blocker with the check that produced it.

## 0. What was asked

> "By interiority I mean simulating how the character inside the book feels and what their
> desires are, especially the main character. We also need to simulate the interiority of the
> Reader who projects themselves as the main character."

Two simulations, and they are not the same problem:

- **Side A — the character.** What the protagonist wants, fears, believes and has just worked
  out, held as *state the system tracks* rather than as prose that happens to contain feeling
  verbs.
- **Side B — the reader.** A simulated reader who projects onto the protagonist: who wants what
  he wants, feels the cost when he pays it, and is impatient for the next step.

The operator's framing is that this is "one of the most important aspects", and the evidence
agrees from two independent directions. `interiority` is one of only three axes in the registry,
admitted from the 2026-08-18 human read that named "no interiority" as a defect; and measured
against 800 RoyalRoad LitRPG chapters our prose sits at the **27th–29th percentile** (2.67 and
2.80 per 1k against a genre median of 4.23).

**What this document is not.** It is not a prose directive. A constraint telling the generator
to write that a character "felt" or "wanted" or "realised" would move `interior_per_1k` without
producing any of this, which is the shallow-because-easy metric §1a.1 warns against — the
counter must never become the target.

## 1. Side A: the character's felt state as canon

### What already works

✅ **The vocabulary exists.** `predicate` is a free-form string, `StateRecordKind.KNOWLEDGE` is
in the contract and used by nothing, and records carry a `story_position`. So `silas wants …`,
`silas fears …`, `silas believes …` are ordinary state records needing no migration and no new
contract field.

✅ **They reach the generator.** `state.describe()` renders them into the **Established facts**
block of every draft packet, at the same trivial cost the ability graph measured (13 records,
351 tokens of a 16,000 budget).

✅ **The research already names the primitive.** `research/progression-generalization.md` reduces
everything to Change, Constraint, Criterion and **View** — and View is precisely belief and
disclosure, with `claim.content`, `believes` and `disclosed_to` as relations. Desire is View's
sibling: what a subject holds to be *wanted* rather than what it holds to be *true*.

### The blocker, measured

❌ **A desire dated later in the book is shown to earlier scenes.** Seeding two wants — one at
`s1`, one at `s5` — and assembling the packet for scene 1 returns **both**:

```
- silas wants the senior seal on his card
- silas wants to know what the token is     <- dated s5, shown while drafting s1
```

`context.assemble` takes a `story_time_cutoff` and `planner.packet_for` never passes one. That
is deliberate and documented: nothing defines a mapping from a manuscript scene to an
`order_key`, and in the live loop "the question does not arise — records are extracted from
accepted prose, so the only records that exist describe scenes already written."

**That reasoning is sound for extracted records and fails for interiority.** A want that changes
across a book is future-dated by construction. Model Silas's arc of desire and scene 1 is told
what he will want in chapter 2 — the story's engine handed to the reader before it starts.

There is a precedent for the fix: `extraction.stated_position` already accepts the beat's
`story_order_key` as a position when the book has no vocabulary of its own, on the stated ground
that it is the *planner's* claim rather than an inference about the book. The beat already
carries that key into the job payload (`selected_by.story_order_key`). Passing it as the
cutoff is the same move, one layer over, and it is the one change Side A cannot proceed without.

### The second gap

❌ **Nothing reads a changed desire off the page.** `extract_state` knows one line form, the
`[STATUS]` block. So a seeded interiority is static: it shapes the prose and the prose cannot
grow it. That is change-surface item 9 in `plan/state-model-abilities.md` and the same wall the
ability graph hit.

### Why this is the progression engine, not decoration

An unmet want is what makes progression crave-able. The promise ledger already models debt
(`PROMISE_KINDS` carries `progression`), and a desire is a debt the *character* holds rather
than one the *book* owes. The two want joining: a rung advance that pays a promise the reader
watched Silas want is the shape the genre runs on. Tracking desire without tracking whether it
is met would reproduce this project's oldest defect — 40 promises opened, none paid — in a new
column.

## 2. Side B: the reader who projects

### What exists

Four personas in `research/quality-measurement/personas.py`: *the systems reader* (reads for
"progression that means something — what a number buys, what it costs"), *the consequence
reader*, *the prose reader*, *the first-time reader*. One reads for progression. **None reads
as someone inhabiting the protagonist.**

### Why a fifth persona is not free

❌ **The panel is capped at four by protocol**, and the cap is load-bearing: *"a panel is not a
cast, and personas the data cannot separate are merged rather than kept for flavour."* The four
are "chosen to be separable by construction — each drops on something the other three tolerate",
so that a measured inter-persona rank correlation ≥ 0.9 is a finding about the instrument rather
than a restatement of four near-identical prompts.

❌ **`system_prompt` is byte-stable on purpose.** It is the cache breakpoint for every
elicitation and the key for the digest-keyed replay cache; editing it invalidates exactly the
records whose prompt it changed. So editing the existing four is not a free improvement — it
silently invalidates the program's own history.

Three options, none of them "just add one":

1. **Replace a panel member.** Keeps the cap and the separability design, costs whichever reader
   is displaced, and requires re-running whatever the old panel produced.
2. **Run the identifying reader as a separate instrument**, outside the four-persona panel, with
   its own registration. Keeps the panel intact and makes the new reader an arm rather than a
   silent instrument change. Most consistent with how this project handles arms.
3. **Do nothing to the panel** and accept that no current reader reports identification.

### And the questions are different

The panel's elicitation asks the audit queue's question — `--keep-reading` / `--would-stop`. A
reader who projects onto the protagonist is not primarily answering that. The questions that
distinguish it are about alignment of want: *did I want what he wanted; did I feel the cost when
he paid it; am I impatient for the next step, or merely willing to continue.* That is a
different elicitation, not the same one with a new system prompt.

**The validity frame binds regardless.** `plan/persona-reader-validity.md` is explicit that a
persona reader is "a predictor, not a witness", that the only measured quantity is
report–population agreement, and that *"is this persona realistic?" is not a question this
program can ask; "is this persona calibrated?" is the only form the question takes.* So an
identifying reader may be built and may be argued for on the ground that it predicts a
population we care about — but not on the ground that it feels like the right reader.

## 3. What could be done, in order

1. **Pass the beat's story key as the packet's cutoff.** One change, unblocks everything in
   Side A, and is worth doing on its own merits: it is a latent correctness bug for any seeded
   or scheduled record, not only for interiority.
2. **Seed the protagonist's wants and fears as canon**, dated, and let them reach the packet.
   Zero code beyond (1). Static until (3).
3. **A second extractor family** so the page can change what the character wants. Shared with
   the ability graph; neither feature is worth building twice.
4. **Decide the reader side** — replace, separate instrument, or nothing — and register it
   before building, because it is an instrument change in a program whose whole discipline is
   that instrument changes are registered.

Nothing above should be started by reading this document. Items 1 and 2 are cheap and
reversible; items 3 and 4 are decisions with a cost, and 4 is the operator's by construction.
