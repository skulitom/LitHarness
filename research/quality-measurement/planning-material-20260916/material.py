"""Research-only planning material: generated developments and placement are separate.

Author text and canon are never classified by a model. Source references check provenance
and coverage, not semantic fidelity; the registered reading must inspect that separately.
"""

from __future__ import annotations

import copy
import hashlib
import json

VERSION = "planning-material.v1"
PROFILE = "planner.outline.material.v1"
STRING_LIST = {"type": "array", "items": {"type": "string"}}


def records(properties):
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        },
    }


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["developments", "staging_options", "placement_suggestions"],
    "properties": {
        "developments": records(
            {
                "id": {"type": "string"},
                "statement": {"type": "string"},
                "source_ids": STRING_LIST,
                "depends_on": STRING_LIST,
                "horizon": {"type": "string", "enum": ["first_arc", "later", "unresolved"]},
            }
        ),
        "staging_options": records(
            {
                "id": {"type": "string"},
                "statement": {"type": "string"},
                "source_ids": STRING_LIST,
            }
        ),
        "placement_suggestions": records(
            {
                "target_ids": STRING_LIST,
                "suggestion": {"type": "string"},
                "source_ids": STRING_LIST,
            }
        ),
    },
}

TASK = (
    "Separate a generated first-arc proposal into story developments, flexible staging, and "
    "tentative placement. This is a source transformation, not a new story or an evaluation. "
    "Use every source unit. Preserve its events, causal order, participant interests, costs, "
    "limits, rejected alternatives, unresolved relationships, and future disclosure bounds. "
    "Developments state what happens or must remain possible, without generated scene or "
    "chapter assignments. Dependencies express necessary causal order, not source paragraph "
    "order. A later or unresolved development must not become a present payoff. "
    "Put existing scene/chapter suggestions in placement_suggestions, linked to developments. "
    "Do not invent deadlines. Put only expressly flexible or incidental physical staging in "
    "staging_options; do not demote a consequence, capability limit, personal response, or "
    "future commitment into an option. Existing generated experience coverage is context, "
    "not permission to erase a source event. Author instructions are supplied unchanged as "
    "context and may not be rewritten, classified as optional, or overridden. "
    "Use unique ids D1, D2, ... for developments and S1, S2, ... for staging options. "
    "Each source_ids entry must exactly name a supplied source unit; every source unit must "
    "support at least one development or staging option. Cite all units used by an item. "
    "Return only the requested JSON."
)

PLANNING_RULE = (
    "planning_material separates generated story developments from tentative placement. "
    "Developments preserve the proposed story's causal commitments and unresolved futures; "
    "they are not author locks or established events. Preserve their costs, limits, personal "
    "responses and necessary dependencies when constructing the requested chapters. "
    "staging_options may be combined, shortened or omitted without erasing those commitments. "
    "placement_suggestions and generated_debt_placements are tentative proposals, not "
    "deadlines or a one-development-per-scene template. Choose connected activity and its "
    "consequence within the actual writing_layout, leaving space for response. If the proposed "
    "experience cannot fit, name the adaptation in chapter coverage rather than silently "
    "dropping it. Do not force later or unresolved developments to close now. The unchanged "
    "author brief, scoped author locks, accepted history, world rules and actual open_promises "
    "retain their authority. On continuation, preserve what happened and plan the remaining "
    "developments; never repeat a completed acquisition or settlement."
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def source_units(concept):
    arc = concept["first_arc"]
    if set(arc) != {"middle", "closes"}:
        raise ValueError("Expected the production outline's middle/close projection")
    return {
        f"first_arc.{field}:{i}": text
        for field in ("middle", "closes")
        for i, text in enumerate(arc[field].split("\n\n"), 1)
        if text.strip()
    }


def validate(material, concept):
    import jsonschema

    jsonschema.validate(material, SCHEMA)
    units = source_units(concept)
    entries = material["developments"] + material["staging_options"]
    ids = [row["id"] for row in entries]
    if not material["developments"] or len(ids) != len(set(ids)) or any(not i for i in ids):
        raise ValueError("Developments need unique nonempty identities")
    covered = set()
    for row in entries + material["placement_suggestions"]:
        if not row["source_ids"] or not set(row["source_ids"]) <= units.keys():
            raise ValueError("Every item must cite existing source units")
        if not row.get("statement", row.get("suggestion", "")).strip():
            raise ValueError("Empty material statement")
        if "statement" in row:
            covered.update(row["source_ids"])
    if covered != units.keys():
        raise ValueError("Source units disappeared from developments and staging")
    graph = {row["id"]: row["depends_on"] for row in material["developments"]}
    for key, parents in graph.items():
        if key in parents or not set(parents) <= graph.keys():
            raise ValueError("Invalid development dependency")
    pending = dict(graph)
    while pending:
        ready = {key for key, parents in pending.items() if not set(parents) & pending.keys()}
        if not ready:
            raise ValueError("Cyclic development dependencies")
        pending = {key: value for key, value in pending.items() if key not in ready}
    for row in material["placement_suggestions"]:
        if not row["target_ids"] or not set(row["target_ids"]) <= set(ids):
            raise ValueError("Placement does not identify existing material")
    return True


def generation_payload(concept):
    return {"source_units": source_units(concept), "unchanged_concept_context": concept}


def transform_prompt(prompt, artifact, first_arc_rule):
    payload = json.loads(prompt)
    concept = payload["book_concept"]
    if digest(concept) != artifact["source_concept_sha256"]:
        raise ValueError("Planning material belongs to a different concept")
    material = artifact["material"]
    validate(material, concept)
    if payload["rules"].count(first_arc_rule) != 1:
        raise ValueError("This prototype requires the first-arc planning rule")
    # Only generated arc prose and generated debt coordinates leave book_concept.
    # Source units remain in the audit artifact; actual world promises are untouched.
    del concept["first_arc"]
    placements = [
        {"debt_index": i, "subject": debt["subject"], "suggested_scene": debt.pop("due_scene")}
        for i, debt in enumerate(concept["debts"])
    ]
    payload["planning_material"] = {
        "version": VERSION,
        "source_concept_sha256": artifact["source_concept_sha256"],
        **copy.deepcopy(material),
        "generated_debt_placements": placements,
    }
    payload["rules"][payload["rules"].index(first_arc_rule)] = PLANNING_RULE
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
