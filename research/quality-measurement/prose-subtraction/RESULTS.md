# Deletion-only diagnostic, 2026-09-05

Both fixed responses were rejected for nonmatching spans. Two claude-opus-5 calls completed
at $0.450017 reported equivalent cost, with no redraw or repaired response. The procedure is
in [PREREG.md](PREREG.md); hashes and per-span checks are in [execution.json](execution.json).
No edited manuscript was produced. All proposed cuts were inspected against their sources.
The observations below harvest defects; they are not quality labels or a general efficacy claim.

The original-chapter response proposed 20 cuts; 18 matched individually. Its two whole-paragraph
quotes included newlines absent from the supplied paragraph strings. The other response
proposed 18 cuts; 15 matched individually, while three paragraph-initial quotes invented leading
spaces. The exact matcher rejected both complete payloads. No fuzzy correction or valid-subset
application was performed. These boundary mismatches are an interface failure, not a literary
judgment, and fixing them would not fix the semantic problems below.

In the original response, cut 19 (P52) removes the protagonist's understanding of a consequential
ability price, describing it as commentary. Cut 18 (P47) removes why distant students remained
seated; the remaining distance statement does not preserve the account of inaudibility and
their response. Cut 16 (P45) removes the degree and manner of a resisting student's struggle.
It would also leave a lowercase fragment after a full stop. Cut 18 similarly leaves a lowercase
sentence start. These are matching spans that still violate the editing request.

In the second response, cuts 7, 10 and 11 together remove the supplied reasons for trained
compliance, not only repeated wording. Cut 9 leaves a lowercase sentence start after deleting
an announcement of future memory. Cut 12 removes the coffee-ring detail along with a repeated
register description. Other cuts remove repeated commentary locally, but both sets leave P1
unchanged. Exact source matching cannot determine whether a removable aside is causally
dispensable. Deletion alone is not sufficient containment for story meaning or grammar.

No production prompt, reader authority or manuscript changed. This result does not justify
adding an unrestricted narrative editor. A possible future design would distinguish protected
causes, choices, costs and revelations from optional emphasis before permitting edits; that is
a conjecture requiring independent controls, not a qualified fix or another queued experiment.

The local directory `runs/ab/prose-subtraction-20260905` retains all source text, requests,
responses, rejection records and a complete `cut-audit.md`. `proposals.html` displays both
sources and every proposed cut, explicitly as rejected proposals. The execution record gives
the local rebuild command and script hash; generated prose remains ignored.
