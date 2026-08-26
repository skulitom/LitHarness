# Blurb-shelf validity — can a reader with a concrete reference name the one that does not belong?

**Status: REGISTRATION, 2026-08-26.** Written before any call. The operator's acceptance test,
in their words: *"we need agent LLM readers to score our generated text near 0 and RR titles
much better."* Here that reads: after the gradient leg detects a LOW listing above its sham
floor, the ours leg must detect OUR listings well above the same construction's floor while
HIGH-target shams stay at floor — **ours picked out of a real shelf of this market's listings,
the market's own not.** `research/quality-measurement/blurb_shelf.py` carries the frozen bytes
and every registered definition; nothing there may be interpreted outside this document.

## 0. Why this can live where the judgment probes died

Six probes asked a model to *judge* its own or others' phrasing and every one came back blind
or inverted (handoff boundary 5). This instrument asks for a **detection with a right answer**:
one of these six listings was not written by this market's writers — which, and quote the exact
phrase that tells you. Nothing rates, ranks, orders or compares; the schema is closed over
`off_shelf` (0-6) and `phrase` and admits no other field, so no verdict vocabulary can arrive.
It is also not the settled pick-between-two (boundary 2): the question, the task shape and the
sham floor are all new, and the reader holds five concrete references before it answers — which
is the entire point of Task 3.

## 1. The instrument

A **shelf** is six listings numbered 1-6, each rendered as title, blank line, listing (the
`page` shape `blurb_gradient.py` uses). One request per shelf: system byte-frozen ("You have
read serial fiction on this market for years."), prompt the six numbered blocks separated by
`\n\n===\n\n` then the frozen ask, schema frozen as `{"off_shelf": integer 0-6, "phrase":
string}` with the phrase empty exactly when `off_shelf` is 0. Every shelf is built by a seeded
deterministic shuffle whose seed comes from a content digest — never unseeded `random`, never
time. K = 4 draws per shelf; the target's slot rotates deterministically across draws so at
least 4 of the 6 slots are exercised per target. Requests carry the measurement conventions
(`listing_arena.py` through `blurb_perception.py`): profile `reader.shelf.v0`,
`call_class="generation"`.

## 2. The legs

- **Sham shelves** — six HIGH listings, top of the admitted pool by followers. The
  false-alarm floor: how often a reader names anything at all when everything is real.
  **Per-sham floors, never pooled across shams** (the persona-battery rule).
- **Gradient leg (KG)** — five HIGH + one LOW (`blurb_gradient`'s pools), the whole shelf
  length-matched around the LOW target via its `matched_pairs` construction. Detection =
  share of draws naming the LOW slot, read only against that shelf's own sham floor.
- **Ours leg** — five HIGH + one of our listings (`--texts`, `listing_arena.load_texts`
  shape), the shelf length-matched around ours exactly as the gradient leg is around LOW.
  Detection of ours, plus the quoted phrases. *(Amended before any call: the first draft
  sampled ours-leg fillers at random, which would have left length as a possible tell on the
  one leg whose reading matters while the validating leg excluded it — the two legs must be
  the same construction or the validation does not transfer.)*
- **Surface-sham leg (KS guard)** — five full-length HIGH plus one HIGH truncated by whole
  sentences, in code and without a model, to the LOW leg's median word count. The truncated
  slot differs only by being shorter.

## 3. Kills and readings, fixed before any call

- **KP — position.** Detection-by-slot spread is reported for every leg. A sham whose false
  alarms track one slot (at least half of its non-zero answers naming that same slot) is a
  position kill: the readership is counting slots, not reading listings.
- **KS — surface.** If truncation alone is detected at gradient-leg rates, the instrument is
  reading length, and is dead. Direction only — no bar over either rate.
- **KD — draw reliability.** Cross-draw agreement of `off_shelf` within a shelf, gate-0
  shape: below half the answered shelves agreeing, no direction is readable from any leg.

No bar over any detection rate anywhere; a null on every kill is a result.

## 4. What a pass means, and the two withdrawal readings

The gradient leg must detect LOW above its sham floor first; §141's H = 0.935 says this
readership can separate the pool's top from its bottom once already. Then:

1. Ours detected well above the same construction's floor while HIGH-target shams stay at
   floor — the operator's acceptance test met on the measurement side.
2. Ours blends in while LOW is detected — the instrument is blind to us **and says so**. A
   result that flatters our own text is a defect in the instrument until proven otherwise
   (boundary 3); this reading is reported, not celebrated.
3. Ours detected while LOW is not — it reads authorship rather than quality, and the
   instrument is withdrawn.

## 5. Anti-scope

Nothing here feeds a prompt (§97.1): the quoted phrase is a **located diagnostic on the
operator's side**, never a revision input. RS1: market text enters measurement only. Results
carry no third-party prose — shelf composition as row digests and slot order; a quoted phrase
stored verbatim only when the named slot holds one of OUR listings, otherwise token offsets
into that listing plus a `located` flag, locvisable by digest. Free legs (`--selftest`,
`--dry-run`) prove the arithmetic before anything spends; the paid run refuses without both
`--yes` and the undocumented `--i-am-the-gated-run`.
