# Serial Pilot 14 — *Unlicensed Weather*: the first book drawn under the genre floor

**Status: LISTING, WORLD AND CHAPTER 1 DRAWN, 2026-08-29.** Scenes 3–8 are not drafted and are
gated on the operator. The read this book was made for is
[`reader-read-8.md`](reader-read-8.md), whose §§0–3 were fixed before the book went in front of
anybody and whose §4 is empty until it has been read.

What is new is not the writer but the **machinery**. `larkin` drew pilot 13 as well, and this
book is the first drawn after the genre floor and its scheduled progression beats (stage-0 §155)
and the three re-signed opening clauses (§154) existed. Three pieces of that machinery ran live
for the first time here, and §2 is what each of them did. **Same writer, changed machinery, every
draw different** — §0 says why that sentence is a refusal and not a comparison.

## 0. The three readings this may not be given

**It is not a treatment comparison, and pilot 13 is the specific one to refuse.** The temptation
is sharper here than in any previous pilot because the writer really is the same, which makes it
*look* like a held constant with the rules as the treatment. Everything else moved at once — a
different seed, a different world, a different scene count, a different number of books stood up,
and a listing drawn on a different day. Where a counter here sits beside pilot 13's it is a
description of two books (§0 of [`serial-pilot-7.md`](serial-pilot-7.md), and the standing
boundary).

**It is not a quality claim.** §61's bar is a blinded, position-swapped win rate against matched
published prose. This is one chapter, unblinded, with no comparator.

**No model ranked, selected or judged anything in this run.** Not the listing, not the world, not
the prose. Two judgment calls presented themselves — which path to seed a starting sheet by, and
whether to abandon a book at the wrong scene count — and both were taken by a person on evidence
gathered first, recorded in §2.2 and §3.

## 1. What produced it

```bash
# §151's roster flag: larkin lives in the roster store, the book has its own database,
# and NO whole-store clone happens — which is the change from pilot 13 §2
uv run litharness --database runs/pilots/databases/serial14.db init
uv run litharness --database runs/pilots/databases/serial14.db \
    --roster-database C:/DEV/LitHarness/runs/roster/roster.db --library book-library \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
    listing --writer larkin --scenes 6 --out runs/pilots/pilot14
uv run litharness --database runs/pilots/databases/serial14.db \
    --roster-database ... --library book-library --writer larkin \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 architect seed
uv run litharness --database runs/pilots/databases/serial14.db world check   # clean
uv run litharness --database runs/pilots/databases/serial14.db world accept  # no --force
uv run litharness --database runs/pilots/databases/serial14.db \
    world declare ilse_vange status_snapshot --value "..." --order-key 1     # §2.2
uv run litharness --database runs/pilots/databases/serial14.db world accept
```

`serial14.db` holds the six-scene book and one drafted scene, and is kept as the record of §3's
finding — the same role [`serial-pilot-13.md`](serial-pilot-13.md) §1 gives `serial13.db` for its
discarded seed. The book was stood up again at **eight** scenes on a fresh database, under the
same listing and title the loop had already written to `runs/pilots/pilot14/`:

```bash
uv run litharness --database runs/pilots/databases/serial14b.db init
uv run litharness --database runs/pilots/databases/serial14b.db --roster-database ... \
    new "$(cat runs/pilots/pilot14/title.txt)" \
    --premise "$(cat runs/pilots/pilot14/listing.txt)" --scenes 8
# seed -> check -> accept -> declare the sheet -> accept, exactly as above
uv run litharness --database runs/pilots/databases/serial14b.db --roster-database ... \
    --library book-library --writer larkin --chapter-scenes 2 \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 tick    # x N, capped, §6
uv run litharness --database runs/pilots/databases/serial14b.db --library book-library \
    --chapter-scenes 2 library
uv run litharness --database runs/pilots/databases/serial14.db --library book-library \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
    cover --bundle runs/pilots/pilot14/listing.json \
    --out book-library/unlicensed-weather/covers
```

`--reader-checkpoints` **off**, deliberately and throughout: it cannot steer either way before
qualification, and off is the baseline.

