# Serial Pilot 6 — a book to be read, on the first world forged from a brief the operator wrote

**Status: FORGING, 2026-08-23.** §5 and §6 are empty until the run happens. Companion to
[`plan/serial-pilot-4.md`](serial-pilot-4.md) (the last pilot that produced prose) and
[`plan/serial-pilot-5.md`](serial-pilot-5.md) (forged, never run); the design record is
[`plan/world-architect.md`](world-architect.md); the machinery it exercises is stage-0 §110–§115.

## 0. What this run is for, and the two things it may not be read as

**It was asked for as a read, not as an arm.** The operator asked for a book generated with the
current stack, to read it and to see what a year of machinery has changed about the prose. That is
the whole purpose, and it is written at the top because every prior pilot in this series exists to
answer a registered structural question and this one does not.

**It may not be read as a quality claim, and no reading of it may make one.** Two chapters is not
a sample; §61's bar is a blinded position-swapped win rate against matched published prose and
this is not that, is not powered for it, and does not attempt it. The operator's own read of the
book is a **defect harvest** and not data (§95, and the four prior reads recorded in
`plan/reader-read-*.md` are the precedent for what a read of ours is allowed to become).

**It may not be read as a comparison to Serial Pilot 4 either.** *A Good Take* was forged from
`"progression fantasy"`; this one is forged from an operator brief naming a different sub-genre,
so brief, world, domain, cast and forge all differ at once. Where a counter here is printed beside
pilot 4's, it is a description of two books and never a difference between two treatments.

**What is held from pilot 4**: shape (`direct`), K (3), scene count (8), chapter shape (4), target
words (900), context budget (16,000), provider, and the six standing craft constraints, which are
carried byte-for-byte in `plan/serial-pilot-5-craft.json` and issued from that file unchanged.
**What differs**: the brief, and everything the machinery gained since — the ordinal ladder and
the protagonist's standing on it (§113), the ability inventory (§114), and the forged width the
pick now reads instead of guessing (§115).

**The three proposed craft constraints stay unissued.** C9, C10 and C11 sit in the `proposed`
array of the craft file and none is issued here. A book asked to put the rung on the page cannot
answer whether the declaration alone puts it there, and pilot 4 is the precedent: C10 was not
issued and the book opened on its protagonist anyway.

## 1. The brief, and how the world is chosen

```powershell
uv run litharness --database pilot6\forge.db forge 'isekai LitRPG progression fantasy; no dungeons' `
  --k 3 --shape direct --out pilot6\direct1 --scenes 8
```

The brief is the operator's own words, narrowed from the standing register direction (popcorn
progression fantasy) to one sub-genre with one exclusion.

**There is no pick rule here, and its absence is the point.** Pilots 2–5 each wrote a mechanical
pick rule down before the candidates existed, because each was answering a registered question and
a rule chosen with candidates in view is a rule fitted to them. This run answers no such question:
the operator asked to read a book, `forge --pick` is `VerdictSource.HUMAN`, and the person reading
it chooses which world it is from the gate report. The report they saw and the candidate they took
are recorded in §5 beside the decision id.

## 2. Standing it up

```powershell
.\tools\serial-pilot-2-setup.ps1 -Forge pilot6\direct1 -Scenes 8 -Database serial6.db `
  -Craft plan\serial-pilot-5-craft.json
```

## 3. The two phases

Direction first, gated, before a paid call is spent on prose — unchanged from pilots 1, 2, 4 and
5. Phase 1 is budgeted at roughly twice the directive count in ticks, because each verbatim
constraint bumps the plan epoch.

```powershell
.\tools\run-loop.ps1 -Database serial6.db -Ticks 26 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial6.db --phase directives `
  --spec pilot6\direct1\directives.json --spec plan\serial-pilot-5-craft.json
```

Only when that gate is green:

```powershell
.\tools\run-loop.ps1 -Database serial6.db -Ticks 48 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial6.db `
  --spec pilot6\direct1\directives.json --spec plan\serial-pilot-5-craft.json
```

**`--context-budget 16000` is a precondition, not a preference** (pilot 2 §3's measurement: at the
6,000 default a ~329-record world dropped every prior scene and 92 facts).

**Box discipline.** `claude -p` fails under box load and the failure is silent-ish — a failing call
still returns and the run completes with unanswered cells. No other paid arm, pilot loop or forge
on the box; one CLI arm at a time; `transport_failures` before any count.

## 4. What will be read off the run, and what no number here licenses

