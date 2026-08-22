"""The world reaches the writer and, until this module existed, reached neither scene planner.

`plan/world-architect.md` builds a world and `tests/test_worlds.py` grades what it projects into
a drafting packet. Nothing graded what the *plan* was written against. Serial Pilot 2 handed its
writer a flat 229-231 established facts per scene out of a 329-record world — and the one
sentence the writer is told to execute, `This scene: {plan}`, was written by a model that had
seen the premise and the beat sheet and nothing else.

**Two tests here are a matched pair and the order matters.**
`test_neither_scene_plan_author_is_told_the_world_the_writer_is_handed` passes on `main` at
`83de11c` — it pins the blindness as a measured fact rather than as a claim in a document.
`test_a_forged_world_reaches_the_outline_request` is its twin and fails there; it is the
assertion the world brief exists to satisfy. A repair whose "before" was never runnable is a
repair to something nobody measured.

Everything else in this file is the additivity discipline `tests/test_worlds.py` established
for the packet, applied one layer up: a book that declares no world must render **byte-identical**
planner payloads, and that is asserted rather than argued.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import litharness_contracts as lc

from litharness.application import architect, narrative_planner, outline
from litharness.domain import worlds
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.directives import Directive, DirectiveKind
from litharness.domain.plan_refinement import PlanRevision
from litharness.domain.revision import new_book
from tests.conftest import BOOK_ID, BRANCH_ID

#: The pilot's own scene count. `records_for` mints a disclosure position only for a reveal the
#: book actually has a scene for, and the key width is the book's, so this is not a free
#: parameter: at 6 the scene-7 reveal loses its position and the world says something else.
SCENES = 8

#: A premise from a book with no forged world, for the control that separates what the *world*
#: put in a payload from what the request template says on its own. Taken from
#: `tests/test_outline.py` rather than invented, so the two files describe one fixture.
NEUTRAL_PREMISE = "A courier in a debt-ledger city must clear a guild debt before it compounds."

#: What the pilot world's own vocabulary would have to appear in a payload as, to be a leak.
#: `key_nouns` is the counter the Architect's own M2 uses, and it is crude on purpose.
_LEAKABLE = (
    worlds.WORLD_RULE_PREDICATE,
    worlds.CONSEQUENCE_PREDICATE,
    worlds.CLAIM_CONTENT,
    worlds.MANIFESTS_PREDICATE,
)


class _Base:
    """The stub `PlanRevision` `tests/test_outline.py` uses for request-shape tests."""

    plan_revision_id = "planrev-1"
    items: tuple = ()


def pilot_records() -> tuple[architect.Candidate, tuple[lc.StateRecord, ...], str]:
    """The world Serial Pilot 2 ran on, rebuilt exactly as `tests/test_architect.py` rebuilds it.

    `plan/serial-pilot-2-world.json` is the committed model answer and `records_for` is the
    only thing that turns it into records, so this is the same 329 rows the pilot's writer was
    handed rather than a fixture that resembles them.
    """
    package = json.loads(
        (Path(__file__).resolve().parents[1] / "plan" / "serial-pilot-2-world.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = architect.Candidate(0, package["world"])
    records = architect.records_for(
        candidate, authority=lc.StateAuthority.ACCEPTED_CANON, scenes=SCENES
    )
    return candidate, records, str(candidate.raw["premise"])


def payload_of(request: object) -> str:
    """Prompt and system message together — the whole of what a provider is sent."""
    prompt = getattr(request, "prompt", "")
    system = getattr(request, "system", None) or ""
    return f"{prompt}\n{system}"


def named_in(text: str, nouns: tuple[str, ...]) -> set[str]:
    """The world's coined nouns that appear in `text` as whole words, case-folded."""
    return {noun for noun in nouns if re.search(rf"\b{re.escape(noun)}\b", text, re.I)}


def leaked_values(text: str, records: tuple[lc.StateRecord, ...]) -> list[str]:
    """Every rule, consequence, claim answer or manifestation stated verbatim in `text`."""
    return [
        f"{record.subject}.{record.predicate}"
        for record in records
        if record.predicate in _LEAKABLE
        and isinstance(record.value, str)
        and record.value
        and record.value in text
    ]


def a_directive(body: str) -> Directive:
    return Directive(
        directive_id="dir-1",
        kind=DirectiveKind.CONSTRAINT,
        body=body,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
    )


def a_plan(premise: str) -> PlanRevision:
    return PlanRevision(
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        items=(
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text=premise,
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            ),
        ),
    )


