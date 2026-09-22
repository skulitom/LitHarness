"""Declared derivation of one derived prompt fragment type: the packed promise line.

A prompt source map (`application/prompt_sources.py`) identifies which packet item was
inserted where. For a derived item that stops at the item: the map says a promise line
was packed, not which ledger row it was rendered from, what that row said at the time, or
which recorded identities the row itself cites. This module records that one step further
for `domain.promises.describe_owed` lines only, at composition time, from the same ledger
tuple the packet was assembled from.

**A derivation is declared, never inferred.** Every node and edge comes from a stored
column or from the pure renderer that produced the packed text, and the construction check
re-renders the row and requires the packed text's digest. Nothing here reads later state,
guesses a missing opening scene, or says what a model attended to. Where the row does not
record an upstream identity, the derivation names it under `not_recorded`.

**Promise lines, and not summaries, because only this producer's inputs are stored.** A
`scene_summaries` row keeps the scene's content hash, model and profile, but not the job or
request the summary call received (open threads and the open ledger), so a summary's
complete inputs cannot be followed without reconstruction. `describe_owed` is a pure
function of four fields on a row the planner already reads.

**Nothing here changes a request.** The derivation is written into the sidecar map after
the system and prompt are final, and the map is excluded from drafting sample material
(`handlers.draft_sampler`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from hashlib import sha256
from typing import Any

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain.events import payload_digest
from litharness.domain.promises import Promise, describe_owed

SCHEMA = "litharness.fragment-derivation.v1"
PROMISE_LINE = "promise_line"
#: Every derivation says what it is not: a record of what the renderer read, not a claim
#: about what the drafting model attended to or used.
CLAIM = "declared_derivation_not_model_attention"
PRODUCER_FUNCTION = "litharness.domain.promises.describe_owed"
#: A source map whose context carries this coverage maps promise-line inputs. It is the
#: discriminator for the extension; the map schema stays `litharness.prompt-sources.v1`
#: so the sampling exclusion and the reviser's lock recovery still recognise the map.
DERIVATION_COVERAGE = (
    "selected_packet_items_and_renderer_fragments; promise_line_inputs_mapped; "
    "upstream_inputs_of_other_derived_fragments_not_mapped"
)

_PROBES = (
    Promise(
        promise_id="probe",
        subject="probe",
        description="probe description",
        opened_at_key="s01",
        due_key="s03",
        opened_by_revision="probe",
        window_start_key="s02",
        window_end_key="s03",
    ),
    Promise(
        promise_id="probe",
        subject="probe",
        description="probe description",
        opened_at_key="s01",
        due_key=None,
        opened_by_revision="probe",
    ),
)
#: The renderer's behaviour over fixed probes, one scheduled and one unscheduled. It moves
#: when the line's wording moves (the prefix change in stage-0 §255 would have moved it); a
#: change that leaves both probes' output alone does not, so it is a fingerprint and not a
#: code identity.
PRODUCER_FINGERPRINT = sha256(
    "\n".join(describe_owed(probe) for probe in _PROBES).encode("utf-8")
).hexdigest()

_NOT_RECORDED = {
    "opening_call_request": "promise_rows_do_not_record_the_call_that_opened_them",
    "asserting_model": "promise_row_names_no_model",
    "opening_evidence": "promise_row_has_no_located_opening_quote",
    "payoff_window_source": "promise_row_names_no_scheduling_plan_revision",
}
_NODE_FIELDS = {
    "promise_ledger_row": {
        "id",
        "kind",
        "promise_id",
        "row_sha256",
        "status_at_read",
        "asserting_model",
    },
    "manuscript_revision": {"id", "kind", "revision_id"},
    "scene_text_span": {"id", "kind", "logical_id", "content_hash", "span"},
    "plan_revision": {"id", "kind", "plan_revision_id"},
}
#: relation -> (source node kind, target node kind, the column or function that declares it)
_RELATIONS = {
    "rendered_from": ("fragment", "promise_ledger_row", PRODUCER_FUNCTION),
    "opened_under": ("promise_ledger_row", "manuscript_revision", "promises.opened_by_revision"),
    "opening_quote_located_in": (
        "promise_ledger_row",
        "scene_text_span",
        "promises.opened_logical_id",
    ),
    "payoff_window_proposed_by": (
        "promise_ledger_row",
        "plan_revision",
        "promises.scheduled_by_plan_revision",
    ),
}
_UNRECORDED_REASONS = {"rendered_text_mismatch"}


def _text_digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def position_relation(key: str | None, at: str | None) -> str:
    """Where a recorded story key sits against the drafting position, or why it cannot say.

    Stricter than `state.comparable`: two keys compare only when they share an order-key
    space **and** a width, because the ledger's string comparison is correct only under
    `beats_for`'s padding and `s2` against `s000003` is a question about spelling.
    """
    if at is None:
        return "drafting_position_not_recorded"
    if key is None:
        return "unpositioned"
    if key == at:
        return "at"
    space = state_mod.key_space(key)
    if space is None or space != state_mod.key_space(at) or len(key) != len(at):
        return "ambiguous"
    return "before" if key < at else "after"


def promise_line_derivation(
    promise: Promise, *, packed_sha256: str, drafting_at: str | None
) -> dict[str, Any]:
    """What one packed promise line was rendered from, as stored at composition time."""
    base: dict[str, Any] = {"schema": SCHEMA, "fragment_type": PROMISE_LINE, "claim": CLAIM}
    if _text_digest(describe_owed(promise)) != packed_sha256:
        return {**base, "status": "not_recorded", "reason": "rendered_text_mismatch"}
    row = f"promise:{promise.promise_id}"
    nodes: list[dict[str, Any]] = [
        {
            "id": row,
            "kind": "promise_ledger_row",
            "promise_id": promise.promise_id,
            "row_sha256": payload_digest(asdict(promise)),
            "status_at_read": promise.status,
            "asserting_model": promise.model or None,
        }
    ]
    edges = [_edge("fragment", "rendered_from", row)]
    missing = ["opening_call_request"]
    if not promise.model:
        missing.append("asserting_model")
    opened = f"manuscript_revision:{promise.opened_by_revision}"
    nodes.append(
        {"id": opened, "kind": "manuscript_revision", "revision_id": promise.opened_by_revision}
    )
    edges.append(_edge(row, "opened_under", opened))
    if promise.opening_evidenced:
        assert promise.opened_start is not None and promise.opened_end is not None
        scene = f"scene_text:{promise.opened_logical_id}@{promise.opened_content_hash}"
        nodes.append(
            {
                "id": scene,
                "kind": "scene_text_span",
                "logical_id": promise.opened_logical_id,
                "content_hash": promise.opened_content_hash,
                "span": [promise.opened_start, promise.opened_end],
            }
        )
        edges.append(_edge(row, "opening_quote_located_in", scene))
    else:
        missing.append("opening_evidence")
    if promise.scheduled:
        if promise.scheduled_by_plan_revision:
            plan = f"plan_revision:{promise.scheduled_by_plan_revision}"
            nodes.append(
                {
                    "id": plan,
                    "kind": "plan_revision",
                    "plan_revision_id": promise.scheduled_by_plan_revision,
                }
            )
            edges.append(_edge(row, "payoff_window_proposed_by", plan))
        else:
            missing.append("payoff_window_source")
    return {
        **base,
        "status": "recorded",
        "producer": {"function": PRODUCER_FUNCTION, "fingerprint_sha256": PRODUCER_FINGERPRINT},
        "rendered_sha256": packed_sha256,
        "rendered_inputs": {
            "description_sha256": _text_digest(promise.description),
            "due_key": promise.due_key,
            "window_start_key": promise.window_start_key,
            "window_end_key": promise.window_end_key,
        },
        "nodes": nodes,
        "edges": edges,
        "temporal": {
            "drafting_at": drafting_at,
            "opened_at_key": promise.opened_at_key,
            "due_key": promise.due_key,
            "opened_relation": position_relation(promise.opened_at_key, drafting_at),
            "due_relation": position_relation(promise.due_key, drafting_at),
        },
        "not_recorded": [{"input": name, "reason": _NOT_RECORDED[name]} for name in missing],
    }


def _edge(source: str, relation: str, target: str) -> dict[str, str]:
    return {
        "from": source,
        "relation": relation,
        "to": target,
        "declared_by": _RELATIONS[relation][2],
    }


def attach_promise_derivations(
    source_map: dict[str, Any], ledger: Sequence[Promise], *, drafting_at: str | None
) -> None:
    """Annotate a finished drafting map's packed promise lines; the request is not touched.

    `ledger` must be the tuple the packet was assembled from, so a packed item and its row
    are one read. An item matches only by its own recorded identity: a derived thread whose
    item and source ids are both a ledger row's id.
    """
    by_id = {promise.promise_id: promise for promise in ledger}
    for entry in source_map["entries"]:
        source = entry["source"]
        if (
            entry["kind"] != "context_item"
            or source.get("source_kind") != lc.ResourceKind.THREAD.value
            or source.get("authority") != lc.StateAuthority.DERIVED.value
        ):
            continue
        promise = by_id.get(source.get("source_logical_id", ""))
        if promise is None or source.get("item_id") != promise.promise_id:
            continue
        source["derivation"] = promise_line_derivation(
            promise, packed_sha256=entry["sha256"], drafting_at=drafting_at
        )
    source_map["context"]["coverage"] = DERIVATION_COVERAGE


def _node_valid(node: object) -> bool:
    if not isinstance(node, dict) or not isinstance(node.get("kind"), str):
        return False
    if node["kind"] not in _NODE_FIELDS:
        return False
    kind = node["kind"]
    if set(node) != _NODE_FIELDS[kind]:
        return False
    if kind == "promise_ledger_row":
        return (
            _string(node["promise_id"])
            and node["id"] == f"promise:{node['promise_id']}"
            and _digest(node["row_sha256"])
            and _string(node["status_at_read"])
            and (node["asserting_model"] is None or _string(node["asserting_model"]))
        )
    if kind == "manuscript_revision":
        return _string(node["revision_id"]) and node["id"] == (
            f"manuscript_revision:{node['revision_id']}"
        )
    if kind == "plan_revision":
        return _string(node["plan_revision_id"]) and node["id"] == (
            f"plan_revision:{node['plan_revision_id']}"
        )
    span = node["span"]
    return (
        _string(node["logical_id"])
        and _string(node["content_hash"])
        and node["id"] == f"scene_text:{node['logical_id']}@{node['content_hash']}"
        and isinstance(span, list)
        and len(span) == 2
        and _integer(span[0])
        and _integer(span[1])
        and span[0] < span[1]
    )


def valid_derivation(
    derivation: object, *, source: dict[str, Any], entry_sha256: str, drafting_at: object
) -> bool:
    """Whether a recorded derivation is internally consistent and carries no free text.

    Closed key sets throughout, so a derivation cannot smuggle source prose past the view.
    The checks are consistency over recorded values; none of them consult current state.
    """
    if not isinstance(derivation, dict):
        return False
    base = {"schema", "fragment_type", "claim", "status"}
    if (
        derivation.get("schema") != SCHEMA
        or derivation.get("fragment_type") != PROMISE_LINE
        or derivation.get("claim") != CLAIM
    ):
        return False
    if derivation.get("status") == "not_recorded":
        return (
            set(derivation) == base | {"reason"}
            and isinstance(derivation["reason"], str)
            and derivation["reason"] in _UNRECORDED_REASONS
        )
    if derivation.get("status") != "recorded" or set(derivation) != base | {
        "producer",
        "rendered_sha256",
        "rendered_inputs",
        "nodes",
        "edges",
        "temporal",
        "not_recorded",
    }:
        return False
    producer = derivation["producer"]
    if (
        not isinstance(producer, dict)
        or set(producer) != {"function", "fingerprint_sha256"}
        or producer["function"] != PRODUCER_FUNCTION
        or not _digest(producer["fingerprint_sha256"])
        or derivation["rendered_sha256"] != entry_sha256
    ):
        return False
    inputs = derivation["rendered_inputs"]
    if (
        not isinstance(inputs, dict)
        or set(inputs) != {"description_sha256", "due_key", "window_start_key", "window_end_key"}
        or not _digest(inputs["description_sha256"])
        or any(
            inputs[key] is not None and not _string(inputs[key])
            for key in ("due_key", "window_start_key", "window_end_key")
        )
        or (inputs["window_start_key"] is None) != (inputs["window_end_key"] is None)
    ):
        return False
    nodes = derivation["nodes"]
    if not isinstance(nodes, list) or not all(_node_valid(node) for node in nodes):
        return False
    by_id = {node["id"]: node for node in nodes}
    rows = [node for node in nodes if node["kind"] == "promise_ledger_row"]
    if (
        len(by_id) != len(nodes)
        or len(rows) != 1
        or rows[0]["promise_id"] != source.get("item_id")
        or rows[0]["promise_id"] != source.get("source_logical_id")
    ):
        return False
    edges = derivation["edges"]
    if not isinstance(edges, list):
        return False
    targets: list[str] = []
    for edge in edges:
        if not isinstance(edge, dict) or set(edge) != {"from", "relation", "to", "declared_by"}:
            return False
        if not all(isinstance(edge[key], str) for key in edge):
            return False
        relation = _RELATIONS.get(edge["relation"])
        if relation is None or edge["declared_by"] != relation[2]:
            return False
        origin = (
            "fragment" if edge["from"] == "fragment" else by_id.get(edge["from"], {}).get("kind")
        )
        target = by_id.get(edge["to"])
        if origin != relation[0] or target is None or target["kind"] != relation[1]:
            return False
        targets.append(edge["to"])
    kinds = {node["kind"] for node in nodes}
    if (
        sorted(targets) != sorted(by_id)
        or "manuscript_revision" not in kinds
        or (inputs["window_start_key"] is None and "plan_revision" in kinds)
    ):
        return False
    temporal = derivation["temporal"]
    if (
        not isinstance(temporal, dict)
        or set(temporal)
        != {"drafting_at", "opened_at_key", "due_key", "opened_relation", "due_relation"}
        or temporal["drafting_at"] != drafting_at
        or not _string(temporal["opened_at_key"])
        or temporal["due_key"] != inputs["due_key"]
        or temporal["opened_relation"]
        != position_relation(temporal["opened_at_key"], temporal["drafting_at"])
        or temporal["due_relation"]
        != position_relation(temporal["due_key"], temporal["drafting_at"])
    ):
        return False
    missing = derivation["not_recorded"]
    if not isinstance(missing, list) or not all(
        isinstance(item, dict)
        and set(item) == {"input", "reason"}
        and isinstance(item["input"], str)
        and _NOT_RECORDED.get(item["input"]) == item["reason"]
        for item in missing
    ):
        return False
    expected = {"opening_call_request"}
    if rows[0]["asserting_model"] is None:
        expected.add("asserting_model")
    if "scene_text_span" not in kinds:
        expected.add("opening_evidence")
    if inputs["window_start_key"] is not None and "plan_revision" not in kinds:
        expected.add("payoff_window_source")
    names = [item["input"] for item in missing]
    return len(names) == len(set(names)) and set(names) == expected


def derivation_summary(entries: Sequence[dict[str, Any]], coverage: object) -> dict[str, Any]:
    """Counts over one validated map; a map built before the extension says so."""
    if coverage != DERIVATION_COVERAGE:
        return {
            "fragment_types": [],
            "status": "not_recorded",
            "reason": "composition_predates_fragment_derivation",
            "recorded": 0,
            "not_recorded": 0,
            "claim": CLAIM,
        }
    statuses = [
        entry["source"]["derivation"]["status"]
        for entry in entries
        if "derivation" in entry["source"]
    ]
    return {
        "fragment_types": [PROMISE_LINE],
        "status": "recorded",
        "reason": None,
        "recorded": statuses.count("recorded"),
        "not_recorded": statuses.count("not_recorded"),
        "claim": CLAIM,
    }


__all__ = [
    "CLAIM",
    "DERIVATION_COVERAGE",
    "PRODUCER_FINGERPRINT",
    "PRODUCER_FUNCTION",
    "PROMISE_LINE",
    "SCHEMA",
    "attach_promise_derivations",
    "derivation_summary",
    "position_relation",
    "promise_line_derivation",
    "valid_derivation",
]
