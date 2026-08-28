# Serial Pilot 12 — *Patch Notes For The Apocalypse*: the first book drawn under the refusing gate

**Status: LISTING, WORLD AND CHAPTER 1 DRAWN, 2026-08-28.** Scenes 3–6 are not drafted and are
gated on the operator. The read this book was made for is
[`reader-read-6.md`](reader-read-6.md), whose §§0–3 were fixed before the book went in front of
anybody and whose §4 is empty until it has been read.

Run for the sixth operator read, under the instruction that produced the fifth: the two books on
the shelf were *"old generations"* the operator had *"already reviewed"*, so a read needs a book
made under the current architecture. Read 5 saw a listing and no chapters and asked for the
decision this run executes — chapter 1, and nothing past it.

## 0. The two readings this may not be given

**It is not a treatment comparison.** Every input differs from every other pilot's at once —
different world, different seed, a gate that did not exist for most of them. Where a counter here
sits beside pilot 7's or pilot 11's it is a description of two books (§0 of
[`serial-pilot-7.md`](serial-pilot-7.md), and the standing boundary).

**It is not a quality claim.** §61's bar is a blinded, position-swapped win rate against matched
published prose. This is one chapter, unblinded, with no comparator.

**No model ranked, selected or judged anything in this run.** Not the listing, not the world, not
the prose. §3 and §4 record the two places where a judgment call presented itself and what was
done instead of making one.

## 1. What produced it

```bash
uv run litharness --database runs/pilots/databases/serial12.db init
uv run litharness --database runs/pilots/databases/serial12.db --library book-library \
    --max-cost-usd-per-day 40 \
    listing --writer ferreira --scenes 6 --out runs/pilots/pilot12
uv run litharness --database runs/pilots/databases/serial12.db --library book-library \
    --writer ferreira --max-cost-usd-per-day 40 architect seed          # <- discarded, §3
```

`serial12.db` holds no prose and is kept as the record of the discarded seed, which is
[`serial-pilot-7.md`](serial-pilot-7.md) §1's pattern exactly: the world it seeded could not be
accepted, and the book was stood up again on a fresh database under the same listing and title,
which the loop had already written to `runs/pilots/pilot12/`.

```bash
uv run litharness --database runs/pilots/databases/serial12b.db init
uv run litharness --database runs/pilots/databases/serial12b.db --library book-library \
    new "$(cat runs/pilots/pilot12/title.txt)" \
    --premise "$(cat runs/pilots/pilot12/listing.txt)" --scenes 6
uv run litharness --database runs/pilots/databases/serial12b.db --library book-library \
    --writer ferreira --max-cost-usd-per-day 40 architect seed
uv run litharness --database runs/pilots/databases/serial12b.db world check
uv run litharness --database runs/pilots/databases/serial12b.db world accept   # no --force
uv run litharness --database runs/pilots/databases/serial12b.db --library book-library \
    --writer ferreira --chapter-scenes 2 \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 tick        # x N, §5
uv run litharness --database runs/pilots/databases/serial12b.db --library book-library \
    --chapter-scenes 2 library
uv run litharness --database runs/pilots/databases/serial12b.db --library book-library \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 \
    cover --bundle runs/pilots/pilot12/listing.json \
    --out book-library/patch-notes-for-the-apocalypse/covers
```

`--reader-checkpoints` **off**, deliberately and throughout: it cannot steer either way before
qualification, and off is the baseline.

**`--max-cost-usd-per-day` and `--writer` are top-level flags**, before the subcommand. A
sequence carrying them after it does not run. Recorded because the shape is easy to copy wrong.

**`--library book-library` on every invocation that republishes.** The flag defaults to
`book-library/` *beside the database*, so a pilot whose database lives under
`runs/pilots/databases/` publishes to `runs/pilots/databases/book-library/` unless told
otherwise — off the operator's shelf entirely.

