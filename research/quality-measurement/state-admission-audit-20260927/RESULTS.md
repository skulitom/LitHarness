# The existing state constructor fails semantic admission

The first bounded candidate is `binary-substitution.case-sham.v1`, the existing state-continuity
constructor. It can produce packets and valid source offsets, but cannot supply an independently
valid answer key for a reader. The executable counterexamples below reject its admission claim.
No generated manuscript was changed or sampled and no model was called. This is an engineering
result about a constructor, not evidence that a reader failed or that fiction has a defect.

## What failed

[results-before.json](results-before.json) records the constructor before the eligibility fix;
[results.json](results.json) records it after. Both identify source bytes, fixture identities and
packet hashes. [audit.py](audit.py) supplies the project-authored cases and the independent finite
state enumeration; [RUNBOOK.md](RUNBOOK.md) specifies the checks and their scope.

| Check | Executable observation | Consequence |
| --- | --- | --- |
| Required context reaches the reader | Across 28 ordinary-case fixtures, all 84 public packets omit both the earlier evidence and intervening no-change statement. The same-scene positive control retains both in all three packets. | The constructor sends only the target scene. A distance field and a private anchor do not give a reader the evidence needed for a cross-scene contradiction. |
| Repeated equal states entail persistence | Each intact two-assertion key has two consistent three-instant binary paths; replacing the later value still leaves two. Adding an explicit no-change constraint leaves one intact path and no damaged path. | Equality at two times does not imply constancy between them. The census checks records and locations but does not establish that persistence constraint, identity/time scope or the assertions' semantic relation to the text. |
| Existing fingerprint matching excludes simple shortcuts | All 28 damage/control pairs match the six fingerprint fields, while every pair differs in character length and uppercase-letter delta. A fixed all-uppercase-word rule identifies all 56 edited ordinary-case packets without the anchor or story relation. | The control operation exposes its identity. The existing fingerprint comparison cannot certify a matched control. |
| The shortcut is a general reader | On the explicit uppercase-source destructive control, the same fixed rule labels the sham incorrectly (one of two edited packets identified). | The shortcut result is a counterexample to the construction guarantee, not a general classifier, ecological rate or reader capability. |

The 28 cases exhaust the current allowlisted substitution directions under two simple renderings.
They are not 28 independent books. Phrases such as a marker being alive are mechanical fixtures,
not examples of natural prose or claims about the quality of an edit. No significance test or
promotion threshold is appropriate here.

## What changed

The ecological manifest now uses `ecological-causal-salience.v2` and reports construction
availability separately from admission. `construction_ready` can be true while
`eligible_for_model_run` is always false. It also names the unresolved semantic, context and
surface-control gaps. Empty construction remains ineligible. The same-scene control is ineligible
too: retaining the anchor does not resolve the other conditions.

The diagnostic constructor and its existing packet identities are retained, so these failures
remain inspectable. Proposed `damaged` and `sham` names in the private packets denote construction
operations, not established literary labels. Previously saved artifacts are not overwritten.
This changes the research-audit eligibility report, not drafting, planning, manuscript acceptance
or reader-mechanism qualification.

Before the fix, `ecological_manifest` used `bool(items)` as its entire eligibility rule. That
implementation is in commit `07b077f2ce64375d47df2dc2d7f32425432247b3`,
`src/litharness/domain/salience.py`; its exact source digest is in the before report. The focused
regression suite now checks that both cross-scene and same-scene constructions remain ineligible.

## What this closes, and the next construction requirement

This result rejects the existing state's automatic-admission route. It does not refute causal
reader testing, prove that all possible state edits are unusable, or revisit the recorded costed
reader results. The earlier generated-book censuses already emitted no eligible items; these
counterexamples explain why increasing their candidate counts would not by itself unblock a run.

A replacement must establish an explicit relation and its temporal scope, intact consistency,
and the contradiction after editing independently of a model annotation. It must deliver every
needed premise to the reader and survive attacks on both semantic preservation and edit
fingerprints. An explicit no-change premise is necessary for this particular persistence
argument; inserting one into generated fiction creates a new synthetic task and does not prove
ecological validity. Relabelling a model's interpretation as a certificate would leave the
original problem intact.

The next design decision is therefore how to obtain that independently known relation on natural
generated text. The current constructor supplies no such answer. Reader calls remain premature;
this bounded attempt ends with a reproducible failure, rather than an admitted battery.

## Verification

The focused construction/regression checks and `uv run python tools/check.py handoff` passed.
The complete local validation receipt is `runs/state-admission-audit-20260927/handoff.log`,
including lint, types, diff/lock validation, branch-aware coverage, wheel build and the
corpus-history audit. Unrelated work already present in the checkout was preserved.
