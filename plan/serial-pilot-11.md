# Serial Pilot 11 — *The Unkillable Exploit*: the first listing no retired path ever touched

**Status: LISTING DRAWN, 2026-08-28. Chapters gated on the operator.** Run for the fifth
operator read ([`handoff-operator-read-5.md`](handoff-operator-read-5.md), as corrected the same
day): the two books on the shelf are *"old generations"* the operator has *"already reviewed"*,
so the read needs a book made under the current architecture. This is that run, stopped after
its cheap half on the operator's instruction — *"let's generate an overview first, not overspend
on chapters. From the overview i'll probably know if we should spend more."*

## 0. The two readings this may not be given

**It is not a treatment comparison.** Every input differs from every other pilot's at once. A
counter here beside pilot 7's or pilot 9's is a description of two books (§0 of
[`serial-pilot-7.md`](serial-pilot-7.md), and the standing boundary).

**It is not a quality claim.** §61's bar is a blinded, position-swapped win rate against matched
published prose. This is one listing.

**What it *is* architecture-honest about is narrow and checkable**, and it is the only reason
this run exists rather than a re-read of what was on the shelf: nothing in its history touched
the retired direct-appetite steering path (§128's *a steered book leaves §61's measurement set
for good* has nothing to bite on here), it ran post-§139.3, and the editorial control plane was
present and inert throughout. The proof is in §2, not in this sentence.

## 1. What produced it

```bash
uv run litharness --database runs/pilots/databases/serial11.db init
uv run litharness --database runs/pilots/databases/serial11.db --max-cost-usd-per-day 40 \
    listing --writer ferreira --scenes 6 --out runs/pilots/pilot11
uv run litharness --database runs/pilots/databases/serial11.db --max-cost-usd-per-day 40 \
    cover --bundle runs/pilots/pilot11/listing.json \
    --out book-library/the-unkillable-exploit/covers
```

`--reader-checkpoints` **off**, deliberately: it cannot steer either way before qualification,
and off is the baseline that makes the honesty claim above cheap to check.

**The writer is `ferreira`, cast by the operator and not by any model** (§84). Asked to pick from
the four unranked, the operator answered *"This is micromanagement, we really want to avoid such
decisions. I don't know, i haven't liked any book yet, the best one so far was ferreira"* — which
is a cast and a standing instruction at once. §4 is the part of this record that the second half
of that sentence bears on.

**Brief: empty.** The bundle's `brief` is `""`, so the listing was drawn under
`overview.render_overview_request`'s *"anything you would most want to read"*, the same control
every pilot since §136 has kept.

## 2. The listing, the title, and the three things the bundle proves

    The Unkillable Exploit

    Every screen on Earth lit with the same message in the same second, and the message said
    that killing the things now coming through would make a person stronger. Then the doors
    opened, in car parks and stairwells and drained swimming pools, and the monsters climbed
    out.

    Ravi maintained inventory software before any of this, so he reads a magic system the way
    he reads any bad interface, hunting for what it never checks. The system pays for kills.
    He finds ways to get paid that involve no killing at all, and he means to be strong enough
    to matter by the time somebody notices and shuts them.

**108 words**, against the market's 40–146 and median 100.

Three properties of `runs/pilots/pilot11/listing.json`, each a fact about the file:

1. **`draft` and `listing` are the same 108 words.** No revision happened. The steering readers
   were asked and their appetite is on the bundle, and the text did not move — which is the
   retired path's absence shown rather than asserted. Pilot 7 §2.1 is what this used to look
   like when the path was live: three clause-level changes, each traceable to a reader sentence.
2. **`appetite_status: "experimental_observation_only"`.** The bundle labels its own appetite
   rows as what `reader-architecture-program.md` says they are.
3. **The title was looked up and is free.** `availability.verdict: "free"`, no collisions,
   eleven near misses recorded with their URLs (three Royal Road serials carrying *Unkillable*,
   one carrying *Exploit*). `titles_abandoned: []`, so — as in pilot 7 — **the retry path is
   still untested against a real collision.**

