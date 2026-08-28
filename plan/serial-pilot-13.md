# Serial Pilot 13 — *The Rainwright's Apprentice Has No Licence*: the first book by a recruited writer

**Status: LISTING, WORLD AND CHAPTER 1 DRAWN, 2026-08-29.** Scenes 3–6 are not drafted and are
gated on the operator. The read this book was made for is
[`reader-read-7.md`](reader-read-7.md), whose §§0–3 were fixed before the book went in front of
anybody and whose §4 is empty until it has been read.

Run for the seventh operator read. What is new is not the recipe but the **writer**: `larkin`,
the Light Fantasy recruit the operator accepted onto the roster on 2026-08-28, is the first
writer to draft a book without being compiled into `domain/writers.py`. That made a wiring
question load-bearing before any paid call, and §2 is that question.

## 0. The three readings this may not be given

**It is not a treatment comparison, and `larkin` versus `ferreira` is the specific one to
refuse.** Every input differs from every other pilot's at once — different writer, different
world, different seed, a different number of seeds. Where a counter here sits beside pilot 12's
it is a description of two books (§0 of [`serial-pilot-7.md`](serial-pilot-7.md), and the
standing boundary).

**It is not a quality claim.** §61's bar is a blinded, position-swapped win rate against matched
published prose. This is one chapter, unblinded, with no comparator.

**No model ranked, selected or judged anything in this run.** Not the listing, not the world, not
the prose. Two judgment calls presented themselves — discarding a seed, and forcing an
acceptance — and both were taken by a person on evidence gathered first; §4 records what was
measured before each.

## 1. What produced it

```bash
# the roster bridge, §2 — larkin lives in the roster store, the book needs its own database
uv run litharness --database runs/roster/roster.db backup runs/pilots/databases/serial13.db
uv run litharness --database runs/pilots/databases/serial13.db init

uv run litharness --database runs/pilots/databases/serial13.db --library book-library \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
    listing --writer larkin --scenes 6 --out runs/pilots/pilot13
uv run litharness --database runs/pilots/databases/serial13.db --library book-library \
    --writer larkin --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
    architect seed                                                    # <- discarded, §4.1
```

`serial13.db` holds no prose and is kept as the record of the discarded seed, which is
[`serial-pilot-7.md`](serial-pilot-7.md) §1's pattern and pilot 12's: the world it seeded could
not be accepted, and the book was stood up again on a fresh database under the same listing and
title, which the loop had already written to `runs/pilots/pilot13/`.

```bash
uv run litharness --database runs/roster/roster.db backup runs/pilots/databases/serial13b.db
uv run litharness --database runs/pilots/databases/serial13b.db --library book-library \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
    new "$(cat runs/pilots/pilot13/title.txt)" \
    --premise "$(cat runs/pilots/pilot13/listing.txt)" --scenes 6
uv run litharness --database runs/pilots/databases/serial13b.db --library book-library \
    --writer larkin --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 architect seed
uv run litharness --database runs/pilots/databases/serial13b.db world check
uv run litharness --database runs/pilots/databases/serial13b.db world accept --force   # §4.3
uv run litharness --database runs/pilots/databases/serial13b.db --library book-library \
    --writer larkin --chapter-scenes 2 \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 tick          # x N, §5
uv run litharness --database runs/pilots/databases/serial13b.db --library book-library \
    --chapter-scenes 2 library
uv run litharness --database runs/pilots/databases/serial13b.db --library book-library \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
    cover --bundle runs/pilots/pilot13/listing.json \
    --out book-library/the-rainwright-s-apprentice-has-no-licence/covers
```

`--reader-checkpoints` **off**, deliberately and throughout: it cannot steer either way before
qualification, and off is the baseline.

**Both ceilings on every paid invocation, as top-level flags before the subcommand.** Pilot 12
§5 found the *token* ceiling binding where the dollar ceiling never was; carrying both from the
start is that entry being used rather than re-learned. Neither bound this run.

**`--library book-library` on every invocation that republishes**, and **`--chapter-scenes 2` on
the `library` invocation as well as the drafting ones**. Both are pilot 12 §5's silent failures
pre-empted; neither recurred.

