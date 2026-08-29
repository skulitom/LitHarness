# Serial Pilot 15b — *What the Kettle Remembers*, drawn again: the same seed instinct met three fixes, and the report an operator reads is the one thing that did not move

**Status: WORLD AND CHAPTER 1 DRAWN ON A FRESH STORE, 2026-08-29.** Scenes 3–6 are not drafted.
This is **iteration 2** of the operator's iterate-until-right loop and its gate is the
coordinator's read, so this document carries **no reader-read skeleton**, by that directive.

Iteration 1 is [`serial-pilot-15.md`](serial-pilot-15.md), and its §7 is the reason this one
exists: the first draw's Architect scheduled its protagonist's whole arc in the schedule space,
and a string comparison handed scene one the end of it. Three entries landed against that draw —
**§165** (two named order-key spaces, and system completion at `world accept`), **§166** (the
prose-number licence narrowed to what a system counts *in a person*), and **§167** (the packet
cutoff and the disclosure schedule moved into one space). This draw is the first live test of all
three, on a fresh store, under the **same title and the same listing**.

## 0. The four readings this may not be given

**It is not a treatment comparison with iteration 1, and the temptation here is the sharpest any
pilot has offered** — same writer, same title, same listing, same scene count, same day. It is
still two draws. The seed is a fresh draw of a different world (a different system, a different
ladder, a different cast), and nothing here holds anything constant except the words on the
listing. Where a counter below sits beside iteration 1's it is a description of two books
(§0 of [`serial-pilot-7.md`](serial-pilot-7.md), and the standing boundary).

**It is not a quality claim.** §61's bar is a blinded, position-swapped win rate against matched
published prose. This is one chapter, unblinded, with no comparator.

**The counterfactual in §2 is arithmetic on records, not a second book.** No pre-fix draw was
made. What is computed there is what the *same* records would have folded to under the comparison
§165 replaced — a statement about a function, not about prose that exists.

**No model ranked, selected or judged anything in this run.** Not the world, not the prose, not
the system. The judgment calls — whether to re-seed, and what to do about the shelf collision —
were taken by a person and are recorded in §1 and §7.

## 1. What produced it

```bash
uv run litharness --database runs/pilots/databases/serial15b.db init
# the settled artifacts, reused: no listing call was made this iteration
uv run litharness --database runs/pilots/databases/serial15b.db \
    --roster-database C:/DEV/LitHarness/runs/roster/roster.db \
    new "$(cat runs/pilots/pilot15/title.txt)" \
    --premise "$(cat runs/pilots/pilot15/listing.txt)" --scenes 6
uv run litharness --database runs/pilots/databases/serial15b.db --roster-database ... \
    --library book-library --writer penhale \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 architect seed
uv run litharness --database runs/pilots/databases/serial15b.db world check    # clean
uv run litharness --database runs/pilots/databases/serial15b.db world accept   # no --force
uv run litharness --database runs/pilots/databases/serial15b.db --roster-database ... \
    --library book-library --writer penhale --chapter-scenes 2 \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 tick    # x4, capped at 6
uv run litharness --database runs/pilots/databases/serial15b.db --library book-library \
    --chapter-scenes 2 library
```

**The title and listing are iteration 1's, byte-for-byte**, read off `runs/pilots/pilot15/` — the
pilot-14 §1 precedent for standing a settled listing up on a fresh store. **No listing loop ran,
so no gate ran**, which is why §8 says this iteration adds nothing to the gate's record.

**One seed draw, one `world check` read, no re-seed.** The check came back clean, so the standing
allowance of one re-seed on mechanical complaints was not spent. **`world accept` without
`--force`.** **`--reader-checkpoints` off**, the baseline. **Both ceilings top-level on every paid
invocation**, `--library book-library` and `--chapter-scenes 2` wherever they apply — pilot 12
§5's silent failures, pre-empted; none recurred. **No covers**, because the loop's gate this
iteration is prose.

**No hand seeding of any kind**, as in iteration 1.

`book=5cf019e2-afc8-4588-94a3-23a63293826d`, `branch=df456176-3f66-4b39-9cb3-514cf3d701fd`.

## 2. Observation 1 — the Architect scheduled the whole arc again, and this time the fold read the opening

