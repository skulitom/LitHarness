# Serial Pilot 2 — the same two chapters, on a world nobody typed

**Status: PACKAGE, 2026-08-21.** Companion to [`plan/serial-pilot-1.md`](serial-pilot-1.md) and
to [`plan/world-architect.md`](world-architect.md); the decision record is
[stage-0 §107](stage-0-decisions.md).

## 0. What this pilot is for, and the one thing it may not be read as

**One difference from Serial Pilot 1, and everything else held.** Pilot 1's seed was fifteen
records the operator typed into `plan/serial-pilot-seed.json` and eight directives written by
hand. Pilot 2's world comes out of `litharness forge`: K worlds in one structured call, gated
deterministically, and one of them chosen by a person. Scene count, chapter shape, target words,
context budget, provider and craft constraints are the same.

**It cannot support a quality claim and no reading of it may make one.** Two chapters is not a
sample; §61's bar is a blinded position-swapped win rate against matched published prose and
nothing here is that. What this pilot answers is narrower and worth the money: **does a forged
world survive contact with the loop** — does it reach the packet, does the writer honour it, does
the integrity gate stay quiet, and does a scheduled reveal land where it was scheduled. Every one
of those is structural.

Pilot 1's §0 said the same thing about itself and it is repeated here rather than referenced,
because a package that assumes its reader has read the previous package is how a bar gets quietly
relaxed.

---

## 1. The world, and how it was chosen

Recorded rather than described, because the choosing is the part that must stay auditable.

- `litharness forge "" --k 3 --shape direct --out pilot2/direct2 --scenes 8` — one structured
  call, an **empty brief**. Empty is deliberate: a world built from no direction at all is the
  control a directed forge would be read against, and there is no directed forge yet.
- Three worlds came back. All three cleared the collapse gate — pairwise distinct real domains,
  pairwise distinct geometries — and the per-candidate gates reported per world.
- `litharness forge --out pilot2/direct2 --pick <n>` recorded the choice as its own policy
  decision with `VerdictSource.HUMAN`, and wrote `seed.json`, `directives.json` and
  `promises.json`.

**The pick was made by an arbitrary rule and not by taste, and that is a limitation of this run
rather than of the design.** The rule was: *the first candidate, in the order the model returned
them, that clears every gate.* It is arbitrary on purpose — it orders nothing and prefers nothing
— because the operator's act had not happened and a stand-in that exercised judgment would have
substituted one taste for another while looking like the real thing. When the operator does pick,
that is a different decision row and a different pilot.

### 1.1 What came back, 2026-08-22

One call, `claude-opus-5`, 98,332 tokens, **$1.53**. Three worlds, all three clear of every gate,
within-forge spread **0.9302**.

| # | title | real domain literalised | geometry | records | edges | rules | manifestation | answers |
|---|---|---|---|--:|--:|--:|--:|--:|
| 1 | **First In Time** | Western water law and hydrology — prior appropriation, beneficial use, forfeiture, curtailment, conjunctive groundwater management | chain | 327 | 76 | 7 | 1.00 | 28 |
| 2 | Borrowed Hands | transplant immunology and surgical grafting — tissue typing, crossmatch, cold ischemia, the law of donated remains | graph | 345 | 79 | 7 | 1.00 | 31 |
| 3 | The Traverse | land surveying and geodesy — traverse and closure, error propagation, monuments controlling over courses | estimate | 324 | 72 | 6 | 1.00 | 27 |

**Candidate 1 was picked by the arbitrary rule.** *First In Time*: a valley where the river
answers a **date**, seniority is written in one book in one town, and a right dies after five
years without a recorded use — so the only ladder available to the protagonist is built out of
other people's vacancies. Progression is a position in a chain, a rank is a thing you wear or
conspicuously do not, and no fight settles anything: every reversal is administrative.

Six mysteries, each with its answer already in canon and a scene attached: two land inside the
eight scenes being written (s4, s7) and four are arc debts at 26, 41, 63 and 92.

**A limitation this run exposed and did not fix.** The collapse gate is *within*-forge. An
earlier forge under the `domain_first` shape produced a land-survey-and-geodesy world; this one
produced another. Two forges can converge on a domain and nothing here notices, because nothing
compares a forge against the ones before it. Recorded rather than patched: a cross-forge memory
is a different object with its own failure modes, and the operator reading K worlds is the
control that currently catches it.

