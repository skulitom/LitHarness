# Findings — how much of the market's progression furniture this house can declare

House form: the claim, the number beside it, and the caveat travelling with the claim.
`PREREG.md` owns the design, the reader's protocol and every translation clause, fixed before
any shard was read for this (with three reader's amendments recorded there, made after the
first batch of dumps and before any declaration ran); this file owns the reading. Status:
**OBSERVED**, 2026-09-03, one corpus pass and one census run. Raw material: `sample.json`
(the draw: 14,156 chapters, 608 stories, 301 that print a window, sixty sampled by seed
20260903), `shapes.jsonl` (sixty-four shapes, one row per story, labels only from the shared
eighty, nothing quoted), `census.json` (every declaration sequence as argv lists, the house's
own sentences, the rendered lines, the floor's answer). No model. Nothing here promotes a
claim past OBSERVED, and no bar is declared.

## The headline, with its list behind it

Declared shape by shape into fresh stores through `world declare`, `world check` and
`world accept`, **three of the sixty market shapes declare cleanly, four more with a
workaround, and fifty-three carry at least one feature the vocabulary has no declaration
for.** Counted feature by feature instead, 844 of the 1,224 features the sixty shapes carry
are declared cleanly (69 percent), 144 with a workaround, 78 are refused by the store, and
158 have nothing to be declared with. The two readings are the same fact seen from two
sides: the house declares most of what a window holds, and almost every story also holds a
line or two the house has no word for.

| group | shapes | clean | workaround | refused | not expressible |
| --- | --- | --- | --- | --- | --- |
| market | 60 | 3 | 4 | 0 | 53 |
| shelf | 4 | 0 | 0 | 0 | 4 |

A shape's outcome is the worst of its features (not expressible, then refused, then
workaround, then clean), so *refused* reads zero at the shape level only because every
shape the store refused also carries a display nothing declares; thirty shapes carry a
refusal the store said in its own words (the second table below).

## The ranked gaps

The share is over the sixty market shapes, under any outcome; the shelf column is the four
anchors beside it. The kind is the clause's in `PREREG.md`.

| rank | gap | kind | market shapes | share | shelf | what is missing |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `notice_other` | missing | 49 | 0.817 | 3 | a notice for anything but a gain or a rise: a welcome, a warning, a quest, a title, a zone, the System speaking |
| 2 | `mixed_columns` | refused | 30 | 0.5 | 1 | a plain column (a pool, a currency, a class) beside a system's grants on one line: accept leaves the system unfinished on purpose and no beat speaks it |
| 3 | `quest_display` | missing | 27 | 0.45 | 0 | a quest card: objective, progress, reward |
| 4 | `readout_on_request` | workaround | 23 | 0.383 | 1 | another subject's sheet where the protagonist reads it: declared, never asked for |
| 5 | `other_screen` | missing | 21 | 0.35 | 1 | a menu, a map, a shop, an inventory screen |
| 6 | `exp_accrual` | missing | 19 | 0.317 | 0 | a rise by accumulation (experience to next level) |
| 7 | `percent_as_number` | workaround | 18 | 0.3 | 0 | a percentage as a number with the unit in the label |
| 8 | `list_not_graph` | refused | 16 | 0.267 | 1 | grants with no prerequisite among them: a list, not a graph |
| 9 | `box_view` | workaround | 15 | 0.25 | 1 | a window wider than nine fields, printed on one line |
| 10 | `growth_two_rounds` | workaround | 15 | 0.25 | 1 | more than eight grants: eight at the seed, the rest after |
| 11 | `description_text` | workaround | 15 | 0.25 | 0 | a paragraph on a screen, carried as one line |
| 12 | `member_rank` | missing | 13 | 0.217 | 0 | a list whose members carry a rank, a rarity or a second number each |
| 13 | `no_depth` | refused | 13 | 0.217 | 0 | grants held or not, with no depth anywhere: no scale can be minted |
| 14 | `item_box` | workaround | 11 | 0.183 | 1 | an item's box, printed as a [STATUS] line nothing asks for |
| 15 | `derived_rule` | missing | 10 | 0.167 | 1 | a figure derived from other columns |
| 16 | `class_effect` | missing | 9 | 0.15 | 0 | a class, title, race or item that moves a number |
| 17 | `draw_count` | refused | 9 | 0.15 | 0 | fewer than five grants in a system |
| 18 | `pool_refill` | missing | 8 | 0.133 | 1 | a pool's refill rule |
| 19 | `rate_as_two_columns` | workaround | 5 | 0.083 | 1 | a pool's regeneration as a second column |
| 20 | `blank_hidden` | workaround | 4 | 0.067 | 1 | a field shown blank, standing at nothing and hidden |
| 21 | `ladder_assumed` | workaround | 3 | 0.05 | 0 | a system with no ladder shown: a three-rung ladder declared for it |
| 22 | `party_display` | missing | 1 | 0.017 | 1 | several subjects' sheets on one screen |
| 23 | `stock_source` | workaround | 1 | 0.017 | 1 | a point stock credited by something other than a rung |
| 24 | `fork_options` | refused | 1 | 0.017 | 0 | a choice screen with one way, or more than four |
| 25 | `scale_ceiling` | refused | 1 | 0.017 | 0 | a grant held past 99: the drawn scale runs to 2..99 |
| 26 | `stock_priced` | refused | 1 | 0.017 | 0 | a column both handed out per rung and allocated by points |
| 27 | `direction_down` | missing | 0 | 0.0 | 1 | a number that improves by falling |