**The browsing pool said 4 of 4 `start_reading`**, and that number is reported with §134's
ceiling written across it rather than believed: continuation and browsing have returned 13/16,
15/16, 15/16, 16/16, 16/16 and 4/4 across earlier rounds, so a full house is where the ceiling
already was. What the four *said* is the part specific enough to be wrong, and all four named the
same thing — the exploit-hunting stance rather than the apocalypse: *"reads the system like a bad
interface and hunts for what it doesn't check"*, *"debugs the magic system instead of grinding
it"*, *"reads a magic system like a bad API and gets paid without killing anything"*.

## 3. The book object, and what is not drafted

`listing --scenes 6` created the book from the title the loop had just written: book
`7ef3abea`, branch `1e6c844f`, **six empty scenes**, template `template.arc-6.v0`. No Architect
seed has been run, so the world does not exist; no scene carries prose; `serial11.db` holds zero
revisions.

The loop's own closing line is a finding and is recorded rather than fixed: **`0 seed state
record(s)` — *"no state seeded — a LitRPG book needs a starting sheet to speak system voice"*.**
That is the loop telling the truth about a book that has had no `architect seed` yet. Whether
the sheet arrives is the next spend, not a defect in this half.

**What the remaining spend would be**, if the operator wants chapters: `architect seed`, then
`world accept`, then drafting ticks at `--chapter-scenes 2` until six scenes, then `library`.
Pilot 7 §3.2 priced one seed at ~$10.69; a repair seed doubles that. Nothing above has been run.

## 4. The finding the operator's own sentence points at

*"i haven't liked any book yet"*. Here is one mechanical thing that is true of every listing this
roster has drawn under an empty brief, recorded in
[`serial-pilot-9-10.md`](serial-pilot-9-10.md) §4 with the full table: **each writer opens on one
premise, every time.** This listing is `ferreira`'s seventh, and all seven open on a message
arriving on every screen or phone on Earth in the same second — pilot 9's book, pilot 10's four
prompt arms, pilot 10's loop run, and this one.

So *The Unkillable Exploit* is a fresh draw and is **not a fresh premise**. That is not an
argument against reading it; the second paragraph is where it diverges, and no earlier ferreira
listing has the get-paid-without-killing turn. It is a fact the operator should have before the
read rather than after it, because "I have read this opening before" is exactly the kind of
reaction a read would otherwise harvest as a defect of *this book*, when the record says it is a
property of the writer under an empty brief.

Routing, per the handoff's task 5: **instrument question**, not a direction gap and not an
enforcement defect. Nothing forbids a writer reusing its own premise, nothing asked it not to,
and nothing counts it. It goes to `reader-perception-research.md`'s battery families as a
question about whether an admitted damage family covers cross-draw premise repetition — and
explicitly **not** to a new metric (`BRIEF.md` first) and **not** to a prompt clause (§127, §135,
§138).

## 5. What is owed and was not done here

- **Chapters.** Gated on the operator, above.
- **The other three writers' fresh listings.** The operator asked to *"generate everything from
  scratch"* for the read surface; only `ferreira`'s has been drawn, because the same instruction
  said not to overspend before the overview was seen. One `listing` loop per writer.
- **The title-blind arm**, still owed from pilot 7 §5.2 and still for the same reason: the flag
  (`--no-title-to-readers`) exists and the fresh listings a side have never been drawn. This
  listing was screened **with** its title (`title_shown_to_readers: true`).

## 6. Anti-scope

No bar is declared. The word counts and the 4-of-4 are distributions and a ceilinged instrument
respectively, never thresholds (§61). §4 is a description of text on disk, unregistered, and
promotes nothing under `EPISTEMIC_GOVERNANCE.md`. Nothing the operator says about this book
becomes a prompt, directive, finding or plan item (§97.1); it routes through
[`reader-read-5.md`](reader-read-5.md)'s standing question instead.