---

## 2. The directives, and which of them belong to the world

Two sets, issued in this order, and the split is the point.

**The world's own**, from `pilot2/direct2/directives.json`, written by the Architect and stamped
`architect:<id>`. These say what is true and how it shows: the system's voice, what a rank looks
like at the wrist, what may never be stated without its doubt beside it.

**The standing craft constraints**, from
[`plan/serial-pilot-2-craft.json`](serial-pilot-2-craft.json). These belong to the project rather
than to any world, and they came from a human reading real prose
([`plan/reader-read-2.md`](reader-read-2.md)), which is one of only two ways an axis enters this
project at all. Six of them:

| id | carried |
|---|---|
| C3 originality / RS1 | verbatim |
| C5 openings | verbatim |
| C6 introduction budget | verbatim |
| C7 the phrase | **edited** — its illustrative noun stack was Reappraisal's own assay house, and another world's vocabulary in every prompt is exactly what C3 forbids. The rule is unchanged; the example moved. |
| C8 register | verbatim |
| C4 price on the page | **rewritten** — pilot 1's wording named that world's Skills, its Appraisal and its System. Same rule, no nouns. |

Both edits are recorded in the JSON beside the text they changed. **A directive is read into every
prompt**, so a world-specific noun inside a project-wide rule is not a cosmetic problem.

---

## 3. Standing it up

```powershell
.\tools\serial-pilot-2-setup.ps1 -Forge pilot2\direct2 -Scenes 8
```

It refuses rather than proceeds on every precondition Serial Pilot 1 learned the hard way: an
existing database (a second book makes every unscoped directive ambiguous and the planner then
materialises none of them), `LITHARNESS_ENV=test`, `LITHARNESS_FAKE_PAD_CHARS`, a missing `claude`
on PATH, and a forge directory where `--pick` has not been run. It draws no prose and makes no
provider call.

Then the two phases, unchanged from pilot 1 — direction first, gated, before a paid call is spent
on prose:

```powershell
.\tools\run-loop.ps1 -Database serial2.db -Ticks 14 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial2.db --phase directives `
  --spec pilot2\direct2\directives.json --spec plan\serial-pilot-2-craft.json
```

**`--context-budget 16000` is not optional here and pilot 1's default would have been wrong.**
Measured on *this* world, 329 records:

| | facts | hidden | prior prose | omitted | tokens |
|---|--:|--:|--:|--:|--:|
| scene 1, budget 16,000 | 229 | 20 | 0 of 0 | **0** | 6,731 |
| scene 8, budget 16,000 | 231 | 18 | **7 of 7** | **0** | 13,031 |
| scene 8, budget 6,000 | 139 | 18 | **0 of 7** | 99 | 4,499 |

The world is a flat ~46% of a 16,000-token packet's usable budget from scene one and does not
grow; prose does. **At the 6,000 default the same world drops every prior scene and 92 facts** —
and note what survives: all 18 hidden claims, because the iceberg packs above the ordinary facts.
That ordering was itself decided by a measurement (stage-0 §107.9.1 defect 4); before it, the
6,000 budget kept 183 facts and **no hidden claims at all**.

Only when the early gate is green:

```powershell
.\tools\run-loop.ps1 -Database serial2.db -Ticks 48 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial2.db `
  --spec pilot2\direct2\directives.json --spec plan\serial-pilot-2-craft.json
```

`--spec` is repeatable and **pilot 2 needs both**: the gate sums the counts, and one spec alone
would report the inbox short by the size of the other — a false alarm is how an operator learns
to ignore a gate.

---

## 4. What is pre-registered, before the loop runs

Numbered so a later reading cannot quietly become a different question. Every one is structural;
none is about whether the prose is good.

| # | question | how it is answered | what would falsify the build |
|---|---|---|---|
| **S1** | does the world reach the writer at all | the drafting prompt for scene 1 carries the world's rules, its criterion brief and its undisclosed claims | a packet whose `facts` hold no `world_rule`, or a system message with no criterion line |
| **S2** | does the writer honour what it may not state | no undisclosed claim's content appears in the prose of a scene before its reveal | an answer stated on the page ahead of its scheduled scene |
| **S3** | does a scheduled reveal land | the claim scheduled inside the eight scenes is disclosed at or before its scene | the reveal never happens, or happens in a scene that is not near its window |
| **S4** | does the integrity gate stay quiet on a forged world | `state.contradiction.v1` and `state.cardinality.v0` findings per accepted scene | a blocking finding on a world the gates already cleared, which would mean the forge produces canon the loop cannot honour |
| **S5** | does the ledger settle anything | promises paid, out of the ones seeded with an answer | 0 paid again, which would mean seeding the answer was not the missing half |