**What the store said, and what the translator's clause counted.** A refusal is tagged
from the store's own sentence where the store said one, and from the clause in `PREREG.md`
where an earlier refusal of the same system masked it; `census.json` keeps both, with
*masked* written where the sentence is the clause's. Thirty shapes took the system route
(any move, a fork, or a column that moves by points), and in every one of the thirty the
store refused the system before it reached the mixed-columns branch: sixteen for grants with
no prerequisite among them (*a list rather than a graph*), thirteen for grants held or not
with no depth anywhere (*declares no depth*), one each for a scale past 99, a column both
handed out per rung and priced, and a fork of six ways; the count floor was said once and
masked eight times. So `mixed_columns` at thirty is the clause's count, every system shape in
the sample printing a pool, a currency, a class or an age beside its grants, and the store's
sentence for it (*a system is drawn and was left unfinished on purpose*) appeared on none of
them here; the probe that fixed the clause (§D1 in the session's probes, reproduced by
`census.py` on a sheet of a level, a paired pool, a currency and five grants) is where it was
read. The ranking is a ranking of clauses; the store's own order of refusal is the one just
given.

## What the shapes carry

Sixty stories, read from their furniture alone (`shapes.jsonl`; a story's shape is a floor
on its system).

- **Windows.** Fifty of the sixty print a window with fields; the widest per story is four
  or fewer in twenty-five, five to nine in twenty, ten to fourteen in eleven, fifteen or
  more in four (the widest twenty-eight, then twenty-five). Fifteen shapes, a quarter, are
  wider than the nine columns the house's line prints as furniture (`MAX_ABILITIES` and the
  rung), which is `box_view`'s count.
- **Owners.** Fifty-five protagonist sheets, sixteen creatures', fifteen other people's,
  eleven items', six places', one institution's, one party screen. A creature's or a
  person's sheet is read where the protagonist reads it in twenty-three stories (an
  Identify, an appraisal, a kill log with levels), which is `readout_on_request`'s count.
- **Kinds**, over 696 fields: a bare number 297, a current/maximum pair 102, text 88, a name
  from a set 39, an ordinal 35, a percent 34, a list 33, a figure the furniture marks as
  derived 23, a list whose members carry more than one value 14, a change written with an
  arrow 10, a list with a depth per member 9, a pool with a rate 7, a blank 5. The reader's
  amendments cover the three shapes the catalogue lacked: a tier with a number after it
  (one story; two fields), decimal numbers (two stories; text), and choice screens whose
  option count the furniture never shows (eight of ten screens; two options recorded).
- **Moves shown**: a gain in 26 stories, a rise in 23, a spend in 21, a deepening in 13, a
  choice in 10, growth past eight named grants in 5, a change of kind in 3, a loss in none.
  Grants are named in 27 stories: one to four in thirteen of them (below the draw's floor
  of five), five to eight in eight, nine or more in six; held with no depth anywhere in
  fifteen of the twenty-seven; with a prerequisite shown in two.
- **Displays beyond the line**: a notice for something other than a gain or a rise in 49
  stories (the System speaking, a welcome, a warning, a quest given, a title, a zone, a kill
  log, a timer), a quest card in 27, another subject's readout in 23, another screen (a
  menu, a store, a map, an inventory, a board) in 21, an item box in 18, a paragraph on a
  screen in 15, a gain notice in 12, a choice screen in 10, a rise notice in 10, a party
  screen in 1.
- **Rules the furniture states and no declaration carries**: a rise by accumulation in 19,
  a derived figure in 10, a class, title, race or item that moves a number in 9, a pool
  that refills in 7 (8 with the rate fields).

The three shapes that declare cleanly are a sheet of six tiered attributes and an age; a
sheet of five attributes, a race with its level, an age, a height and a charge; and a talent
sheet of five pairs. The four workarounds are one enormous status screen (twenty-five
fields on one line), a pilot's readout with a machine's box, a pair of pools with a creature's
level read beside them, and a set of summon cards. Every one of the fifty-six shapes that
carries a sheet clears the floor (`has_starting_sheet`); the four that do not carry only
notices.

