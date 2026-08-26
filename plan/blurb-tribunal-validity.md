# Blurb-tribunal validity — one agent flags, another defends, and code decides

**Status: REGISTRATION, 2026-08-26.** Written before any call. This is the adversarial span
tribunal of `plan/reader-architecture-program.md`: a mechanism family in which disagreement is
resolved by checkable evidence instead of a third opinion.
`research/quality-measurement/blurb_tribunal.py` carries the frozen bytes and every registered
definition; nothing there may be interpreted outside this document.

## 0. Why the third seat is code

A model asked to resolve two models' dispute is a judge — and the judge channel is the one
that died six times in the handoff session and twenty times in the ledger (§89, §97.4,
boundary 5). So the tribunal's third seat is not a model at all: when the advocate claims a
parallel exists in listing 3, the question "does this string occur verbatim inside that
listing" is answered by `blurb_shelf.locate_tokens`, a token-normalised membership check with
a right answer. The advocate's burden is therefore falsifiable in exactly one bit, the
flagger's quotation is checkable against the target listing the same way, and no stage of the
mechanism ever asks any model whether anything is good, bad, idiomatic or improved. What the
models do — flag spans, produce parallels — is behaviour; what the code does — locate strings,
count, divide — is measurement. A panel that reconciled two agents by *agreement* would be the
verdict channel with extra steps; this one reconciles them by *evidence*, which is the entire
difference.

## 1. The frozen asks and schemas

System (byte-frozen, reused from `blurb_shelf` by import — deliberately the same one-sentence
persona for both seats):

> You have read serial fiction on this market for years.

Stage 1 ask (byte-frozen), after five reference listings numbered 1-5 (`blurb_shelf.page`
shapes separated by `\n\n===\n\n`) and a block headed `THE LISTING UNDER READING:`:

> Quote every phrase in the listing under reading that would not appear in a listing written
> by this market's writers. Quote exactly. An empty list is a normal answer.

Stage 1 schema (byte-frozen): `{"flags": [string, ...]}`, `maxItems` 8, closed object.

Stage 2 ask (byte-frozen), after the SAME five references and the phrase alone — never the
target listing, never a hint that the phrase was flagged or why:

> Here is a phrase: {phrase}. If a construction that works the same way appears in any of
> these five listings, quote it exactly and name its listing number. If none does, answer 0.

Stage 2 schema (byte-frozen): `{"parallel": string, "from_listing": integer 0-5}`, closed;
`from_listing` 0 pairs only with an empty `parallel`, any other number demands a non-empty
quote. Both parsers accept one shape and give no partial credit, in the style of
`blurb_shelf.parse_answer`.

Requests carry profile `reader.tribunal.v0`, call class `generation`,
`max_output_tokens=400`. K = 4 draws per target (§124's lesson, the siblings' K).

## 2. The stages and the measurables, all scored by code

- **Stage 1 — flagger, per target.** K draws. A returned flag that does not LOCATE in the
  target listing is dropped and counted in `unlocated_flags` — a fabricated quotation is not
  a flag. Flags are deduplicated across draws by normalised text; each unique flag carries
  its draw support. Unique flags are truncated to 8 per target (strongest support first,
  ties by text) so **stage 2 is bounded by maxItems × targets** and the dry-run arithmetic is
  exact rather than estimated.
- **Stage 2 — advocate, once per unique located flag.** The same references; the phrase
  alone. A malformed reply is no evidence, like a failed call.
- **Stage 3 — the third seat.** A defense is VALID iff its `parallel` locates verbatim
  (`locate_tokens`) inside the NAMED reference listing. A flag SURVIVES iff it has no valid
  defense. Per target: `surviving_flags`, `flags_per_100_words` and
  `surviving_per_100_words` over the listing's own word count, plus the rows.

## 3. Legs and shelf construction

References reuse blurb_shelf's pool conventions: for every target, the five HIGH listings
nearest the target's word count (`nearest_high`), the target excluded by identity; seeds via
`seed_of`; pairing via `matched_pairs`.

- **Sham** — the target is itself a HIGH listing. Its surviving-flag rate is that target's
  floor. **Per-target floors, never pooled** (the persona-battery rule); there is no function
  anywhere in the module that accepts two targets' rows. Default 6 targets.
- **Gradient (KG)** — targets are the LOW side of `matched_pairs(high, low, pairs)`, default
  8. Direction: LOW targets carry more surviving flags than their length-matched HIGH
  partners. Every pair is measured on both sides — the partner is a sham target already when
  word counts allow, otherwise it is appended as an additional sham-leg target. Statistic:
  share of pairs with `surviving_per_100_words(LOW) > (HIGH)`, seeded pair bootstrap exactly
  as `blurb_rewrite.gradient_stat` — imported; if the import were unavailable, its seeded
  construction is mirrored byte-for-byte and the results record which implementation ran.
- **Ours** — targets from `--texts` (`listing_arena.load_texts` shape).

## 4. Kills and controls, readings fixed before any call

Directions plus distributions, **no bars** (§61):

- **KD — flag stability**, per leg: mean pairwise Jaccard of the draws' flagged-token sets
  (the token-set idea of `blurb_rewrite.draw_agreement`), each leg against the registered
  floor 0.5. Below it the flagger disagrees with itself more than it agrees and no direction
  is readable from that leg.
- **KA — advocacy integrity**, per leg: `fabricated_defenses / defenses`, direction only, no
  bar. If the advocate fabricates constantly, valid defenses vanish and the mechanism
  collapses toward everything-surviving; that rate is the number that says so.
- **KG — the gradient**, above. §141's precondition adopted whole: **until KG separates,
  nothing this instrument says about ours is believed.**
- **Transport failures** are excluded from every rate and counted, never scored:
  `transport_failures: {flag_calls, defend_calls}`. A failed defend call offers no evidence,
  so its flag survives by default and sits outside KA's denominator. The run output says to
  read these before any verdict.

## 5. The acceptance test, in the operator's words

*"We need agent LLM readers to score our generated text near 0 and RR titles much better."*
On this instrument the orientation is: our listings must carry markedly more SURVIVING flags
per hundred words than the market's listings, with the shams at their floors and KG already
separated. The inverted result — ours blending into the market while LOW stands out —
withdraws the instrument, never flatters the text (boundary 3). Nothing here certifies us
against the operator's judgment, which is the ground truth.

## 6. Anti-scope

- **§97.1:** a surviving flag is a **located diagnostic on the operator's side**, never a
  revision input. No drafting, revision or planning path reads anything this module writes.
- **RS1:** market text enters on the measurement side only. **§95:** LLM-only mechanism —
  the seats are models, the resolver is arithmetic, and arithmetic is not being proposed as a
  reader.
- **Prose firewall:** results carry no third-party prose, enforced in code through
  `blurb_shelf.phrase_record` — the single choke point every flag and every parallel passes.
  Verbatim text only for spans of OUR listings; token offsets plus `located` for any market
  listing, references included. Full raw text goes only to the gitignored `derived/`
  sidecar.
- **Cost gate:** free legs first (`--selftest`, `--dry-run`); `--run --yes` refuses without
  the undocumented `--i-am-the-gated-run`; worst-case calls above the registered guard of
  500 refuse without `--yes`.