**The writer is `ferreira`, cast by the operator and not by any model** (§84).

**Brief: empty.** The bundle's `brief` is `""`, the standing control every pilot since §136 has
kept.

## 2. The listing, the title, and what the gate did

    Patch Notes For The Apocalypse

    Every phone on Earth lit up with the same message, and monsters came out of the flooded
    stairwell under the parking garage before anyone finished reading it. Marcus tested other
    people's games for a living. So while the world argued about whether the system was real,
    he read the class descriptions the way he used to read patch notes, and found one that
    pays experience for damage taken instead of damage dealt. He wants to be the strongest
    man alive, and he wants it before anybody else learns to read the rules that way. The
    dungeon under the garage is where he starts.

**103 words.**

### 2.1 The gate measured and did not fire

This is the first book drawn since the listing loop's coordinator-density gate began refusing
(the gate's derivation, its four attainability checks and why it sits outside RS1 are stage-0
§147; the read that found the defect is [`reader-read-5.md`](reader-read-5.md) §4.1).

**The listing measured 2.91 coordinator tokens per 100 words against the gate's 5.89 ceiling.**
No refusal, no redraw: the first draw was kept. The bounded redraw budget was not spent.

So **this run says nothing about whether the gate works.** A gate that does not fire has been
exercised only in its passing branch, and the interesting branch — a refusal, a redraw, and
whether the redraw lands under the bar — remains untested against a live draw. That is the
honest state and it is worth more than a number that looks like a result.

### 2.2 Three properties of the bundle, each a fact about the file

1. **`draft` and `listing` are byte-identical.** No revision happened, which is the retired
   direct-appetite steering path's absence shown rather than asserted.
2. **`appetite_status: "experimental_observation_only"`.** The bundle labels its own appetite
   rows as what `reader-architecture-program.md` says they are.
3. **The title was looked up and is free.** `availability.verdict: "free"`, no collisions, five
   near misses recorded with their URLs. `titles_abandoned: []`, so — as in pilots 7 and 11 —
   **the retry path is still untested against a real collision.**

**Two things about this title that are descriptions and not complaints.** The nearest miss is
*Patch Notes: Apocalypse*, a Royal Road LitRPG serial by another author; the lookup returned
`free` because it is not an exact collision, and it is the closest any pilot title has come to a
live serial in the same genre on the same platform. And the title is close to this project's own
*Patch Notes For Earth*, already on the shelf. Nothing forbids either, nothing counts either.

**The browsing pool said 4 of 4 `start_reading`**, reported with §134's ceiling written across it
rather than believed — a full house is where that ceiling already was. What the four *said* is
the part specific enough to be wrong, and all four named the same thing: the damage-taken payout
class and the QA habit that finds it.

**The opening beat is `ferreira`'s standing one** — a message reaching every phone on Earth at
once. [`reader-read-5.md`](reader-read-5.md) §4.3 located the cause in the writer's own dossier,
which names an inciting beat and not only an appetite. That is a property of the writer under an
empty brief and not a defect of this draw, and it is recorded here so a read does not harvest it
as one.

## 3. Two seeds, and the one that was thrown away

**The first seed was discarded rather than forced.** It proposed 204 records and `world check`
refused them with fifteen complaints. Eleven were standings on rungs no chain declared.

**Its own written diagnosis of that failure was wrong, and that is the part worth keeping.** The
seed reported the eleven as an unfixable defect in the CLI, said it had isolated them on
throwaway ids, and concluded the records were stored correctly. Every one of those claims argued
for `--force`. The actual cause was mechanical and in the seed's own declarations: it scoped all
nine `precedes` edges with `--order-key`, which is documented as *"where in story time"*, while
`rank_order` reads a ladder's criterion from `--value`. An edge with no value belongs to every
ladder, so three chains produced three starting points, `ladder_of` returned empty for all three,
no rung counted as declared, and every standing complained.