**S5 is the one with a measured prior and it is not flattering.** 40 opened and 0 paid on the live
serial; 32 and 0 before it. The difference this time is that the debt exists before scene one and
its answer is in canon. If it still pays nothing, the answer was never the binding constraint and
the finding is worth more than a success would be.

**S2's honest limit, and the first version of its probe was worse than the limit.** "No
undisclosed content on the page" is reported by `serial_pilot_check.py`'s disclosure block, which
looks for the recorded answer's **coined** nouns in the prose. The first version compared ordinary
content words and reported shares of 0.20 to 0.59 on a book that had leaked nothing — every one of
them driven by *because*, *being*, *every*, *water* and *basin*. That is a shallow metric wearing a
finding, and this repository already owns the case (`opening_proper_nouns`, 68.5th percentile). So
the block is a **note and never a check**: a coined name on the page is not the secret being told,
and deciding from prose that a hint has gone too far is exactly the judgment this project has no
instrument for.

---

## 5. Anti-scope

No quality claim, no comparison against pilot 1's prose, no reader consultation, and no
acceptance read spent unless `serial_pilot_check.py` exits zero. The world is not amended
mid-run: there is no amendment surface and inventing one under time pressure is how an
unmeasured lever gets in. Nothing here admits an axis, promotes a counter or moves a licence.
`plan/world-architect.md` §9's anti-scope stands whole and this adds to it rather than relaxing it.

---

## 6. The run, as it happened

**Two runs, and the first one's defect is why there are two.** Run A drafted all eight scenes and
then a probe of its own canon showed that its reveal schedule had been inverted; run B is the same
world, the same directives and the same commands with the schedule corrected. Both are recorded,
because run A is the evidence.

### 6.1 Run A, 2026-08-22 — eight scenes, and the iceberg upside down

`serial2.db`. **72 ticks, 46 jobs, all succeeded; 21 policy decisions, every one ACCEPT; 12
provider invocations, 743,603 tokens, $5.67.** Eight of eight scenes drafted, **7,579 words**, 9
revisions all rebuilding cleanly and none unattributed, 0 parked and 0 poisoned.

| # | question | answer |
|---|---|---|
| **S1** | does the world reach the writer | **yes.** Scene one's frozen prompt carries 231 facts, 18 hidden claims, 6 owed threads and 14 locked constraints, at **9,037 tokens** of a 16,000 budget; the system message carries both criteria with their ladders (`cr_priority: ordinal — k_no_date then k_junior_date then k_working_date then k_senior_date then k_first_water`). **`context_omitted = 0` across the whole book.** |
| **S2** | does the writer honour what it may not state | **not answerable on this run**, because S3 failed: five of the six answers had been moved into the ordinary facts, so most of what the writer was forbidden to state it had been told it could rely on. |
| **S3** | does a scheduled reveal land | **no, and the failure is the finding.** The Architect minted `s04`, `s41`, `s92` against a book whose beats are `s1…s8`; `order_key` compares lexicographically, so `"s1" > "s04"`. **Both answers the opening existed to keep were handed over as established fact from scene one**, and by scene eight five of six had been. Stage-0 §107.9.1 defect 10. |
| **S4** | does the integrity gate stay quiet | **yes.** 5 findings on the whole book, **all five `promise.overdue.v0` MINOR** and every one of them defect 9's artefact — the four arc debts clamped to the last beat. Zero `state.contradiction.v1`, zero `state.cardinality.v0` against three declared shapes, zero duplicate-scene. 21 of 21 decisions ACCEPT. |
| **S5** | does the ledger settle anything | **no. 41 opened, 0 paid** — 6 seeded with their answers and 35 opened by the summariser out of the prose. The prior was 40/0 and 32/0; seeding the answer did not move it, and on this run S3 explains why the seeded six could not have been paid. **Whether the answer was ever the binding constraint is now the open question**, and that a null result is worth more than the success would have been is the reason it was pre-registered. |

