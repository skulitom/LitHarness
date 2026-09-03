# Pre-registration — the market's system displays, chapters one to three

Registered 2026-09-03, before any shard is read, for phase 0 of `plan/system-generality.md`.
A census, not a bar: it describes what the genre's openings put on the page as system
displays, so the defaults of the phases that follow are set by a recorded decision against a
distribution rather than by anybody's impression (*"most LitRPG doesn't list skills at zero"*
is the operator's read and this is where it becomes a number, or does not).

## What is read

`corpus_io.royalroad_chapters` over the cached LitRPG shards, every story with at least three
chapters present, chapters one to three by `position`. Text only; no engagement field is
read (this is a census of what is on the page, and the conversion label would be a second
question). Under the MirrorBench interpreter, one CPU job, no model.

## Amendment before the run (2026-09-03, after two dry runs and before any full read)

The shards hold an arbitrary slice of each fiction, not its opening: `corpus_io` leaves
`position` at zero and the chapter title field carries the fiction's title, so *chapters one
to three by position* cannot be read off the metadata. Two readings replace it, both fixed
here before the run. **The early slice:** each story's three earliest chapters in the shards
by release date (positions 1 to 3 *within the sampled slice*), for every story with at least
three chapters present; this is a census of early-sampled chapters and is reported as such.
**The true openings:** the subset of chapters whose first lines carry a chapter-one or
prologue heading in the text itself (a dry run found about one such chapter in a hundred and
sixty, roughly one story in seven); the chapter-one readings below are taken from this subset
when it holds at least two hundred stories, and the entry says so if it does not. The subset's
bias is named: authors who write the heading into the text.

## What is counted, per chapter

Lines that are not prose come from `progression_cadence`'s furniture classifier (`v2`), the
same reading the cadence census used, so the two censuses agree on what a line is.

- **A window** is a run of two or more furniture lines with only blank lines between them
  (the placed openings put a blank line between fields; a run ends at a prose line). Per window: the field
  count (lines that read as `label: value` or `label value`, value numeric or a short token),
  and the share of fields whose value is `0`, `N/A`, `None`, `---`, `-` or empty.
- **A notice** is a furniture line that is not inside a window, split by the cadence census's
  families: level up, capability gain, stat delta, other.
- **A choice screen** is a window whose text names options (two or more numbered or bulleted
  lines, or the words *choose*, *select*, *pick*, *option*, *choice* on its first line). Per
  screen: the option count.
- **An item box** is a window whose first two lines carry an item marker (*rarity*, *durability*,
  *damage*, *item*, *weapon*, *armour*, a rarity tier word). **A quest card** is a window carrying
  *quest*, *objective* or *reward* on its first two lines. Both are heuristics and are reported
  as such; neither feeds a default.
- **No display at all**: a chapter with no window and no notice.

## What is reported

Per chapter position (1, 2, 3) and pooled: the share of chapters with any display, with a
window, with a choice screen; windows per chapter; fields per window (median, quartiles,
maximum); the share of window fields at zero or blank, and the share of windows carrying any
such field; notices per thousand words by family; options per choice screen. Raw rows in
`rows.jsonl` (one per chapter: counts only, no text), the summary in `results.json`, the
reading in `FINDINGS.md`.

## The reading, fixed before the run

- Phase 1's default for a newly drawn system's sheet (`show_unheld`) is set from the share of
  window fields at zero or blank: below one in five, unheld columns are hidden by default;
  above two in five, shown; between, hidden with the entry saying the range is wide.
- Phase 2's expectation of what a first window carries is the median field count at position
  1, and the maximum bounds the budgeted print rule for a `set` field.
- Phase 3's question, whether a choice display is a first-chapter object, is answered by the
  share of position-1 chapters with a choice screen against the share at position 3.
- A share of chapters with no display at all above one half at position 1 says the floor
  (phase 5) must not require a line in chapter one.

## What this cannot show

The classifier reads typography; a system written into prose without furniture is invisible
to it, so every share here is a floor. Three chapters per story is a census of openings and
not of the genre's middle. Nothing here is about quality; a display's presence is not a merit.

## Anti-scope

No model. No score. No ranking of books. The rows carry counts and never text; no corpus text
leaves the measurement side (RS1).
