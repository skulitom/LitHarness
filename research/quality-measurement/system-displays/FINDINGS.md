# Findings — the market's system displays in its early chapters

House form: the claim, the number beside it, and the caveat travelling with the claim.
`PREREG.md` owns the design and the reading fixed before the run, with its amendment; this
file owns the reading. Status: **OBSERVED**, 2026-09-03, one run over the cached LitRPG shards
(14,156 chapters read, 462 stories with three or more chapters present, 1,386 rows: each
story's three earliest sampled chapters by release date). Raw rows in `rows.jsonl` (counts
and identifiers, no text), the summary in `results.json`, the run's log beside them. No model.
Nothing here promotes a claim past OBSERVED.

## The table

| group | chapters | any display | a window | fields per window (median, q3, max) | fields at zero or blank | windows with any zero | choice screens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| earliest sampled (position 1) | 462 | 0.31 | 0.20 | 2, 4, 19 | 0.058 | 0.16 | 0.002 |
| position 2 | 462 | 0.37 | 0.24 | 2, 4, 18 | 0.071 | 0.19 | 0.002 |
| position 3 | 462 | 0.39 | 0.25 | 2, 4, 13 | 0.065 | 0.15 | 0.002 |
| pooled | 1,386 | 0.36 | 0.23 | 2, 4, 19 | 0.065 | 0.17 | 0.002 |
| true openings (own heading) | 51 | 0.31 | 0.14 | 2.5, 5, 7 | 0.071 | 0.25 | 0.0 |

Notices (a furniture line outside a window) run at about half a line per thousand words,
almost all in the *other* family; the cadence census's level-up, capability and stat-delta
families each sit at or under one per hundred thousand words in these chapters. Item boxes and
quest cards, by the heuristic, at two to four in a hundred chapters.

## The reading, by the table fixed before the run

**Phase 1's default: unheld columns are hidden.** Fields at zero or blank are 6.5 percent of
window fields pooled and 5.8 percent in the earliest sampled chapters, below the one-in-five
line the pre-registration set for hiding; one window in six carries any zero at all. A row of
eight fields with five or six at zero (stage-0 §201's census of ours) is a shape the market's
windows do not have.

**Phase 2's expectation of a first window: small.** The median window carries two fields and
three in four carry four or fewer; the largest in the early chapters carries nineteen. The
budgeted print rule for a list-shaped field is bounded by that maximum, and the ordinary case
is a line, not a screen.

**Phase 3's question: a choice display is not a first-chapter object.** Three choice screens in
1,386 early chapters, none among the true openings.

**Phase 5's floor: a line must not be required in chapter one.** Sixty-nine percent of the
earliest sampled chapters, and sixty-nine percent of the true openings, print no display at
all; the share with no display is above the one-half line the pre-registration set.

## The true openings, and what they cannot carry

Chapters whose own first lines say chapter one or a prologue: 51 rows from 43 stories, below
the two hundred stories the amendment required for the chapter-one readings to be taken from
that subset. So the readings above are taken from the early slice, as the amendment says, and
the true-opening row is shown beside them: it does not disagree on any reading (no display for
most, small windows, no choice screens, few zeros).

## What it cannot show

The classifier reads typography; a system written into prose without furniture is invisible
to it, so every share is a floor on what the genre displays. The early slice is each story's
earliest *sampled* chapters and not its opening. The notice families are the cadence census's
narrow patterns and undercount notices written in other words. Field reading splits a line at
its label marks and reads a change at its end; a window laid out as a table with no labels
reads as zero fields. Nothing here is about quality.

## The fields the windows carry (`field_labels.py`, `field_labels.json`, 2026-09-03)

Over every LitRPG chapter in the shards (14,156), 301 stories print at least one window and
their windows carry 19,628 label-value fields. By value kind, pooled: a bare number 47 percent,
a number with words beside it 24 percent (*17 (due to ...)*, *5 (+2)*), a name or text 9
percent, a current/maximum pair 7 percent, a list 6 percent, a change written with an arrow
3 percent, a blank or placeholder 3 percent, a percentage 1 percent. By label, counted once
per story: the attributes lead (*strength* in a third of the window stories, then
*intelligence*, *agility*, *dexterity*, *wisdom*, *endurance*, *vitality*, *constitution*,
*perception*, *charisma*, *luck*), *level* in a fifth, the paired resources (*health*,
*mana*, *stamina*, *hp*, *mp*, *experience*) in a tenth to a sixth, and then the fields
whose values are not numbers: *name*, *class*, *skills*, *skill*, *rank*, *reward*,
*warning*. *Free points* appears in one story in twenty-five.

The reading for phase 2: the types the plan names are the market's (number, paired, name,
text, list, and percent as a number with a unit); a name-valued field is common enough
(*class*, *name*, *rank*, *skill*) that a sheet must be able to carry one; and the market's
*rank* is a number where ours is a rung with a name, so the ordinal type prints a name the
market mostly does not, which is a difference to keep in view rather than a defect. No bar.

## What is owed

Owners: this census does not read whose window a window is (a person, a place, an item), so
phase 2's owner generalisation rests on the plan's reasoning and not on a count.

## Which way the written changes go (`changes.py`, `changes.json`, 2026-09-03)

Phase 4 of the plan asks whether a book's numbers may fall. Over the same 14,156 chapters,
596 window fields are written as a change with an arrow; 570 rise, 22 fall, 4 stay. An end
written with a sign (*171 → +29*) is an increment and counts by its sign; the first run read
sixteen of those as falls and the script now reads the sign. Twenty-two stories write a change
this way and eight of them write a fall.

The falls, read by label and value only: six are points spent to nothing (*Free Stats 230 →
0*, *Unused Points 32 → 0*, *Stat bonus 3 → 0*; three stories), six are a pool or a derived
figure going down (*HP 660 → 252*, *MP 220 → 192*, *Armor 1920 → 1454*; two stories), and
ten are an attribute or a standing going down (*Magic 23 → 20*, *Strength 12 → 10*, *Essence
10 → 7*, *Supreme blood influence 82% → 51*; four stories).

The reading for phase 4: numbers go up is the genre's rule and not a law. Written falls are
one change in twenty-seven, and the commonest is a spend, which is a fall paired with a rise
somewhere else on the window. An attribute that falls on its own is written by four stories in
twenty-two, so a book that wants one declares it. Nothing here is about quality, and no bar.