**Brief: empty.** The bundle's `brief` is `""`, the standing control every pilot since §136 has
kept.

**The writer is `larkin`, cast by the operator's recorded slate order and not by any model**
(§84). The operator listed Light Fantasy first among the twelve shelves; that ordering is the
casting rule, applied deterministically, and no model expressed a preference among recruits.

## 2. The roster bridge: an accepted writer could not reach a book, and the fix here is interim

**Measured first, and free.** On a database created by `init`, naming the accepted recruit
refuses before the first paid call:

    $ litharness --database <fresh.db> listing --writer larkin --scenes 6
    litharness: no writer named 'larkin'; the cast is ferreira, halloran, vance, okonjo,
    and `litharness roster show` lists every writer this database holds

**Exit 2, zero calls, zero tokens.** The refusal lands before any spend (`cli.py:2029-2035`),
which is the one good property of this gap: it fails cheaply and loudly rather than expensively.

**The cause is that a roster is per-database while the code says otherwise.**
`cli.py::_resolve_writer` reads `store.roster_rows(...)` from whatever `--database` is open, so
an accepted writer exists only in the store that accepted them. The parser comment at
`cli.py:5515` says *"a roster belongs to the installation"*; the `--writer` help says *"any
writer **this database's** roster has accepted"*. **The help is what the code does**, and the
comment is aspiration. `litharness roster` offers show/check/vocabulary/declare/accept/refuse and
no export, no import, and no copy; `litharness export` is prose export; `LITHARNESS_DATABASE` is
only a default for `--database`.

**The bridge used, and it is a workaround and not the fix:**

    litharness --database runs/roster/roster.db backup runs/pilots/databases/serial13.db

`SqliteStore.backup_to` (`sqlite_store.py:309`) takes an online SQLite backup — deliberately not
a file copy, because the store runs in WAL mode — and refuses to overwrite an existing
destination. It clones the **whole store**, so `larkin`'s row and the decision rows that recorded
the acceptance travel together. Nothing is transplanted and nothing is asserted: the clone
carries other writers' acceptance rows too, which is the property showing up as data rather than
as a claim.

**The option that was available and was refused: re-declaring `larkin` and re-accepting.** The
dossier is reproducible, so this would mint the same writer under a fresh acceptance — and that
is precisely what makes it wrong. `roster accept`'s content is *a person admitted this writer*,
and a run re-executing it asserts a human act that did not happen, while orphaning the recruit
provenance row that records which shelf and which registered form produced the dossier. The
clone carries the provenance; the re-declaration would have manufactured it.

**Two properties of the clone, recorded rather than left implicit:**

1. **It inherits the source store's spend.** Both pilot databases start from a baseline of 18
   calls, 5,906,311 tokens and $8.32 — the recruitment run's, already spent that day. §9 reports
   this run's cost as a **delta** against that baseline for exactly this reason.
2. **It forks the roster.** `serial13b.db` holds a frozen snapshot; roster acts taken in
   `runs/roster/roster.db` after the clone do not appear in it. Harmless for one book, and
   written down because it is invisible otherwise.

**The named fix is a real `roster export` / `roster import` path**, filed as a follow-up task and
cited here so the workaround is not mistaken for a design. `runs/roster/roster.db` remains the
canonical roster; nothing in this run wrote to it.

## 3. The listing, the title, and what the gate did

    The Rainwright's Apprentice Has No Licence

    The rain over Ambry Market has been sold to someone else, and Corin is carrying a jar of
    it in his bag. Weather is a trade in these valleys, drawn down by charter and paid back in
    kind, and nobody can explain how a boy with no licence got a storm into glass. He wants to
    sell it quietly and buy his mother's orchard back before the season turns. The town's
    licensed rainwright wants to know his method. The bailiff wants him gone. By afternoon
    half the market is arguing over him, and the jar has started to hum.

**99 words.**

### 3.1 The gate measured and did not fire

The decision row records it exactly:

    99 words; 5.05 coordinators/100w vs the 5.89 ceiling; 4 of 4 would start it;
    title "The Rainwright's Apprentice Has No Licence" free