**What the prose did with the world, read rather than counted.** The opening enforces a water call
against a sympathetic neighbour from the side of the person turning the wheel, exactly as the
world's own `chapter_note` asked; the ladder appears as two spoken dates — *"Fourteen sixty-one."*
against *"Mine's eighty-eight."* — and the doctrine is never explained, which is what the world's
first forged constraint demands. The bestiary shows up as one clause about moths coming off a wet
row. That is the register the whole design is for, and it is an observation and not a measurement.

**One incidental property, found by running two books at once.** `library.slugify` names a shelf
from the **title alone**, so two books called *First In Time* in one library root share
`book-library/first-in-time/` and the later publish overwrites the earlier reading copy. Nothing
is lost — revisions are immutable and `litharness export` reproduces either — but a second run of
the same world needs its own root or its own export, and this pilot took the export
(`pilot2/runs/first-in-time-runA.md`). Recorded rather than fixed: the id is already the fallback
when a title is unusable, and making it a discriminator when a title *collides* is a library
change with its own compatibility question.

### 6.2 Run B — the same world with the schedule corrected

`serial2b.db`, 329 records (two more: the reveal ordinals now stored as ordinals), the same six
promises, the same twelve directives. Positions minted only where the book has a scene:
`m_holts_date → s4`, `m_orrin_last_call → s7`, and the four arc answers carry their ordinal and
**no position at all**, so they stay hidden for the whole run.

**53 ticks, 46 jobs, all succeeded; 21 decisions, every one ACCEPT; 12 invocations, 753,551
tokens, $5.89.** Eight of eight scenes, **7,812 words**, 9 revisions rebuilding cleanly, 0 parked,
0 poisoned, 0 unattributed. **The gate exits 0.**

**S3 answered, and the evidence is the frozen prompts rather than a reading.** Every scene's
drafting payload is stored, so what the writer was handed is auditable scene by scene:

| scene | facts | hidden | threads | prose | summaries | prompt tokens |
|--:|--:|--:|--:|--:|--:|--:|
| 1 | 229 | **20** | 6 | 0 | 0 | 9,052 |
| 2 | 229 | 20 | 10 | 1 | 0 | 10,061 |
| 3 | 229 | 20 | 16 | 2 | 0 | 11,536 |
| 4 | 230 | **19** | 21 | 3 | 0 | 12,808 |
| 5 | 230 | 19 | 27 | 3 | 1 | 13,415 |
| 6 | 230 | 19 | 32 | 3 | 2 | 13,744 |
| 7 | 231 | **18** | 37 | 3 | 3 | 14,077 |
| 8 | 231 | 18 | 41 | 3 | 4 | 14,443 |

The hidden count drops by one at scene 4 and again at scene 7 — **exactly the two scenes the world
scheduled its two in-book answers for** — and the fact count rises by one each time. Nothing else
moves. Run A's same table runs 18 → 15, and its scene-one packet was already two claims short.

| # | run A | run B |
|---|---|---|
| **S1** world reaches the writer | yes | yes; and `context_omitted` = **0** on both, whole book |
| **S2** writer honours what it may not state | not answerable | no coined-noun leak the probe can see, and the probe is a note rather than a check |
| **S3** scheduled reveal lands | **no** — 5 of 6 answers handed over as fact | **yes**, mechanically: the claim moves from hidden to fact at its own scene and at no other |
| **S4** integrity gate quiet | yes — 5 findings, all MINOR overdue | yes — **5 findings, all MINOR overdue**, zero `state.contradiction.v1`, zero `state.cardinality.v0` against three declared shapes, 21 of 21 ACCEPT |
| **S5** ledger settles anything | **no — 41 opened, 0 paid** | **no — 47 opened, 0 paid** |

**S5 is the null this pilot was pre-registered to be able to report, and it is the finding.** Six
debts existed before scene one with their answers already in canon, and two of them were disclosed
to the writer at the scenes they were scheduled for. **The summariser still paid none of them, and
opened 41 more of its own.** So the missing answer was not the binding constraint: `promises_paid`
comes out of a per-scene summary call that is not told which debts are due, and seeding the ledger
does not reach it. That is a concrete next question and it is not one this pilot's scope may
answer.

**What is deliberately not claimed.** Whether the scene at s4 *actually answers* its question, and
whether the prose is any good, are reads this pilot does not spend. The gate exits 0, which is the
only thing it was ever entitled to say.

---
