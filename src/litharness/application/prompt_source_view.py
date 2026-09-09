"""Validate and page recorded prompt provenance without looking up or inferring sources."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from litharness.domain.jobs import input_digest_for

SCHEMA = "litharness.prompt-sources.v1"
MAX_SOURCE_LIMIT = 100
COMPOSITION_COVERAGE = (
    "selected_packet_items_and_renderer_fragments; upstream_inputs_of_derived_fragments_not_mapped"
)
_CONTEXT_FIELDS = {
    "source",
    "query",
    "query_id",
    "manuscript_revision_id",
    "plan_revision_id",
    "book_id",
    "branch_id",
    "logical_id",
    "pov_character_id",
    "story_order_key",
    "coverage",
    "disclosure_at",
    "story_time_cutoff",
}
_ITEM_FIELDS = {
    "item_id",
    "source_logical_id",
    "source_kind",
    "authority",
    "pov_visibility",
    "source_span",
    "packed_text_sha256",
}


def _integer(value: object, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def validate_source_query(source_id: str | None, source_offset: int, source_limit: int) -> None:
    """Reject malformed paging even when the requested historical map is absent."""
    if source_id is not None and not _string(source_id):
        raise ValueError("source_id must be a nonempty string or null")
    if not _integer(source_offset):
        raise ValueError("source_offset must be a nonnegative integer")
    if not _integer(source_limit) or source_limit > MAX_SOURCE_LIMIT:
        raise ValueError(f"source_limit must be an integer from 0 through {MAX_SOURCE_LIMIT}")


def _source_valid(source: dict[str, Any], kind: str, entry_hash: str) -> bool:
    if kind == "context_item":
        if not source.keys() >= _ITEM_FIELDS or source.keys() - (
            _ITEM_FIELDS | {"source_record_sha256", "plan_revision_id"}
        ):
            return False
        if not all(
            _string(source[key])
            for key in ("item_id", "source_logical_id", "source_kind", "authority")
        ):
            return False
        visibility = source["pov_visibility"]
        if not isinstance(visibility, list) or not all(_string(value) for value in visibility):
            return False
        span = source["source_span"]
        if span is not None and not (
            isinstance(span, list)
            and len(span) == 2
            and _integer(span[0])
            and _integer(span[1])
            and span[0] <= span[1]
        ):
            return False
        if source["packed_text_sha256"] != entry_hash:
            return False
        if "source_record_sha256" in source and not _digest(source["source_record_sha256"]):
            return False
        return "plan_revision_id" not in source or _string(source["plan_revision_id"])
    if kind == "renderer":
        return (
            {"producer", "attribution"} <= source.keys()
            and not source.keys() - {"producer", "attribution", "writer_id"}
            and _string(source["producer"])
            and source["attribution"] == "renderer_fragment"
            and ("writer_id" not in source or _string(source["writer_id"]))
        )
    if kind != "scene_plan":
        return False
    if not {"producer", "rendered_argument_sha256"} <= source.keys() or source.keys() - {
        "producer",
        "rendered_argument_sha256",
        "source_logical_id",
        "plan_revision_id",
        "stored_text_sha256",
        "rendered_equals_stored",
    }:
        return False
    return (
        _string(source["producer"])
        and _digest(source["rendered_argument_sha256"])
        and all(
            source.get(key) is None or _string(source[key])
            for key in ("source_logical_id", "plan_revision_id")
        )
        and (source.get("stored_text_sha256") is None or _digest(source["stored_text_sha256"]))
        and (
            source.get("rendered_equals_stored") is None
            or isinstance(source["rendered_equals_stored"], bool)
        )
    )


def _validated(
    recorded: object, payload: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(recorded, dict) or set(recorded) != {
        "schema",
        "stages",
        "entries",
        "context",
    }:
        return None, "malformed_source_map"
    if recorded["schema"] != SCHEMA:
        return None, "unsupported_source_schema"
    stages = recorded["stages"]
    if not isinstance(stages, dict) or set(stages) != {"system", "prompt"}:
        return None, "malformed_stage_identities"
    for name, identity in stages.items():
        if (
            not isinstance(identity, dict)
            or set(identity) != {"chars", "sha256"}
            or not _integer(identity["chars"])
            or not _digest(identity["sha256"])
        ):
            return None, "malformed_stage_identities"
        text = payload.get(name)
        if not isinstance(text, str):
            return None, "stage_not_recorded"
        if len(text) != identity["chars"] or _hash(text) != identity["sha256"]:
            return None, "stage_identity_mismatch"
    context = recorded["context"]
    if not isinstance(context, dict) or context.keys() - _CONTEXT_FIELDS:
        return None, "malformed_source_context"
    if any(value is not None and not _string(value) for value in context.values()):
        return None, "malformed_source_context"
    if "coverage" in context and context["coverage"] != COMPOSITION_COVERAGE:
        return None, "malformed_source_context"
    for key, payload_key in (
        ("book_id", "book_id"),
        ("branch_id", "branch_id"),
        ("logical_id", "logical_id"),
        ("manuscript_revision_id", "revision_id"),
        ("plan_revision_id", "plan_revision_id"),
    ):
        if (
            context.get(key) is not None
            and payload.get(payload_key) is not None
            and context[key] != payload[payload_key]
        ):
            return None, "source_context_scope_mismatch"
    entries = recorded["entries"]
    if not isinstance(entries, list):
        return None, "malformed_source_entries"
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "stage",
            "start",
            "end",
            "sha256",
            "kind",
            "section",
            "source",
        }:
            return None, "malformed_source_entry"
        if not isinstance(entry["stage"], str) or entry["stage"] not in stages:
            return None, "malformed_source_entry"
        text = payload[entry["stage"]]
        if not (
            _integer(entry["start"])
            and _integer(entry["end"])
            and entry["start"] <= entry["end"] <= len(text)
        ):
            return None, "invalid_source_span"
        if (
            not _digest(entry["sha256"])
            or _hash(text[entry["start"] : entry["end"]]) != entry["sha256"]
        ):
            return None, "source_entry_hash_mismatch"
        if (
            not _string(entry["section"])
            or not isinstance(entry["source"], dict)
            or not _source_valid(entry["source"], entry["kind"], entry["sha256"])
        ):
            return None, "malformed_source_metadata"
        if entry["kind"] == "scene_plan" and entry["source"].get("plan_revision_id") is not None:
            entry_plan = entry["source"]["plan_revision_id"]
            if any(
                recorded_plan is not None and entry_plan != recorded_plan
                for recorded_plan in (
                    context.get("plan_revision_id"),
                    payload.get("plan_revision_id"),
                )
            ):
                return None, "source_plan_revision_mismatch"
    return recorded, None


def validated_prompt_sources(
    payload: dict[str, Any], *, recorded_input_digest: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate frozen composition data without paging, presentation or source lookup."""
    if "prompt_sources" not in payload:
        return None, "prompt_sources_not_recorded"
    recorded, reason = _validated(payload["prompt_sources"], payload)
    if recorded is None:
        return None, reason
    # Slice hashes bind text; the complete payload digest also binds source identities.
    if recorded_input_digest is None:
        return None, "input_digest_not_recorded"
    if not _digest(recorded_input_digest):
        return None, "invalid_recorded_input_digest"
    try:
        current_digest = input_digest_for(payload)
    except (TypeError, ValueError):
        return None, "input_payload_not_serializable"
    if current_digest != recorded_input_digest:
        return None, "input_digest_mismatch"
    return recorded, None