**No refusal, no redraw: the first draw was kept**, and the bounded redraw budget was not spent.
So as with pilot 12, **this run says nothing about whether the gate works** — the interesting
branch, a refusal followed by a redraw that lands under the bar, remains untested against a live
draw. The number sits closer to the ceiling than pilot 12's did; that is a description of two
listings and not a trend, and two points on a counter are not a direction.

### 3.2 Four properties of the bundle, each a fact about the file

1. **`draft` and `listing` are byte-identical.** No revision happened, which is the retired
   direct-appetite steering path's absence shown rather than asserted.
2. **`appetite_status: "experimental_observation_only"`.** The bundle labels its own appetite
   rows as what `reader-architecture-program.md` says they are.
3. **The title was looked up and is free**, and unusually so: `availability.verdict: "free"` with
   **zero collisions and zero near misses** across six searches, where pilot 12's nearest miss
   was a live Royal Road serial in the same genre. `titles_abandoned: []`, so — as in pilots 7,
   11 and 12 — **the retry path is still untested against a real collision**.
4. **`paired: null` and `title_shown_to_readers: true`.** No named competitor, which is the
   control arm; and the listing was screened **with** its title, so the title-blind arm is still
   owed.

**The browsing pool said 4 of 4 `start_reading`**, reported with §134's ceiling written across it
rather than believed — a full house is where that ceiling already was. What the four *said* is
the part specific enough to be wrong, and two of them independently named the same reservation:
that the charter system could turn into paperwork instead of pressure.

### 3.3 The opening beat is the writer's own, again

`larkin`'s dossier names what it loves: *"a stranger walking into a market town on a bright
morning with something impossible in their bag"*, and *"magic that behaves like weather"*. The
listing is a boy walking into Ambry Market with a jar of rain in his bag, in a world where
weather **is** the magic. **This is the same property [`reader-read-5.md`](reader-read-5.md) §4.3
located in the compiled cast** — a writer draws its dossier's named beat every time — now
observed on a recruit, where the dossier was written by the recruiter rather than by hand. It is
a property of the writer under an empty brief and not a defect of this draw, and it is recorded
here so a read does not harvest it as one.

## 4. Two seeds, one discarded and one forced

### 4.1 The first seed, discarded rather than forced

317 records, and `world check` refused them. **Its own diagnosis was honest**, which is worth
saying because pilot 12 §3's was not: it named both of its defects and did not argue for
`--force`.

- **The `--order-key`/`--value` trap again.** Every `precedes` and `stands_at` was scoped with
  `--order-key` where `rank_order` reads `--value`. This is [`serial-pilot-7.md`](serial-pilot-7.md)
  §3.1.3 and pilot 12's seed 1 for the **third** documented time, and the seed walked into it
  despite its own memory note warning about that exact trap.
- **Six malformed `consequence` records**, from a genuine disagreement between the tool and its
  own documentation: the vocabulary documents `--object` as the rule, and the checker reads that
  slot as the domain.

**`world accept` without `--force` was run, and it did most of the work.** Acceptance applies
supersession *before* validating (`cli.py:3866-3872`), so **all 32 standings complaints
cleared** — the ladder half really was repairable, exactly as the seed said. Six complaints
survived.

**Why the six could not be repaired, established from the code and not from the seed's word.**
The supersession slot is `(subject, predicate, object_ref, order_key)`
(`integrity.disagreement_key`, `integrity.py:236-250`), and `object_ref` is the field carrying
the malformed value. **Any superseding declaration must therefore repeat the error.** There is no
`world retract` in the `world` command set. The records are permanent in `serial13.db`.

The seed was discarded rather than forced, on the standing rule that mechanical `world check`
complaints buy at most one more draw.

### 4.2 The second seed, and the failed prediction that matters

258 records: eight rules, eight capabilities, seven cast, three criteria, seven answered
questions each with the scene it lands in. **It hit the same `--order-key` trap** — two for two
in this pilot — and left **one** permanently malformed `consequence` record where the first left
six.

