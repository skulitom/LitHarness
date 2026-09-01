# Findings — opening parity

House form (the backtest's `FINDINGS.md`): the claim, the number beside it, and the caveat
travelling with the claim. Every arm is listed, run or not; an absence is marked, never
silent. `PREREG.md` owns the design and its amendment; this file owns the reading.

## Status

**Registered 2026-09-01, amended five times the same evening (PREREG §5a–§5e, each recorded
before any cell under it was bought), and stopped after 22 pairs of the `opening` arm at $34
of the ceiling, once the shuffle controls had answered.** The reading is below; the pair
files are committed under `results/opening/`; every bought record replays from
`runs/opening-parity/panel-cache.jsonl`.

## Free findings (no model asked)

- **The shape census** (`shape_census.py` over the manifest, counts only): the two anchors are
  close third with a reported mind (interior verbs 5 and 11 against our 1–4); the four local
  summits split between first person (389, 129 marks) and close third (29, 1); every summit
  gives the person's days before in its first paragraphs and every summit blurb on disk names
  the person's ordinary situation in its first sentence; our four listings do not. Stage-0
  §195.1 carries the table.
- **One local summit cannot be length-matched** (*The Butcher of Gadobhra*: a single paragraph
  in the dump) and one operator-placed anchor arrived with no blank lines (*The Gam3*); the
  first is excluded by name, the second is paragraphed on its newlines (PREREG §5a).

## Arms

| arm | status | note |
| --- | --- | --- |
| `opening`, ours × summits | PARTIAL: 10 of 24 bought (station × 6, kettle × 1, game × 3), floors × 6 not bought | first 1,500 words, length-matched, both orders, ten personas |
| `opening`, calibration | RUN: 3 anchor × anchor, 3 ours × ours | |
| `opening`, controls | RUN: 5 control × anchor, 1 control × source; floors-shuffled not bought | PREREG §5b, §5d, §5e |
| `listing`, all pairs | NOT_RUN | stopped before the arm; would need its own controls |
| recognition probes | RUN for every stimulus in both arms | every summit opening clean except *Randidly* (title); in the listing arm *Primal Hunter* (title), *Defiance* (author) and *Randidly* (title) recognised |

## The reading

### What the first seven baseline pairs said, before any control existed

Read off the result files of the cut run (2026-09-01, `opening` arm, all probe-clean except
*Randidly*, whose opening the title probe recognised): station over *Primal Hunter* 20 of 20,
over *Defiance* 19 of 19, over *The Gam3* 20 of 20, over *Magical Girl Gunslinger* 19 of 19,
over *Low-Fantasy Occultist Isekai* 19 of 20, over *Randidly Ghosthound* 15 of 20 with a
first-slot share of 0.65; kettle over *Primal Hunter* 20 of 20. Every pair but the last is
order-clean (first-slot share 0.50–0.55). The reason code is `hooked-by-other` in most cells.

**This is not read as parity, and the reason is on the record before the controls' numbers
are.** It is the shape stage-0 §140 produced on listings — ours over the market's best 15 of 16
— where §141.3 then found the readership's resolution within the top tier unproven and the
reader-architecture programme named the failure to watch for: a mechanism that passes the
follower gradient and still prefers polish to event. Seven pairs at 19–20 of 20 against four
summits with 5,000 to 34,000 followers is either that failure or a finding, and nothing in
these cells can tell which.

### The decision table for the controls, fixed before they were bought (PREREG §5b, §5d)

| control result | what the ours-vs-summit shares then mean |
| --- | --- |
| `control-vs-source` near even: the panel cannot tell a shuffled opening of ours from the ordered one | the panel is not reading story order at this length; every ours-vs-summit share is about surface and none is about story |
| `control-vs-summit` at or near the ordered opening's rate: a shuffled opening of ours is still taken over an anchor 18–20 of 20 | the preference does not depend on the story being in order; the shares are a preference about surface, never parity |
| `control-vs-summit` well under the ordered rate, and `control-vs-source` clearly for the source | the preference depends on order; the shares are the panel's preference about these openings, which is still a pilot-grade instrument's preference and not a validity claim |

No threshold is declared for "near" or "well under": the numbers are reported and read against
each other, and §61's attainability checks were not run because none of this is a bar.

### The result (2026-09-01, `opening` arm; 22 pairs bought, then the run was stopped)

The pair files are committed under `results/opening/` (counts, labels, digests; no text) and
`tabulate.py` prints them. Every summit was probe-clean except *Randidly*, whose opening the
title probe recognised. Transport failures: zero in every pair.

**The controls, first, because they decide the reading.**

| pair | kind | decided | for the shuffled copy | first-slot share |
| --- | --- | --: | --: | --: |
| station-shuffled vs *Primal Hunter* | control-vs-summit | 20 | **20** | 0.50 |
| game-shuffled vs *Primal Hunter* | control-vs-summit | 20 | **20** | 0.50 |
| station-shuffled vs *Defiance* | control-vs-summit | 20 | 18 | 0.60 |
| kettle-shuffled vs *Primal Hunter* | control-vs-summit | 19 | 18 | 0.53 |
| kettle-shuffled vs *Defiance* | control-vs-summit | 18 | 14 | 0.44 |
| station-shuffled vs station (its source) | control-vs-source | 20 | 7 (source 13) | **0.85** |

The ordered openings' rates against the same anchors were 20 of 20 (station vs *Primal
Hunter*), 20 of 20 (game vs *Primal Hunter*), 19 of 19 (station vs *Defiance*), 20 of 20
(kettle vs *Primal Hunter*). **A shuffled opening of ours is taken over an anchor at the
ordered opening's rate**, and against its own ordered source the panel took whichever copy
it was shown first 17 times in 20. By the decision table above, rows one and two: the panel
is not reading story order at this length, and every ours-vs-summit share in this run is a
preference about surface. **The instrument cannot arbitrate the operator's question.**

