"""Record input provenance at composition time; no inference from generated prose."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from litharness.domain.context import RenderedContext


def text_digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class PromptSources:
    """Sidecar spans over the existing request, without adding text to that request.

    Renderer fragments can overlap their inserted context items. A renderer fragment
    identifies the producing function; it does not claim complete provenance of every
    upstream argument from which that function derived its text.
    """

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(
        self,
        stage: str,
        base: str,
        text: str,
        section: str,
        *,
        source: dict[str, Any] | None = None,
        kind: str = "renderer",
        rendered: RenderedContext | None = None,
        rendered_offset: int = 0,
    ) -> str:
        start = len(base)
        self.entries.append(
            {
                "stage": stage,
                "start": start,
                "end": start + len(text),
                "sha256": text_digest(text),
                "kind": kind,
                "section": section,
                "source": source
                if source is not None
                else {
                    "producer": "application.planner.render_prompt:" + section,
                    "attribution": "renderer_fragment",
                },
            }
        )
        if rendered is not None:
            if text[rendered_offset : rendered_offset + len(rendered.text)] != rendered.text:
                raise ValueError("rendered context does not match its inserted fragment")
            for span in rendered.spans:
                item = span.item
                if rendered.text[span.start : span.end] != item.text:
                    raise ValueError("rendered item does not match its recorded insertion")
                self.entries.append(
                    {
                        "stage": stage,
                        "start": start + rendered_offset + span.start,
                        "end": start + rendered_offset + span.end,
                        "sha256": text_digest(item.text),
                        "kind": "context_item",
                        "section": span.section,
                        "source": {
                            "item_id": item.item_id,
                            "source_logical_id": item.source_logical_id,
                            "source_kind": item.source_kind.value,
                            "authority": item.authority.value,
                            "pov_visibility": list(item.pov_visibility),
                            "source_span": list(item.span) if item.span is not None else None,
                            "packed_text_sha256": text_digest(item.text),
                        },
                    }
                )
        return base + text

    def prepend(self, stage: str, text: str, base: str, section: str) -> str:
        for entry in self.entries:
            if entry["stage"] == stage:
                entry["start"] += len(text)
                entry["end"] += len(text)
        self.append(stage, "", text, section)
        return text + base

    def finish(self, system: str, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        stages = {"system": system, "prompt": prompt}
        entries = sorted(self.entries, key=lambda item: (item["stage"], item["start"], item["end"]))
        for entry in entries:
            text = stages[entry["stage"]]
            if not 0 <= entry["start"] <= entry["end"] <= len(text):
                raise ValueError("source span falls outside its request stage")
            if text_digest(text[entry["start"] : entry["end"]]) != entry["sha256"]:
                raise ValueError("source span changed during request composition")
        return {
            "schema": "litharness.prompt-sources.v1",
            "stages": {
                stage: {"chars": len(text), "sha256": text_digest(text)}
                for stage, text in stages.items()
            },
            "entries": entries,
            "context": context,
        }
