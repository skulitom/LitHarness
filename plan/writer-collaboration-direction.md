# Writer collaboration: the operator's question, and what the record already says about it

**Status: direction note, 2026-08-28. No arm, no build, no claim.** The operator, verbatim:

> *"Do writers get to collaborate on books? i feel like this would help?"*

## What exists today

One writer per book, cast at the start; every scene call carries that one dossier
(§139.1). The book is already a collaboration **across roles** — the Architect builds the
world, the Narrative Planner plans, the Writer drafts, deterministic gates accept, the
editorial control plane stands ready — but the prose voice is deliberately singular. No
mechanism lets two writers touch one book.

## The three rails a collaboration design must not hit, each already paid for

1. **A writer never judges** (R3, `domain/writers.py`; §137's distinctness gate has empty
   calibration). Any scheme where writer A critiques, scores, or picks over writer B's prose
   is a judge in a hat, twice over.
2. **Reconciliation by agreement is the verdict channel with extra steps**
   (`reader-architecture-program.md` on panels). A writers' room that converges by consensus
   would relitigate everything §89/§97.4 closed.
3. **The one collaboration-shaped thing this repo measured shipped off.** VariationSession
   (§105): multiple perspectives on the same work, measured — same commits, 2.25× the calls,
   null. "More agents on the text" has a recorded prior, and it is null until an arm says
   otherwise.

## The admissible shapes, if this is ever built

- **Role-split collaboration, not peer collaboration**: a drafter and a *reviser* with
  different jobs — the reviser rewrites under its own dossier (a generative transformation,
  the mechanism family that stayed reliable where judgment went blind — `blurb_rewrite`'s
  lesson), never scores, never selects; deterministic gates still decide acceptance. Read 6
  hands this shape its motivating fact: the harvest's two halves sat at two defect strata
  with zero overlap — structure (the operator's items) and sentence mechanics (Maria's).
  A two-writer split that assigns one altitude each is the version of "collaboration" the
  evidence actually gestures at.
- **Arc- or volume-level splits** on the open-ended serial (different writers on different
  arcs) are structurally cheap and keep voice singular within any stretch a reader sits in.
- **Not admissible**: best-of-N writer drafts with any model picking (selection without
  containment, §61(5)); writers reviewing writers; consensus rooms.

## The order of cheapness, so the expensive thing is not built first

The defects that motivated the feeling ("this would help") are read 6's, and every one of
them routed as a **direction gap** — none routed as "the writer was alone." Before any
second writer exists: (1) the gap fixes (register direction, the compression-clause audit,
the class-menu clause post-mortem); (2) if a mechanics pass is still wanted after that, a
single-writer self-revision arm is cheaper than a second writer and tests the same
mechanism; (3) only then a cross-writer reviser, as a registered arm with §105 as the null
prior — measured on effects, shipped off if null, exactly as VariationSession was.

## Anti-scope

Nothing scheduled; nothing here licenses a build. The recruiter's twelve, the registered
dossier arm, and read 6's routed fixes come first.