## What the ranked list says for the slices

1. **The notice** (rank 1, four shapes in five). The genre's furniture is a System that
   speaks: every kind of event has its bracketed line, and the house prints a line for a
   gain and a line for a rise and nothing else. A declared shape exists for the fact (a
   `change` node with a `manifests_as` line, which the Architect already writes as story
   beats, §212) and no scene is asked to print it. The smallest change is the ask, in the
   book's own bracket, for a change that lands at the scene; no module, no default phrase.
2. **Plain columns beside a system's grants** (rank 2, half the shapes, every shape with a
   system). The house's line is the rung and the grants; the market's is the rung, the
   pools, the points, the class and the grants. The refusal is deliberate (§165.2's branch)
   and it is the one the census earns reversing: a snapshot that carries the system's
   columns and others is a position in the system with columns of its own beside it.
3. **The quest card** (rank 3) is the notice's twin with counters: given, progressed,
   completed, rewarded. Under the first slice a quest is a change the System announces;
   its counters are paired columns already. A card of its own is not earned separately
   until the notice has been drawn and read.
4. **The readout on request** (rank 4, the item §209 owed): every fact is declarable
   (§206), nothing is asked for.
5. **Another screen** (rank 5): a menu, a store, a board. Not one display but several, and
   the census does not separate them; the store (a currency spent on listed things) is the
   commonest.

Below these, the store's own refusals (a flat skill list, held-or-not grants, fewer than
five grants) block the system route in every shape that took it; they are the draw's rules
(§160) applied to a hand-declared system at completion, and whether a *declared* system may
be a list, held-or-not, or three grants wide is a decision for the ledger, not a slice this
census lands by itself. The market's skills are a list with levels; the house's are a graph
with depths.

## What the declaring found in the house itself

Three defects, found by the probes that fixed the translation clauses and by the census run,
each fixed before the numbers above were taken and replayed identical on the four stored
books with `tools/replay_books.py --baseline`:

- **An owner's sheet counted as a second book sheet.** `genre.system_gap` counted every canon
  `status_sheet`, so a book with its own sheet and a creature's, a place's or an item's (§206)
  was told it had declared two and must retract one, on every `world check` since §206. It
  now counts the book's own sheets only (commit 9490336).
- **Growth blocked the floor and printed `?`.** After §211 let a system grow, the floor
  compared a snapshot's keys to the system's exactly, so the first grant declared after the
  seed took the book from drafting to blocked until the snapshot was re-seeded by hand; and
  the sheet that follows its system printed `?` for every grown column. A snapshot carrying
  the rung and only the system's columns is now a position in it, and a following sheet
  hides a column the snapshot never held as it hides any unheld one (commit 49d5fe6). The
  fifteen shapes that grow past eight grants pass the floor after their second round.
- **An unreadable sheet declaration brought `world accept` down.** The first census run
  declared, through a translator fault, a sheet repeating a value key; `world accept` read it
  through §213.1's preview and the floor and fell over with a `MalformedSheet` traceback,
  where a sentence was owed. The parser's refusal is right; `declare` now says the sheet
  cannot be read, `check` lists it as a complaint and still answers over the readable
  records, `accept` refuses it without `--force`, and a declaration in the same slot replaces
  it.

And one thing that is not a defect but bit the first numberless probe: a graph-line label is
printed inside its own brackets, so a label written as `[REALM]` declares a line that silently
never prints (`graph_line_for` degrades to absence by design). The vocabulary line says the
label is a bracket tag; it does not say the brackets are added.

## What it cannot show

A sample of sixty from the 301 stories that print windows, which are half of the LitRPG
stories in two shards, themselves an arbitrary slice of each fiction; a story's shape is a
floor on its system, since a system written into prose without furniture is invisible to the
classifier, and the dump each shape was drawn from is capped at 160 lines. Shapes drawn by
one reader from furniture alone, with no second reader and no agreement measured; the
reader's three amendments are recorded in `PREREG.md`. The translation is one sequence per
feature, fixed before the sample was read, and a cleverer sequence may exist for a shape
reported as a workaround; `census.json` records which was tried. The system route inflates
the sheet with the grants a fork's ways would open (one per option), which is faithful to
what a fork is here and adds to the count refusals. Nothing here says whether a declared
shape produces a chapter that reads as its genre.

## Anti-scope

No model, no score, no ranking of books. No corpus text in any committed file, store, prompt,
fixture or test: labels only from the shared list, counts otherwise, and the dumps stay
outside the tree. The census declared into scratch stores and drew no chapter; whether a
declared shape produces a chapter that reads as its genre is the shelf's question and the
operator's read.