**Both ceilings on every paid invocation, as top-level flags before the subcommand**, and
**`--library book-library`** on every invocation that republishes, with **`--chapter-scenes 2` on
the `library` invocation as well as the drafting ones**. These are pilot 12 §5's silent failures
and pilot 13 §1's inherited lessons, pre-empted; none recurred. Neither ceiling bound this run.

**Brief: empty.** The bundle's `brief` is `""`, the standing control every pilot since §136 has
kept.

**The writer is `larkin`, cast by the operator's recorded slate order and not by any model**
(§84). Light Fantasy is first among the twelve shelves; that ordering is the casting rule, applied
deterministically, and no model expressed a preference among recruits.

## 2. Three pieces of machinery, live for the first time

### 2.1 The roster flag (§151): resolved on a fresh database, no clone

Pilot 13 §2 could not get an accepted recruit to a book without cloning the entire roster store,
and recorded two costs of that workaround: the clone inherited the recruitment run's spend, so
every figure had to be reported as a delta, and it forked the roster into a frozen snapshot.
**Both costs are gone.** `--roster-database` is a top-level flag; on a database created by `init`
and nothing else:

    $ litharness --database serial14.db roster show
    "writers": []                       # and the four compiled cast

    $ litharness --database serial14.db --roster-database runs/roster/roster.db roster show
    "writers": [ ... 18 accepted recruits ... ]

`larkin` resolves as `wtr-dce4b363c398d27fbe14644c`, specialization `light-fantasy`, accepted
2026-08-28, and the writer's dossier reaches the listing prompt from the roster store while the
book's own records stay in the book's own database. **No regression**, and §9 reports this run's
spend as an absolute figure rather than a delta for exactly this reason. Nothing in this run wrote
to `runs/roster/roster.db`.

### 2.2 The genre floor (§155.2): it refused, at zero spend — and the paths its refusal names are unreachable

**The refusal fired and cost nothing, which is the half that worked.** The Architect's prompt was
not changed by the fix round, so neither seed produced a `status_snapshot`; the predicate is
absent from all 296 records of the first world. A `tick` carrying both ceilings then returned:

    no_work tick=... reconciled=0 ingested=0
      library: book-library — Unlicensed Weather 0 of 6 scene(s) drafted — 0 word(s)

**Spend before and after that tick is identical** — 12 calls, $5.79 — so no packet was built, no
job enqueued and no call made. That is §155.2's report-then-gate shape doing exactly what it
says, in front of the spend rather than behind it.

**Then the operator story, which is where the friction is.** The refusal names two paths, and on
the path this pilot was on **both are unreachable**:

- **`new --state` cannot be used**, because `listing --scenes 6` creates the book itself and
  passes `state=None` when it does (`cli.py:2299-2305`). A book created by the listing loop can
  never carry a seeded sheet and therefore always trips the floor.
- **`import --state` cannot be used**, because `import` has no `--book` or `--branch` flag: it
  takes both from the manuscript artifact and is the command that *creates* a book, not one that
  adds state to an existing one.
- **`litharness state` is read-only**, a query with `--subject` and `--predicate`.

So the reachable path is the in-world one, and it is documented on its own terms rather than
being a loophole: `world declare <subject> status_snapshot` mints a `PROPOSED` record, and
`world accept` promotes it to `ACCEPTED_CANON`. `world declare`'s predicate positional carries no
allowlist and `worlds.validate` says nothing about `status_snapshot`.
**`DraftPolicy(require_starting_sheet=False)` was not used and was never a candidate** — it is
how the suite drafts the golden mystery fixture, and this is production.

**What the sheet says, and why a person wrote it.** The Architect declares the standings; the
snapshot restates them and invents nothing:

    ilse status_snapshot "guild grade no glass (1 of 7); eleven coppers"  --order-key 1

`grade_no_glass` is rung 1 of 7 on the accepted `guild_grade` ladder and the eleven coppers are in
Ilse's own canon description. Authoring world facts is the thing pilot 12 §3 refused a licence
for; restating two already-accepted ones in status-line form is not that, and the note on the
record says so. The shape follows the floor's own test, which uses a plain string
(`tests/test_genre_floor.py`).