**Pilot 12 recorded a prediction of ours that failed: that the documentation trap would recur,
and it did not.** This run is the counter-observation. Two independent draws hit it here, so the
honest current state is that the trap is **frequent but not certain**, three sightings out of
four seeds across two pilots — and that the *class* of defect it belongs to (a tool whose
vocabulary and checker disagree) is deterministic in the tool, where the dice cannot help.

### 4.3 The forced acceptance, and what was verified before forcing it

`world accept` without `--force` refused on exactly one record, verbatim:

    litharness: weather_money names a consequence in 'rule_weather_belongs', which is not one
    of economy, law, religion, crime, daily_life, politics, craft, war

**Three things were verified before the force, and each is mechanical:**

1. **It cannot fire the detector.** The record is alone in its slot, and
   `state.contradiction.v1` fires on two values in one slot — the failure that made every scene
   of Serial Pilot 7 undraftable. One record in one slot cannot produce it.
2. **The validator is not in the drafting path.** `worlds.validate` is called at `world check`,
   `world accept` and `world declare` only (`cli.py:2567`, `3870`, `3972-3973`;
   `application/world.py:314`). No scene draft consults it.
3. **Nothing unmanifested can reach the prose.** `world check` reports `unmanifested: []` with 28
   of 28 manifested, so no scratch identifier is owed a place on the page. This is the condition
   that killed pilot 7 and forced pilot 12's discard, and it is absent here.

**The distinction from Serial Pilot 7, stated so this entry cannot be cited as licence for the
lazy kind.** Pilot 7's force was **reflexive**, applied past scratch-probe contradictions that
the detector was right about and that did stop the book. This one is a **single verified-inert
record produced by a documented tool defect**, forced after two independent draws showed the
cause to be in the tool rather than in the draw. The two are not the same act and a future
session should not read them as one.

**The fix is the tool; the force is the workaround.** A follow-up task is filed for the
`consequence` vocabulary/checker mismatch and the `--order-key`/`--value` trap. Forcing bought
one book past a defect that a redraw cannot touch.

**What acceptance did:** 234 of 258 records promoted to canon, 24 left proposed as the strays
supersession declined to carry. Nothing was demoted; `promote_state_records` is only ever upward.

### 4.4 The post-accept state, quoted so read 7 is honest about it

    "ok": false,
    "manifested": 28,
    "needing_manifestation": 28,
    "unmanifested": []

**`world check` continues to report `ok: false` on the accepted world, and its complaint list
still contains all the standings complaints** — because `check` validates all 258 records
including the 24 that acceptance deliberately did not carry. The authoritative statement is the
one acceptance itself made: over the carried set, one complaint remained, and it is the one
quoted in §4.3.

## 5. The world, chapter 1, and a view that lies about both

The accepted world is a licensed weather trade in the vale of Ambry: eight rules each with
knock-on effects in a named domain, eight capabilities, seven cast, and seven answers on record
that nobody has been told, each with the scene it lands in.

**Three ladders resolve in canon**, which is §113's countable ordinal shape:

| criterion | rungs, lowest first |
| --- | --- |
| `charter_standing` | unlisted → watcher → tallyman → underwright → rainwright → weatherwright |
| `reckoning` | single_name → handful → score → hundred → full_round |
| `keeping_reach` | keeps_a_shower → keeps_a_day → keeps_a_season → keeps_a_place |

Corin Ashe stands at **position 1 on all three**. Six of the seven cast are placed on
`charter_standing`, four on `reckoning`, and Corin alone on `keeping_reach` — the off-charter
ladder whose cost is attention rather than power and whose ceiling nobody has seen.

**And a tool finding that a reader of this repo should have before they trust a view:
`world ladders` prints `[]` on this world.** Not because the ladders are broken — the same
function returns all three chains in full when handed canon alone — but because the view reads
every record including the 24 permanently-proposed strays, and `rank_order` gives an edge with no
criterion in its value membership of **every** ladder (`worlds.py:633-645`). Extra starting
points, so `ladder_of` returns empty for each chain, so the view returns nothing.

