"""Whole-book audit: what a drafted serial says about itself when its scenes are read together.

**Why this exists.** Every in-process check reads one scene or one story position:
`detect_contradictions` keys on `order_key` on purpose, so a value that changes between
positions is a story and never a defect; `gate_progression` compares the plan's quantity at
one scene's own key; the tells counter and the duplicate-scene check read one candidate.
Stage-0 §231 named the gap when one chapter printed its status line two different ways —
*nothing compares one scene's furniture with the next's* — and the promise ledger records a
payoff as a model-reported field without asking whether the debt landed on the page. The
first whole-volume draw (runs/volume1, 2026-09-07) is the first book long enough for those
gaps to matter, and these views are what reads it across scenes.

**What these views are and are not.** Descriptions. Each one lists what the book holds and
marks where two places disagree, so that a person reading the book knows where to look. No
view produces a score, a rank, a pass or a bar (§61(5), §105): a status column that fell is
reported as a fall, which may be a story; a debt paid with no locatable quote is reported as
unlocated, which may be a paraphrase. Nothing here gates a draft or reaches a prompt; the
diagnostic fence (§97.1) applies to every line of output.

Imports domain code and a structural port only; the CLI and the MCP server bind a store.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, Protocol

import litharness_contracts as lc

from litharness.domain import beats as beats_domain
from litharness.domain import gamesystem
from litharness.domain import state as state_mod
from litharness.domain.names import display_name, humanise_subject
from litharness.domain.nodes import NodeKind
from litharness.domain.plans import scene_plan_for
from litharness.domain.promises import Promise
from litharness.domain.revision import Revision

DESCRIPTIVE_ONLY = (
    "Descriptive only: what the book holds and where two places disagree. No score, no "
    "rank, no bar, no gate (stage-0 §61(5), §105). A person reads the book; these views say "
    "where to look. Nothing here may become a prompt, directive, finding or plan item (§97.1)."
)


class AuditStore(Protocol):
    """The five reads the audit needs, named structurally so any store that has them fits."""

    def head(self, book_id: str, branch_id: str) -> Revision | None: ...

    def plan_items(self, book_id: str, branch_id: str) -> Sequence[lc.PlanItem]: ...

    def state_records(self, book_id: str, branch_id: str) -> Sequence[lc.StateRecord]: ...

    def scene_summaries(self, book_id: str, branch_id: str) -> dict[str, dict[str, str]]: ...

    def promises(self, book_id: str, branch_id: str, *, open_only: bool = ...) -> list[Promise]: ...


# ------------------------------------------------------------------------------- the facts


@dataclass(frozen=True)
class StatusLine:
    ordinal: int
    logical_id: str
    subject: str
    columns: tuple[tuple[str, str], ...]
    line: str

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(label for label, _ in self.columns)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "scene": self.ordinal,
            "logical_id": self.logical_id,
            "subject": self.subject,
            "columns": dict(self.columns),
            "line": self.line,
        }


@dataclass(frozen=True)
class SceneFacts:
    ordinal: int
    chapter: int
    logical_id: str
    story_key: str | None
    text: str
    summary: str | None
    summary_stale: bool
    plan: str | None
    status_lines: tuple[StatusLine, ...]

    @property
    def drafted(self) -> bool:
        return bool(self.text.strip())

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class BookFacts:
    book_id: str
    branch_id: str
    title: str
    scenes: tuple[SceneFacts, ...]
    records: tuple[lc.StateRecord, ...]
    promises: tuple[Promise, ...]
    scenes_per_chapter: int
    scene_by_key: dict[str, int] = field(default_factory=dict)

    @property
    def drafted(self) -> tuple[SceneFacts, ...]:
        return tuple(scene for scene in self.scenes if scene.drafted)

    def scene_for_key(self, key: str | None) -> int | None:
        """The 1-based scene a story key names, for the two key shapes this house writes.

        Beats key scenes `s01`…`sNN`; a hand- or Architect-declared record keys the scene
        it belongs to as zero-padded scene-times-a-hundred (`0300` is scene 3). Anything
        else is left unmapped rather than guessed.
        """
        if not key:
            return None
        if key in self.scene_by_key:
            return self.scene_by_key[key]
        match = re.fullmatch(r"s0*(\d+)", key)
        if match:
            return int(match.group(1))
        if key.isdigit() and len(key) >= 3 and key.endswith("00"):
            return int(key) // 100
        return None


#: A status line's frame, as `domain/sheet.py` reads it: the tag, the subject up to the em
#: dash, and the rest as `Label value` pairs split on pipes.
_STATUS_LINE = re.compile(
    r"^\[STATUS\][^\S\n]*(?P<subject>[^\n|]+?)[^\S\n]*—[^\S\n]*(?P<pairs>[^\n]+)$", re.MULTILINE
)
_PAIR = re.compile(r"^(?P<label>.+?)[^\S\n]+(?P<value>\S+)$")


def status_lines_in(text: str, *, ordinal: int, logical_id: str) -> tuple[StatusLine, ...]:
    """Every `[STATUS]` line in one scene, its pairs read loosely: the last token of a pair
    is its value and the rest its label, so a label of two words survives."""
    found: list[StatusLine] = []
    for match in _STATUS_LINE.finditer(text):
        columns: list[tuple[str, str]] = []
        for pair in match.group("pairs").split("|"):
            pair = pair.strip()
            read = _PAIR.match(pair)
            if read is None:
                if pair:
                    columns.append((pair, ""))
                continue
            columns.append((read.group("label").strip(), read.group("value").strip()))
        found.append(
            StatusLine(
                ordinal=ordinal,
                logical_id=logical_id,
                subject=match.group("subject").strip(),
                columns=tuple(columns),
                line=match.group(0).strip(),
            )
        )
    return tuple(found)


def load(
    store: AuditStore, book_id: str, branch_id: str, *, scenes_per_chapter: int
) -> BookFacts | None:
    """Everything the audits read, gathered once. `None` when the branch has no head."""
    head = store.head(book_id, branch_id)
    if head is None:
        return None
    nodes = [
        node
        for node in head.nodes
        if node.kind is NodeKind.SCENE and not getattr(node, "tombstoned", False)
    ]
    try:
        beats = beats_domain.beats_for(head, beats_domain.template_for(head))
    except beats_domain.TemplateMismatch:
        beats = ()
    key_of = {beat.logical_id: beat.story_order_key for beat in beats}
    plan_items = list(store.plan_items(book_id, branch_id))
    summaries = store.scene_summaries(book_id, branch_id)
    scenes: list[SceneFacts] = []
    scene_by_key: dict[str, int] = {}
    for index, node in enumerate(nodes):
        ordinal = index + 1
        text = node.content or ""
        key = key_of.get(node.logical_id)
        if key:
            scene_by_key[key] = ordinal
        by_hash = summaries.get(node.logical_id, {})
        summary = by_hash.get(node.content_sha256) if node.content_sha256 else None
        plan = scene_plan_for(plan_items, node.logical_id)
        scenes.append(
            SceneFacts(
                ordinal=ordinal,
                chapter=(ordinal - 1) // max(scenes_per_chapter, 1) + 1,
                logical_id=node.logical_id,
                story_key=key,
                text=text,
                summary=summary,
                summary_stale=summary is None and bool(by_hash) and bool(text.strip()),
                plan=(plan.text if plan is not None else None),
                status_lines=status_lines_in(text, ordinal=ordinal, logical_id=node.logical_id),
            )
        )
    root = next((node for node in head.nodes if node.kind is NodeKind.BOOK), None)
    return BookFacts(
        book_id=book_id,
        branch_id=branch_id,
        title=(root.title if root is not None and root.title else None) or book_id,
        scenes=tuple(scenes),
        records=tuple(store.state_records(book_id, branch_id)),
        promises=tuple(store.promises(book_id, branch_id)),
        scenes_per_chapter=scenes_per_chapter,
        scene_by_key=scene_by_key,
    )


# -------------------------------------------------------------------- the status-line census


def _numeric(value: str) -> int | None:
    match = re.fullmatch(r"(\d+)(?:/\d+)?", value)
    return int(match.group(1)) if match else None


def status_line_report(book: BookFacts) -> dict[str, Any]:
    """Every status line the book printed, read one against the next.

    Reports, per printing, the subject as spelled and the columns as labelled; then the
    distinct subject spellings, the distinct column sets with the scenes each appears in,
    each place the column set changed from the previous printing, each numeric column that
    fell, each column whose value was a number on one line and words on another, each
    printing that repeated the previous one with nothing moved, and the drafted scenes
    that printed no line at all. A fall may be a cost the story charged; a
    changed column set may be a rung that added a column. The census says where.
    """
    lines = [line for scene in book.drafted for line in scene.status_lines]
    subjects: dict[str, list[int]] = defaultdict(list)
    column_sets: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for line in lines:
        subjects[line.subject].append(line.ordinal)
        column_sets[line.labels].append(line.ordinal)

    drift: list[dict[str, Any]] = []
    decreases: list[dict[str, Any]] = []
    kind_flips: list[dict[str, Any]] = []
    unmoved: list[dict[str, Any]] = []
    previous: dict[str, StatusLine] = {}
    for line in lines:
        subject_key = line.subject.casefold()
        before = previous.get(subject_key)
        if before is not None:
            if before.columns == line.columns:
                # The genre prints the line when a number moves (§233); a line printed
                # again with every number the same is furniture, or a beat the prose
                # around it earns. The census says where; the reader says which.
                unmoved.append(
                    {
                        "subject": line.subject,
                        "from_scene": before.ordinal,
                        "to_scene": line.ordinal,
                    }
                )
            if before.labels != line.labels:
                drift.append(
                    {
                        "subject": line.subject,
                        "from_scene": before.ordinal,
                        "to_scene": line.ordinal,
                        "added": [label for label in line.labels if label not in before.labels],
                        "removed": [label for label in before.labels if label not in line.labels],
                        "reordered": (
                            set(before.labels) == set(line.labels) and before.labels != line.labels
                        ),
                    }
                )
            earlier = dict(before.columns)
            for label, value in line.columns:
                if label not in earlier:
                    continue
                now, then = _numeric(value), _numeric(earlier[label])
                if now is not None and then is not None and now < then:
                    decreases.append(
                        {
                            "subject": line.subject,
                            "column": label,
                            "from_scene": before.ordinal,
                            "to_scene": line.ordinal,
                            "was": earlier[label],
                            "now": value,
                        }
                    )
                if (now is None) != (then is None):
                    kind_flips.append(
                        {
                            "subject": line.subject,
                            "column": label,
                            "from_scene": before.ordinal,
                            "to_scene": line.ordinal,
                            "was": earlier[label],
                            "now": value,
                        }
                    )
        previous[subject_key] = line

    return {
        "printings": [line.to_jsonable() for line in lines],
        "subjects": dict(subjects),
        "column_sets": [
            {"labels": list(labels), "scenes": scenes} for labels, scenes in column_sets.items()
        ],
        "drift": drift,
        "decreases": decreases,
        "kind_flips": kind_flips,
        "unmoved": unmoved,
        "silent_scenes": [scene.ordinal for scene in book.drafted if not scene.status_lines],
    }


# ---------------------------------------------------------------------- the promise ledger


def promise_report(book: BookFacts) -> dict[str, Any]:
    """Every debt on the ledger, with where it was opened, when it is due, whether and where it
    was paid, and whether either end was located in the prose by an exact quote.

    `overdue` is open past its due scene at the last drafted scene; `paid_unlocated` is a
    payment the summariser reported without a quote that matched the scene; `paid_early` is a
    payment recorded at a scene before the one that opened the debt. None of these is a
    verdict: an unlocated payment may be a paraphrase, and an overdue debt may be the plan.
    """
    last = book.drafted[-1].ordinal if book.drafted else 0
    rows: list[dict[str, Any]] = []
    for promise in sorted(book.promises, key=lambda item: (item.due_key or "", item.subject)):
        opened = book.scene_for_key(promise.opened_at_key)
        due = book.scene_for_key(promise.due_key)
        paid = book.scene_for_key(promise.paid_at_key)
        is_open = promise.paid_at_key is None
        rows.append(
            {
                "subject": promise.subject,
                "description": promise.description,
                "kind": promise.kind,
                "status": promise.status,
                "opened_scene": opened,
                "opened_key": promise.opened_at_key,
                "due_scene": due,
                "due_key": promise.due_key,
                "paid_scene": paid,
                "paid_key": promise.paid_at_key,
                "opening_located": promise.opened_logical_id is not None,
                "payment_located": promise.paid_logical_id is not None,
                "overdue": bool(is_open and due is not None and last and due < last),
                "paid_unlocated": bool(not is_open and promise.paid_logical_id is None),
                "paid_early": bool(
                    not is_open and paid is not None and opened is not None and paid < opened
                ),
            }
        )
    return {
        "last_drafted_scene": last,
        "promises": rows,
        "open": sum(1 for row in rows if row["status"] != "paid" and row["paid_key"] is None),
        "overdue": [row["subject"] for row in rows if row["overdue"]],
        "paid_unlocated": [row["subject"] for row in rows if row["paid_unlocated"]],
        "paid_early": [row["subject"] for row in rows if row["paid_early"]],
    }


# ------------------------------------------------------------------------ the fact timeline


def _key(record: lc.StateRecord) -> str | None:
    position = getattr(record, "story_position", None)
    return getattr(position, "order_key", None) if position is not None else None


def _says(record: lc.StateRecord) -> str:
    value = getattr(record, "value", None)
    object_ref = getattr(record, "object_ref", None)
    parts = [str(object_ref)] if object_ref else []
    if value not in (None, ""):
        parts.append(str(value))
    return " ".join(parts)


def fact_timeline(book: BookFacts, *, subject: str | None = None) -> dict[str, Any]:
    """Each fact the book holds, in story order, with every place its value moved.

    Grouped by subject and predicate (and object, where the predicate takes one) and sorted
    by order key, so that the reader sees `stands_at` for one person as the sequence of rungs
    the book put them on. `reverted` marks a value that came back after being replaced; a
    return may be a story (a rank lost and regained) or two scenes disagreeing. Each row
    says whether the page established it (`read`) or a declaration did (`given`), so a
    schedule the Architect wrote is never mistaken for what the prose did.
    """
    groups: dict[tuple[str, str, str], list[lc.StateRecord]] = defaultdict(list)
    for record in book.records:
        if subject and record.subject != subject:
            continue
        object_ref = getattr(record, "object_ref", None) or ""
        groups[(record.subject, str(record.predicate), str(object_ref))].append(record)

    facts: list[dict[str, Any]] = []
    for (who, predicate, object_ref), items in sorted(groups.items()):
        ordered = sorted(items, key=lambda item: (_key(item) or "", _says(item)))
        history: list[dict[str, Any]] = []
        seen: list[str] = []
        reverted: list[str] = []
        for record in ordered:
            said = _says(record)
            key = _key(record)
            history.append(
                {
                    "order_key": key,
                    "scene": book.scene_for_key(key),
                    "says": said,
                    "authority": str(getattr(record.authority, "value", record.authority)),
                    # `read` is a fact the page established; `given` is a declaration or a
                    # schedule, which the page may not have reached. The reader keeps them
                    # apart because a schedule contradicting itself is the seed's defect.
                    "provenance": "read" if getattr(record, "evidence", None) else "given",
                }
            )
            if seen and said != seen[-1] and said in seen:
                reverted.append(said)
            if not seen or said != seen[-1]:
                seen.append(said)
        if len(seen) > 1 or reverted:
            facts.append(
                {
                    "subject": who,
                    "predicate": predicate,
                    "object": object_ref or None,
                    "values": seen,
                    "reverted": reverted,
                    "history": history,
                }
            )
    return {
        "subject": subject,
        "records": len(book.records),
        "moving_facts": facts,
        "reverted": [
            {"subject": fact["subject"], "predicate": fact["predicate"], "values": fact["reverted"]}
            for fact in facts
            if fact["reverted"]
        ],
    }


# ------------------------------------------------------------------------- cast presence


_CAST_ROLES = {"cast", "protagonist", "creature"}
_WORD = re.compile("[A-Za-z][A-Za-z'\u2019-]+")


def _cast_subjects(records: Iterable[lc.StateRecord]) -> list[str]:
    subjects: list[str] = []
    for record in records:
        if (
            str(record.predicate) == "entity_role"
            and str(getattr(record, "value", "")) in _CAST_ROLES
            and record.subject not in subjects
        ):
            subjects.append(record.subject)
    return subjects


def _mentions(text: str, name: str) -> bool:
    if not name:
        return False
    pattern = r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def cast_presence(book: BookFacts, *, gap: int = 6) -> dict[str, Any]:
    """Who the world declares as a person or creature, and which scenes name them.

    A name is matched as a whole word, case-insensitively, under the display name the
    records give it and under the first word of that name on its own. `gaps` lists every
    run of at least `gap` drafted scenes between two mentions, and `never_on_page` the
    declared cast the prose never names. `undeclared` is a heuristic: a capitalised word that
    recurs in three or more scenes without being declared, which may be a place, a brand or
    a person the world never recorded. The reader decides which.
    """
    drafted = book.drafted
    declared = _cast_subjects(book.records)
    people: list[dict[str, Any]] = []
    known_words: set[str] = set()
    for who in declared:
        shown = display_name(book.records, who) or humanise_subject(who)
        first_word = shown.split()[0] if shown.split() else shown
        forms = {shown, first_word} - {""}
        known_words.update(word.casefold() for form in forms for word in form.split())
        scenes = [
            scene.ordinal for scene in drafted if any(_mentions(scene.text, form) for form in forms)
        ]
        gaps: list[dict[str, int]] = []
        for earlier, later in pairwise(scenes):
            if later - earlier - 1 >= gap:
                gaps.append(
                    {"from_scene": earlier, "to_scene": later, "silent": later - earlier - 1}
                )
        people.append(
            {
                "subject": who,
                "name": shown,
                "scenes": scenes,
                "first": scenes[0] if scenes else None,
                "last": scenes[-1] if scenes else None,
                "gaps": gaps,
            }
        )

    counts: dict[str, set[int]] = defaultdict(set)
    for scene in drafted:
        # The status line's labels are furniture, not names; the census above reads them.
        prose = _STATUS_LINE.sub("", scene.text)
        for match in _WORD.finditer(prose):
            word = match.group(0)
            if not word[0].isupper() or word.casefold() in known_words:
                continue
            start = match.start()
            preceding = prose[max(0, start - 2) : start]
            if start == 0 or preceding.strip() in {"", ".", "!", "?", '"', "“", "—"}:
                continue
            counts[word].add(scene.ordinal)
    undeclared = sorted(
        (
            {"word": word, "scenes": sorted(scenes)}
            for word, scenes in counts.items()
            if len(scenes) >= 3 and word.casefold() not in _COMMON
        ),
        key=lambda item: (-len(item["scenes"]), item["word"]),
    )
    return {
        "declared": len(declared),
        "people": people,
        "never_on_page": [person["subject"] for person in people if not person["scenes"]],
        "with_gaps": [person["subject"] for person in people if person["gaps"]],
        "undeclared": undeclared[:60],
        "caveat": "mid-sentence capitalised words that recur in three or more scenes; a heuristic",
    }


_COMMON = {
    word.casefold()
    for word in [
        "I",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "God",
        "Earth",
        "Mr",
        "Mrs",
        "Ms",
        "Dr",
        "OK",
        "Okay",
        "The",
        "A",
        "An",
        "And",
        "But",
        "Or",
        "If",
        "So",
        "Then",
        "When",
        "Where",
        "What",
        "Who",
        "Why",
        "How",
        "Not",
        "No",
        "Yes",
    ]
}


# ------------------------------------------------------------------------ plan and summary


def plan_summary_pairs(book: BookFacts) -> dict[str, Any]:
    """Each scene's plan beside what the summariser said it contained, for a reader to
    compare. A missing summary is `null`; `summary_stale` marks a scene whose text moved on
    after it was summarised. No comparison is made here: the pair is the view."""
    rows = [
        {
            "scene": scene.ordinal,
            "chapter": scene.chapter,
            "logical_id": scene.logical_id,
            "story_key": scene.story_key,
            "words": scene.words,
            "plan": scene.plan,
            "summary": scene.summary,
            "summary_stale": scene.summary_stale,
        }
        for scene in book.drafted
    ]
    return {
        "scenes": rows,
        "unplanned": [row["scene"] for row in rows if not row["plan"]],
        "unsummarised": [row["scene"] for row in rows if row["summary"] is None],
        "stale": [row["scene"] for row in rows if row["summary_stale"]],
    }


# ------------------------------------------------------------------------------ refrains


_TOKEN = re.compile(r"[a-z0-9']+")


def refrains(
    book: BookFacts,
    *,
    words: int = 5,
    max_words: int = 24,
    min_scenes: int = 2,
    limit: int = 60,
) -> dict[str, Any]:
    """Word runs the book says again in more than one scene.

    `integrity.duplicate_scene.v0` needs a hundred and twenty verbatim words before it
    speaks; the first whole-volume draw repeated "the way a match goes into water" two
    chapters apart, "at a reader's pace" in every scene the lamp walked, and one character's
    entrance ("with his coat still half on and his panel swimming") three times in four
    chapters. Some of that is refrain and some is a writer's hand showing; the census says
    which runs of `words` to `max_words` words appear in `min_scenes` or more scenes, with
    the scenes, and leaves the judgment to the reader. Status lines are dropped before
    counting. A run that is only part of a longer run said in exactly the same scenes is
    folded into the longer one; a shorter run said in more scenes is kept beside it.
    """
    tokens_by_scene = {
        scene.ordinal: _TOKEN.findall(_STATUS_LINE.sub("", scene.text).casefold())
        for scene in book.drafted
    }
    where: dict[str, set[int]] = defaultdict(set)
    for ordinal, tokens in tokens_by_scene.items():
        for size in range(words, max_words + 1):
            if len(tokens) < size:
                break
            for i in range(len(tokens) - size + 1):
                where[" ".join(tokens[i : i + size])].add(ordinal)
    repeated = [
        (run, frozenset(scenes)) for run, scenes in where.items() if len(scenes) >= min_scenes
    ]
    repeated.sort(key=lambda item: (-len(item[0].split()), item[0]))
    kept: dict[frozenset[int], list[str]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    for run, scenes in repeated:
        padded = f" {run} "
        if any(padded in f" {longer} " for longer in kept[scenes]):
            continue
        kept[scenes].append(run)
        rows.append({"phrase": run, "scenes": sorted(scenes), "count": len(scenes)})
    rows.sort(key=lambda row: (-row["count"], -len(row["phrase"].split()), row["phrase"]))
    return {
        "words": words,
        "max_words": max_words,
        "min_scenes": min_scenes,
        "repeated": len(rows),
        "phrases": rows[:limit],
        "caveat": (
            "runs of words said in more than one scene; a refrain and a tic look the same "
            "here and the reader tells them apart"
        ),
    }


# --------------------------------------------------------------------------------- seams


def seams(book: BookFacts, *, words: int = 6, tail: int = 120, head: int = 160) -> dict[str, Any]:
    """Where a scene opens by saying again what the scene before it closed on.

    Scene 10 of the first whole-volume draw opened with two sentences that were scene 9's
    last two, nearly verbatim — the second writer restating the boundary it was handed —
    and the duplicate-scene check, which needs a hundred and twenty shared words, said
    nothing. This reads the last `tail` words of each drafted scene against the first
    `head` words of the next and reports every run of `words` words they share, with the
    scenes. A deliberate echo and a restated boundary look the same here; the reader
    decides which, and a chapter boundary is where a restatement is most often meant.
    """
    drafted = list(book.drafted)
    rows: list[dict[str, Any]] = []
    for earlier, later in pairwise(drafted):
        end = _TOKEN.findall(_STATUS_LINE.sub("", earlier.text).casefold())[-tail:]
        start = _TOKEN.findall(_STATUS_LINE.sub("", later.text).casefold())[:head]
        if len(end) < words or len(start) < words:
            continue
        opening = {" ".join(start[i : i + words]) for i in range(len(start) - words + 1)}
        shared = [
            " ".join(end[i : i + words])
            for i in range(len(end) - words + 1)
            if " ".join(end[i : i + words]) in opening
        ]
        if not shared:
            continue
        # Fold the overlapping runs into their maximal phrases.
        phrases: list[str] = []
        for run in shared:
            if phrases and run.split()[:-1] == phrases[-1].split()[-(words - 1) :]:
                phrases[-1] = phrases[-1] + " " + run.split()[-1]
            else:
                phrases.append(run)
        rows.append(
            {
                "from_scene": earlier.ordinal,
                "to_scene": later.ordinal,
                "same_chapter": earlier.chapter == later.chapter,
                "shared_words": sum(len(phrase.split()) for phrase in phrases),
                "phrases": phrases,
            }
        )
    return {
        "words": words,
        "tail": tail,
        "head": head,
        "restated": rows,
        "caveat": "an opening that repeats the previous close; an echo or a restated boundary",
    }


# ------------------------------------------------------------------- the sheet and the page


def _subject_of(printed: str, records: Sequence[lc.StateRecord]) -> str | None:
    """The subject id a status line's printed name stands for, by display name first."""
    wanted = printed.strip().casefold()
    for subject in _cast_subjects(records):
        shown = display_name(records, subject) or humanise_subject(subject)
        if shown.casefold() == wanted or shown.split()[0].casefold() == wanted:
            return subject
    for record in records:
        if humanise_subject(record.subject).casefold() == wanted:
            return record.subject
    return None


