# Pre-registration — how much of the market's progression furniture this house can declare

Registered 2026-09-03, before any shard is read for it, for deliverable 1 of
`plan/handoff-market-fit.md`. A census, not a bar: it measures, by declaring rather than by
arguing, how much of the market's system furniture the house vocabulary
(`litharness world vocabulary`, stage-0 §202 to §212.1) expresses without a code change, and
names every gap by the share of sampled stories it blocks. Nothing here is about quality; a
shape's presence is not a merit, and no model is asked anything.

## What is read

The cached LitRPG shards through `corpus_io.royalroad_chapters`, every chapter, under the
MirrorBench interpreter, one CPU job. A story is in the population when at least one of its
chapters prints a **window**: the system-displays census's reading (a run of two or more
furniture lines by `progression_cadence`'s `v2` classifier, `system_displays.runs_of`). The
sample is sixty stories drawn from that population by `random.Random(20260903).sample`, in
`sample.py`; the seed and the population size are written to `sample.json`. Beside them, the
four shelf anchors under `book-library/` (stage-0 §196's placed openings) are read from their
files with the same script (`--files`), one chapter each, and reported as their own row so the
market share is never computed over them.

## Shapes, and the reader

A **shape** is what a story's furniture says its system looks like, written in the vocabulary
of `litharness world vocabulary` and never as text: which fields of which kinds on which
owners, which moves, which displays, which rules. One reader (the session that runs this
census) reads each sampled story's furniture dump — its window lines and notice lines, in
release order, duplicates dropped, capped at 160 lines — and writes one row of
`shapes.jsonl`. The reader's protocol, fixed here:

- Furniture only. A system written into prose without furniture is invisible, so every shape
  is a floor on the story's system, and a story whose sampled chapters print one two-field
  window is a two-field shape.
- A field's label is recorded verbatim only when it is one of the eighty shared labels
  `system-displays/field_labels.json` already publishes; any other label is recorded as its
  class (`other attribute`, `other pool`, `other text`), so a story's own coinage never
  leaves the measurement side. A set's members are recorded by count and depth, never by
  name. Nothing else from a line is written down.
- Kinds are read off the value: `number`, `paired` (current/maximum), `percent`, `rate` (a
  pool with a regeneration figure beside it), `ordinal` (a rank or grade with a name), `name`
  (a class, race, title or profession from a set), `text`, `set` (a list), `set_depth` (a
  list whose members carry a level), `set_rank` (members carrying a rank or rarity each),
  `blank` (shown as `---`, `N/A` or empty), `derived` (a figure the furniture marks as computed
  from others), `change` (written as before → after).
- Owners: `protagonist`, `person` (another character), `creature`, `place`, `item`, `party`
  (several subjects on one screen), `institution`.
- Moves, when the furniture shows one: `gain`, `deepen`, `rise`, `choose`, `spend`,
  `growth` (more than eight named grants over the sampled chapters), `change_kind` (a thing
  becoming another), `loss`. A field that moves by allocation, by rung, or both, says so.
- Displays: `line` (any window), `offer` (a choice screen, with its option count and whether
  the options carry text or conditions), `notice_gain`, `notice_rise`, `notice_other` (a
  furniture line for any other event: a welcome, a warning, a quest, a title, a zone, the
  System speaking), `readout_other` (another subject's sheet where the protagonist reads it),
  `item_box`, `quest`, `other_screen` (a menu, a map, a shop, an inventory screen),
  `description_text` (a paragraph on a screen), `party_display`.
- Rules the furniture states and no declaration carries: `exp_accrual` (a rise by
  accumulation), `pool_refill`, `class_effect` (a name that moves a number), `derived_rule`,
  `direction_down` (a number that improves by falling).

The schema is the one `census.py` reads; a row the script cannot read is a row the reader
rewrites, never one the script guesses at.

## Declaring each shape (`census.py`)

For every shape the script builds the `world declare` sequence that expresses it, runs it
against a fresh store (`init`, `new`, the declarations, `world check`, `world accept`,
`world check`, a second round where growth needs one), renders every declared owner's line
through `extraction.render_status_line`, and records the house's own sentences. The
translation is fixed here, one clause per feature, and the outcome of a feature is one of:

- **clean** — a declaration exists whose meaning is the feature's and the store accepts it;
- **workaround** — a declaration carries the feature's facts in a different form (named);
- **refused** — the store's `check`, `accept` or completion complains, in the house's words;
- **missing** — no declaration carries the feature (named).

A shape's outcome is the worst of its features, in the order missing, refused, workaround,
clean. Each non-clean feature carries a **gap tag**, and the gaps are ranked by the share of
the sixty market shapes carrying the tag under any outcome.

The clauses:

| feature | declared as | outcome | gap tag |
| --- | --- | --- | --- |
| a window (`line`) | `status_sheet` with typed columns and a `status_snapshot` | clean | — |
| a window wider than nine fields | the same, printed on one line | workaround | `box_view` |
| `number`, `paired`, `text`, `name`, `set`, `set_depth`, `change` | the sheet kinds of §204 (`change` as the after value) | clean | — |
| `ordinal` column | `kind: ordinal` on a declared ladder | clean | — |
| `percent` | a number, the unit in the label (§204 refused a percent kind) | workaround | `percent_as_number` |
| `rate` | two number columns, the pool and its regeneration; the refill rule is not modelled | workaround, and `pool_refill` missing | `rate_as_two_columns`, `pool_refill` |
| `blank` | the column declared, standing at nothing and hidden (§203) | workaround | `blank_hidden` |
| `derived` | a number nothing derives | workaround, and `derived_rule` missing | `derived_rule` |
| `set_rank` | a set without its members' ranks | missing | `member_rank` |
| owner `person`, `creature`, `place`, `institution` | a `status_sheet` with `owner` (§206) | clean | — |
| owner `item` | a `carrier` subject's own sheet, printed as a `[STATUS]` line and never asked for | workaround | `item_box` |
| owner `party` | one sheet per member; nothing prints them together | missing | `party_display` |
| `readout_other` | the other subject's owner sheet; no scene is asked to print it (§209 owed) | workaround | `readout_on_request` |
| `offer` with two to four options | a fork `governed_by` the system, `offers` its ways, each `grants` a capability; text as `manifests_as`, a condition as `requires` (§207) | clean | — |
| `offer` with one, or more than four, options | the same; the store answers | refused as the store says | `fork_options` |
| `notice_gain`, `notice_rise` | a `graph_line` with a phrase for `can_do` or `stands_at` (§208, §113) | clean | — |
| `notice_other` | nothing | missing | `notice_other` |
| `quest` | nothing | missing | `quest_display` |
| `other_screen` | nothing | missing | `other_screen` |
| `description_text` | `manifests_as`, one line | workaround | `description_text` |
| a ladder | `type criterion`, `comparator ordinal`, three rungs `precedes`, `stands_at`; a ladder the furniture never shows but a system needs is declared and tagged | clean; workaround | `ladder_assumed` |
| a system (any move, a fork, or a field that moves) | the system role, its grants `governed_by` it with `is_a`, `can_do` at the depths seen, `requires` where the furniture shows prerequisites, the sheet naming it; the store answers | as the store says | see below |
| more than eight grants | eight at the seed, the rest declared after the first accept (§211) | workaround; then the store answers | `growth_two_rounds`, and `growth_floor` when the second check refuses |
| `spend` by allocation | the attribute a grant paid in a stock the rungs hand out (§210) | clean | — |
| a stock credited by something other than a rung | the same `per_rung` stock | workaround | `stock_source` |
| a field that both rises per rung and is allocated | `per_rung` and `costs` on one grant; the store answers | refused | `stock_priced` |
| `change_kind`, `loss` | a `change` node with `participant` and `effect` (§212) | clean | — |
| `exp_accrual`, `class_effect`, `direction_down` | nothing | missing | the rule's own tag |
| no display in the sampled chapters | nothing to declare; this house prints from chapter one (§209) | workaround | `opening_without_display` |

The store's refusals are read from `accept`'s completion sentence and the second `check`,
and tagged by the clause they name: `fork_options` (*a fork offers 2 to 4*), `draw_count`
(*a drawn system carries 5 to 8*), `list_not_graph` (*a list rather than a graph*),
`no_depth` (*declares no depth*), `scale_ceiling` (*a drawn scale runs to 2..99*),
`mixed_columns` (*left unfinished on purpose*: plain columns beside a system's), `stock_priced`,
`growth_floor` (*describing different books* after growth), `second_system_line` (two book
sheets), and `other_refusal` for anything else, with the sentence kept. A refused system
leaves the shape's sheet half as it was: the book drafts under its plain sheet and no beat
speaks its system, which is the house's own sentence and is recorded beside the tag.

## What is reported

`sample.json` (the draw), `shapes.jsonl` (sixty-four rows), `census.json` (per shape: the
declaration sequence as argv lists, the features with their outcomes and the house's
sentences, the rendered lines, the floor's answer), and `FINDINGS.md`: the outcome table for
the market shapes with the shelf beside it, the distribution of widest windows, the ranked
gap list with each gap's share, kind and what is missing, and the defects the declaring
found in the house itself. Distributions, no bar.

## What it cannot show

A sample of sixty from the stories that print windows, which is a third of the LitRPG
stories in two shards, themselves an arbitrary slice of each fiction. Shapes drawn by one
reader from furniture alone, with no second reader and no agreement measured. A story's
shape is a floor on its system. The translation is one sequence per feature; a cleverer
sequence may exist for a shape reported as a workaround, and the report says which form was
tried. Nothing here says whether a declared shape produces a chapter that reads as its genre.

## Anti-scope

No model. No score, no ranking of books or systems. No corpus text in any committed file, in
any store, prompt, fixture or test: labels only from the shared list, counts otherwise. The
census declares into scratch stores and draws no chapter.