**Generalised, because the instance is the less useful half: supersession repairs acceptance but
not the read views.** A world can be correctly accepted and still be unreadable through the
command an operator would use to look at it, permanently, because the records that poison the
view can never be retracted. That is a reporting defect and not a world defect, and it belongs
with the follow-up task above.

**Drafting is unaffected, and this was checked rather than assumed.** The context packet filters
to canon (`extraction.py:676`, `context.py:506`), so no stray reaches a writer's prompt.

**Chapter 1 is two scenes and 1,994 words**, drafted at `--chapter-scenes 2`. Drafting stopped
there: the loop drafted the two scenes its chapter shape called for and never enqueued scene 3,
so the operator's gate on everything past chapter 1 **held by construction rather than by
remembering to stop**. The tick loop was additionally capped at eight iterations with a break on
the two-scene condition, so a misparse could not have spent on its own.

**The chapter was read once, to verify it published intact** — complete prose, both scenes with a
scene break, no truncation, no placeholders. A mechanical scan for internal identifiers returned
two hits, `handful` and `hundred`, both appearing as the world's own diegetic vocabulary in
dialogue rather than as leaked machinery, which is a rung being manifested and is what
manifestation is for. **That is an integrity check and not a verdict**; no model judged the prose
and neither does this record (§97.1).

## 6. The covers, and the one number worth repeating

Four variants, from the listing, through the pipeline pilots 11 and 12 established.

**Zero recorded calls.** `serial13b.db` reports the same spend before and after the cover run
($14.51 either side), which is `--max-cost-usd-per-day` behaving as documented — it applies only
where the provider reports cost, and the image provider reports none. §9's total is a floor for
this reason.

### 6.1 The luminance arithmetic, on the instrument read 5 used

[`reader-read-5.md`](reader-read-5.md) §4.4 measured mean luminance over the eight finished
covers then on the shelf, on a 0–255 scale, and found **the brightest cover this project had ever
produced was 53.4 — not one of the eight reaching mid-grey.** That arithmetic was reproduced here
before the new covers existed: the mean of a Pillow `L` conversion over each finished
`cover-NN.png` returns all eight of read 5's numbers **to the decimal**, so the instrument is the
same one and the comparison is not an apples-to-oranges reading of a differently-computed number.

Extending it to every finished cover on the shelf gives the baseline this set arrived against —
pilot 12's four (42.4, 41.4, 48.1, 49.6) added to read 5's eight, for **twelve covers, mean 43.3,
maximum 53.4, none at mid-grey.**

**This book's four:**

| cover | mean luminance |
| --- | --: |
| `cover-01.png` | **77.6** |
| `cover-02.png` | 59.9 |
| `cover-03.png` | 41.7 |
| `cover-04.png` | 66.3 |

**Three of the four are brighter than any cover this project had made before**, and the set's mean
is 61.4 against the prior twelve's 43.3. The darkest of them, 41.7, sits near the old mean. **No
cover reaches mid-grey (127.5) even now**, so the standing description — this project makes dark
covers — is narrowed rather than overturned.

**What this is and is not.** It is a description of one cover set, four images, arrived at by
arithmetic on pixels — never a threshold and never a quality claim (§61). Its one methodological
interest is that read 5 §4.4 corrected itself on precisely this point: a path from listing to
cover exists by construction, because the pipeline takes the listing as the art's description,
but **no dose-response along it could be read, because all eight covers came from dark listings
and the sample had no variation on the input.** This is the first cover set drawn from a listing
that is not disaster-shaped, so it is the first observation with variation on that input at all.
One point is not a dose-response either, and nothing here establishes that the listing caused the
brightness — the writer, the world and the palette all changed at once. What is now true that was
not before: the sample is no longer constant on the input.

## 7. What this says about the light-fantasy capability question, and what it does not

[`reader-read-5.md`](reader-read-5.md) §4.4 recorded a **capability question about the system** —
*can this setup produce light fantasy at all?* — after the operator corrected an earlier reading
of it: *"I didn't say Light Fantasy missing was a defect, I was just concerned we build a system
that is not capable of producing this."* **This is the first artifact that bears on it**, and
what follows is a description of what the artifacts *are*, never a claim that they are good.

