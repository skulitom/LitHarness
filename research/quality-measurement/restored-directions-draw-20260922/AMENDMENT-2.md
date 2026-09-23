# Amendment 2: draw 2 after a listing fix

**Located cause.** Draw 1 passed its concept gate and failed listing item L1 ("the listing
promises LitRPG: a system and progression the reader can see"): the listing never said System,
rendered the book's Slot as "room for one magical skill", and named no rank; progression was only
"Getting better takes practice against problems that can hurt" (`draw-1/GATE-listing.md`). The
listing prompt `application/overview.py` `_CONCEPT_TASK` (`writer.overview.concept.v2`) told the
writer to "use ordinary language before special terminology" and that exact counts do not belong.

**Remedy.** Commit `406073f` (stage-0 §261): the supplied-concept listing task
(`writer.overview.concept.v3`) asks for the game system, its skills and the ranks or levels it
counts as the book names them, keeps ordinary language for everything else, and says a rank the
system counts is not incidental. It touches `src/`; nothing else in the draw changes. Draw 1 was
shown to the operator on 2026-09-23 and recorded (`shown`).

**Draw 2** is a fresh draw from the concept: the same brief, writer (rowntree), provider, layout,
ceilings and gates. Its concept is newly invented, so the concept gate is read again.