Structural counters only, each of which already has a home and an instrument:

| | instrument | what it answers |
|---|---|---|
| gate | `tools/serial_pilot_check.py`, both specs | every issued directive reached a plan revision, every scene drafted, nothing parked |
| ladder | `research/quality-measurement/standing.py` | rungs declared, who stands on one, whether a standing rises on the page |
| inventory | `research/quality-measurement/ability_inventory.py` | whether declared capabilities are used rather than listed |
| promises | the ledger in `serial6.db` | opened against paid, against pilot 4's 49 / 40 / 9 |
| cast | whole-word counts over the drafted prose | how many forged cast members reach the page |

**No bar is declared over any of them** and none may be read in: no count here has had the four
attainability checks (§81, §85, §87, §89 are four bars declared over quantities that could not do
what they said), and a bar declared over a book already written is a bar fitted to it.

## 5. The run

### 5.1 Six forges, two refusals of subject, two refusals of size

Recorded in the order they happened, because the order is the finding: **the first four forges
bought no world and every one of them changed the repository instead.**

| # | brief | K | outcome | out tokens | thinking | cost |
|---|---|--:|---|--:|--:|--:|
| 1 | `isekai LitRPG progression fantasy; no dungeons` | 3 | **lost** — non-conforming, nothing kept | ? | ? | ~$1.50 |
| 2 | same | 3 | 3 worlds; **operator refused all three** | 57,862 | 17,931 | $1.6665 |
| 3 | techniques/rank, 1,911 chars | 3 | **lost** — answer arrived as its own tail | 64,546 | 23,630 | $2.5029 |
| 4 | same | 2 | 2 worlds; **operator refused both** | 46,799 | 16,136 | $1.3992 |
| 5 | wish brief, 1,911 chars | 2 | **lost** — same tail, half the budget on thinking | 64,051 | 33,564 | $2.5020 |
| 6 | `brief4.txt`, 247 chars, rules carrying the direction | 2 | see §5.4 | | | |

Plus five health probes at $0.6892 the set. **Traced spend $8.7597**, and forge 1 is untraced
because the branch it died on kept nothing — which is stage-0 §117 and was fixed here.

### 5.2 The two subject refusals, which are stage-0 §116 and §118

Forge 2 returned water law, orchard deeds and a surveying tariff on a brief that names no
institution, no economy and no law. The operator read the three premises and refused them:
*"All these sounds depressing and incredibly boring. Anything related to debt or ledgers is a no
no in a story"*, then *"Can we make sure such ideas never come up again?"*. The census that
answered it — 30 worlds, every one administrative, 18 naming one in the premise — is §116.1, and
the rule text that caused it is §116.2.

Forge 4 returned bell-founding and dyeing at 0.29 and 0.28 administrative words per 1,000, against
a prior median of 7.21: **the amended rules worked on the thing they were amended for**. The
operator refused both anyway, for the next thing: *"unnecessarily esoteric and the concept isn't
inspirational ... Readers want to feel cool and progress in meaningful ways ... the words used are
adding unnecessary complexity eg mordant"*. That is §118 — 32 worlds, 27 domains, every one a
trade or a science, and 16 rules of which none asked whether anybody would want the power.

**Neither refusal is a measurement and neither is recorded as one.** Two operator reads of six
worlds are direction (§95), and what came out of them is instruction text, not a datum.

### 5.3 The size ceiling, which is stage-0 §117

Forges 1, 3 and 5 died the same way and it took a wrapper around the provider to see it: the
answer outgrows a single message, the CLI returns its **tail**, and `parse_schema_payload`
correctly refuses a fragment. `is_error` is false and `stop_reason` is `end_turn` either way, so
the only signal is size. Measured across the four traced calls:

| | thinking tokens | outcome |
|---|--:|---|
| forge 4 | 16,136 | conformed |
| forge 2 | 17,931 | conformed |
| forge 3 | 23,630 | fragment |
| forge 5 | 33,564 | fragment |

**A long brief is expensive twice**: forge 5's 1,911-character brief doubled the deliberation
against forge 4's 1,136, and the deliberation is charged to the same ceiling the answer is. The
response is not a bigger ceiling but a shorter brief — since §116 and §118 the standing direction
lives in `_RULES`, so forge 6's brief is 247 characters and says only what is particular to this
book.

### 5.4 The world this book is written on

*(empty until forge 6 lands and the operator picks)*

## 6. The record

*(empty until it runs)*
