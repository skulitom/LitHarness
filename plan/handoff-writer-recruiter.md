# Handoff: a Recruiter that grows the roster, and the twelve shelves the operator named

**Status: OPEN, 2026-08-28.** Companion to [`plan/writer-roster.md`](writer-roster.md), which
owns the roster design, its prior, and its rails — this brief adds the missing half: the roster
is four hand-written dossiers in `domain/writers.py` and nothing can grow it. Read the roster
plan's §4 and §5 before any design work here.

The operator, 2026-08-28, verbatim:

> *"Can there be some internal recruiter system, which will generate more varied and useful
> writers? i aknowledge i never asked for Light Fantasy, but having diverse writers would be an
> asset to our project. Here are interesting writers specializations: Light Fantasy, Cozy
> Fantasy, Litrpg Comedy, Sci-Fi, Dark Fantasy, Supernatural, Cultivation, Chinese Cultivation
> (in english), Historical, Progression Fantasy, Isekai, Portal Fantasy"*

And the sequencing directive from the same conversation: fix what made pilot 11's overview read
poorly first, then continue to chapters. That fix is reader-read-5's routing, not this brief's;
the two do not gate each other. This brief is system-improvement work, the spend category the
operator granted generous headroom for.

## Why a recruiter, said plainly

The premise lock is visible in the dossier text itself. Each cast dossier carries one vivid
image and its writer opens every empty-brief listing on it: ferreira's dossier says *"the first
message nobody asked for"* and ~~all eight~~ **all seven distinct ferreira listings** on disk
open on screens lighting at once — **nine of nine counting the two drafts that differ from
their own revisions, which is the stronger fact: the beat survives the revision step as well as
the draw** (corrected in place 2026-08-28; the executing session's recount); halloran's says
the first monster in an impossible place and all five open on the thing in the stairwell. The tonal skew rides the same text — eight of eight covers ever produced sit
below mid-grey, and the cover pipeline reads the listing, so the darkness propagates downstream
from prose whose upstream is the dossier and the prompts. Variety is a roster property before it
is a prompt property, and roster growth is generative work — the kind the Architect pattern
already contains.

## Rails, before the design — each bought by a failure already on the record

1. **`legal_dossier` (R1) unchanged and unweakened.** A dossier says what this writer knows and
   loves, never what good prose is; the registered prose axes are refused at the gate. A
   recruiter that drafts around the vocabulary is drafting a violation, not a workaround.
2. **A specialization is an appetite, never a day job or a setting** (the G3 lesson in
   `writers.py`'s CAST comment: four career-dossiers produced four worlds with no magic in
   them). "Cozy Fantasy" recruits somebody who *reads and loves to write* cozy fantasy, not an
   innkeeper.
3. **Deep in domain, shallow in demography** (roster plan §4).
4. **No model hires or casts by preference.** §84, §137 (the distinctness gate's calibration is
   still empty), §61(5)/§105.1. Recruitment output lands `PROPOSED`; acceptance is legality
   checks plus a person's decision row. Casting keeps the operator's standing default; where a
   brief names a shelf with exactly one matching specialist, that is a deterministic match, and
   with several, a deterministic rotation (least-recently-cast) — never a judgment.
5. **A dossier is a containment surface.** It rides the system message of every scene call.
   New dossiers are versioned, content-addressed (`writer_id_for` already exists and includes
   the exemplar digest from first mint), append-only, and refusable.
6. **The prior stays stated.** §89.1, §83 and §77 say identity may be decorative. The roster
   plan's §6 measurement order still governs before anybody claims a recruit *does* anything.

## The slate

The twelve, verbatim from the operator: **Light Fantasy, Cozy Fantasy, LitRPG Comedy, Sci-Fi,
Dark Fantasy, Supernatural, Cultivation, Chinese Cultivation (in English), Historical,
Progression Fantasy, Isekai, Portal Fantasy.**

Coverage note, description not judgment: the current cast already sits on roughly four
(ferreira ≈ system-apocalypse progression, halloran ≈ portal/isekai, vance ≈ reincarnation and
beasts, okonjo ≈ cultivation). The slate is a recruitment brief, not a quota, and "useful" is
the operator's word beside "varied" — both halves are theirs.

## Design shape — build on roster plan §3, do not re-design it

- **Store-backed roster beside the compiled cast.** Writers become records (id from
  `writer_id_for`), with `CAST` retained as the control fixtures it already is; `--writer`
  resolves store-first. Migration plus adapter; no model involved.
- **`litharness recruit` runs an agent in the Architect containment pattern**: a narrow tool
  allowance (a `roster` suite — `vocabulary`, `declare`, `show`, `check`, `accept`), everything
  it declares `PROPOSED` until `roster accept` carries it with a decision row. `roster
  vocabulary` must name each field's *shape*, not just its name — the write-only-interface
  lesson has now been paid for three times.
- **One recruit call per specialization**, drafting dossier, interests, and note; `legal_dossier`
  runs at declare and again at accept.
- **The premise-image question is a design variable, not an assumed fix.** The four cast
  dossiers all use the single-vivid-image shape. Recruit in at least two deliberate shapes —
  single image, and several distinct loves at category level — so a registered listing arm can
  measure whether image count drives the premise lock. Do not silently standardize on either.

## Tasks

1. Store-backed roster, migration, resolution path. Tests beside `writers.py`'s existing ones.
2. The recruit agent and `roster` tool suite, contained as above. Free until run.
3. The recruitment run over the twelve. Dossier-sized text; small spend, log it anyway.
4. Fresh listings by recruits ride the existing listing loop and sit **behind** the listing fix
   in the operator's stated order. Whether a recruit's listing reads differently is a question
   for the registered brief/dossier arm, never for an ad-hoc model read (§95, §97.4).

## Not in scope, refused here so it is not discovered later

- Director casting (that is `director-role.md`'s build, and it needs its own containment).
- Any ranking among recruits or writers; any "best dossier"; any model reading two dossiers and
  preferring one.
- Craft content in dossiers (R1), or a dossier asserting what the genre's reader wants — the
  retired Forge's dead move.
- Deleting or editing the four cast writers. They are the controls the roster is read against.