**And the cost of that path, established from the code rather than guessed.** `_scalar`
(`cli.py:2447-2466`) keeps a parsed `--value` only when it is `int | float | bool`, so a mapping
round-trips back to its raw string. `system_voice_example` requires
`isinstance(record.value, Mapping)` (`extraction.py:1265`). **So the only reachable seeding path
cannot produce a snapshot the status-line machinery can render from**, and §7 is what that costs.

### 2.3 The beats (§155.3): scheduled exactly, on the second book only

On the eight-scene book, after the outline job and **before any prose was drafted**, the eight
`SCENE_PLAN` items carry the beat on ordinals **{1, 3, 5, 7}** and nowhere else — which is
`beat_ordinals(8)` exactly, and leaves the even scenes byte-identical as the control §155.3 asks
to be read against. Scene 1's plan, verbatim:

> Ilse runs the guild's sealed jars through the Ashfold gate and signs for them at first glass,
> hearing her own unstamped jar knock under her coat, unsayable. **One of the numbers this book
> counts moves here, and the person it belongs to is there when it does.**

The outline's own statement leads and the beat is appended, which is `with_beat`'s documented
order. Scene 2's plan carries none.

**On the six-scene book it did not fire at all**, and that is §3.

## 3. The six-scene dead spot: a fix-round feature keyed to a condition the standard recipe never meets

**Measured, on the first book.** After a tick that drafted scene 1, the book's plan held **one**
item, of kind `PREMISE`. No `SCENE_PLAN` existed, so no beat did.

**The mechanism, established from the code in three steps.**

1. `genre.with_beat` has exactly one production call site: `application/outline.py:905`, inside
   `record_outline`. Beats exist only in `SCENE_PLAN` items the outline writes.
2. The outline is enqueued only when `needs_outline` holds (`application/planner.py:857-861`),
   which requires `len(set(functions)) < len(functions)` — duplicate beat functions.
3. A six-scene book's functions are `setup, inciting, rising, turn, crisis, resolution`: six
   distinct functions, so `needs_outline` is False, no outline job is ever enqueued, and no
   `SCENE_PLAN` is ever written.

**Six is the only length at which this happens**, because only `rising` repeats and a six-scene
book has exactly one of it:

| scenes | distinct functions | outline runs, so the beat can fire |
| --: | --- | --- |
| **6** | 6 of 6 | **no** |
| 7 | 6 of 7 | yes |
| 8 | 6 of 8 | yes |
| 12 | 6 of 12 | yes |
| 24 | 6 of 24 | yes |

**This is the flag-mismatch shape again** — pilot 12 §5's class, where a feature is keyed to a
condition the standard recipe never meets. `--scenes 6` is what every serial pilot recipe uses,
so §155.3's schedule shipped into a pipeline whose default book length is the one length it
cannot reach. The outline gate itself is doing exactly what `planner.py:843-848` says it should;
what was unnoticed is that the beats were hung off it.

**What was done and what was not.** The book was stood up again at eight scenes, which is the
smallest count that fires. **No code was changed mid-run**, on the operator's instruction; the fix
is filed as a follow-up, and whoever takes it decides between applying `with_beat` in the
no-outline path and giving six-scene books outlines — by reading intent, not by patching the
recipe. The six-scene book is kept in `runs/pilots/databases/serial14.db` as the record.

## 4. The listing, the title, and what the gate did

    Unlicensed Weather

    **Ashfold, market day.**

    Ilse walks in with a thunderstorm in a jar and eleven coppers to her name.

    Weather here is a licensed trade. Stormwrights sell rain to farmers, frost to brewers, clear
    skies to anyone who can pay, and every jar of it is stamped, taxed and logged in a ledger.
    Hers is not. She can wake the thing inside without a guild seal, which is supposed to be
    impossible, and she wants exactly what that impossibility might buy: an apprenticeship the
    stormwrights have never once offered a stranger off the road.

    The guild's sharpest young forecaster means to find out how she does it. The jar has already
    started to leak.

**113 words.** The decision row records the gate exactly:

    113 words; 3.54 coordinators/100w vs the 5.89 ceiling; 3 of 4 would start it;
    title 'Unlicensed Weather' free

**No refusal, no redraw: the first draw was kept**, and the bounded redraw budget was not spent.
So as with pilots 12 and 13, **this run says nothing about whether the gate works** — the
interesting branch, a refusal followed by a redraw that lands under the bar, is still untested
against a live draw, now for the third pilot running.