def _cutoff_for(records: Sequence[lc.StateRecord], ordinal: int) -> str:
    """The scene key this book's own scene-space records use, projected onto `ordinal`.

    `state.scene_cutoff` refuses when any positioned record is in the other space, which on a
    world an Architect has keyed both ways is every world; the audit needs a coordinate
    to read the edges at, so it takes the width the scene-space keys agree on (six for a new
    serial) and leaves the schedule space out of the count.
    """
    from collections import Counter

    widths = Counter(
        len(match.group(1))
        for record in records
        if (key := getattr(getattr(record, "story_position", None), "order_key", None))
        and (match := re.fullmatch(r"s(\d+)", key))
    )
    width = widths.most_common(1)[0][0] if widths else 6
    return f"s{ordinal:0{width}d}"


def sheet_vs_page(book: BookFacts) -> dict[str, Any]:
    """Every printed status line beside what the world's own edges say at that scene.

    The world reads holdings off `stands_at` and `can_do` edges and declared changes
    (`gamesystem.sheet_of`); the page prints a line. On the first whole-volume draw the two
    parted in chapter 3 and never met again: the page spent Reading and then Overlay like
    charges while the world kept them held, and a grow later put Reading at 2 against a page
    that had printed 0 for nine scenes. Nothing compared the two. This does, scene by scene,
    for the one system a book declares: the rank the line prints against the rung the edges
    put the subject on, and each grant column against the edges' depth. A difference is a
    place where the book and its record disagree; which of them is right is the reader's.
    """
    systems = gamesystem.systems_of(book.records)
    if not systems:
        return {"comparable": False, "reason": "no declared system", "scenes": [], "mismatches": []}
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for scene in book.drafted:
        if not scene.status_lines:
            continue
        line = scene.status_lines[-1]
        labels = {label.casefold() for label, _ in line.columns}
        # The system whose ladder word the line prints; failing that, the one whose grants
        # the line's columns name most. A line naming no system's words is left unread.
        system: gamesystem.SystemDef | None
        by_rank = [system for system in systems if system.rank_label.casefold() in labels]
        if len(by_rank) == 1:
            system = by_rank[0]
        else:
            scored = sorted(
                systems,
                key=lambda candidate: (
                    -len(labels & {ability.name.casefold() for ability in candidate.abilities})
                ),
            )
            system = (
                scored[0]
                if scored
                and (labels & {ability.name.casefold() for ability in scored[0].abilities})
                else None
            )
        if system is None:
            rows.append(
                {
                    "scene": scene.ordinal,
                    "subject": line.subject,
                    "world": None,
                    "why": "the line names no declared system's ladder or grants",
                }
            )
            continue
        grant_ids = {ability.name.casefold(): ability.ability_id for ability in system.abilities}
        grant_ids.update(
            {ability.ability_id.casefold(): ability.ability_id for ability in system.abilities}
        )
        rank_label = system.rank_label.casefold()
        rank_ids = list(system.rank_ids)
        subject = _subject_of(line.subject, book.records)
        if subject is None:
            rows.append(
                {
                    "scene": scene.ordinal,
                    "subject": line.subject,
                    "world": None,
                    "why": "no subject on record prints under this name",
                }
            )
            continue
        key = state_mod.scene_cutoff(book.records, scene.ordinal) or _cutoff_for(
            book.records, scene.ordinal
        )
        sheet = gamesystem.sheet_of(book.records, subject, system=system, at=key)
        if sheet is None:
            rows.append(
                {
                    "scene": scene.ordinal,
                    "subject": subject,
                    "system": system.system_id,
                    "world": None,
                    "why": "the edges put this subject on no rung of this ladder at this scene",
                }
            )
            continue
        held = dict(sheet.magnitudes)
        world_rank = rank_ids.index(sheet.rank_id) + 1 if sheet.rank_id in rank_ids else None
        compared: dict[str, dict[str, Any]] = {}
        for label, value in line.columns:
            page = _numeric(value)
            if label.casefold() == rank_label:
                world = world_rank
            elif label.casefold() in grant_ids:
                world = held.get(grant_ids[label.casefold()], 0)
            else:
                continue
            compared[label] = {"page": page, "world": world}
            if page is not None and world is not None and page != world:
                mismatches.append(
                    {
                        "scene": scene.ordinal,
                        "subject": subject,
                        "system": system.system_id,
                        "column": label,
                        "page": page,
                        "world": world,
                    }
                )
        rows.append(
            {
                "scene": scene.ordinal,
                "subject": subject,
                "system": system.system_id,
                "at": key,
                "columns": compared,
            }
        )
    return {
        "comparable": True,
        "systems": [system.system_id for system in systems],
        "scenes": rows,
        "mismatches": mismatches,
    }


