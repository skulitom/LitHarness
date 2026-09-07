# Visible source-group identifiers in the initial response

2026-09-07, after the sole initial call and before any update or chapter call. The initial
response completed, but structural validation rejected its F01/F06/F03 references. Those are
the source_id metadata values actually present in its four-unit input; the validator expected
the split id values. The initial prompt said source ID without distinguishing these fields.
Concern and unresolved text use opening facts only. Raw request, response, failure log and
original frozen code/registration remain unchanged. This is a declared protocol deviation.

Amend only the identifier handling for this retained initial response. Deterministically expand
each source_id reference to ALL its member id values visible in the actual initial request:
F01 -> F01a,F01b; F03 -> F03b; F06 -> F06b. Never consult the complete chapter to expand a group:
F03a was not visible and must not enter. Leave already-canonical IDs unchanged. Preserve list
order with stable deduplication and leave concern/unresolved wording untouched. Reject unknown
references, namespace collisions, foreground/peripheral overlap or size overflow. No model
selects a member, repairs language or proposes another initial state.

The expanded state is a separate retained artifact, not a replacement for the raw response.
The initial structural failure remains in the result history. This exception does not waive
temporal/semantic review or permit changed character content. It resolves the grouping namespace
that the input itself exposed; it is not evidence for the attention hypothesis.

Before the first update call, remove source_id metadata from its source_units and explicitly
identify id as the reference field. Keep every source unit's id, kind, when and text, allowed
availability sets, initial concern text, activations, model, system and call budget unchanged.
This input adjustment is committed and frozen before its output exists. The update response
must satisfy the original canonical-ID validator; no general repair loop is introduced.

Use the amendment adapter while keeping the original runner immutable:

```powershell
uv run python research/quality-measurement/prose_attention_event_ids.py prepare --out runs/ab/prose-attention-events-20260907
uv run python research/quality-measurement/prose_attention_event_ids.py updates --out runs/ab/prose-attention-events-20260907
uv run python research/quality-measurement/prose_attention_event_ids.py freeze --out runs/ab/prose-attention-events-20260907 --review runs/ab/prose-attention-events-20260907/temporal-review.json
uv run python research/quality-measurement/prose_attention_event_ids.py draft --out runs/ab/prose-attention-events-20260907
```

Run handoff and commit this amendment, adapter and focused tests before normalization/further
generation. Freeze the normalized initial state, exact adjusted update request, amendment and
adapter hashes in normalization-manifest.json. All downstream calls verify it. The two chapter
conditions still receive identical material except rendering_mode. Six total calls maximum;
the initial call counts once. No direct API, model redraw, new source fact or quality selection.
