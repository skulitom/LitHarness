# Opening parity: our openings against the market's summits, on the frozen panel

**Status: REGISTERED 2026-09-01, before any paid call.** Exploratory and descriptive, in
`house_panel.py`'s sense: the sim-readership backtest's frozen ten-persona panel, its two
byte-frozen turns, its closed stage-2 answer, its blinding and its both-orders cell, pointed at
a new pairing. Nothing here gates, ranks, promotes, or reaches a prompt. The operator's
direction this answers, verbatim: *"I would be happy if as a first step we would be able to
produce as good of an overview and chapter 1 as primal hunter for example."*

## 1. The question

Where does one of our openings land when a simulated genre reader is handed it beside a
summit's opening and asked, with limited reading time, which to continue? Two artifacts, two
arms:

| arm | stimulus per side | shape borrowed from |
| --- | --- | --- |
| `opening` | the first 1,500 words of chapter 1, extended to the paragraph boundary, blinded | the C-arm, length-matched instead of capped at 6,000 |
| `listing` | the blurb, then the first 500 words of chapter 1, blinded | the P-arm, byte for byte (`arms.PREMISE_WORDS`) |

Length is matched by construction (both sides cut at the same word count to a paragraph
boundary), because §141 matched length pair by pair for the reason stated there: a readership
that takes the longer text every time has measured length.

## 2. The stimuli

**Ours**: four chapter-1 openings on the shelf, one per writer where possible, each with its
listing. The manifest (`manifest.json`) names them by shelf folder; the result files carry the
blinded digests.

**Summits**: the two anchors the operator placed on the shelf on 2026-09-01 (*The Primal
Hunter*, *Defiance of the Fall*; `plan/anchor-set.md` rows 1 and 2, both VERIFIED SUMMIT), plus
the four highest-follower LitRPG-tagged fictions in the cached shards that carry a chapter 1 of
at least 1,500 words, a blurb of at least 30 words, no declared-AI cohort label, and paragraph
breaks the cut can land on. One fiction above the fourth (*The Butcher of Gadobhra*, 10,516
followers) is excluded on the last condition: its shard text is a single paragraph, so it
cannot be length-matched, and the driver refuses that shape by name. Their follower counts sit
above the local sample's p99.9 (8,136). Their text lives only under
`research/quality-measurement/derived/` (gitignored) and `book-library/` (gitignored); no
third-party prose is committed by this experiment.

The two anchors run in the `opening` arm only until their blurbs are on disk: RoyalRoad
returns 403 to the fetcher, and a blurb reconstructed from memory would be a fabricated
stimulus.

## 3. The cells

- Every (ours x summit) pair, both orders, all ten personas: 20 sessions per pair.
- **Calibration pairs, run beside and reported beside**: summit x summit and ours x ours, same
  cell shape. They say what a same-class pair looks like on this panel; without them a lopsided
  ours-vs-summit share has nothing to be read against.
- **Recognition probes precede every stimulus** (`recognition.PROBES`, scored by
  `recognition.score_probe`, classified by `recognition.classify`). A stimulus with any hit is
  reported in a `recognised` stratum and its pairs are reported separately, never pooled with
  the clean stratum and never dropped silently. The two anchors are expected to be recognised;
  that expectation is written here so the result cannot be read as a surprise either way. Our
  own openings are probed too, as the false-positive control on the probe itself.

## 4. What is read, and what is refused

- Shares of decided answers in file space, per pair, per persona, and pooled per ours-book and
  per summit; `neither` counts beside them. The positional split in slot space, per
  `house_panel.positional`; a first-slot share outside [0.35, 0.65] on a pooled arm is reported
  as a void reading for that arm, the §120 precedent, not corrected for.
- **No bar, no aggregate score, no verdict, no rank.** `house_panel.write_result` refuses any
  key containing `verdict` or `score`; the summary file is checked by the same function.
- **No model ranks candidate books** (§61(5), §84). The pairs are fixed in the manifest before
  the run; nothing selects among our openings on the result.
- **Nothing reaches a prompt.** Stage-1 free text is never parsed; reason codes are counted and
  nothing consumes them. RS1 holds: summit text goes into a persona's context on the
  measurement side and nowhere else.
- **The panel's provenance sentence** (`house_panel.PROVENANCE`) rides on every result file
  and on the summary.

## 5. Ceilings and cost

Both ceilings are required on the command line, as `house_panel` requires them. Planned:

| | pairs | sessions | basis | estimate |
| --- | --: | --: | --: | --: |
| `opening` | 24 + 4 calibration | 560 | $0.0747/session | ~$42 |
| `listing` | 16 + 3 calibration | 380 | $0.0747/session | ~$28 |
| probes | 18 stimuli x 3 | 54 calls | ~$0.02/call | ~$1 |

(The dry run of 2026-09-01 printed exactly this plan: 47 pairs, 940 sessions, 54 probe
calls, $70.22 at the session basis.)

Registered ceilings: **$100** and **1,100 sessions** across both arms. The elicitor's ledger
is cumulative over its cache file, so an abort can only come early. Cache:
`runs/opening-parity/panel-cache.jsonl`; every bought record replays free.

## 5a. Amendment, 2026-09-01, recorded before any cell under it was bought

The first run was stopped at 164 cache records (the 54 probes and the first ~55 sessions of
the `opening` arm) when the operator placed four things on the shelf: the two anchors' blurbs,
and chapter 1 plus blurb of *The Gam3* and *The Legend of Randidly Ghosthound*. Every bought
record replays; nothing is lost.

- **Stimuli.** The two anchors now run in both arms. The two new anchors join both arms. The
  third and fourth local summits (*Cultivation is Creation*, *Soul of the Warrior*) leave: with
  four operator-named anchors the local leg's job is a market-sample check, and two locals do
  it. Any pair session already bought against them is sunk (~$4 at most) and is reported in
  the cache, not in the result.
- **A single-newline chapter is paragraphed on its newlines.** *The Gam3*'s file has one
  newline per paragraph and no blank lines; `first_words` would show it whole. The driver now
  re-separates such a file on its newlines (`run._paragraphed`) and leaves every file with
  blank lines untouched, so the ten stimuli already built are byte-identical.
- **The plan and the ceilings.** Four of ours × six summits per arm, plus five and four
  calibration pairs: 29 + 28 = 57 pairs, 1,140 sessions, 60 probes (the dry run of the
  amended manifest printed exactly this). The registered $100 stands (the estimate is $85.16
  at the session basis); the session ceiling moves 1,100 → 1,200 to fit the plan and for no
  other reason.
- **Follower figures for the two new anchors are not yet retrieved** and are `null` in the
  manifest; `plan/anchor-set.md`'s rule is checkability, and they can be fetched through the
  browser when the operator is beside it. Both are operator-named summits in the same sense as
  rows 1 and 2 there.

## 5b. Amendment, 2026-09-01, the damage control — recorded before any cell under it was bought

The first pair result written by the amended run (`opening`, station vs *The Primal Hunter*,
both openings probe-clean) read 20 of 20 decided for ours, 10 of 10 in each order. That is the
shape §140 produced on listings, where this readership preferred ours to the market's best 15
of 16 times and §141.3 then found its resolution within the top tier unproven; the
reader-architecture programme's own caution is that a mechanism can pass the follower gradient
and still prefer polish to event. Nothing in this run can tell those apart, so one control is
added, the backtest's damage arm brought to this pairing:

- **A control entry** is one of our openings with its paragraphs in a seeded random order —
  the same cut, the same words, a fixed permutation (`run._shuffled`, seed in the manifest and
  the result file). It never enters the ours × summit product; it is paired only where the
  calibration list names it, and the pair's kind names it (`control-vs-summit`,
  `control-vs-source`).
- **The reading, fixed now.** If a shuffled opening of ours is still taken over an anchor at
  the rate the ordered one is, the panel's preference does not depend on the story being in
  order, and the ours-vs-summit shares in this run are read as a preference about surface,
  never as parity. `control-vs-source` is the sanity check that the panel can see the shuffle
  at all; a panel that cannot is not reading story either way.
- **Cost.** Two controls (station, kettle) × two anchors (*Primal Hunter*, *Defiance*) plus one
  control-vs-source pair in the `opening` arm: 5 pairs, 100 sessions, ~$7.50, no probes (a
  control is never probed; its source's probe stands for it). The whole plan is then 62 pairs
  and 1,240 sessions, $92.63 at the session basis, inside the registered $100; the session
  ceiling moves 1,200 → 1,300 to fit it and for no other reason. Bought on the next launch of
  the driver, which replays every cell already bought; the run in flight is untouched.

## 6. Anti-scope

No persona is edited. No bar is declared and none of §61's four attainability checks was run,
because no quantity here is a bar. No claim is promoted under `EPISTEMIC_GOVERNANCE.md`: the
result is `OBSERVED` at n of one draw per opening, and the smallest claim it can carry is a
description of where these particular openings landed on this particular panel. The backtest's
registered programme, its cache, its salts and its paused stage (c) are untouched.