**Four properties of the bundle, each a fact about the file.** `draft` and `listing` are
byte-identical, so no revision happened. `appetite_status` is
`experimental_observation_only`. The title was looked up across six searches and is `free` with
zero collisions and zero near misses, and `titles_abandoned` is `[]` — so **the retry path is
still untested against a real collision**, as in pilots 7, 11, 12 and 13. `paired` is `null` and
`title_shown_to_readers` is `true`: no named competitor, and the title-blind arm is still owed.

**The browsing pool said 3 of 4 `start_reading`, 1 `save_for_later`, 0 passed**, reported with
§134's ceiling written across it rather than believed. What the four *said* is the part specific
enough to be wrong, and the one who saved it named the setting's own engine as the reason —
paperwork-magic is what that reader bails on.

### 4.1 The opening shape, described and not scored

**The listing opens on the person and her exception.** The first sentence is *Ilse walks in with
a thunderstorm in a jar and eleven coppers to her name*; the second beat is that she can wake it
with no guild seal, *which is supposed to be impossible*; the account of the world is third.
§154 removed the listing clause's permission entirely and narrowed its person-ban to the prior
life, and the assembled prompt confirms the narrowed clause is live: *"Not an account of the
world, and not the life whoever this happens to had before it began."*

**What this is not.** §154 shipped three edits together and said so — *"the three edits land
together on that read, so it cannot attribute a change to any one of them"* — and this is one
listing. It is a description of where this draw opened, offered because §154 named pilot 14 as
where openings would next be looked at, and it settles nothing about which edit did what or
whether the next draw does the same.

**The writer's own named beat recurs, as it did in pilot 13.** `larkin`'s dossier loves *"a
stranger walking into a market town on a bright morning with something impossible in their bag"*
and *"magic that behaves like weather"*; this listing is a stranger walking into a market town
with a storm in a jar, in a world where weather is the trade. This is the second book from this
writer under an empty brief and the second to draw that beat — a property of the writer, recorded
here so a read does not harvest it as a defect of this draw.

## 5. Two worlds, both clean, and one accepted whole

**Both seeds came back clean and neither needed `--force`.** `world check` on each:

    "complaints": [], "ok": true, "will_not_resolve": [], "unmanifested": []

- **The six-scene world:** 296 records; `world accept` promoted 291 and left 5 proposed as slots a
  later declaration had replaced.
- **The eight-scene world:** 253 records; `world accept` promoted **253 of 253, leaving nothing
  proposed at all.**

**The stronger claim available here is refused.** *"The first clean world check in pilot history"*
is what this looked like and it is not true:
[`serial-pilot-12.md`](serial-pilot-12.md) §3 records a second seed with an empty complaint list,
ladders resolving, and acceptance without `--force`. What is accurate is narrower and still worth
recording: **both seeds were clean here, where pilot 13's two seeds were both dirty**, and the
`--order-key`/`--value` trap — three sightings across four seeds in pilots 12 and 13, and the
thing that cost pilot 13 a discarded seed — **did not recur on either draw**. A zero-stray accept
is not something the two prior pilots produced.

**Two things §§152–153 shipped, observed live.** `world check` now prints a `will_not_resolve`
field, and it was empty on both worlds. And **`world ladders` resolves** on the accepted world,
printing both chains in full — where pilot 13 §5 recorded the same command printing `[]` on a
correctly accepted world because the view read permanently-proposed strays. Post-accept
`world check` also stayed `ok: true` here, where pilot 13's stayed `ok: false` permanently.
**These are observations of two worlds, not a demonstration that the defects are fixed**: the
eight-scene world has no strays at all, so it cannot exercise the path that poisoned pilot 13's
view.

**One flag the seed raised about itself**, quoted because it is the gap that is still open:
`one_weather_per_jar` was left policing a graph shape rather than the fiction its id names,
*"because the CLI has no retraction and I'd already claimed that id"*. No `world retract` exists;
that is the standing gap the world-CLI work left open, met again.

## 6. Chapter 1