**It drew a system, unprompted, on one draw**, as iteration 1's did. The occupant is
**`the_keeping`**, holding `entity_role` `system`, and it owns the only ladder anybody climbs:

    listener → steadier → asker → setter → keeper

Five rungs, four `precedes` edges, six `governed_by` edges, and a prerequisite graph with a fork —
`setter` requires both `asker` and `steadier`. `ashfen_meeting` is an `institution` and
`millers_company` an `agency`; both read the ladder off `the_keeping` and neither issues it, which
is §160.5's refusal to ban them paying off a second time on a second world.

**And it scheduled the arc in the schedule space again, which is the whole point of this draw.**
Seven records carry a schedule key; 193 are un-keyed; **none is in neither space**, so §165.1's
new `will_not_resolve` report had nothing to say:

| key | predicate | value |
| --- | --- | --- |
| `0300` | `status_snapshot` | `holds 2, keeping 14/15, carry 3/4, vouched 4` |
| `0300` | `stands_at` | `steadier` |
| `0500` | `stands_at` | `asker` |
| `0800` | `status_snapshot` | `holds 4, keeping 26/27, carry 6/7, vouched 5` |
| `0800` | `stands_at` | `setter` |
| `1100` | `status_snapshot` | `holds 5, keeping 31/33, carry 4/9, vouched 7` |
| `1100` | `stands_at` | `keeper` |

with the opening state left **un-keyed** — `holds 1, keeping 9/11, carry 2/4, vouched 3`, and
`stands_at listener` — which is exactly what the `status_snapshot` vocabulary line asks for. **The
behaviour §165 set out to protect survived the fix**: this is a seed committing in advance to
where its protagonist's numbers will stand, and nothing refused it, normalised it or warned about
it.

**What scene one was actually shown, verbatim from the assembled prompt:**

    [STATUS] mira_kell — Holds 1 | Repairs Keeping 9/11 | Carrying 2/4 | Vouched By 3

**Entry rung. `Holds 1` of the five the ladder grants.**

### 2.1 The counterfactual, computed on the same records

Under the comparison §165 replaced — `key <= 's1'` with no space check — those same records fold
four snapshots to a ceiling of `1100` and render:

    [STATUS] mira_kell — Holds 5 | Repairs Keeping 31/33 | Carrying 4/9 | Vouched By 7

**Holds 5 of 5: the top of the ladder, in the chapter that introduces it.** Iteration 1 lost four
rungs of six this way; the same defect on this world would have lost four of five. The magnitude
is a property of the draw and not of the defect — §165 established that already — but it is worth
recording that the second world independently produced a worse instance of it.

**And §167's second door, the one §165 did not catch, reproduces and is closed too.**
`standing_of(mira_kell, at='s1')` returns `listener`; under the pre-fix `key > at` skip it returns
`keeper`. The un-keyed opening standing is what the book now opens on.

`records_before('s1')` admits **193 of 200 records, with 0 incomparable admitted**.

## 3. Observation 2 — the packet said which records it could not place, and why, seven times per scene

§167.2 chose to exclude the schedule-keyed records *and complain about them*, on the argument that
a record dropped for standing later in the book will arrive at some scene while a record dropped
for stating a position in the other space will be dropped at every scene. **That complaint is on
the page of scene 1's dossier**, naming all seven:

    omitted       7 context item(s) the packet could not hold
                    rec-w2e85d6d69ac0d6f22bbfe85d  position '0300' is not in the scene key
                      space this cutoff reads, so it is unplaceable here
                    …
                    rec-wf03d7155c6fc63d8402bd710  position '1100' is not in the scene key
                      space this cutoff reads, so it is unplaceable here

The run's digest records `context_omitted 14`, which is seven records across two scenes and is
the arithmetic closing on itself.

## 4. Observation 3 — 9 of 9 claims stayed hidden at scene one, by a route that does not re-test the fix