# -- Task 0: the blindness, pinned before it was repaired ----------------------------------


def test_neither_scene_plan_author_is_told_the_world_the_writer_is_handed() -> None:
    """Measured on 2026-08-22 against `main` at `83de11c`, and true there: of a 329-record
    world with 7 rules, 21 consequences, 28 claims and 42 manifestations, **exactly zero
    values reach either planner payload**, and the coined nouns that do reach them are the
    premise's own and nothing else.

    Both sentences a writer executes are written here. `render_outline_request` writes one
    statement per scene from the premise, the beat sheet, the starting sheet and the open
    promises; `narrative_planner.render_request` rewrites them from a directive and the plan.
    Neither is handed a state record — the outline handler reads `store.state_records` and
    keeps only the `status_snapshot`, and the narrative-plan handler reads no state at all.
    So the consequence cascades the design calls "each a plot engine", the cast with their
    wants and ties, and every hidden answer with its reveal scene arrive at the *writer* under
    "Established facts", and the plan the writer is told to execute was written against none
    of them.

    **The narrative-planner arm carries a control rather than an exact equality, and the
    reason is a measured collision.** `key_nouns` reads inner-capital words out of a world's
    own prose, and this world's `r_lag` manifests as "a tax on a column headed NEVER" — so
    `never` is one of its 49 coined names, and the request template's own eighth rule begins
    "Never update or delete a locked item." The template's contribution is therefore computed
    from a payload built with a neutral premise and a neutral directive and subtracted, which
    is the honest form of the same assertion.
    """
    candidate, records, premise = pilot_records()
    nouns = worlds.key_nouns(records)
    revision = new_book(BOOK_ID, BRANCH_ID, title=candidate.title, scenes=SCENES)
    beats = beats_for(revision, arc_template(SCENES))

    outline_payload = payload_of(
        outline.render_outline_request(premise, beats, base=_Base())  # type: ignore[arg-type]
    )
    assert leaked_values(outline_payload, records) == []
    # Exactly the premise's, with nothing added and nothing lost: the outline request is the
    # premise, the sheet and seven fixed rules, and the sheet names no part of any world.
    assert named_in(outline_payload, nouns) == named_in(premise, nouns)

    template = payload_of(
        outline.render_outline_request(
            NEUTRAL_PREMISE, beats, base=_Base()  # type: ignore[arg-type]
        )
    )
    assert named_in(template, nouns) == set(), "the beat sheet coins nothing of its own"

    scene_ids = tuple(f"s{index}" for index in range(1, SCENES + 1))
    blind = named_in(
        payload_of(
            narrative_planner.render_request(
                a_plan(NEUTRAL_PREMISE), a_directive("Keep it moving."), scene_ids
            )
        ),
        nouns,
    )
    for entry in architect.directives_for(candidate):
        payload = payload_of(
            narrative_planner.render_request(
                a_plan(premise), a_directive(entry["text"]), scene_ids
            )
        )
        assert leaked_values(payload, records) == []
        beyond = named_in(payload, nouns) - named_in(premise, nouns)
        beyond -= named_in(entry["text"], nouns) | blind
        assert beyond == set(), f"the world reached a {entry['kind']} payload: {sorted(beyond)}"


def test_the_outline_call_knew_the_questions_and_the_windows_and_not_the_answers() -> None:
    """What the blindness is **not**: the pilot's planner was not told nothing at all.

    It was handed the premise, an eight-beat sheet, and — once the ledger had anything on it —
    the open promises as owed, each with the scene it is due by. Six of those debts were the
    world's own mysteries, seeded by `architect.promises_for` with the question as the
    description and the reveal ordinal as the due date. So the schedule was in the request and
    the answers were not, which is a different defect from ignorance and wants a different
    repair. Recorded here so a later reading of the uptake census cannot mistake one for the
    other.
    """
    candidate, records, _ = pilot_records()
    seeded = architect.promises_for(candidate)
    assert len(seeded) == 6
    assert {entry["subject"] for entry in seeded} == set(worlds.questions(records))
    for entry in seeded:
        assert entry["description"] == worlds.questions(records)[entry["subject"]]
        assert entry["due_scene"] == worlds.reveal_scenes(records)[entry["subject"]]
    # And the answers are somewhere else entirely: `claims` holds them, `questions` does not.
    answers = worlds.claims(records)
    for entry in seeded:
        assert answers[entry["subject"]] != entry["description"]