**This trap is now twice-documented** — [`serial-pilot-7.md`](serial-pilot-7.md) §3.1.3 is the
first sighting — and it survived the vocabulary-shapes fix that was supposed to prevent it. That
is a tool finding, not a story finding, and it belongs to whoever next touches the world CLI.

**Why the world was not repaired by hand.** Two reasons, and the second is the binding one:

- `world declare` appends and has no retraction path, so the nine bad edges could not be
  withdrawn. Supersession *would* have reached them — `world accept` drops a record a later
  declaration replaced in the same slot — so the ladders alone were mechanically repairable.
- **The world also carried the seed's own scratch probes** (`zz_a`, `zz_b`, a scratch criterion
  `zz_c`, `c_probe`), and `check` listed the first two as **needing manifestation** — accepting
  that world would have asked the writer to put scratch identifiers on the page. Serial Pilot 7
  died of this class; its postmortem names the agent's scratch probes among the pairs that
  blocked every scene.

And repairing the ladders by hand would have meant **authoring world facts** — declaring that a
lanyard colour sits one rung above a notch count is a statement about the story, not a mechanical
fix. That is a judgment this run had no licence to make, so it was not made.

**The second seed, on a fresh database, came back clean**: 222 proposals, `world check` with an
empty complaint list and nothing unmanifested, and `world ladders` resolving — a seven-rung
`standing` chain and a `payout` chain. `world accept` **without `--force`** promoted 205 records
to canon and left 17 proposed, being slots a later declaration had replaced; the seed predicted
that outcome and it matched.

**A prediction of ours failed here and the failure is recorded rather than quietly dropped.**
Before spending on the second seed it was argued that the `--order-key` trap would probably
recur, on the reasoning that a documentation trap is deterministic and a fresh draw reads the
same help text. It did not recur. So seed 1's failure was a property of that draw and not a fixed
property of the Architect's interaction with the tool — which changes what a tool fix has to
target, and would have been invisible had the prediction gone unrecorded.

## 4. The world, and chapter 1

The accepted world holds ten rules each with a consequence in a named domain, twelve
capabilities, four cast, ten mysteries that each record their answer and the scene it lands, and
three criteria. Its engine is that a class is paid for exactly the thing its own description
names, priced against how close a wound came to killing the person.

**Chapter 1 is two scenes and 1,925 words**, drafted at `--chapter-scenes 2`. Drafting stopped
there: the loop's stop condition was two scenes drafted and the queue drained, and it never
enqueued scene 3. The operator's gate on everything past chapter 1 held by construction rather
than by remembering to stop.

**The chapter was read once, to verify it published intact** — complete prose, both scenes with a
scene break, no truncation, no placeholders, no internal identifiers on the page. That is an
integrity check and not a verdict; no model judged the prose and neither did this record (§97.1).

## 5. Five operator-surface gaps this run hit, none of them about the book

Recorded because each is a property of the machinery that the documented recipe does not warn
about, and three of the four fail quietly.

**The daily *token* ceiling parked the first chapter, and cost was never the binding
constraint.** The Architect seed spent 4,931,787 of the 5,000,000 **default** daily token
ceiling, so the scene-2 draft was refused before it made a call: *4983966 tokens spent today plus
a projected 34953 would exceed the daily ceiling of 5000000*. The pilot recipe specifies
`--max-cost-usd-per-day` on every paid invocation and this run carried it; at $4.83 for 4.93M
tokens the two guards are calibrated for different regimes and the token one bites first. The fix
applied was to raise `--max-tokens-per-day` for drafting while leaving the operator's cost
ceiling untouched at 40, on the reasoning that the dollar ceiling is the guard the operator
actually set and the token ceiling is a library default. **The good half is that it parked
without spending** — the guard refused the call rather than making a degraded one. Anyone
following the documented sequence hits this whenever a seed and a draft share a day and a
database.

