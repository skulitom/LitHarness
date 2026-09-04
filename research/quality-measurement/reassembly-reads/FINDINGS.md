# Findings — order recovery across the chapters the operator read

House form: the claim, the number beside it, and the caveat travelling with the claim.
`PREREG.md` beside this file owns the stimuli, the two classes and the reading fixed before
spend; this file owns the reading. Status: **OBSERVED**, 2026-09-04. The registered reading is
**NO_SEPARATION**. Raw answers in `raw.jsonl` (labels only, never prose), the summary in
`results.json`. Nothing here promotes a claim past OBSERVED.

## The run

Fifty-four calls on the registry's pinned model, **zero transport failures**, $13.71 against
the registered $30 cap, nothing stopped, no cell repaired — every answer returned every label
exactly once. All nineteen chapters answered at all three seeds; the six cells the instrument
had already bought were reused by pointer and not bought again. The instrument is
`../reassembly/run.py` imported by path at sha256 `7f28e8a807514e61…`, so a cell here is the
same measurement as a cell there.

It ran on the Opus seat about an hour after that seat came back: Opus `-p` hung past its
120-second probe from roughly 15:00 to 23:19 on 2026-09-03 while Haiku answered throughout, so
this arm was moved ahead of the larger Haiku one on the reasoning that a 54-call arm is cheap
to lose and expensive to discover unrunnable twelve hours later. A health check through the
production provider answered in 4.5 seconds before the arm was launched.

## The reading, by the table fixed before spend

| | class S — a chapter-level item | class T — sentence-level only |
| --- | --- | --- |
| chapters | 12 | 7 |
| mean tau | **0.9324** | **0.9656** |
| min / max | 0.7962 / 1.0000 | 0.9249 / 0.9985 |

**T minus S = +0.0332, 90% interval [−0.0037, +0.0702].** The interval contains zero, so by the
table fixed before spend the reading is **NO_SEPARATION**: recoverability does not separate the
chapters the operator could not follow from the chapters where every item he named was a
sentence. That is the same answer the instrument's six prior cells gave for two chapters, now
at nineteen.

**The lower bound is −0.0037, and that is not a finding.** It is as close to excluding zero as
an interval can come without doing it, and the honest reading of a pre-registered rule is the
one it returns rather than the one it nearly returned. The design was registered at nineteen
chapters, nineteen is what it had, and this is its answer; pursuing the direction would be a
new registration with its own sizing and its own stimuli, not more of this one.

## What is reported beside the reading and is not the reading

**The three chapters below the anchors' range, which the registration named as a thing to
report whatever its class.** The four placed openings recover between 0.8544 and 0.9969; three
of ours fall under that floor:

| chapter | mean tau | adjacent | class |
| --- | --- | --- | --- |
| `signed-for-by-nobody` | 0.7962 | 0.919 | S |
| `reading-the-ladder-wrong` | 0.8191 | 0.874 | S |
| `what-the-kettle-remembers` | 0.8360 | 0.736 | S |

All three are class S. **That is a description and not a separation**, and the distinction is
the whole of why the interval was registered first: the pre-registered test for whether the
classes differ declined to support it, and a subgroup noticed after the fact does not overturn
the test that was fixed before the spend. What the list is licensed to say is what the
registration said it would say — these three chapters' paragraphs are less recoverable than
any of the four openings on the shelf, found by code, which is the *list* shape the reads have
named.

**And the sixteen others sit inside or above the shelf's range**, including both chapters at
the top: `reappraisal` and `what-takes` reassemble at 1.0000 on every seed. Recoverability is
coherence, not engagement, and `reappraisal` is the book the operator's second read called one
where *"not much seems to be happening"*. A chapter can be perfectly ordered and not worth
reading; this instrument cannot tell the difference and does not claim to.

## What it cannot show

One reader, one model, three seeds, nineteen chapters drafted between 2026-08-21 and
2026-09-02 under different pipelines, persons and writers — nothing here is a treatment effect
between any two of them. The classes were assigned from the operator's own words before any
number existed, but they are our reading of his items, and a defect harvest is not data (§95):
the classes describe what he happened to name on the day he read each chapter, not a property
the chapters are guaranteed to have. Twelve against seven is a thin split, and the interval
says so.

## What is owed

Nothing from this arm. It answered the question it was registered to ask, in the direction of
no separation, and the handoff's second experiment is closed with a null. The instrument
remains what §199.2 made it: a diagnostic beside the tells counter, where a chapter below the
shelf's range is a *list* found by code — and three of ours now are.
