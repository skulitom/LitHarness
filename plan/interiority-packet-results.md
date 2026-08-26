# The packet's story-time cutoff, and the pilot's seeded interiority — what changed, measured

**Status: RESULTS, 2026-08-22.** Built and landed. Everything below was run against this
repository at commit `19cb6cd`; nothing here is a projection. Scope was the story-time cutoff
and seeded-interiority tasks and nothing else: no directive was authored, no
axis was admitted, and `research/quality-measurement/personas.py` and the panel were not
touched.

**This note makes no claim about prose.** The change alters what the generator is *told*.
Whether being told it produces felt state on the page is a reader question, and the only
reader in this project is an instrument this work was not permitted to touch. `interior_per_1k`
is not reported here and must not be read as evidence either way — `plan/interiority-model.md`
§1 and the handoff's boundary 1 both say why, and the seeded predicates share a stem with two
of the verbs that counter matches, which makes it exactly the number not to quote.

## 1. The leak, before

`domain/context.py::assemble` has taken a `story_time_cutoff` since it was written.
`application/planner.py::packet_for` never passed one, and its docstring argued why: nothing
defines a mapping from a manuscript scene to an `order_key`, and in the live loop "the question
does not arise — records are extracted from accepted prose, so the only records that exist
describe scenes already written."

Reproduced first, not taken on trust. Eight-scene book, the pilot's seed, two wants at `s1` and
`s5`, packet for scene 1:

```
- silas wants the senior seal on his card
- silas wants to know what the token is     <- dated s5, shown while drafting s1
```

## 2. The argument's second half was false for the loop as well as for seeding

The handoff named the seeded case. The loop reaches the same state with nothing seeded at all,
and this is a plain correctness bug rather than a consequence of the interiority work:

- §4.1 skips a blocked beat rather than waiting on it, so beat 3 can park or poison while beats
  4-8 draft. The manuscript is then a book with a hole, and `is_draftable` still reports scene 3
  as selectable — asserted, not assumed, in
  `test_a_record_the_extractor_wrote_for_a_later_scene_does_not_reach_an_earlier_one`.
- `cmd_replan` bumps the plan epoch and "plans the still-empty beats afresh against the current
  head", which is a fresh `packet_for` call for the hole. **A directive arriving mid-book bumps
  the epoch too**, so no operator intervention is needed for this to happen.
- Canon by then holds the records `extract_state` read out of scenes 4-8, at `s4`-`s8`. Beat 3's
  packet carried all of them.

`revive` is *not* the path, and the first version of that test said it was. A revived job
replays the payload its packet was already rendered into, so it cannot produce a fresh packet.
Recorded here because the difference is the whole of whether the case is reachable.

## 3. The fix, and where it abstains

`packet_for` now passes `extraction.stated_position(records, beat.story_order_key)` as the
cutoff. That is the same function extraction already uses for the same judgement, one layer
over — a `BeatTemplate` that declares itself `chronological` is a statement about the sheet the
planner laid out, `beats_for` turns it into `story_order_key`, and `stated_position` refuses to
hand it over for a book whose story positions somebody else chose.

| book | `has_story_vocabulary` | cutoff | packet |
|---|---|---|---|
| mystery fixture | True (`fixture.v1`) | `None`, every beat | byte-identical, every beat |
| litrpg fixture | True (`fixture.v1`) | `None`, every beat | byte-identical, every beat |
| Serial Pilot / Book Zero | False | the beat's own key | sliced |

**No gold context case moved.** One of the five golden cases is a `draft_scene` case
(`mystery:q1-draft-scene-6`, 4 mandatory targets and 1 forbidden); the other four are
`evaluate` and `repair`, which nothing in LitHarness serves. The mystery abstains, so the case
is graded against exactly the packet it was graded against before. This is the reported
negative result the handoff asked for either way, and it is not an accident of the one graded
case: `test_a_book_whose_story_positions_somebody_else_chose_gets_no_cutoff` compares
`packet_for` against a no-cutoff `assemble` for **every** beat of **both** fixtures.