**The listing and chapter are recognisably in the register the question was about.** The palette
is a market town in a dry season, cider vinegar and bruised plums, a pickle jar of grey afternoon,
four crows on an awning. The stakes are an orchard and eleven miles walked; the antagonists are a
guild wright who wants to know a method, and a bailiff who wants a boy off the square by dark. No
apocalypse, no system message, no monster, and nobody dies. The world's engine is a licensed
trade with paperwork, and its unclimbed ladder is named *keeping*. **The covers moved with it**:
§6.1 records three of four brighter than any cover this project had made, against a shelf whose
previous twelve were uniformly dark — a description of four images, with the causal path
explicitly not established.

**Three things this does not establish, each for its own reason.**

- **It is one draw.** Read 5 §4.4's two separating tests — the tonal audit of our own text, and a
  brief-versus-empty arm — are what would tell *won't, by default* from *can't, when asked*.
  Neither was run. A single light listing is consistent with both answers.
- **The cause is locatable in our own text, which is the §116 shape and cuts both ways.**
  `larkin`'s dossier says the world *"is not out to break anybody"*. So the light register was
  supplied by the writer's dossier, not discovered by the model against its grain — which
  supports read 5's reading that the earlier skew was **our text and not the model's range**,
  and equally means this draw tests the dossier path rather than the range.
- **Nothing here is measured.** No instrument read this book's tone. The paragraph above is a
  description an operator can check by reading, which is the only claim it makes.

**What can be said plainly:** before this run, every listing and every book this project had
drawn was disaster-shaped, and the roster's four compiled dossiers were threat-forward by
construction. One accepted recruit with a light dossier produced a light listing and a light
chapter on the first draw. Whether that generalises is exactly what is not known.

**And the same draw carries a second finding that cuts the other way**, which is §8: the dossier
that supplied the light register also failed to supply the house genre, because nothing but a
dossier was ever supplying it. One artifact, two results, and the second was named by the
operator rather than by us.

## 8. The house genre, named by the operator mid-run, and where it turned out to live

The operator saw the book while this run was still finishing and said, verbatim:

> *"One big problem i noticed right away with the book. It's not litrpg... we shouldn't be
> writing any books that don't have litrpg as the genre."*

**This is recorded as a §116-class direction and not as a read-7 item.** It is an operator
constraint that surfaced through an artifact rather than a defect routed by
[`reader-read-7.md`](reader-read-7.md) §3, and it arrived before the read rather than out of it.
The distinction matters for §97.1: a constraint the operator states is direction entering where
operator direction was always designed to enter, and it does not need laundering through a
harvest to be acted on.

**The book is not a failure and must not be recorded as one.** It is the draw that located the
gap, which is what a pilot is for.

### 8.1 Structure and system are different things, and this book has one of them

**The progression *structure* is all present.** Three resolving ladders, ranks worn on the body,
a countable inventory of 316 named skies with people at named positions on it, and a protagonist
at position 1 on all three chains with an unclimbed ceiling above him. That is §113's machinery
in full — the numbers go up, and they are countable.

**The LitRPG *system* is entirely absent.** There is no status furniture, no sheet, no interface
the character reads, no system voice addressing anybody. The ladders are social and institutional
facts — a guild's cuff colours, a reckoning of skies you can name — that the characters know the
way people know a professional grade, not the way a player reads a screen.

**The operator's constraint names exactly this distinction**, and nothing in this project's rule
text had drawn it before. A world can satisfy every progression check we have and still not be
the genre we publish in.

### 8.2 The house genre was never a floor; it lived in the dossiers by accident

**The measurement this run supplies:** the genre has been carried implicitly by the writers'
dossiers and nowhere else. `ferreira`'s names *"system apocalypse"*, so books drafted under it
come out LitRPG. `larkin`'s names light fantasy, market towns and weather, and carries **no
system frame at all** — so the book does not, and nothing anywhere in the pipeline required it
to. Every previous pilot drew a LitRPG book because every compiled dossier happened to be
system-shaped, not because any rule said so. The first recruit whose dossier lacked that frame
produced a non-LitRPG book on the first draw, and no gate objected.

