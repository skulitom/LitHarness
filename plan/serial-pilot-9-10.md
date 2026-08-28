# Serial Pilots 9 and 10 — the third seed, and the listing surface nobody wrote down

**Status: RECORD, written 2026-08-28 for runs of 2026-08-25 and 2026-08-26.** Neither run had a
document. Pilot 9's existence was recorded only inside another pilot's section
([`serial-pilot-7.md`](serial-pilot-7.md) §3.1, "third seed"), and pilot 10 lived entirely in an
untracked run folder. This file is the provenance a read needs: what produced each artifact,
which prompt arm each listing came from, and what was never measured. It declares no result.

**These are not treatment comparisons.** Every input differs between pilot 9 and any other book
at once. Pilot 10's four arms *are* a designed 2x2 over one prompt, and §5 says exactly how far
that goes and where it stops.

## 1. Pilot 9 — *Patch Notes For Earth*

| | |
| --- | --- |
| store | `runs/pilots/databases/serial9.db` |
| listing loop output | `runs/pilots/pilot9/` — `listing.json`, `listing.txt`, `title.txt` |
| reading copy | `book-library/patch-notes-for-earth/` |
| writer | `ferreira` |
| brief | **empty** — the bundle's `brief` field is `""`, so the listing was drawn under *"anything you would most want to read"* |
| title | *Patch Notes For Earth*, shown to the readers (`title_shown_to_readers: true`) |
| listing | 112 words; the published `overview.txt` is the loop's revised listing, byte for byte |

**What produced it.** The same evening as pilot 7's second seed, and it is that pilot's §3.1
"third seed": a listing loop, an Architect seed, `world accept`, then drafting ticks. Its store
records the drafting window as 19:31 to 20:01 on 2026-08-25, with four scene summaries, 256 state
records and one plan revision.

**It is two chapters because it is four scenes.** `serial9.db` holds six scene nodes and only
four carry prose; scenes 5 and 6 are empty. At `--chapter-scenes 2` that publishes as
`Chapter1` and `Chapter2` and stops. Nothing in the store says the run was ever told to finish —
it stopped, and the record does not say why. **Do not read the two chapters as a length
decision.**

**What was never measured.** Its eight `reader_reads` rows are one continuation screen taken at
20:02 and carry §134's ceiling; no arm, no comparison, no counters against the market were run
on this book. It has no cover set of its own beyond what `library` publishes, and no operator
read was recorded for it as a `reader-read-*.md`.

**Its world carries the probe leak.** [`serial-pilot-7.md`](serial-pilot-7.md) §3.1 measured it
here and it belongs in this record too: this world's eleven-rung clearance ladder has `rung_a`,
`rung_b`, `rung_c`, `zz_one`, `zz_two` and `zz_three` chained above `clearance_4` — the
Architect's own scratch vocabulary, inside the one structure §113 built so the genre's numbers
could not be faked. The protagonist stands at rung two, so two chapters never climb into it. The
leak is latent, not realised, which is the worst way for a defect to sit.

## 2. Pilot 10 — sixteen listings under a 2x2, and one loop run

| | |
| --- | --- |
| store | `runs/pilots/databases/serial10.db` — **0 revisions, 0 events, 0 scene nodes** |
| output | `runs/pilots/pilot10/` — `overviews.md` (the sixteen plus the loop), `listing.json`, `listing.txt`, `title.txt` |
| reading copy | **none. No book was drafted.** |
| written | 2026-08-26, 01:09 to 01:11 |

**`serial10.db` is an empty database.** It holds no book, no scene and no revision. Pilot 10 is a
prompt experiment over the listing call and nothing else; the store exists because the command
needs one.

**The 2x2.** Two clauses varied independently over the listing prompt, four writers drawn under
each of the four cells, every draw fresh and under an empty brief:

| arm, as `overviews.md` labels it | genre-noun clause | two restored `house.CLARITY` clauses |
| --- | --- | --- |
| **`genre_clarity` — SHIPPED** | kept | restored |
| clarity clauses only | removed | restored |
| base (what shipped before that day) | kept | not restored |
| genre clause removed | removed | not restored |

**The shipped arm is `genre_clarity`.** Its four listings — halloran 114 words, vance 98,
okonjo 105, ferreira 112 — are the current listing surface, and are what the fifth read's
commissioning brief (since retired) meant by it; the operator later took them out of the read
package — *"Let's generate everything from scratch"* ([`reader-read-5.md`](reader-read-5.md)).

**The seventeenth listing is a full loop run**, `ferreira` with `--rivals`, title *Read The
Patch Notes*, availability *free*. `overviews.md` carries its draft and its revision and the
one clause the steering readers' appetite added — *and the edit costs the writer a rule of his
own* — with the file's own note that none of the readers' vocabulary came across. `pilot10/`'s
`listing.txt` and `title.txt` are that run's, not any of the sixteen.