**The drafting shape and the packaging shape are separate flags that must agree, and disagreeing
fails silently.** `library` run without `--chapter-scenes 2` packaged the book against the
default of 4 and reported *0 pastable chapter(s), 2 chapter(s) withheld*: two scenes do not
complete a four-scene chapter, so the reading copy had no chapters in it. **No error, no
warning** — a person following the recipe gets an empty book and no clue why. Republishing with
the shape the book was drafted under produced `Chapter1`.

**Spend has no cross-database view.** `status` reports per database, so a pilot that hops
databases — as this one did, `serial12.db` → `serial12b.db` — loses its budget view. The $40
ceiling was enforced against a total no single command shows, and the total in §6 was kept by
hand.

**Cover generation is not metered at all, so the dollar ceiling does not cover it.** The cover
run made **zero recorded calls**: `serial12b.db` reports the same spend before and after it. That
is `--max-cost-usd-per-day` behaving as documented — it *"applies only where the provider reports
cost"* — and the image provider does not report any. The consequence is worth stating plainly
rather than leaving implicit in a help string: **a dollar ceiling passed on a `cover` invocation
constrains nothing.**

**Generalised, because the instance is the less useful half:** a ceiling that silently constrains
nothing on the one call class that reports no cost means **every spend figure this project has
ever recorded is a floor and not a total** — including §6's, and including every earlier pilot's.
The gap is not that this run's covers were unpriced; it is that a number named "spend today"
answers a narrower question than its name, and nothing at the call site says so. Any decision
made by comparing two pilots' recorded costs has been comparing metered subsets.

**Quiet-minutes inference is dead as a box-clear signal.** A watcher judged the box clear on five
quiet minutes and released a full handoff gate — lint, types, full suite with coverage, wheel,
leak audit — into the window where this pilot was between paid stages. The pilot's free work
(store reads, greps, read-only `world check`) is invisible to a process-list watcher, so a
mid-run pilot looks identical to a finished one. The gate was abandoned on report and the seed
that overlapped it was verified afterwards against its exposure window rather than assumed
clean — exit status, full scale against the seed-1 and pilot-7 band, clean `check`, resolving
ladders, and an empty transport-failure scan. **Explicit gos only**, and a paid stage announces
its own start and end.

## 6. Spend

**$11.90 in reported cost**, and that figure is incomplete in a way §5 names:

| database | reported | what it bought |
| --- | --: | --- |
| `serial12.db` | $6.44 | the listing loop, and the seed that was discarded |
| `serial12b.db` | $5.46 | the second seed, and the drafting ticks |
| — | **not reported** | the cover set: zero recorded calls, no cost returned by the provider |

Kept by hand, because no single command totals across databases. The $40 ceiling was never
approached on the metered side and **did not apply at all** to the covers. The token ceiling, not
the dollar ceiling, is what actually bound this run.

## 7. What is owed and was not done here

- **Scenes 3–6.** Gated on the operator.
- **The other three writers' fresh listings**, still owed from
  [`serial-pilot-11.md`](serial-pilot-11.md) §5. One `listing` loop per writer.
- **The title-blind arm**, still owed from [`serial-pilot-7.md`](serial-pilot-7.md) §5.2. This
  listing was screened **with** its title (`title_shown_to_readers: true`).
- **A live test of the gate's refusing branch**, now owed by §2.1.
- **The world CLI's `--order-key`/`--value` trap**, twice-documented and unfixed.

## 8. Anti-scope

No bar is declared. The word count, the density and the 4-of-4 are a description, a measurement
against an already-derived ceiling, and a ceilinged instrument respectively — never thresholds
(§61). Nothing here admits an axis or promotes a research claim under
`EPISTEMIC_GOVERNANCE.md`, and no stage-0 number is claimed: a § gets claimed when something
ships because of this. Nothing the operator says about this book becomes a prompt, directive,
finding or plan item (§97.1); it routes through [`reader-read-6.md`](reader-read-6.md) §3
instead.