**The pipeline said so out loud, twice, and nothing acted on it.** Both `listing --scenes 6` and
`new` printed the same advisory:

    0 seed state record(s)
    no state seeded — a LitRPG book needs a starting sheet to speak system voice

It is a message, not a gate. The tool observed the exact condition the operator later named, on
two separate databases, and the run proceeded — because there is nothing for it to fail against.
That is the gap stated as mechanically as it can be.

### 8.3 The consequence for casting, recorded as open

**`larkin` cannot cast another book until the genre floor exists somewhere real**, and neither
can any accepted writer whose dossier carries no system frame. The candidate homes are a dossier
successor mint, the system half of the recruit prompt, and a pipeline-level genre floor;
**which one is right is not decided here.** That decision is recorded as open in
[`house-genre-constraint.md`](house-genre-constraint.md), and this entry defers to it rather than
pre-empting it — a run record is the wrong place to settle a standing constraint.

## 9. Spend

**$13.17 in reported cost for this run**, and that figure is a **floor**, not a total, for the
reason pilot 12 §5 generalised: cover generation reports no cost, so a dollar ceiling passed on a
`cover` invocation constrains nothing, and every spend figure this project records is a metered
subset.

Reported as a **delta** against the baseline both databases inherited from the roster clone (18
calls, 5,906,311 tokens, $8.32 — the recruitment run's, not this book's):

| stage | database | calls | tokens | reported |
| --- | --- | --: | --: | --: |
| listing loop | `serial13.db` | 11 | 662,163 | $2.20 |
| seed 1, discarded | `serial13.db` | 1 | 4,736,440 | $4.78 |
| seed 2, accepted | `serial13b.db` | 1 | 5,931,424 | $5.50 |
| chapter 1, two scenes | `serial13b.db` | 2 | 111,995 | $0.69 |
| cover set | `serial13b.db` | — | — | **not reported** |
| **total** | | **15** | **11,442,022** | **$13.17** |

Kept by hand, because no single command totals across databases — pilot 12 §5's gap, met again
and now compounded by the clone, since the inherited baseline has to be subtracted before the
figures mean anything. **Neither ceiling bound this run**: the $40 ceiling was never approached,
and the token ceiling that parked pilot 12's chapter was carried at 20,000,000 from the first
call and never reached.

**The drafting stage cost $0.69 of the $13.17.** Two seeds are 78% of this run's spend, and the
discarded one alone cost seven times the chapter.

## 10. What is owed and was not done here

- **The house genre floor** (§8), and with it whether `larkin` may cast again. Open in
  [`house-genre-constraint.md`](house-genre-constraint.md).

- **Scenes 3–6.** Gated on the operator.
- **A real `roster export` / `roster import`**, so an accepted recruit reaches a book without a
  whole-store clone. Filed; §2 is the workaround it replaces.
- **The `consequence` vocabulary/checker mismatch and the `--order-key`/`--value` trap.** Filed.
  Three sightings of the trap across two pilots, and the mismatch cost this run a seed.
- **`world ladders` reading proposals**, so a correctly accepted world shows an empty view (§5).
- **The other three writers' fresh listings**, still owed from
  [`serial-pilot-11.md`](serial-pilot-11.md) §5.
- **The title-blind arm**, still owed from [`serial-pilot-7.md`](serial-pilot-7.md) §5.2.
- **A live test of the gate's refusing branch**, owed since pilot 12 §2.1 and not paid here
  either.
- **Read 5 §4.4's two separating tests** for the capability question (§7).

## 11. Anti-scope

No bar is declared. The word count, the coordinator density, the 4-of-4 and the cover luminances
are a description, a measurement against an already-derived ceiling, a ceilinged instrument, and
an arithmetic on pixels respectively — never thresholds (§61). Nothing here admits an axis or
promotes a research claim under `EPISTEMIC_GOVERNANCE.md`, and no stage-0 number is claimed: a §
gets claimed when something ships because of this. Nothing the operator says about this book
becomes a prompt, directive, finding or plan item (§97.1); it routes through
[`reader-read-7.md`](reader-read-7.md) §3 instead.