**What was never measured.** The counters `overviews.md` reports per listing are word count,
genre nouns and longest sentence, against 42 published RoyalRoad serials above 1,000 followers.
No arm was run against any other arm on anything but those counters; nothing here is a
preference, a ranking or a quality claim, and §137 is why no comparison between the four writers
exists at all. No operator read was recorded.

## 3. *Reappraisal*'s provenance is not lost — it is Serial Pilot 1

The fifth read's commissioning brief (since retired per the house rule on completed handoffs)
inventoried *Reappraisal* as provenance "unrecorded in `plan/`" and asked for it to be found or
the book excluded. **The premise is wrong and the book stays.** *Reappraisal* is the Serial Pilot 1 book, documented at
length in [`plan/serial-pilot-1.md`](serial-pilot-1.md) — whose title line is literally *"Serial
Pilot 1 — 'Reappraisal': the operator package"* — with its preflight in
[`serial-pilot-1-preflight.md`](serial-pilot-1-preflight.md). Its store is `serial.db`, the only
database on this box holding a book by that name, and the directive text quoted throughout
`serial-pilot-1.md` (the loop rule, the `[STATUS] Silas` voice, the register clause) is that
book's. It has no `overview.txt` because it predates the listing loop entirely: pilot 1 was
seeded from operator directives, not from a written listing, which is the whole difference
between it and pilots 7 to 11.

This is the second premise in that handoff to turn out wrong on inspection, after the tribunal's
"complete-looking run" (stage-0 §145). Recorded here rather than corrected silently.

## 4. What the four writers do under an empty brief, which nothing counts

**A description of the artifacts on disk, not a result.** It is not registered, no bar is
declared, and it is written down here because it is checkable and because it survived being
looked for. Every listing each writer has produced under an **empty brief** opens on that
writer's single premise:

| writer | listings on disk | what every one of them opens on |
| --- | --- | --- |
| `ferreira` | 7 — pilot 10's four arms, pilot 10's loop run, pilot 9's book, pilot 11's book | a message arriving on every screen or phone on Earth in the same second |
| `halloran` | 5 — pilot 10's four arms, pilot 7/8's book | a thing in a dark stairwell that takes the light |
| `vance` | 4 — pilot 10's four arms | a thing out of the dark that should have killed the narrator and did not |
| `okonjo` | 4 — pilot 10's four arms | a sect entrance or practice duel decided by a forbidden breathing form |

Two of halloran's four pilot-10 listings open with the same five words, *"The thing in the
stairwell"*. Pilot 9's title is *Patch Notes For Earth*, pilot 10's loop title is *Read The
Patch Notes*, and pilot 11's is *The Unkillable Exploit*.

**The part that bears on pilot 10 specifically:** the 2x2 moved the counters it was built to
move — genre nouns from 6 to 0, longest sentence from 38 to 21 — and **moved no writer off its
premise in any cell**. Whatever a listing is about is decided somewhere the two varied clauses
do not reach. §136 already measured the other side of this: two words of brief outweighed every
rule in the prompt. These four columns are what the *absence* of a brief produces.

**Where this goes, and where it does not.** ~~It routes to the reader-architecture programme's
battery families as an instrument question — does an admitted damage family cover premise
repetition across draws?~~ **Corrected 2026-08-28 by [`reader-read-5.md`](reader-read-5.md)
§4.3, which found the cause without needing a new instrument:** each writer's dossier in
`domain/writers.py` **names an inciting beat and not only an appetite**, and each writer draws
that beat every time — `ferreira`'s dossier says *"everybody finds out at the same moment"* and
*"the first message nobody asked for"*, and `halloran`'s says *"people who wake up somewhere
impossible"*. So this is a **direction gap whose cause is our own instruction text**, the §116
shape, and what to do about it is a roster act belonging to the operator
(`plan/writer-roster.md`).

`writers.py`'s own docstring records the *previous* version of this defect — the first cast named
four real careers and *"each writer promptly set a book inside their own day job"*. Making the
dossier's variable appetite rather than profession fixed that leak and reproduced it one level
up, as a fixed opening beat.

What is unchanged: it does **not** route to a new ad-hoc metric (`BRIEF.md` before anything is
proposed), and it does **not** route to a prompt clause — §127, §135 and §138 are the three
entries on what clause-adding costs, and this is the failure mode a fifth rule is reliably
useless against.

## 5. Anti-scope

Nothing here is a quality claim, a comparison between writers, or a preference. The counters in
`overviews.md` are distributions against the market's, never bars (§61); §137 leaves any
between-writer comparison with no key; and §4 above is a description of text on disk with its
own epistemic status stated in its first line. No number in this file is restated from anywhere
else — pilot 7's findings stay in `serial-pilot-7.md`, the refutation count stays in `BRIEF.md`,
and the decisions stay in `plan/stage-0-decisions.md`.