**Chapter 1 is two scenes and 2,016 words**, drafted at `--chapter-scenes 2` under a tick loop
capped at six iterations with a break on the two-scene condition. The loop stopped itself: it
drafted the two scenes its chapter shape called for and never enqueued scene 3, so **the
operator's gate on everything past chapter 1 held by construction rather than by remembering to
stop**, as in pilot 13. `library` reports 1 pastable chapter and 3 chapters withheld.

**The chapter was read once, to verify it published intact** — complete prose, two scenes with a
break, no truncation, no placeholders, ending mid-incident. Two mechanical scans were run. Of 73
identifier-shaped tokens in the book's canon, **none appears verbatim in the prose**. One
`house.MACHINERY_WORDS` term appears — `standing` — and in context it is ordinary English
(*"because the alternative was standing there"*) rather than the repo's ladder sense.
**That is an integrity check and not a verdict**; no model judged the prose and neither does this
record (§97.1).

## 7. What the progression machinery did, and the one defect that disables half of it

Four mechanisms can put progression in front of a scene writer. **On the six-scene book, none of
them fired. On the eight-scene book, two did.** Measured at scene 1 on each:

| mechanism | six-scene book | eight-scene book | why |
| --- | --- | --- | --- |
| scheduled beat in the scene plan | — | **fires** | §3: no outline at six scenes |
| `standing_target` | — | **fires** | the outline mints the `PROPOSED` standing schedule it reads |
| `system_voice_example` | — | — | §2.2: `--value` cannot carry a mapping |
| `progression_target` | — | — | needs a `PROPOSED` mapping-valued snapshot, which has no source |

**The consequence for the book on the shelf, stated plainly because a reader will notice it.**
The status-line instruction lives inside the `if status_example:` branch
(`application/planner.py:370-376`), so **this book was never asked to end a scene with a status
line.** The floor is cleared, the sheet is in the writer's packet as fact — it appears twice in
the assembled scene-1 prompt — and the chain the floor exists to start is still only half started:
canon holds a snapshot, and nothing renders an example from it.

**The two dark mechanisms have a single root cause**, which is the useful half of this table:
both need a mapping-valued `status_snapshot`, and the only reachable seeding path cannot make
one. That is one defect with two symptoms, not two defects.

**And a related advisory the run printed, recorded because nothing acts on it:**

    rules pack  NOT RUNNING on 1 book(s) that state game state on the page;
                set --continuity-evaluator-command

The book is now detected as one that states game state, and the checker that would police its
numbers is not configured. Nothing in this run set it.

**A second gap found while establishing the above.** `plan_progress` computes `blocked_reason`
and the selector honours it, but **no CLI command prints it** — the identifier appears in
`application/planner.py` and in no other module. §155.2 argues that a blocked book *"reports its
reason rather than looking finished"*, and the domain object does; the operator sees `no_work` and
a library line reading `0 of 6 scene(s) drafted`. The report half fires at `new`, where seeding is
cheap; at tick time the refusal is silent.

## 8. The covers

Four variants, from the listing, through the pipeline pilots 11 to 13 established.

**Zero recorded calls, confirming pilot 13 §6.** `policy_decisions` on `serial14.db` holds no row
for the cover run at all; the image provider reports no cost, so a dollar ceiling passed on a
`cover` invocation constrains nothing. §9's total is a floor for this reason.

### 8.1 The luminance arithmetic, on the instrument read 5 used

Reproduced before the new covers existed: a Pillow `L`-conversion mean over each finished
`cover-NN.png` returns read 5 §4.4's eight numbers and pilot 13 §6.1's four **to the decimal**
(77.6, 59.9, 41.7, 66.3), and the prior twelve's mean of 43.3 exactly. Same instrument, so the
comparison is not a differently-computed number.

The baseline this set arrived against is **sixteen covers, mean 47.8, maximum 77.6, minimum 26.5.**

| cover | mean luminance |
| --- | --: |
| `cover-01.png` | 69.2 |
| `cover-02.png` | **71.6** |
| `cover-03.png` | 50.9 |
| `cover-04.png` | 58.5 |

**The set's mean is 62.5 against the prior sixteen's 47.8, and its darkest cover (50.9) is
brighter than eleven of the sixteen.** No cover beats pilot 13's 77.6, and **none reaches
mid-grey (127.5)**, so the standing description — this project makes dark covers — is narrowed
again rather than overturned.