`undisclosed_claims(at='s1')` returns **9** — every `claim.content` record this world holds. The
one `claim.false`, `q_past_saving` (the millwright's "past saving"), is correctly not among them.
Iteration 1 returned **0 of 7** at the same position.

**And the honest half: this draw does not exercise the comparison §167 fixed for disclosure.**
This world wrote its reveals as **eight `reveal_scene` ordinals** — 4, 6, 7, 8, 9, 11, 12, 14 —
and exactly **one `disclosed_to` record**, un-keyed, pointing at the false claim. There is no
schedule-keyed `disclosed_to` anywhere in it, so `_disclosed_by`'s middle case never fires. What
is confirmed live here is §167's *cutoff* (§3) and its *second door* (§2.1); the disclosure
comparison itself is confirmed only by the tests §167 shipped, and is still owed a live world that
writes a schedule-keyed reveal.

**What this draw does show live is §167.1's registered gap.** Nothing in the pipeline writes a
`disclosed_to` record, and §165's vocabulary correction documents scene keys as not-for-writing-
by-hand, so a world following that line has no shape it may write that discloses at a scene. This
world followed the line, and its eight answers are hidden at scene one **and at every other
position** — `at=None` returns 9 as well. That is the cheap side of §167.1's asymmetry, behaving
exactly as registered, on a book rather than in a test.

## 5. Observation 4 — `world accept` completed nothing, said something true about why, and `world check` went on saying something false

**§165.2's `completion_records` ran, and declined.** The acceptance call's own words:

    accepted 198 of 200 proposal(s) into canon
      not finished: the_keeping declares no depth: nothing on its capabilities is held or
      required past 1, so this world says who holds what and never how far. A scale would be
      invented rather than read, so none is minted and the system gap stays open

**The reason is true of this world.** Every one of its three `can_do` records and five `requires`
records carries the value `1`; nothing is held or asked for past the first step, so the deepest
magnitude readable off its own numbers is one — and §165.2 refuses to mint a scale of one on
§114.6's grounds, because that is the word for a decoration and inventing it would author the
single dimension the world declined to have. **The guard did the thing it was built to do**, and
the gate row records it: `0 system record(s) minted; 1 system(s) unfinished`.

**And then `world check` printed this, after acceptance:**

    this book declares no game system: no subject holds the system role with a magnitude scale
    and a governed ordinal ladder. Its sheet is whatever was seeded by hand, its numbers have no
    home, and a progression beat has no vocabulary to land in.

**Three of that sentence's clauses are false about this world.** `the_keeping` holds
`entity_role` `system`. The ladder is governed — six `governed_by` edges point at it. The sheet
was not seeded by hand: it is the Architect's own `status_sheet`, `Holds | Repairs Keeping |
Carrying | Vouched By`, and no person typed a record into this store at any point. What is
actually missing is one predicate, `magnitude_scale`, and the acceptance call said so in a
sentence an operator does not see unless they were watching that call.

**This is iteration 1 §2.1's finding surviving the entry written against it, at a narrower
address.** §165.2 gave the completion path a named true reason and put it on the `accept` channel;
`genre.system_gap`'s first branch — reached whenever `_declared_systems` is empty, which is
whenever no scale exists — still carries the text written for a world that declared nothing. So
the two channels now disagree: `accept` names the reason standing in the way, `check` names an
absence that is not the one standing in the way. That is §155.2's shape, one door along from where
§165.2 moved it.

**Nothing here proposes the fix**, and the shape of one is not obvious: the branch is reached by
worlds that genuinely declared no system as well as by worlds like this one, so the text has two
audiences and currently serves the first. Recorded with its mechanism and left for its own entry.

**The other gap closed.** The `status_snapshot` acceptance gate is gone after `world accept`, and
the book drafted without being refused. **2 of 200 proposals were left proposed** — `q_sabb
claim.content` and `mira_kell edge` — as slots a later declaration in the same draw had replaced.

### 5.1 The world, by predicate

198 canon records at acceptance:

| predicate | n | | predicate | n |
| --- | --: | --- | --- | --: |
| `manifests_as` | 33 | | `costs` | 7 |
| `is_a` | 25 | | `stands_at` | 6 |
| `entity_role` | 23 | | `governed_by` | 6 |
| `consequence` | 13 | | `requires` | 5 |
| `believes` | 11 | | `status_snapshot` | 4 |
| `price` | 10 | | `precedes` | 4 |
| `world_rule` | 9 | | `can_do` | 3 |
| `claim.content` | 9 | | `status_sheet` | 1 |
| `asks` | 8 | | `disclosed_to` | 1 |
| `reveal_scene` | 8 | | `claim.false` | 1 |

with `comparator`, `type`, `evaluates` and `taught_by` at 2 each, and `graph_line`,
`exception_to` and `edge` at 1.

## 6. Observation 5 — the beat named a person-counted column, and both scenes moved a number

**The plan holds one item, of kind `premise`; no `SCENE_PLAN` exists**, and scene 1's dossier
records `plan item ABSENT`. The beat is derived at render time, and the last line of scene 1's
assembled prompt is:

> Now write What the Kettle Remembers: Scene 1 — open-ended series; release volume 1 (packaging
> only); arc 1; chapter 1 (1 of this arc); scene 1 of 2 (arc scene 1 of 6). Point of view:
> mira_kell. Dramatic function: setup. **This scene: Holds moves here, and the person it belongs
> to is there when it does.**

**Scene 2's prompt ends at *"Dramatic function: inciting."*** and carries no beat sentence — the
unscheduled control, which is `beat_ordinals(6)` = {1, 3, 5} doing what §155.3 registered. §157's
six-scene fix therefore works on a second book.

**`Holds` is the ladder column of the book's own sheet**, so this is `movable_names`' legacy arm
again, as in iteration 1 §4 — the system arm needs a real `SystemDef`, which §5 explains does not
exist here. **Scene 3's and 5's beats were not observed**, because chapter 1 is two scenes.

**§166.5's residual did not bite this draw, and it could have.** This book's sheet carries
`Repairs Keeping`, a count of repairs still holding across the town — a world aggregate, the exact
class §166.5 warns a scheduled beat may name and the prose may no longer speak. The beat named
`Holds` instead, which is counted in a person. That is one draw of a selector with no marker to
distinguish the two, not a demonstration that the residual is gone.

**Every `[STATUS]`-form line in chapter 1, verbatim, both of them:**

    [STATUS] Mira Kell — Holds 2 | Repairs Keeping 9/11 | Carrying 2/4 | Vouched By 3

    [STATUS] Mira Kell — Holds 2 | Repairs Keeping 9/11 | Carrying 3/4 | Vouched By 3

**One per scene, which is §161.3's cardinality, and both take the same branch of the placement
rule** — mid-scene, immediately after the sentence in which a number moves. Scene 1's follows Mira
feeling a patch hold for the first time and takes `Holds` from the 1 her packet carried to 2;
scene 2's follows *"Three, now. Room for one more"* and takes `Carrying` from 2/4 to 3/4.
Iteration 1 got one scene of each branch; this one got two of the change branch, so **the
scene's-end branch is unobserved on this book**.

**The columns are the book's own** — no `Level | HP | MP | Gold`, no `?`.

**And the extractor closed the loop, into the scene space.** Two new `accepted_canon` snapshots
were minted from the prose at order keys `s1` and `s2`, and they now sit in the same store as the
three at `0300`, `0800` and `1100` and the un-keyed opening — **six snapshots across three key
categories, coexisting, with the fold reading only the scene keys and the timeless.** Scene 2's
packet carried `Holds 2 | … Carrying 2/4 | …`, folded forward from scene 1's extraction, so the
scene-to-scene chain works. That co-existence is what §165 bought.

**This is an integrity observation and not a verdict.** No model judged the prose and neither does
this record (§97.1).

## 7. The shelf collision, and what was done about it

`library.publish_book` derives its folder from `slugify(document.title, …)` with **no
deduplication**, and clears stale files out of `chapters/`. Two books titled *What the Kettle
Remembers* therefore claim one shelf, and the second overwrites the first — including its chapter
files, and including `README.md`, which is regenerated from the publishing store alone.

**This was checked before the first `tick`, not before the final `library` call**, because
`publish` runs on every tick and the first drafting tick would have taken the folder.

**What was done, as a person's call:** iteration 1's shelf was copied whole to
`runs/pilots/pilot15/shelf-draw-1/` — twelve files, including its 2,029-word `Chapter1.txt` — and
this draw then published to the canonical slug. `book-library/` therefore holds exactly one
*What the Kettle Remembers*, which is iteration 2, and the coordinator's read has one folder to
open. **Nothing was lost either way**: iteration 1's prose lives in `serial15.db` regardless, and
now in the archive as well.

**No fix is proposed here.** Whether a library should refuse, suffix or overwrite a colliding slug
is a question this run poses; it did not arise in pilots 7 or 11–14 because no two books had
shared a title before, and it will arise every time an iterate-until-right loop redraws a book
under a kept title.

## 8. The listing, the title, and what the gate did not do

**Nothing.** The listing and title were reused verbatim, so no listing loop ran, no browsing pool
was polled, and no gate decision was taken this iteration. Iteration 1's row stands as the record.

**So the gate's interesting branch — a refusal followed by a redraw that lands under the bar —
remains untested against a live draw, now for the fifth pilot running**, and this iteration
neither advances nor sets that back. The title-blind arm is still owed, since
[`serial-pilot-7.md`](serial-pilot-7.md) §5.2.

One thing iteration 1 §8 recorded is worth re-reading beside §2 of this document: three of the
four browsing readers named the absence of a ladder in the pitch. The book under that listing now
has a five-rung ladder for the second time, and the listing still does not mention it. Nothing
here proposes a clause (§127).

## 9. Chapter 1

**Chapter 1 is two scenes and 1,969 words**, drafted at `--chapter-scenes 2` under a tick loop
capped at six iterations with a break on the two-scene condition. **The loop stopped itself at
tick 4**: two beat jobs, one evaluation, one summary, and scene 3 was never enqueued — so the gate
on everything past chapter 1 held by construction rather than by remembering to stop, as in
pilots 13, 14 and 15. `library` reports 1 pastable chapter, 1 release volume, 2 chapters withheld.

Both scenes passed all three blocking gates: `shape.draft.v0` (943 and 1,023 words against a
target of 900), `integrity.standing.v0`, and `integrity.findings.v0` with four detectors running
and nothing found. `findings` is empty, `exceptions` is 0 open, and all three paid calls returned
and were accepted — **no step in this run is being trusted over a silent failure.**

**The advisory the run prints, recorded because nothing acts on it, and it is iteration 1's:**

    rules pack  NOT RUNNING on 1 book(s) that state game state on the page;
                set --continuity-evaluator-command

**The chapter's text is at**
`book-library/what-the-kettle-remembers/chapters/Chapter1.txt` (and `.html`), with the reading
copies at `book-library/what-the-kettle-remembers/what-the-kettle-remembers.md` and `.html`.

## 10. Spend

**$4.16 in reported cost**, a floor rather than a total for the standing reason (pilot 12 §5). No
covers were drawn and **no listing was drawn**, so iteration 1's $2.55 listing loop is not
respent — this iteration's cost is the seed plus two scenes.

| stage | calls | tokens | reported |
| --- | --: | --: | --: |
| architect seed | 1 | 3,051,483 | $3.34 |
| scene 1 | 1 | 56,727 | $0.38 |
| scene 2 | 1 | 60,178 | $0.44 |
| **total** | **3** | **3,168,388** | **$4.16** |

**Neither ceiling bound this run**, and the $40 ceiling was never approached. **The token total is
under the default 5,000,000 daily ceiling this time** — 3.17M against iteration 1's 5.17M, because
the listing loop is absent — so unlike iteration 1 a run that forgot `--max-tokens-per-day` would
have completed. The flag was passed anyway.

**The seed is $3.34 of the $4.16**, and it is again the most expensive call in the run.

## 11. What is owed and was not done here

- **`world check`'s system-gap text**, which is §5's finding and is unfixed by design here.
- **A live seed whose system completes.** §165.2's minting path has now run twice against a real
  world and declined both times — once on a guard, once on depth — so a `magnitude_scale` minted
  from a seed's own numbers is still **unobserved outside its tests**.
- **A live world that writes a schedule-keyed `disclosed_to`**, which is what §4 could not test.
- **A disclosure channel a world may actually write** — §167.1's registered gap, now with a book
  behind it: eight answers hidden for the whole book.
- **A slug policy for a redrawn book under a kept title** (§7).
- **`world retract`**, still absent, still owed from pilot 14 §10.
- **The continuity evaluator** on a book that states game state (§9).
- **Scenes 3–6**, and with them scene 3's and 5's beats, and the scene's-end branch of the
  placement rule, which §6 could not observe.
- **A live test of the gate's refusing branch**, owed since pilot 12 §2.1 — five pilots running.
- **The title-blind arm**, owed since [`serial-pilot-7.md`](serial-pilot-7.md) §5.2.
- **Covers**, deliberately skipped this iteration.

## 12. Anti-scope

No bar is declared. The word counts, the record and predicate counts, the seven omissions, the
9-of-9, and the spend table are descriptions and arithmetic, never thresholds (§61). The four
attainability checks were not run because nothing here is a bar. The counterfactual in §2.1 is a
statement about a replaced function evaluated on records that exist, and is not a second draw.
Nothing admits an axis or promotes a research claim under `EPISTEMIC_GOVERNANCE.md`; agent prose
is not evidence. **No stage-0 number is claimed**: what shipped here is a book and two filed
findings. No model ranked, selected or judged anything, and no corpus was read — RS1 is untouched.
Nothing the operator or the coordinator says about this book becomes a prompt, directive, finding
or plan item (§97.1).

## The coordinator's read — the iteration gate, and it passes

Read 2026-08-29 by the coordinating session under the operator's standing loop directive
("give it a read yourself... Don't stop until you think it reads right"). Diagnostic, never
measurement; the operator's read 9 is the judgment that counts.

**Verdict: the loop closes.** Item by item against the operator's cumulative list: every
prose number is the character's own quantity under §166's licence — her Carrying spoken as
*"Three, now. Room for one more"* with its cost dramatized, her rung as Hanne's *"Then
that's two"*, her failure count as the two returned repairs — and the world-aggregate class
is absent entirely. The rung-up is scene 1's centrepiece, felt before it is named, socially
confirmed before the sheet prints. The furniture prints at the number-moves and nowhere
else. No licences, ledgers or guilds; the antagonists are a buyer, a secret, and a social
economy of suppers. The endgame leak is dead — Holds 2 of 5, the goal locked behind a
rule the reader can verify (*"a repair answers the hand that made it and no other"*). No
spoonfed inference in the operator's named shape; craft vocabulary grounded in context;
exception-first opening.

Residuals below the defect line, recorded so the next read knows they were seen: the
opening paragraph runs writerly for two sentences before the trade's cost lands; *"the way
you look at a grown-up you have decided to let handle something"* sits at the gloss
boundary but is specific and earned. Neither rises to any item on the operator's list.

Covers and the operator package follow; read 9 is the operator's.

## The cover set — four variants, measured against the prior twenty

Drawn after the gate passed, from `runs/pilots/pilot15/listing.json`, pilot 14's exact
invocation shape: no art direction (the standing control), both ceilings as top-level flags,
default publication name. The image provider again reported no cost. Output:
`book-library/what-the-kettle-remembers/covers/`, manifest beside the images.

| cover | mean luminance | what it is |
| --- | --: | --- |
| `cover-01.png` | 48.4 | Mira working the wheel, memory-panels glowing in the paddles |
| `cover-02.png` | **59.4** | the wheel over the town, overcast, fire accents |
| `cover-03.png` | 50.6 | the kettle itself, patched seams glowing, steam curling into a shape |
| `cover-04.png` | 39.5 | Mira's hand on the wheel, faces in the mist inside it |

**The set's mean is 49.5 against the prior twenty covers' 50.8** (that pool folds pilot 14's
four into read 8's sixteen-cover baseline: mean 50.8, max 77.6, min 26.5). The standing
description — this project makes dark covers — holds unchanged; pilot 14's brighter set was
one point, not a trend. One observation worth a line: the set's *brightest* cover by pixels
(`cover-02`, grey sky) is the one that reads gloomiest to a person, which is pilot 14 §8's
"brighter is not light" met from the other side — luminance and mood are different axes, and
neither substitutes for the click question only the operator answers. Arithmetic on pixels,
a description, never a threshold and never a quality claim (§61); no model ranked the four
(§84 — all four ship, the choice is the reader's).
