"""Stored text stages for one scene's attributed job, without replay or interpretation.

The default response carries identities and lengths only. One explicitly requested stage
can return a bounded excerpt. Raw text is the provider adapter's returned text, not its
transport envelope; missing historical records are never reconstructed from current code.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from litharness.application import dossier as dossier_mod
from litharness.application import exemplars as exemplars_mod
from litharness.application.handlers import REVISION_GATE, SCENE_DRAFT
from litharness.application.ports import DossierStore, StoredEvent
from litharness.application.reviser import REVISION_PROFILE
from litharness.domain.events import EventType
from litharness.domain.nodes import Node
from litharness.domain.revision import Revision

STAGES = ("system", "prompt", "raw_draft", "pre_revision_draft", "accepted")
MAX_EXCERPT_CHARS = 20_000
_SHELF_HEADINGS = (exemplars_mod.OPENINGS_HEADING, exemplars_mod.BLURBS_HEADING)
_TEXT_EVENTS = {
    EventType.MANUSCRIPT_CANDIDATE_CREATED,
    EventType.MANUSCRIPT_REVISION_ACCEPTED,
}


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _story_order(payload: dict[str, Any], request_absent: str | None) -> dict[str, Any]:
    """Read the frozen drafting cutoff without deriving it from current reading order."""
    result: dict[str, Any] = {
        "source": "job_payload.selected_by.story_order_key",
        "status": "not_recorded",
        "key": None,
    }
    if request_absent is not None:
        return {**result, "status": "unavailable", "reason": request_absent}
    selected = payload.get("selected_by")
    if not isinstance(selected, dict) or "story_order_key" not in selected:
        return result
    key = selected["story_order_key"]
    if key is None:
        return {**result, "status": "unpositioned"}
    if not isinstance(key, str) or not key.strip():
        return {**result, "status": "invalid_recorded_value"}
    return {**result, "status": "recorded", "key": key}


def _has_shelf_heading(text: object) -> bool:
    return isinstance(text, str) and any(heading in text for heading in _SHELF_HEADINGS)


@dataclass(frozen=True)
class _Stage:
    descriptor: dict[str, Any]
    text: str | None


def _stage(
    original: str | None = None,
    *,
    absent_reason: str | None = None,
    recorded_sha256: str | None = None,
    delivered: str | None = None,
    withholding_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> _Stage:
    original_hash = _hash(original) if original is not None else None
    matches = (
        original_hash == recorded_sha256
        if original_hash is not None and recorded_sha256 is not None
        else None
    )
    if matches is False:
        withholding_reason = "recorded_hash_mismatch"
    withheld = original is not None and withholding_reason is not None
    text = (
        None if withheld or original is None else delivered if delivered is not None else original
    )
    return _Stage(
        {
            "available": original is not None,
            "absent_reason": absent_reason if original is None else None,
            "original_chars": len(original) if original is not None else None,
            "original_sha256": original_hash,
            "recorded_sha256": recorded_sha256,
            "recorded_hash_matches": matches,
            "delivered_chars": len(text) if text is not None else None,
            "delivered_sha256": _hash(text) if text is not None else None,
            "redacted": withheld or (text is not None and text != original),
            "withheld": withheld,
            "withholding_reason": withholding_reason if withheld else None,
            "metadata": metadata or {},
        },
        text,
    )


def _decision_rows(
    rows: list[dict[str, Any]], events: list[StoredEvent], *, job_kind: str | None
) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        matched = [
            item for item in events if item.event.payload.get("decision_id") == row["decision_id"]
        ]
        revision = (
            row.get("profile") == REVISION_PROFILE
            or any(
                item.event.event_type is EventType.POLICY_DECISION_RECORDED
                and item.event.payload.get("stage") == "revision"
                for item in matched
            )
            or any(gate.get("rule_or_critic_id") == REVISION_GATE for gate in row.get("gates", []))
        )
        result.append(
            {
                **row,
                "stage": "revision"
                if revision
                else "scene_draft"
                if job_kind == SCENE_DRAFT
                else "unknown",
                "event_sequence": min((item.sequence for item in matched), default=None),
            }
        )
    # Attempt counters can reset on revival. Only recorded event sequence supplies time
    # order; rows without an event keep their relative order after the recorded rows.
    return sorted(
        result, key=lambda row: (row["event_sequence"] is None, row["event_sequence"] or 0)
    )


def _text_event(
    events: list[StoredEvent], decision: dict[str, Any] | None, logical_id: str
) -> tuple[StoredEvent | None, str | None]:
    if decision is None:
        return None, "decision_not_recorded"
    candidates = [
        item
        for item in events
        if item.event.event_type in _TEXT_EVENTS
        and item.event.payload.get("logical_id") == logical_id
        and item.event.payload.get("decision_id") == decision["decision_id"]
    ]
    resulting = decision.get("resulting_revision_id")
    matches = [
        item
        for item in candidates
        if (
            item.event.event_type is EventType.MANUSCRIPT_REVISION_ACCEPTED
            and resulting is not None
            and item.event.revision_id == resulting
            and item.event.payload.get("accepted") is True
        )
        or (
            item.event.event_type is EventType.MANUSCRIPT_CANDIDATE_CREATED
            and resulting is None
            and item.event.revision_id == decision.get("base_revision_id")
            and item.event.payload.get("accepted") is False
        )
    ]
    if len(matches) > 1:
        return None, "ambiguous_event"
    if not matches:
        return None, "event_revision_mismatch" if candidates else "raw_draft_not_recorded"
    return matches[0], None


def _event_metadata(stored: StoredEvent | None) -> dict[str, Any]:
    if stored is None:
        return {}
    event = stored.event
    result: dict[str, Any] = {
        "event_sequence": stored.sequence,
        "event_type": event.event_type.value,
        "revision_id": event.revision_id,
    }
    for key in ("em_dashes_removed", "markup_removed", "revised_by"):
        if key in event.payload:
            result[key] = event.payload[key]
    if event.event_type is EventType.MANUSCRIPT_REVISION_ACCEPTED:
        result["cleanup_counts_scope"] = "adopted_candidate"
    return result


def _excerpt(stage: str, value: _Stage, offset: int, max_chars: int) -> dict[str, Any]:
    text = value.text
    total = len(text) if text is not None else 0
    end = min(offset + max_chars, total)
    return {
        "stage": stage,
        "offset": offset,
        "total_chars": total,
        "next_offset": end if end < total else None,
        "truncated": end < total,
        "text": text[offset:end] if text is not None else None,
        "redacted": value.descriptor["redacted"],
        "withheld": value.descriptor["withheld"],
        "reason": value.descriptor["withholding_reason"] or value.descriptor["absent_reason"],
    }


def build_scene_trace(
    store: DossierStore,
    book_id: str,
    branch_id: str,
    node: Node,
    head: Revision,
    *,
    decision_id: str | None = None,
    stage: str | None = None,
    offset: int = 0,
    max_chars: int = 12_000,
) -> dict[str, Any]:
    """Trace a decision in the scene's current attributed or unfinished job only.

    A decision is a policy record, not necessarily a provider invocation. In particular,
    revision-stage decisions do not inherit the frozen writer request. Character offsets
    refer to the delivered, possibly redacted text; hashes identify exact UTF-8 strings.
    """
    if stage is not None and stage not in STAGES:
        raise ValueError(f"stage must be one of {', '.join(STAGES)}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a nonnegative integer")
    if (
        isinstance(max_chars, bool)
        or not isinstance(max_chars, int)
        or not 0 < max_chars <= MAX_EXCERPT_CHARS
    ):
        raise ValueError(f"max_chars must be an integer from 1 through {MAX_EXCERPT_CHARS}")

    dossier = dossier_mod.scene_dossier(store, book_id, branch_id, node, head)
    job_info = dossier["job"]
    job_id = job_info["job_id"] if job_info else None
    job = None
    if job_id is not None:
        with suppress(KeyError):
            job = store.load_job(job_id)
    payload = dict(job.payload) if job is not None else {}
    for key, expected in (
        ("book_id", book_id),
        ("branch_id", branch_id),
        ("logical_id", node.logical_id),
    ):
        if key in payload and payload[key] != expected:
            raise ValueError("job payload does not match the requested scene scope")
    events = (
        sorted(
            (
                item
                for item in store.read_job_log(book_id, branch_id, job_id)
                if item.event.book_id == book_id
                and item.event.branch_id == branch_id
                and item.event.payload.get("job_id") == job_id
            ),
            key=lambda item: item.sequence,
        )
        if job_id is not None
        else []
    )
    attempts = _decision_rows(
        [row for row in dossier["attempts"] if row.get("logical_id") in (None, node.logical_id)],
        events,
        job_kind=job.job_kind if job is not None else None,
    )
    selected_id = decision_id
    if selected_id is None and dossier["scene"]["accepted_in"] is None:
        # Revival can reset attempts. The dossier's historical fallback sorts that
        # counter; for an unfinished trace prefer actual recorded drafting chronology.
        recorded = [
            row
            for row in attempts
            if row["stage"] == "scene_draft" and row["event_sequence"] is not None
        ]
        if recorded:
            selected_id = recorded[-1]["decision_id"]
    if selected_id is None and dossier["decision"] is not None:
        selected_id = dossier["decision"]["decision_id"]
    selected = next((row for row in attempts if row["decision_id"] == selected_id), None)
    if decision_id is not None and selected is None:
        raise ValueError("decision_id is not in this scene's attributed or unfinished job")
    if selected is None and dossier["decision"] is not None and decision_id is None:
        if dossier["decision"].get("logical_id") not in (None, node.logical_id):
            raise ValueError("attributed decision does not match the requested scene scope")
        selected = _decision_rows(
            [dossier["decision"]], events, job_kind=job.job_kind if job is not None else None
        )[0]
    is_revision = selected is not None and selected["stage"] == "revision"

    originals = {
        key: payload.get(key) if isinstance(payload.get(key), str) else None
        for key in ("system", "prompt")
    }
    shelf_provenance = "exemplars" in payload
    shelf_heading = any(_has_shelf_heading(value) for value in originals.values())
    shelf_exposure = shelf_provenance or shelf_heading
    cleaned = dossier_mod.redact_shelf({"prompt": originals})["prompt"]
    stages: dict[str, _Stage] = {}
    request_absent = (
        "revision_request_not_recorded"
        if is_revision
        else "job_not_recorded"
        if job is None
        else "unsupported_job_kind"
        if job.job_kind != SCENE_DRAFT
        else None
    )
    for name in ("system", "prompt"):
        original = originals[name]
        delivered = cleaned[name]
        withholding = None
        if _has_shelf_heading(original) and name == "system":
            withholding = "exemplar_shelf_exposure"
        elif (delivered == dossier_mod.PROMPT_WITHHELD and original != delivered) or (
            name == "prompt" and shelf_provenance and not _has_shelf_heading(original)
        ):
            withholding = "exemplar_shelf_boundary_not_recorded"
        stages[name] = _stage(
            original if request_absent is None else None,
            absent_reason=request_absent or f"{name}_not_recorded",
            delivered=delivered,
            withholding_reason=withholding,
            metadata={"source": "job_payload", "job_id": job_id},
        )

    matched, event_absent = _text_event(events, selected, node.logical_id)
    event_meta = _event_metadata(matched)
    raw = matched.event.payload.get("raw_draft") if matched is not None else None
    raw = raw if isinstance(raw, dict) else {}
    raw_text = raw.get("text") if isinstance(raw.get("text"), str) else None
    raw_meta = {**event_meta, "source": "provider_adapter_text"}
    for key in ("provider", "model"):
        if isinstance(raw.get(key), str):
            raw_meta[key] = raw[key]
    stages["raw_draft"] = _stage(
        raw_text if not is_revision else None,
        absent_reason="revision_output_not_recorded"
        if is_revision
        else event_absent or "raw_draft_not_recorded",
        recorded_sha256=raw.get("sha256") if isinstance(raw.get("sha256"), str) else None,
        withholding_reason=(
            "exemplar_shelf_exposure" if shelf_exposure or _has_shelf_heading(raw_text) else None
        ),
        metadata=raw_meta,
    )

    resulting = selected.get("resulting_revision_id") if selected is not None else None
    accepted = None
    accepted_absent = "no_resulting_revision"
    if resulting is not None and not is_revision:
        try:
            accepted_revision = store.load_revision(resulting)
            if accepted_revision.book_id != book_id or accepted_revision.branch_id != branch_id:
                accepted_absent = "accepted_revision_scope_mismatch"
            else:
                accepted = accepted_revision.node(node.logical_id)
                accepted_absent = "accepted_text_not_recorded"
        except KeyError:
            accepted_absent = "accepted_revision_not_recorded"
    stages["accepted"] = _stage(
        accepted.content if accepted is not None else None,
        absent_reason=accepted_absent,
        recorded_sha256=accepted.content_sha256 if accepted is not None else None,
        withholding_reason=(
            "exemplar_shelf_exposure"
            if accepted is not None and _has_shelf_heading(accepted.content)
            else None
        ),
        metadata={**event_meta, "source": "accepted_revision", "revision_id": resulting},
    )
    kept = (
        [
            item
            for item in store.pre_revision_drafts(book_id, branch_id, logical_id=node.logical_id)
            if item.book_id == book_id
            and item.branch_id == branch_id
            and item.logical_id == node.logical_id
            and item.job_id == job_id
            and item.revision_id == resulting
        ]
        if resulting is not None and not is_revision
        else []
    )
    before = kept[0] if len(kept) == 1 else None
    stages["pre_revision_draft"] = _stage(
        before.content if before is not None else None,
        absent_reason="ambiguous_pre_revision_draft"
        if len(kept) > 1
        else "pre_revision_draft_not_recorded",
        recorded_sha256=before.content_sha256 if before is not None else None,
        withholding_reason=(
            "exemplar_shelf_exposure"
            if shelf_exposure or (before is not None and _has_shelf_heading(before.content))
            else None
        ),
        metadata={
            "source": "pre_revision_drafts",
            "revision_id": resulting,
            **(
                {
                    "draft_id": before.draft_id,
                    "attempt": before.attempt,
                    "drafted_by": before.drafted_by,
                    "revised_by": before.revised_by,
                    "em_dashes_removed": before.em_dashes_removed,
                    "recorded_at": before.recorded_at,
                }
                if before is not None
                else {}
            ),
        },
    )
    raw_hash = stages["raw_draft"].descriptor["original_sha256"]
    accepted_hash = stages["accepted"].descriptor["original_sha256"]
    stages["accepted"].descriptor["metadata"]["differs_from_raw_draft"] = (
        raw_hash != accepted_hash if raw_hash is not None and accepted_hash is not None else None
    )
    absent = [name for name in STAGES if not stages[name].descriptor["available"]]
    if job is None:
        absent.append("job")
    if selected is None:
        absent.append("decision")
    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "logical_id": node.logical_id,
        "head_revision_id": head.revision_id,
        "job_id": job_id,
        "decision": selected,
        "attempts": attempts,
        "request": {
            "source": "job_payload",
            "scope": "current_attributed_or_unfinished_job",
            "input_digest": job.input_digest if job is not None else None,
            "provider_transport_captured": False,
            "story_order": _story_order(payload, request_absent),
            "available": request_absent is None and originals["prompt"] is not None,
            "absent_reason": request_absent
            or ("prompt_not_recorded" if originals["prompt"] is None else None),
            "exemplar_shelf_exposure": shelf_exposure,
        },
        "stages": {name: stages[name].descriptor for name in STAGES},
        "excerpt": _excerpt(stage, stages[stage], offset, max_chars) if stage is not None else None,
        "absent": absent,
    }


__all__ = ["MAX_EXCERPT_CHARS", "STAGES", "build_scene_trace"]
