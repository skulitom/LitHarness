# Prospective attention: timing delivered, explanatory narration remains

2026-09-07. **OBSERVED**, not a qualified literary improvement. Three prefix-only proposals
and all four complete chapter draws were retained. Both guided chapters use the proposed
anticipations before encountering the selected new observations/action. They still supply
opening inventory, interpretive framing and explanations of already-presented particulars.
This addresses the proposer's hindsight exposure; it does not establish a fix for how the
chapter reads or justify installing a production narrative agent.

## What was corrected before generation

Simply cutting the canonical unit list was insufficient. Manual input review caught a future
event named in an opening-known fact's text/timing, and another incoming action named in an
earlier unit's timing annotation. The initial 21 regression cases had passed without detecting
those semantic hints. Before registration commit or any model call, the planner view was
changed to id/kind/text, omitting all timing metadata. One opening-known fact was shortened to
its earlier instruction; one reference to an already-visible display was expanded in place.
All other fact text, IDs, kinds and order stayed unchanged. Three further regression cases
guard the complete reviewed view and exclusion of timing metadata. Both preflight handoffs
and the source review are retained, including the earlier successful but insufficient checks.

The complete writer source was unchanged. Proposer requests contained **4, 23 and 34** available
units respectively, with no original prose, future unit, later display inventory, source notes,
endpoint or other proposal. Code enforces prefix selection and canonical references; semantic
review still checks what earlier text discloses. Writers continue to see the full chapter.

## Retained comparison

The three independent proposals concerned ordinary seated stillness, the retreating threat
after a movement award, and a possible further award after a rescue. These choices were derived
without their incoming events. They were reviewed as tentative expectations, not new rules:
the second could not establish scoring immunity, and the third could not license a new award,
an asserted non-award or a repaired total. The compatibility review was not sent to writers.

Two source-only and two guided requests share identical source, required narration and common
system. Only prospective_attention differs, adding **182 reported input tokens** per guided
writer call. This is a package comparison including extra information and planning, not an
isolated timing or agent-architecture effect. Both guided draws share the same three cards.

| Draw | Words | Paragraphs | Display word sequences/order |
| --- | ---: | ---: | --- |
| source-1 | 1635 | 80 | All 10 retained |
| prospective-1 | 1678 | 80 | All 10 retained |
| prospective-2 | 1698 | 80 | All 10 retained |
| source-2 | 1732 | 84 | All 10 retained |

All four were read in full through final status, with **168 source correspondences and 24
attention/span correspondences** recorded. The 31 required units per chapter were located
with the qualifications below. The original scene division, two awards following both blows,
private second movement award, literal total and unusual recall consequence remain. No fourth
rescue award was invented. These checks do not certify prose quality or semantic perfection.

## Located behavior and remaining defects

- **Opening attention is present without removing exposition.** Both guided first paragraphs
  watch seated students, then inventory or characterize the cohort. Prospective-2 3 looks along
  the seated row before looking down after the light changes. Source-1 and source-2 instead open
  with the disturbance and place the register/cohort inventory at 3. Source-1 3-4 spontaneously
  supplies an expectation of continued writing and interrupts it; source-2 8 and 11 also contain
  expectations without cards. Prospective behavior is not exclusive to the treatment.
- **The threat check precedes the shout.** Both guided draws at 33 watch the figure continue
  away, then explain the difference between movement and inactivity. The source-only draws
  contain the earlier source-required retreat but no located renewed check at this boundary.
  No protective immunity rule is asserted. This is observable card use alongside explanation.
- **The possible award precedes the wide look.** Prospective-1 60 leaves a moment for an award
  while turning, before the new hall facts at 61-62. It is interwoven with the last micro-action
  of the preceding unit, so exact separation from that turn is not demonstrated. Prospective-2
  60-62 completes the turn, searches the award's possible location, then sees those still inside.
  Neither supplies the anticipated award or explicitly denies an unspecified payment. The
  encounter redirects attention. Both then explain failed reach at 63 or 64-65. The source-only
  returns go directly to the hall and also end in explanatory summaries.
- **Writer restatement survives the planner change.** All four repeat or expand interpretations
  around assessment, rescue limits and recall's cost. Required interpretations are not defects
  merely for being present; the readings locate additional formulations and rationales. Both
  guided openings still explain the significance of the register/cohort arrangement.

Source qualifications were retained rather than repaired. Source-1 4-5 and prospective-2 4-5
narrate pens stopping before questions changing, making causal/temporal presentation unclear.
Source-2 uses past-perfect change at 5, which can preserve prior causation despite that reading
order. Prospective-2 1 adds a condition to the earlier briefing and 72 leaves glove appearance
implicit. Prospective-1 77 implies no register page is available to offer, though only one page
was torn out; this may mean none ready to hand rather than none remaining. Source-2 56 adds a
practical rationale involving obstructing pages; its 50 ties recognition to the award/landing
interval, which could be retrospective comparison rather than an earlier realization. Full
reading records preserve these uncertainties and the exact paragraph pointers.

## Next suspect, not a result of an isolated test

The writer may turn editorial constraints into narration. Prospective-1 26, prospective-2 26
and source-2 28 explicitly discuss the absence of a clock reading; source-1 27 discusses the
basis for measurement. Source-2 69 explicitly declines to reconstruct the final total. These
resemble source qualifications that ought to constrain rendition without necessarily becoming
character behavior or explanation. A separate comparison could distinguish narratable facts
from non-narratable editorial constraints in the writer input. This run changed the planner
view only; it cannot establish that input annotation is the cause or that separating it will
improve prose. No further model call or production intervention was made from this conjecture.

## Accounting and reproduction

Registration commit **2d31db949f884f91329006dba7006fc9d2e069d3**. CLI 0.153.4, requested
gpt-6-astra/high, existing ChatGPT subscription authentication; resolved model not separately
exposed. **Seven completed calls, 441.823 total call seconds**, zero model tool use.
**49511 input + 10206 output + 1633 separately reported reasoning = 61350 accounted tokens**,
below the 125000 stop. Cached input 16128 is already included. No direct API, alternate provider,
probe, retry, redraw, reset or purchase was used.

Ignored root: runs/ab/prose-prospective-attention-20260907. Each call retains exact request/argv,
raw stream, parsed result and text. Manifests bind source, reviewed prefixes, code, systems,
three proposals, compatibility review and writer requests. Reading records and comparison show
all four unranked complete outputs. The builder verifies frozen bytes, raw/result/text identity,
request equality except cards, source/attention correspondence and display word sequences.

```powershell
uv run python -X utf8 runs/ab/prose-prospective-attention-tools/manual_readings.py
uv run python -X utf8 runs/ab/prose-prospective-attention-tools/build_review.py
```

This is agent defect harvest from one fixture, not independent quality labels, candidate
selection, a causal estimate or production qualification. Production code is unchanged.

Final handoff: **4149 passed, 19 skipped, 88.76% coverage**, with clean lint, types, diff/lock
checks, wheel build and corpus-history audit. Explicit claim validation passes. Browser QA
covered both draws and final status lines, three cards/review, all four reading sections,
prefix inputs and exact writer disclosures. No horizontal overflow at 1280/740px and zero
console messages. Two screenshots were visually inspected and eight owned snapshots archived
under the ignored run with verified hashes. Final handoff and QA artifact hashes are recorded
in execution.json.