**What this is and is not.** It is a description of one cover set, four images, arrived at by
arithmetic on pixels — never a threshold and never a quality claim (§61). This is the second
cover set drawn from a listing that is not disaster-shaped, so the sample now has two points with
variation on that input rather than one; two points are not a dose-response, and nothing here
establishes that the listing caused the brightness, since the writer, the world and the palette
all moved together again.

## 9. Spend

**$11.16 in reported cost for this run**, and that figure is a **floor**, not a total, for the
reason pilot 12 §5 generalised and §8 confirms again: cover generation reports no cost, and every
spend figure this project records is a metered subset.

Reported absolutely rather than as a delta — **there is no inherited baseline this time**, which
is §2.1's saving:

| stage | database | calls | tokens | reported |
| --- | --- | --: | --: | --: |
| listing loop | `serial14.db` | 11 | 767,134 | $2.61 |
| seed 1, six scenes | `serial14.db` | 1 | 2,745,210 | $3.17 |
| scene 1, abandoned book | `serial14.db` | 1 | 59,468 | $0.39 |
| cover set | `serial14.db` | — | — | **not reported** |
| seed 2, eight scenes | `serial14b.db` | 1 | 3,702,572 | $3.61 |
| outline | `serial14b.db` | 1 | 72,947 | $0.60 |
| chapter 1, two scenes | `serial14b.db` | 2 | 118,476 | $0.79 |
| **total** | | **17** | **7,465,807** | **$11.16** |

Kept by hand, because no single command totals across databases — pilot 12 §5's gap, met again.
**Neither ceiling bound this run**: the $40 ceiling was never approached, and the token ceiling
was carried at 20,000,000 from the first call and never reached. It is worth noting that
`serial14b.db` alone spent 3.89M tokens against the **default** 5M daily ceiling, so a run that
forgot the flag would have been close to it — which is pilot 12 §5's lesson still being earned
rather than merely inherited.

**The two seeds are $6.78 of the $11.16, and the chapter is $0.79.** Standing the book up twice
cost $3.61; the six-scene dead spot is what bought that, and §3 is what it bought.

## 10. What is owed and was not done here

- **Where `with_beat` is applied** (§3), so a six-scene book is not the one length the schedule
  cannot reach. Filed as a follow-up; deliberately not fixed mid-run.
- **A seeding path that can carry a mapping** (§2.2, §7), so a book can clear the floor *and* be
  asked for a status line. Today the two reachable facts are in tension: the path that can reach
  an existing book cannot make a renderable snapshot.
- **A `--state` passthrough on `listing --scenes`**, or any way for the loop that creates a book to
  seed one, so the floor's own named paths are reachable from the path pilots use.
- **An operator surface for `blocked_reason`** (§7), so a floored book says why instead of
  reporting `no_work`.
- **`world retract`** (§5), still absent, and still the reason a mis-claimed id is permanent.
- **The continuity evaluator** on a book that states game state (§7) — the advisory prints and
  nothing sets the command.
- **Scenes 3–8.** Gated on the operator.
- **The other three writers' fresh listings**, still owed from
  [`serial-pilot-11.md`](serial-pilot-11.md) §5.
- **The title-blind arm**, still owed from [`serial-pilot-7.md`](serial-pilot-7.md) §5.2.
- **A live test of the gate's refusing branch**, owed since pilot 12 §2.1 and not paid here
  either — three pilots running.
- **Read 5 §4.4's two separating tests** for the light-fantasy capability question.

## 11. Anti-scope

No bar is declared. The word count, the coordinator density, the 3-of-4, the scene-count table and
the cover luminances are a description, a measurement against an already-derived ceiling, a
ceilinged instrument, a property of a pure function, and an arithmetic on pixels respectively —
never thresholds (§61). Nothing here admits an axis or promotes a research claim under
`EPISTEMIC_GOVERNANCE.md`, and **no stage-0 number is claimed**: a § gets claimed when something
ships because of this, and what shipped here is a book and two follow-up filings. Nothing the
operator says about this book becomes a prompt, directive, finding or plan item (§97.1); it routes
through [`reader-read-8.md`](reader-read-8.md) §3 instead.
