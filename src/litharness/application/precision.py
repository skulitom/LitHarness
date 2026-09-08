"""Bounded author-directed quantity edits, without scoring or narrative selection."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from typing import Any

from litharness.domain import house, schema_words
from litharness.domain.generation import CompletionRequest

PROFILE = "writer.concept.precision.v1"

# A cheap scheduling check, not a quality measure: if there is no numeric expression,
# there is no quantity phrase to edit. The editing model decides relevance, not a counter.
_NUMBER_WORD = (
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    r"fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion)"
)
_ORDINAL_WORD = (
    r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|"
    r"twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|"
    r"twentieth|thirtieth|fortieth|fiftieth|sixtieth|seventieth|eightieth|ninetieth|"
    r"hundredth|thousandth|millionth|billionth)"
)
# Articles can also express a measured quantity. Generations and similar relative spans
# deliberately are not fixed units; this is syntax for locating edits, not a relevance test.
_MEASURED_UNIT = (
    r"(?:inch|foot|yard|mile|league|metre|meter|kilometre|kilometer|centimetre|centimeter|"
    r"millimetre|millimeter|second|minute|hour|day|week|month|year|decade|century|"
    r"gram|kilogram|ounce|pound|litre|liter|gallon|dozen)"
)
_QUANTITY = re.compile(
    rf"(?<!\w)[+-]?\d+(?:[.,:/]\d+)*(?:st|nd|rd|th)?(?!\w)"
    rf"|\b(?:{_NUMBER_WORD}[- ](?:and )?)*{_ORDINAL_WORD}\b"
    rf"|\b{_NUMBER_WORD}(?:[- ](?:and )?{_NUMBER_WORD})*\b"
    rf"|\b(?:a|an) {_MEASURED_UNIT}(?![\w-])",
    re.IGNORECASE,
)
PRECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["edits"],
    "properties": {
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field", "before", "after"],
                "properties": {
                    "field": {"type": "string"},
                    "before": {"type": "string"},
                    "after": {"type": "string"},
                },
            },
        }
    },
}
_PRECISION_TASK = (
    "Line-edit only unnecessary exact quantity phrases in these unpublished story-planning fields. "
    "Return local replacements, not a rewritten treatment or an evaluation.\n"
    f"{house.QUANTITY_DETAIL}\n"
    "Keep exact game-system amounts, costs, thresholds and values used in an actual choice "
    "or calculation unchanged. Keep scene positions and structural metadata unchanged. "
    "Remove decorative precision from other quantity phrases, "
    "using a natural relative expression or dropping the unnecessary modifier.\n"
    "Each before is a short, exact, unique phrase from the named field, at most 120 "
    "characters; each after replaces that phrase only and contains no exact quantity. "
    "Give separate edits for separate occurrences, using enough context to identify each. "
    "Preserve every event, ability, causal relation, name and other wording outside those "
    "phrases. Do not edit a system display or create a reason to keep an incidental number. "
    "Return an empty edits list if no such phrase needs changing."
)


def has_quantities(fields: Mapping[str, str]) -> bool:
    return any(_QUANTITY.search(value) for value in fields.values())


def apply_edits(source_fields: Mapping[str, str], payload: Mapping[str, Any]) -> dict[str, str]:
    """Apply only unambiguous local edits, atomically, before the source is retained.

    This bounds the editing surface, not semantic quality. Original source and proposed
    replacements are traced by the caller; accepted story state is never rewritten here.
    """
    edits = payload.get("edits")
    if not isinstance(edits, list):
        raise ValueError("precision response must contain an edits list")
    fields = dict(source_fields)
    spans: dict[str, list[tuple[int, int, str]]] = {key: [] for key in fields}
    for edit in edits:
        if not isinstance(edit, Mapping):
            raise ValueError("precision edit must be an object")
        key, before, after = (edit.get(name) for name in ("field", "before", "after"))
        if not isinstance(key, str) or key not in fields:
            raise ValueError("precision edit names an unknown field")
        if not isinstance(before, str) or not before or len(before) > 120:
            raise ValueError("precision edit must quote a short phrase")
        if (
            not isinstance(after, str)
            or len(after) > 120
            or any(mark in before + after for mark in "\r\n")
        ):
            raise ValueError("precision edit must stay within a line")
        if not _QUANTITY.search(before) or _QUANTITY.search(after):
            raise ValueError("precision edit must remove an exact quantity, not invent one")
        if schema_words.named_in(after):
            raise ValueError("precision edit cannot introduce a reserved name")
        source = fields[key]
        start = source.find(before)
        if start < 0 or source.find(before, start + 1) >= 0:
            raise ValueError("precision edit does not uniquely locate its source")
        end = start + len(before)
        quantities = [
            match
            for match in _QUANTITY.finditer(source)
            if start < match.end() and match.start() < end
        ]
        if not quantities or any(
            match.start() < start or end < match.end() for match in quantities
        ):
            raise ValueError("precision edit does not contain a complete quantity")
        line = source[source.rfind("\n", 0, start) + 1 :].split("\n", 1)[0].lstrip()
        bracket_overlap = any(
            start < match.end() and match.start() < end
            for match in re.finditer(r"\[[^\]\n]*\]", source)
        )
        if (
            line.lstrip("*_ ").startswith("[")
            or bracket_overlap
            or any(mark in before + after for mark in "[]")
        ):
            raise ValueError("precision edit cannot alter a bracketed system display")
        if any(start < old_end and old_start < end for old_start, old_end, _ in spans[key]):
            raise ValueError("precision edits overlap")
        spans[key].append((start, end, after))
    for key, replacements in spans.items():
        for start, end, after in sorted(replacements, reverse=True):
            fields[key] = fields[key][:start] + after + fields[key][end:]
    return fields


def render_request(
    fields: Mapping[str, str], protected: Mapping[str, Any] | None = None
) -> CompletionRequest:
    schema = copy.deepcopy(PRECISION_SCHEMA)
    schema["properties"]["edits"]["items"]["properties"]["field"]["enum"] = list(fields)
    return CompletionRequest(
        system=_PRECISION_TASK,
        prompt=json.dumps(
            {"fields": dict(fields), "protected": dict(protected or {})}, ensure_ascii=False
        ),
        schema=schema,
        profile=PROFILE,
        max_output_tokens=3200,
        timeout_seconds=600.0,
        call_class="generation",
    )