Unplaced records are untouched by any cutoff — `records_before` keeps a record with no
`story_position`, because it asserts no narrative position and treating "unplaced" as "later
than everything" would empty the first packet of every book in the project. The pilot's
fifteen-record ability graph is exactly that shape and all fourteen non-configuration records
of it are in scene 1's packet.

## 4. What the packet carries now

Eight empty scenes, the pilot's seed, no prose, no provider —
`uv run python tools/interiority_packet_proof.py`, which prints this rather than asserting it:

```
  scene        s1    s2    s5    s7
  scene-1      yes     .      .      .
  scene-2      yes    yes     .      .
  scene-3      yes    yes     .      .
  scene-4      yes    yes     .      .
  scene-5      yes    yes    yes     .
  scene-6      yes    yes    yes     .
  scene-7      yes    yes    yes    yes
  scene-8      yes    yes    yes    yes
```

Scene 1's Established facts block, interiority lines only:

| | lines | which |
|---|---|---|
| before | 4 | all four wants and fears, including one dated three scenes past the end of chapter 1 |
| after | 1 | `silas wants the senior appraiser's seal on his card, …` |

18 facts before, 15 after; the three that went are exactly the three not yet due, and nothing
else in the packet changed. The four records cost **89 counted tokens** against the pilot's
16,000-token budget — for comparison, the whole ability graph measured 351.

## 5. The seed, and the decision the handoff asked to be made deliberately

Four records, at `s1`, `s2`, `s5` and `s7` — sparing on purpose, because each occupies every
packet from its own scene to the end of the book. The arc is the pilot's own: an ordinary want
before the System, the wound the class assignment leaves, the want that turns survival into
method once the loop is proved, and the cost of resetting people who do not reset with him.

**Repeated predicates: distinct story positions, verified against the detector.** The seed's
standing property was that no two canon records share a `(subject, predicate)` pair, because
until scoped cardinality lands (`plan/state-model-abilities.md` §2) a repeated predicate is
reported as a blocking contradiction. Two `silas wants` and two `silas fears` break that
property *as stated*. They do not break the one `detect_contradictions` enforces, which groups
on `(subject, predicate, order_key)`. Measured over the whole nineteen-record seed: **19
distinct groups, none holding more than one record, 0 findings, 0 blocking.** The third of the
handoff's three options, taken because it is the only one that does not either bend the records
to the tool (distinct predicates would give the same fact four names) or make this task
dependent on a cardinality model that is still a design.

The property is restated in `plan/serial-pilot-1.md` §8 in the form that is load-bearing rather
than quietly dropped, so a later reader does not find a violated invariant with no record of the
decision.

## 6. Three findings

**F1 — a dated seed record silently disables both the cutoff and extraction, and this was not
in the handoff's list.** `has_story_vocabulary` reads "any canon record with an order key that
this system's extractor did not write" as a story vocabulary somebody else chose. A seeded
interiority record is canon, has an order key, and was not written by the extractor — so
seeding one flips the check, `stated_position` abstains, and *both* consumers stop: the new
cutoff never applies, and §12 step 5 extraction reads back nothing from any scene of the book
for the rest of its life. Measured on the pilot's seed and a `Loop | Day` status line:

| seed | `has_story_vocabulary` | `stated_position(…, 's3')` | `extract_state` |
|---|---|---|---|
| as it stood, nothing dated | False | `'s3'` | 1 record |
| + one dated want, undeclared | **True** | `None` | **0 records** |
| + one dated want, declared | False | `'s3'` | 1 record |

That second row is the same silence `has_story_vocabulary`'s own docstring records finding by
running Book Zero — a book that looks, at every layer, like one whose scenes established
nothing — arriving through a different door. It is also circular: without a fix, the task's
Task 1 and Task 2 cannot both be satisfied, because the seeding that Task 2 requires turns off
the cutoff that Task 1 installs.

