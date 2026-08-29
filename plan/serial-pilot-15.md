# Serial Pilot 15 — *What the Kettle Remembers*: the seed drew a game system without being asked twice, and then a sort order handed scene 1 the last page of it

**Status: LISTING, WORLD AND CHAPTER 1 DRAWN, 2026-08-29.** Scenes 3–6 are not drafted. This is
iteration 1 of the operator's iterate-until-right loop, and its gate is the coordinator's read
rather than the operator's — so this document carries **no reader-read skeleton**, by that
directive.

This is the first book produced under the complete first-principles redesign (stage-0 §§160–163,
merged at `1931dfe`). Five things had never run live before; §§2–6 are what each of them did, and
§7 is the one that misbehaved. The writer is **penhale**, cast by the recorded slate-order
rotation — larkin drew pilots 13 and 14, cozy fantasy is next in the order, and no model expressed
a preference among recruits (§84).

## 0. The three readings this may not be given

**It is not a treatment comparison, and pilot 14 is the specific one to refuse.** Different
writer, different seed, different world, different genre shelf, different day. Where a counter
here sits beside pilot 14's it is a description of two books (§0 of
[`serial-pilot-7.md`](serial-pilot-7.md), and the standing boundary).

**It is not a quality claim.** §61's bar is a blinded, position-swapped win rate against matched
published prose. This is one chapter, unblinded, with no comparator.

**No model ranked, selected or judged anything in this run.** Not the listing, not the world, not
the prose, not the system. The one judgment call — whether to re-seed on the finding in §7 — was
taken by a person and is recorded in §7.

## 1. What produced it

```bash
uv run litharness --database runs/pilots/databases/serial15.db init
uv run litharness --database runs/pilots/databases/serial15.db \
    --roster-database C:/DEV/LitHarness/runs/roster/roster.db --library book-library \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
    listing --writer penhale --scenes 6 --out runs/pilots/pilot15
uv run litharness --database runs/pilots/databases/serial15.db --roster-database ... \
    --library book-library --writer penhale \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 architect seed
uv run litharness --database runs/pilots/databases/serial15.db world check    # clean
uv run litharness --database runs/pilots/databases/serial15.db world accept   # no --force
uv run litharness --database runs/pilots/databases/serial15.db --roster-database ... \
    --library book-library --writer penhale --chapter-scenes 2 \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 tick   # x N, capped
uv run litharness --database runs/pilots/databases/serial15.db --library book-library \
    --chapter-scenes 2 library
```

**`--scenes 6`, deliberately**, because §157's fix makes six work and this run is its first live
test. **Brief: empty**, the standing control since §136. **`--reader-checkpoints` off**, the
baseline. **Both ceilings top-level on every paid invocation**, `--library book-library` and
`--chapter-scenes 2` wherever they apply — pilot 12 §5's silent failures, pre-empted; none
recurred. **Covers were skipped**, because the loop's gate this iteration is prose.

**No hand seeding of any kind.** Pilot 14 needed a person to type a `status_snapshot` before its
book would draft. Nothing in this run declared a world fact by hand, and §2 is why.

## 2. Observation 1 — the seed minted a system, and `world check` came back clean

**It drew one.** This is the first Architect run under §163's issuer text, and §163 closes by
saying that whether an issuer in the ask changes what a world declares is *"unmeasured,
unregistered and not claimed"*. On this one draw it declared a system without being asked twice,
and the predicates it reached for are the ones §160 and §163 had just built and documented.

`world check` on the seed, before acceptance:

    "complaints": [], "ok": true, "will_not_resolve": [], "unmanifested": []

**239 records**, of which `world accept` promoted **234**, leaving 5 proposed as slots a later
declaration had replaced. No `--force`. The predicate census, which is the artifact:

| predicate | n | what it is |
| --- | --: | --- |
| `governed_by` | 7 | §163.2's issuer edge — the ladder and all six capabilities |
| `can_do` | 16 | §114's inventory, now carrying holder depth in §160's reused value slot |
| `stands_at` | 7 | positions on the ladder |
| `costs` | 6 | |
| `precedes` | 5 | the six-rung ladder |
| `requires` | 5 | prerequisites, carrying thresholds in §160's other reused slot |
| `status_snapshot` | 5 | object-valued, §158's shape |
| `status_sheet` | 1 | the book's own columns |
| `graph_line` | 1 | |