def build_prompt_source_view(
    payload: dict[str, Any],
    *,
    source_id: str | None = None,
    source_offset: int = 0,
    source_limit: int = 0,
    unavailable_reason: str | None = None,
    shelf_exposure: bool = False,
    recorded_input_digest: str | None = None,
) -> dict[str, Any]:
    """Read a hash-bound input map; identities do not establish semantic or causal support."""
    validate_source_query(source_id, source_offset, source_limit)
    result: dict[str, Any] = {
        "status": "not_recorded",
        "reason": "prompt_sources_not_recorded",
        "schema": None,
        "count": None,
        "matched_count": None,
        "stages": {},
        "entries": [],
        "context": None,
        "pagination": {
            "offset": source_offset,
            "limit": source_limit,
            "shown": 0,
            "next_offset": None,
            "truncated": False,
        },
    }
    if unavailable_reason is not None:
        return {**result, "status": "unavailable", "reason": unavailable_reason}
    if "prompt_sources" not in payload:
        return result
    recorded, reason = validated_prompt_sources(
        payload, recorded_input_digest=recorded_input_digest
    )
    if recorded is None:
        status = (
            "unavailable" if reason == "input_digest_not_recorded" else "invalid_recorded_value"
        )
        return {**result, "status": status, "reason": reason}
    result.update(schema=SCHEMA, count=len(recorded["entries"]), stages=recorded["stages"])
    if shelf_exposure:
        return {**result, "status": "withheld", "reason": "exemplar_shelf_exposure"}
    selected = [
        {"entry_index": index, **entry}
        for index, entry in enumerate(recorded["entries"])
        if source_id is None
        or source_id in (entry["source"].get("item_id"), entry["source"].get("source_logical_id"))
    ]
    shown = selected[source_offset : source_offset + source_limit] if source_limit else []
    next_offset = source_offset + len(shown)
    more = bool(source_limit) and next_offset < len(selected)
    return {
        **result,
        "status": "available",
        "reason": None,
        "matched_count": len(selected),
        "entries": shown,
        "context": recorded["context"],
        "pagination": {
            "offset": source_offset,
            "limit": source_limit,
            "shown": len(shown),
            "next_offset": next_offset if more else None,
            "truncated": more,
        },
    }


__all__ = [
    "COMPOSITION_COVERAGE",
    "MAX_SOURCE_LIMIT",
    "SCHEMA",
    "build_prompt_source_view",
    "validate_source_query",
    "validated_prompt_sources",
]