**The product pairs, for the record and not for a reading.** Ours over every summit, in both
orders: station 20/20, 19/19, 20/20, 19/19, 19/20 and 15/20 (*Randidly*, first-slot 0.65)
against *Primal Hunter*, *Defiance*, *The Gam3*, *Magical Girl Gunslinger*, *Low-Fantasy
Occultist Isekai* and *Randidly*; kettle 20/20 against *Primal Hunter*; pilot 19's opening
20/20, 20/20 and 19/19 against *Primal Hunter*, *Defiance* and *The Gam3*. Pilot 20's opening
and the listing arm were not bought.

**The calibration pairs say the panel is not saturated in general — only across the ours/summit
line.** Anchor against anchor: *Defiance* over *Primal Hunter* 15 of 18 (first-slot 0.33);
*Randidly* over *The Gam3* 18 of 18 (0.44); *Low-Fantasy Occultist Isekai* over *Magical Girl
Gunslinger* 16 of 18 (0.56). Ours against ours: pilot 19 vs station 9 to 11 (0.65); station vs
kettle 11 to 9 (0.65); weather over ladder 14 to 6 (0.50). The panel discriminates within the
summits and within ours, with positional leans, and puts every opening of ours above every
summit whether or not its paragraphs are in order.

**What this is evidence of, stated as small as it can be.** This panel — ten haiku personas
asked which of two 1,500-word openings they would continue — responds to a property our
openings carry and the summits' openings lack, and that property survives a paragraph
shuffle. Sentence-level texture is the obvious candidate and is not measured here. It is the
§140/§141 finding again with the shuffle added: the readership reads the market's coarse
follower gradient off listings and reads our prose as above the market's top, and the second
reading is not about story. **No parity claim is made, in either direction.** The two
openings drawn under §195 are on the shelf for the operator's milestone read, which is the
one channel left for the question as asked.

**Why the run was stopped after 22 pairs (post hoc, and recorded as such).** The remaining 48
pairs were product pairs and the listing arm; the controls had voided the reading of the
product, and a listing arm without its own controls would have needed the same treatment.
$34 of the registered ceiling bought the answer; the rest was not spent.

## What is owed

- A story-sensitive instrument for the parity question: something whose answer changes when
  the paragraphs are shuffled. Candidates already in the repository: the anticipation probe
  (`reader.anticipation.v0`, code-scored futures) and the causal-salience battery
  (`plan/reader-perception-research.md`); the C-arm at its full 6,000-word cap was only
  weakly order-sensitive in the backtest (11 of 15 intact preferred). None is built into this
  harness; the manifest and the control shape carry over to whichever is tried.
- The operator's read of *The Game Nobody Plays Anymore* and *Nineteen Floors Down* beside
  *The Primal Hunter*'s opening, at the milestone this track was started for.