`seamwork` holds `entity_role` `"system"` — the occupant role, filled. The ladder is
`rung_tacker → rung_seamer → rung_keeper → rung_joiner → rung_wright → rung_townwright`, six
rungs, subject=lower to object=higher, which is the direction §160 took off the reader's code
rather than off the docstring beside it. The prerequisite graph has a fork the value slots carry:

    cap_seam  requires cap_tack  3
    cap_keep  requires cap_seam  4
    cap_carry requires cap_seam  2
    cap_join  requires cap_keep  3
    cap_join  requires cap_carry 3

**Both of §160's reused value slots are in live use by a model that was never told they existed
as magnitudes** — `magnitude_scale` and `system_digest` are deliberately undocumented (§163.2), so
the numbers above arrived through `requires` and `can_do` alone.

**The institutions came back, and they do not own the ladder.** `the_roll` is declared an
`institution` and `the_company` an `agency`, which is §160.5's refusal to ban them paying off:
the world says the Company *"will not paper anybody below Wright, and it counts the rung off its
own register in Wenn, not off the work standing in front of it"*, and that the Roll *"does not
read rungs and never has; it reads who has eaten at your table"*. Two institutions read the
ladder, neither issues it, and the protagonist's rung is Seamwork's. That is the shape
[`first-principles-litrpg-core.md`](first-principles-litrpg-core.md) §2 asked for, on one draw.

### 2.1 And `system_gap` stayed open anyway, permanently, by design

After `world accept` the floor's own gap closed and one gap remained:

    this book declares no game system: no subject holds the system role with a magnitude scale
    and a governed ordinal ladder. Its sheet is whatever was seeded by hand, its numbers have no
    home, and a progression beat has no vocabulary to land in.

**Every clause of that sentence is false about this world except the one that decides it.**
`seamwork` holds the system role; the ladder is governed; the sheet was not seeded by hand. What
is missing is `magnitude_scale`, and §163.2 deliberately leaves that predicate out of
`world vocabulary` so that only `gamesystem.records_for` can mint it. **So a seed-drawn system
cannot close `system_gap`, and the report a person reads names an absence the seed had no
documented way to fill.** This is recorded as a consequence rather than a defect — §163.2 argues
the omission is correct, and it may well be — but the gap's own text is the §155.2 failure it was
written against, at a new address: an operator sent hunting an absence that is not the one
standing in the way. Nothing here proposes the fix; the two candidate shapes are letting the
Architect declare a scale, and having a drawn `SystemDef` replace hand declaration entirely.

## 3. Observation 2 — the floor passed, on the book's own sheet, and not by the path the question named

**It passed.** `litharness status` reports no blocked book, and the drafting loop was never
refused. The `status_sheet` the floor read is the seed's own:

    {"fields": [{"label": "Seamwork", "name": "rung", "paired": false},
                {"label": "Reach", "name": "reach", "paired": false},
                {"label": "Carried", "name": "carried", "paired": true},
                {"label": "Seams standing in Ashfen", "name": "standing", "paired": false}]}

**It did not pass via `records_for` writing `status_sheet` itself**, because §2.1's missing
magnitude scale means no `SystemDef` was ever constructed. The sheet is a hand-shaped declaration
in the seed's own output, promoted by `world accept` — §158's declare→accept path, walked by the
Architect instead of by a person. That is the change from pilot 14, whose §2.2 needed an operator
to type the snapshot; it is not the change §160 built toward.

**`Carried` is `paired`, and it renders.** The one label at the width limit —
`Seams standing in Ashfen`, 24 characters — passed §160.4's rewritten prohibition rather than
tripping it.

## 4. Observation 3 — the beat named the system's own quantity, at six scenes, with no plan item

**The plan holds exactly one item, of kind `premise`.** No `SCENE_PLAN` exists, because
`needs_outline` is false at six distinct dramatic functions — §157's diagnosis, met again and
this time harmless. The beat is derived at render time in the selector instead, and the last line
of scene 1's assembled prompt is:

> Now write What the Kettle Remembers: Scene 1 — open-ended series; release volume 1 (packaging
> only); arc 1; chapter 1 (1 of this arc); scene 1 of 2 (arc scene 1 of 6). Point of view: mira.
> Dramatic function: setup. **This scene: Seamwork moves here, and the person it belongs to is
> there when it does.**

