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

## 6. Anti-scope

No persona is edited. No bar is declared and none of §61's four attainability checks was run,
because no quantity here is a bar. No claim is promoted under `EPISTEMIC_GOVERNANCE.md`: the
result is `OBSERVED` at n of one draw per opening, and the smallest claim it can carry is a
description of where these particular openings landed on this particular panel. The backtest's
registered programme, its cache, its salts and its paused stage (c) are untouched.