# ------------------------------------------------------------------------------ the report


VIEWS = ("status", "promises", "facts", "cast", "plans", "refrains", "seams", "sheet")


def report(
    book: BookFacts, *, views: Sequence[str] = VIEWS, subject: str | None = None
) -> dict[str, Any]:
    """The audit, view by view, under one caveat."""
    out: dict[str, Any] = {
        "book_id": book.book_id,
        "branch_id": book.branch_id,
        "title": book.title,
        "scenes_drafted": len(book.drafted),
        "scenes_total": len(book.scenes),
        "chapters_drafted": (len(book.drafted) // max(book.scenes_per_chapter, 1)),
        "words": sum(scene.words for scene in book.drafted),
        "caveat": DESCRIPTIVE_ONLY,
    }
    unknown = [view for view in views if view not in VIEWS]
    if unknown:
        raise ValueError(f"unknown audit view(s): {', '.join(unknown)}; known: {', '.join(VIEWS)}")
    if "status" in views:
        out["status"] = status_line_report(book)
    if "promises" in views:
        out["promises"] = promise_report(book)
    if "facts" in views:
        out["facts"] = fact_timeline(book, subject=subject)
    if "cast" in views:
        out["cast"] = cast_presence(book)
    if "plans" in views:
        out["plans"] = plan_summary_pairs(book)
    if "refrains" in views:
        out["refrains"] = refrains(book)
    if "seams" in views:
        out["seams"] = seams(book)
    if "sheet" in views:
        out["sheet"] = sheet_vs_page(book)
    return out


def attention(audit: dict[str, Any]) -> list[str]:
    """The lines a person should look at first, from a report; empty is a clean census."""
    notes: list[str] = []
    status = audit.get("status")
    if status:
        if len(status["subjects"]) > 1:
            notes.append(f"status line printed under {len(status['subjects'])} subject spellings")
        if len(status["column_sets"]) > 1:
            notes.append(f"status line printed with {len(status['column_sets'])} column sets")
        for row in status["decreases"]:
            notes.append(
                f"{row['subject']} {row['column']} fell {row['was']} -> {row['now']} "
                f"(scene {row['from_scene']} -> {row['to_scene']})"
            )
        if status["unmoved"]:
            notes.append(
                f"status line printed {len(status['unmoved'])} time(s) with no number moved"
            )
        for row in status["kind_flips"]:
            notes.append(
                f"{row['subject']} {row['column']} changed kind {row['was']!r} -> {row['now']!r} "
                f"(scene {row['from_scene']} -> {row['to_scene']})"
            )
    promises = audit.get("promises")
    if promises:
        for subject in promises["overdue"]:
            notes.append(f"debt open past its due scene: {subject}")
        for subject in promises["paid_unlocated"]:
            notes.append(f"debt paid with no located quote: {subject}")
        for subject in promises["paid_early"]:
            notes.append(f"debt paid before it was opened: {subject}")
    facts = audit.get("facts")
    if facts:
        for row in facts["reverted"]:
            notes.append(
                f"{row['subject']} {row['predicate']} returned to an earlier value: "
                + ", ".join(row["values"])
            )
    cast = audit.get("cast")
    if cast:
        for subject in cast["never_on_page"]:
            notes.append(f"declared and never named on the page: {subject}")
        for subject in cast["with_gaps"]:
            notes.append(f"named, then silent for a run of scenes: {subject}")
    said_again = audit.get("refrains")
    if said_again and said_again["phrases"]:
        # A five-word run is often a preposition and a noun; the line names the longest
        # run said most, which is where a writer's hand shows rather than the language's.
        long_runs = [row for row in said_again["phrases"] if len(row["phrase"].split()) >= 7]
        top = (long_runs or said_again["phrases"])[0]
        notes.append(
            f"{said_again['repeated']} word run(s) said in more than one scene; the most "
            f"repeated long one, {top['phrase']!r}, in scenes {top['scenes']}"
        )
    boundaries = audit.get("seams")
    if boundaries:
        for row in boundaries["restated"]:
            notes.append(
                f"scene {row['to_scene']} opens on {row['shared_words']} word(s) scene "
                f"{row['from_scene']} closed on"
                + (" (same chapter)" if row["same_chapter"] else "")
            )
    sheet = audit.get("sheet")
    if sheet and sheet.get("comparable"):
        for row in sheet["mismatches"]:
            notes.append(
                f"scene {row['scene']}: the page prints {row['column']} {row['page']} and the "
                f"world's edges hold {row['world']} for {row['subject']}"
            )
    plans = audit.get("plans")
    if plans:
        if plans["unplanned"]:
            notes.append(f"drafted without a scene plan: scenes {plans['unplanned']}")
        if plans["stale"]:
            notes.append(f"summary older than the prose: scenes {plans['stale']}")
    return notes


__all__ = [
    "DESCRIPTIVE_ONLY",
    "VIEWS",
    "AuditStore",
    "BookFacts",
    "SceneFacts",
    "StatusLine",
    "attention",
    "cast_presence",
    "fact_timeline",
    "load",
    "plan_summary_pairs",
    "promise_report",
    "refrains",
    "report",
    "seams",
    "sheet_vs_page",
    "status_line_report",
    "status_lines_in",
]