**It names `Seamwork`.** §161.4's `NAMED_BEAT` fired, on a live draw, with the quantity coming off
`movable_names`. Scene 2's prompt ends at *"Dramatic function: inciting."* and carries no beat
sentence at all — the unscheduled control, byte-bare, which is `beat_ordinals(6)` = {1, 3, 5}
doing what §155.3 registered.

**So §157's fix works and this is the first live evidence of it**: at the length that was
structurally dead when pilot 14 met it, the schedule fires from the selector, and what fires names
a quantity instead of a category.

**Which arm answered is worth recording.** `Seamwork` is the label of the sheet's `rung` column,
so this is `movable_names`' **legacy arm** — the columns the book's own status line prints. The
system arm needs `gamesystem.legal_moves` over a real `SystemDef`, which §2.1 explains does not
exist here. The named beat this book got is therefore the superset answer, not the one that knows
an unmet prerequisite is not on offer. **Scene 3's and 5's beats were not observed**, because
chapter 1 is two scenes; nothing here says what they would name.

## 5. Observation 4 — the furniture rendered, twice, and the placement rule is visible on the page

**Every `[STATUS]`-form line in chapter 1, verbatim, both of them:**

    [STATUS] mira — Seamwork 5 | Reach 9 | Carried 4/9 | Seams standing in Ashfen 42

    [STATUS] mira — Seamwork 5 | Reach 9 | Carried 4/9 | Seams standing in Ashfen 42

**One per scene, which is §161.3's cardinality**, and the two placements are the contract's two
arms visible side by side. Scene 1's sits mid-scene, immediately after the sentence in which a
number moves — Mira takes a carried minute off the ledger box, *"and the barn and the lamp and the
scoop came off the box and into her and stayed"* — and the line follows it. Scene 2's sits at the
scene's end, where nothing moved. That is *"Print that line exactly once: where one of its numbers
changes, or at the scene's end if none of them does"*, obeyed in both branches by one book.

**The columns are the book's own** — no `Level | HP | MP | Gold`, no `?`. §161.1's defect could
not arise here.

**And the extractor closed the loop.** Two new `accepted_canon` snapshots were minted from the
prose, at order keys `s1` and `s2`, both
`{"carried": 4, "carried_max": 9, "reach": 9, "rung": 5, "standing": 42}` — the printed line read
back into canon. Scene 2 was shown the folded result of scene 1's, so the scene-to-scene chain
works. §7 is about the other end of it.

**This is an integrity observation and not a verdict.** No model judged the prose and neither does
this record (§97.1).

## 6. Observation 5 — the listing opens on the person and her exception, and carries no institutional vocabulary

The listing, verbatim:

    What the Kettle Remembers

    Mira Kell mends things, and everything she mends remembers. The patched kettle will tell
    whoever asks who knocked it off the shelf. The rejoined chair names the argument that cost
    it a leg. So Ashfen carries its broken belongings to her counter carefully, and she learns
    more about the town than she ever meant to.

    What she wants is the mill wheel. It has stood still since before she arrived, the
    millwright calls it past saving, and the shop stays hers only if the town decides she is a
    mender worth keeping.

    She starts with kettles, and with the people who come in for a repair and stay for supper.

**Exception-first, inside the first sentence.** The person is named and her exception arrives as
the second clause of sentence one; the account of the world is third. §154's narrowed clause is
what the assembled listing prompt carries.

**Zero hits for licence, ledger, guild, warden, excise, tax or register in the listing**, on a
case-insensitive scan. Pilot 14's listing opened on a licensed trade with stamps, taxes and a
ledger; this one has a counter, a kettle, a chair and a mill wheel. **This is a description of one
draw and not a demonstration that anything was fixed** — §156.1 measured that the institutional
lean is not in our text, so a draw without it is a draw, not a treatment effect, and the writer
and the shelf both moved.

**The chapter is not free of institutions and was never meant to be.** `the Roll` appears three
times, `the Company` once, `register` once, and Piet's `ledger box` is the object scene 1 turns
on. What changed is ownership, not vocabulary: §2 records the ladder belonging to the system while
those two read it.

## 7. The finding: every numeric order key sorts before every scene, so scene 1 was handed the last page of the schedule

