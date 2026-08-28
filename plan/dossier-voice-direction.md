# Dossier voice: exhibit the writer's register instead of describing it

**Status: direction note, 2026-08-28. No arm, no build; a named follow-on to §146's
registered dossier-shape arm.** The operator, verbatim:

> *"I'm thinking we might need to give them instructions in that writers voice. Do you not
> think they will use the same voice as used in their prompt?"*

## The answer is yes, and it is already measured, three ways

1. **Punctuation register leaked from our rule text into output.** The round-one listings
   carried 11.8 em dashes per 1k words against the market's 0.0 — our instruction prose is
   em-dash-heavy, and the model wrote listings in the *prompt's* punctuation
   (`handoff-listing-loop.md`'s table records the fall to 0.0).
2. **Vocabulary leaks.** §120: machinery words from persona/prompt text reached a chapter;
   `house.MACHINERY_WORDS` exists because of it, and the recruiter's census just caught
   `rung` arriving in a fresh dossier (§146.8).
3. **Phrasing leaks.** §138: a rule's affirmative half returns as a verbal formula; §146.8
   measured it again the same day — *"a moment a story opens on"* came back verbatim in two
   of four dossiers.

A model writes in the register it is handed. Today every writer is handed the same register:
the dossier is written in this repository's own institutional voice, so the one channel that
demonstrably steers style is currently steering all writers toward one style.

## Why exhibition is the interesting design, not just a rephrasing

R1 (`legal_dossier`) forbids a dossier from *naming* what good prose is — a craft
instruction is the banned move. A dossier **written as the writer writes** names nothing:
it demonstrates. Exhibition is a third channel beside instruction (which fails, §135/§138)
and subtraction (which works): it uses the measured leak *for* differentiation instead of
suffering it as contamination. It also fits the roster's own frame — appetite was the
identity variable §146 tests; voice is the other half of identity, and it is currently
constant across the cast by construction.

## Two cautions, fixed before anyone builds

- **A registered axis can be pre-empted by demonstration as surely as by instruction.**
  `prose_axes_named` catches the words; it cannot catch a dossier that simply *is* heavy in
  a registered marker (an em-dash-laden exhibited voice asserts by example what the em-dash
  loop exists to test). An exhibited-voice dossier needs a mechanical census against the
  registered axes before it is legal, not a vibe check.
- **Scope: dossiers only, not the rule stack.** The house floor (`CLARITY` etc.) is shared
  semantics; per-writer rewrites of rules would fork what the rules mean. The dossier is the
  identity carrier; exhibition belongs there first.

## The test, when it is wanted

A follow-on arm in §146's own framework, registered before any draw: same recruit slate,
`house-voiced` vs `voice-exhibited` dossier cells, the exhibited voice drafted by the
recruiter as a generative act; readings on the writers' *listings* (register counters against
the market, premise lock beside them), prediction written first, §105's null prior inherited.
Composes with the beat/no-beat variable rather than replacing it. Until that arm runs,
"exhibited voice changes output voice" is a well-supported conjecture with three mechanism
receipts and zero direct measurements.

## The exemplar question, same day

The operator, verbatim: *"yet i'm sure we have plenty examples of text in other voices. Why
don't we just ask a model to rewrite X instruction in Y voice example?"*

Rewrite-against-exemplar is the right mechanism, and the roster design already carries its
socket: `writer_id_for`'s `exemplar_digest` has participated in every writer id since the
first mint, canonically empty, put there so that *"populating an exemplar later should mint
a new writer, because an exemplar changes what the writer drafts and that is identity"*
(`domain/writers.py`, roster plan §3.1). What decides everything is where voice Y's example
text comes from, and the three sources are not alike:

1. **Market text as the exemplar — forbidden by RS1, and for the right reason.** ~~A voice
   cloned from a specific serial's pages is also derivative in precisely the way the
   firewall exists to prevent.~~ **Corrected in place, on the operator's push-back
   (verbatim: *"We aren't breaking any copyright we are asking to write a prompt with a
   similar style"*): the copyright half was this note's overclaim — style is not
   copyrightable and similar-style generation infringes nothing.** The rail's real load is
   measurement independence: the market is the project's yardstick (the follower gradient,
   the register counters, the coordinator ceiling's 0-of-60, §61's eventual bar are all
   comparisons *to* it), and corpus passages inside generation prompts make our artifacts
   partial functions of the measurement corpus — after which every ours-vs-market number
   partly measures the market against itself, and the memorization controls the salience
   battery needs are poisoned by design. `tests/test_corpus_leak_audit.py` enforces the
   crossing mechanically. **The permitted middle path:** the measurement side may distill a
   market voice into a *derived style descriptor* — sentence-length distribution, connective
   density, person, tense, fragment rate; numbers and labels, never prose ("commit derived
   numbers and identifiers, never third-party prose") — and the descriptor may cross to
   generation. The corpus aims; the pretrained prior executes. If the operator ever decides
   raw market exemplars should cross anyway, that is theirs to amend — as a recorded stage-0
   decision naming which instruments lose their independence, never as a side effect.
2. **Our own books as the exemplar — legal but circular.** Every book on the shelf speaks
   the leaked house register this note is about; using them as Y reproduces the homogeneity.
3. **A fresh, model-drafted exemplar — legal, and the designed path.** The model already
   carries the genre's voices from pretraining; invoking that prior ("write as this writer
   writes") is how all generation here works, and is categorically different from pasting
   held text into a prompt. So the flow is: the writer drafts a short *original* passage as
   itself (a generative act, no judging), the passage becomes the exemplar, its digest mints
   the writer identity, and the dossier — or any instruction bound for that writer — can be
   rewritten against it.

Two gates carry over unchanged onto any rewritten text, because the output is a containment
surface: `legal_dossier` (no named prose axes survive a rewrite) and the registered-axis
census (an exemplar heavy in a measured marker pre-empts the instrument that measures it).
And the scope caution stands: writer-bound text may be voice-rewritten; the shared rule
floor may not.

## Anti-scope

Nothing scheduled; §146's arm, read 6's routed fixes, and the dashboard come first. Nothing
here licenses editing any existing dossier — content-addressed ids stay put, and populating
an exemplar mints a **new** writer rather than mutating one.