**The fix, and why it is narrow.** The exclusion becomes a set of two:
`extraction.PLANNED_POSITION_VERSION` ("this record's position is the planner's own beat key"),
declared on the four seeded records. The namespace is not new and this is not the first thing
written in it — `Promise.opened_at_key` already stores a key "in `beats_for`'s padding", and the
only reason it does not read as a foreign vocabulary is that promises live in their own table;
`PromiseRepository`'s docstring names `has_story_vocabulary`'s registry check as one of three
things that folding them into `StateRecord` would break. A seeded record dated at a beat is that
same key with nowhere to say so.

**The default direction is unchanged and stays the safe one.** An undeclared dated canon record
still counts as a foreign vocabulary, so forgetting the declaration loses coverage and can never
mint a false order — the direction `BeatTemplate.chronological` defaults in, for the same reason.
`test_an_undeclared_dated_record_turns_the_cutoff_off` pins the trap so that forgetting it fails
loudly instead of leaking quietly.

**F2 — the keys are width-dependent, and the seed is keyed for eight scenes.** `beats_for`
zero-pads `story_order_key` to the book's own scene-count width, because order keys are compared
as strings and `s10 < s2`. At eight scenes the width is 1, so the beats are `s1`-`s8` and the
seed matches. **Re-plan the same book at ten scenes or more and the beats become `s01`-`s10`,
at which point `s1` sorts after `s08`** and every seeded record silently lands in the wrong
place — a want dated at the opening would first appear at scene 10. Not fixed: fixing it needs a
key-rewrite path on re-plan that does not exist, and inventing one here would be building a
migration for a book that has not yet been drafted once. Recorded in each record's `note`, where
`litharness state` prints it, and in `plan/serial-pilot-1.md` §8.

**F3 — POV-restricting a private desire would erase it.** `pov_visibility` on the four records
is empty, which is the counter-intuitive direction: what a character privately wants looks like
the obvious candidate for a whitelist. Nothing in the live loop passes a `pov_character_id` —
`packet_for`'s parameter defaults to `None` and no caller sets it — and `visible_to` treats an
absent POV as *not* satisfying a restriction, deliberately, so that "forgot to pass the POV"
cannot mean "leak everything private". A restricted record would therefore be dropped from every
packet in the book and logged as `not visible to POV (none named)`. The pilot's tone note anchors
the whole book to Silas, so there is no second POV for an objective record to leak to.

## 7. What was deliberately not built

- **Reading a changed desire off the page.** Nothing extracts non-stat facts from prose, so the
  seeded interiority is static: it shapes the prose and the prose cannot grow it. That is a
  second extractor family, shared with the ability graph, and item 9 of
  `plan/state-model-abilities.md` §5. Half of it built here would be half of it built twice.
- **The reader who projects onto the protagonist.** `plan/interiority-model.md` §2's three
  options are an instrument decision in a validity programme, the panel is capped at four by
  protocol, and `system_prompt` is byte-stable as the replay cache's key. Out of scope by the
  handoff's boundary 3 and the operator's by construction.
- **Any bar, axis, or directive.** None declared, none admitted, none authored.

## 8. What was run

- `uv run pytest` — **1257 passed, 5 skipped**, up from 1242 before this work. The 15 new
  cases are `tests/test_context_cutoff.py` (14 functions, one of them parametrised over both
  fixtures); **5 of the 15 fail against the `packet_for` as it stood before this work**, which
  is what makes them a regression test rather than a description of current behaviour.
- `uv run ruff check src/ tests/ tools/` and `uv run mypy` — clean.
- `uv run python tools/interiority_packet_proof.py` — exit 0, output in §4.
- `litharness init` / `new --state plan/serial-pilot-seed.json` / `state` against a scratch
  store on the deterministic fake: 19 seed records land, 4 dated and printed as `given`, 15
  unplaced. No provider call, no cost.