**Measured, from the assembled prompt.** The seed declared Mira's whole arc as `status_snapshot`s
at order keys `0110`, `0250` and `0350`, and left the opening state un-keyed — which is exactly
what §163's documented line instructs, *"leave it off for the state the book opens in, which is
then the one found at every position."* Scene 1 was then shown:

    [STATUS] mira — Seamwork 5 | Reach 9 | Carried 3/9 | Seams standing in Ashfen 41

That is the **`0350`** snapshot: `{"carried": 3, "carried_max": 9, "reach": 9, "rung": 5,
"standing": 41}`. The un-keyed opening state the same seed declared —
`{"carried": 4, "carried_max": 5, "reach": 3, "rung": 2, "standing": 19}` — was in the same packet,
rendered as *"At before the recorded story: mira stands at rung_seamer"*, four rungs below the
cast block's *"stands at: rung_wright on seamwork_rank (rung 5)"*.

**The mechanism, in three steps, established from the code and confirmed against the artifact.**

1. `planner.py:1081` calls `system_voice_example(records, at=beat.story_order_key)`, and a
   scene's story order key is `s1`, `s2`, … .
2. `snapshot_at`'s rule is the snapshot *at* the position, failing that the latest one before it;
   `state_as_it_stands` then folds every canon snapshot `<= ceiling`, later values winning.
3. **Order keys are compared as strings, and digits sort before letters.** `'0350' <= 's1'` is
   `True`. So `0110`, `0250` and `0350` are all "before" scene 1, the ceiling is `0350`, and the
   fold returns the end of the book.

**The magnitude of the number is irrelevant**, which is what makes this a class rather than an
instance: *any* numeric order key an Architect writes lands before *every* scene. §163's promise
that the un-keyed snapshot is *"the one found at every position"* does not survive a single keyed
snapshot existing beside it, and no documented line tells an Architect what namespace a key must
live in. This is §152's shape at a further address — a documented slot whose reader reads it
differently — and the sub-case that does not fail loudly, because both records are valid, canon,
and contradict each other only in the fold.

**The scheduling is not the defect, and the distinction is the whole of what to fix.** An
Architect that declares where a character's numbers will stand at three later positions is doing
the good thing: it is §110's promise-scheduling instinct applied to stats, the seed committing in
advance to an arc instead of leaving each scene to invent one. That behaviour should survive any
fix. What failed is that the two vocabularies for "where in the book" were never introduced to
each other — scene positions in one namespace, declared positions in another, compared as strings.
**The defect is nine characters wide: `'0350' <= 's1'` is `True`.**

**What it cost this book, stated plainly because a reader will notice it.** Mira opens at rung 5
of 6 with reach 9, and the seed's own canon says reach nine is what the mill wheel takes. The mill
wheel is the thing the listing says she wants. So scene 2 has her wade in, put both hands on it,
and report *"I can reach all of it now"* — the book's stated target, available in chapter 1,
because a sort order moved her there before the first sentence.

**What was done.** Nothing, in code: no code was changed mid-run, on the standing instruction that
a fix is chosen by reading intent rather than by patching a live pilot. **The book was not
re-seeded either**, and that was a person's call on evidence: the seed is clean, the system is the
best artifact this pipeline has produced on observation 1, and re-drawing it to dodge a sort-order
defect would have spent $4.50 to hide the finding this iteration exists to surface. `serial15.db`
keeps it. The fix belongs to whoever takes it, and the two visible candidates are keying scene
positions into a namespace that sorts after declaration keys, and refusing or normalising a
declared order key that is not in the scene namespace.

## 8. The listing, the title, and what the gate did

**110 words.** The decision row records the gate exactly:

    110 words; 4.55 coordinators/100w vs the 5.89 ceiling; 1 of 4 would start it;
    title 'What the Kettle Remembers' free

**No refusal, no redraw: the first draw was kept.** So as with pilots 12, 13 and 14, **this run
says nothing about whether the gate works** — the interesting branch, a refusal followed by a
redraw that lands under the bar, is still untested against a live draw, now for the fourth pilot
running.

`draft` and `listing` are byte-identical, so no revision happened. `appetite_status` is
`experimental_observation_only`. `titles_abandoned` is `[]` and the title is `free`, so **the
retry path is still untested against a real collision**, as in pilots 7 and 11–14. `paired` is
`null` and `title_shown_to_readers` is `true`: no named competitor, and the title-blind arm is
still owed.

