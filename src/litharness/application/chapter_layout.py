"""One numeric chapter layout for invention, development and outline reconciliation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from litharness.domain.serials import SerialShape, chapters_for

INVENTION_RULE = (
    "writing_layout is the actual scene-to-chapter map and approximate prose budget. "
    "Choose an opening experience that fits its first chapter, including the character's "
    "response to its consequence. Necessary routine action may pass in summary. Leave "
    "later developments for the chapters that can hold them; do not call several mapped "
    "chapters one opening chapter. Zero or absent word targets mean unspecified length. "
    "The author's supplied brief takes priority over generated proposals."
)
DEVELOPMENT_RULE = (
    "Use writing_layout's actual chapter and scene coordinates for first_arc and for each "
    "question's due_scene. Preserve the proposed experience within that layout; adapt "
    "flexible staging to the available prose space instead of inventing a different chapter "
    "grouping. Generated scene placements remain proposals for the planner, not author "
    "deadlines."
)
PLANNING_RULE = (
    "First plan the chapter coverage, then its scenes. Return exactly the chapters in "
    "writing_layout; each contains only its listed response scene ordinals. For each "
    "chapter, intent names the connected activity, experienced consequence and response "
    "this chapter is to contain, as applicable to the supplied story. adaptation records "
    "how you reconciled proposed coverage with available prose space, author instructions, "
    "locks and established history; state explicitly when no adaptation was needed. "
    "The actual map takes precedence over chapter groupings suggested in generated "
    "first_arc text or due_scene values. Preserve the proposed experience where "
    "feasible, simplify flexible staging before deferring its consequence, and record "
    "any changed coverage. Put the resulting events in these scenes' briefs. These "
    "records describe intended coverage, not a judgment of quality."
)


@dataclass(frozen=True, slots=True)
class WritingLayout:
    # Response-local scene ordinals; chapter numbers retain the actual book coordinates.
    chapters: tuple[tuple[int, tuple[int, ...]], ...]
    target_scene_words: int | None = None

    def __post_init__(self) -> None:
        seen: set[int] = set()
        previous = 0
        for chapter, ordinals in self.chapters:
            if type(chapter) is not int or chapter <= previous or not ordinals:
                raise ValueError("writing layout needs ordered positive, non-empty chapters")
            previous = chapter
            for ordinal in ordinals:
                if type(ordinal) is not int or ordinal < 1 or ordinal in seen:
                    raise ValueError("writing layout needs unique positive scene ordinals")
                seen.add(ordinal)
        if not seen or sorted(seen) != list(range(1, len(seen) + 1)):
            raise ValueError("writing layout must cover every response scene exactly once")
        ordered = [ordinal for _, ordinals in self.chapters for ordinal in ordinals]
        if ordered != sorted(ordered):
            raise ValueError("writing layout chapters must preserve scene order")
        if self.target_scene_words is not None and (
            type(self.target_scene_words) is not int or self.target_scene_words < 0
        ):
            raise ValueError("writing layout word target must be a non-negative integer")

    @classmethod
    def opening(
        cls, scenes: int, shape: SerialShape, target_scene_words: int | None,
    ) -> WritingLayout:
        if type(scenes) is not int or scenes < 1:
            raise ValueError("an opening layout needs at least one scene")
        # The same grouping function drives manuscript chapters and drafting positions.
        ids = tuple(str(ordinal) for ordinal in range(1, scenes + 1))
        return cls(tuple(
            (chapter.index, tuple(int(sid) for sid in chapter.scene_ids))
            for chapter in chapters_for(ids, shape)
        ), target_scene_words)

    @classmethod
    def mapped(
        cls, scenes: Sequence[tuple[str, int]], chapter_by_scene: Mapping[str, int],
        target_scene_words: int | None,
    ) -> WritingLayout:
        groups: dict[int, list[int]] = {}
        for logical_id, ordinal in scenes:
            if logical_id not in chapter_by_scene:
                raise ValueError(f"writing layout has no chapter for {logical_id}")
            chapter = chapter_by_scene[logical_id]
            if type(chapter) is not int or chapter < 1:
                raise ValueError("writing layout chapter must be a positive integer")
            groups.setdefault(chapter, []).append(ordinal)
        return cls(tuple((chapter, tuple(ordinals)) for chapter, ordinals in groups.items()),
                   target_scene_words)

    @property
    def scene_count(self) -> int:
        return sum(len(ordinals) for _, ordinals in self.chapters)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "chapters": [
                {
                    "chapter": chapter,
                    "scene_ordinals": list(ordinals),
                    **({"target_words": self.target_scene_words * len(ordinals)}
                       if self.target_scene_words is not None else {}),
                }
                for chapter, ordinals in self.chapters
            ],
            **({"target_scene_words": self.target_scene_words}
               if self.target_scene_words is not None else {}),
        }

    def render(self) -> str:
        return "writing_layout:\n" + json.dumps(self.to_jsonable(), ensure_ascii=False)