**The browsing pool said 1 of 4 `start_reading`, 1 `save_for_later`, 2 `pass_on_it`**, reported
with §134's ceiling written across it rather than believed. What the four *said* is the part
specific enough to be worth quoting, and three of them named the same absence — a ladder:

> *"the pitch is all cozy town and no ladder — I can't see what she gets better at or what the
> next rung looks like"*

**This is an artifact and not a result.** The book underneath that listing has a six-rung ladder
and a five-ability graph, declared before the readers ever saw the pitch; the listing did not
mention it. Whether a listing should carry the system is a question this run poses and does not
answer, and nothing here proposes a clause — §127 records what a fourth rule against the same
complaint is worth.

## 9. Chapter 1

**Chapter 1 is two scenes and 2,026 words**, drafted at `--chapter-scenes 2` under a tick loop
capped at six iterations with a break on the two-scene condition. The loop stopped itself: it
drafted the two scenes its chapter shape called for and never enqueued scene 3, so the gate on
everything past chapter 1 held by construction rather than by remembering to stop, as in
pilots 13 and 14. `library` reports 1 pastable chapter, 1 release volume, 2 chapters withheld.

Both scenes passed their gates: `shape.draft.v0` (989 words against a target of 900),
`integrity.standing.v0`, and `integrity.findings.v0` with four detectors running and nothing
found. `transport_failures` is empty; no step in this run is being trusted over a silent failure.

**The advisory the run prints, recorded because nothing acts on it:**

    rules pack  NOT RUNNING on 1 book(s) that state game state on the page;
                set --continuity-evaluator-command

The book is detected as one that states game state — which is itself an observation, since the
detection is what §160's ratchet exists to make true — and the checker that would police its
numbers is not configured. Nothing in this run set it.

## 10. Spend

**$7.85 in reported cost**, a floor rather than a total for the standing reason (pilot 12 §5);
no covers were drawn this iteration, so the usual unreported line is absent.

| stage | calls | tokens | reported |
| --- | --: | --: | --: |
| listing loop | 11 | 670,669 | $2.55 |
| architect seed | 1 | 4,381,624 | $4.50 |
| scene 1 | 1 | 59,065 | $0.40 |
| scene 2 | 1 | 59,884 | $0.39 |
| **total** | **14** | **5,171,242** | **$7.85** |

**Neither ceiling bound this run.** The $40 ceiling was never approached. **The token total
exceeds the default 5,000,000 daily ceiling**, so a run that forgot `--max-tokens-per-day` would
have been refused partway through drafting — pilot 12 §5's lesson earned again rather than merely
inherited, and closer here than in pilot 14.

**The seed is $4.50 of the $7.85**, and it is the most expensive single call any pilot has
recorded. It is also the call that produced §2.

## 11. What is owed and was not done here

- **The order-key namespace** (§7), which is this run's finding and is unfixed by design.
- **A way for a drawn system to exist at all in a seeded book** (§2.1) — today the Architect can
  declare a system in every respect except the one predicate that makes `system_gap` close.
- **`world retract`**, still absent, still owed from pilot 14 §10.
- **The continuity evaluator** on a book that states game state (§9).
- **Scenes 3–6**, and with them scene 3's and 5's beats, which §4 could not observe.
- **A live test of the gate's refusing branch**, owed since pilot 12 §2.1 — four pilots running.
- **The title-blind arm**, owed since [`serial-pilot-7.md`](serial-pilot-7.md) §5.2.
- **Covers**, deliberately skipped this iteration.

## 12. Anti-scope

No bar is declared. The word count, the coordinator density, the 1-of-4, the record and predicate
counts, and the spend table are descriptions, a measurement against an already-derived ceiling, a
ceilinged instrument, and arithmetic — never thresholds (§61). The four attainability checks were
not run because nothing here is a bar. Nothing admits an axis or promotes a research claim under
`EPISTEMIC_GOVERNANCE.md`. **No stage-0 number is claimed**: what shipped here is a book and a
filed finding. No model ranked, selected or judged anything, and no corpus was read — RS1 is
untouched. Nothing the operator says about this book becomes a prompt, directive, finding or plan
item (§97.1).
