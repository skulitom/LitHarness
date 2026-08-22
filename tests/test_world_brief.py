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
from collections.abc import Sequence
from pathlib import Path

import litharness_contracts as lc

from litharness.adapters import contracts_fixtures
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import architect, narrative_planner, outline
from litharness.domain import world_brief, worlds
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.directives import Directive, DirectiveKind
from litharness.domain.generation import CompletionResult, Resolution, Usage
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.plan_refinement import PlanRevision
from litharness.domain.revision import new_book
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

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

    **What it pins now that the repair has landed, so nobody reads it as still current.** Both
    calls take a `world` and this passes none, so what is asserted here after 2026-08-22 is
    that a request built without a brief carries no world — which is boundary 4's other face
    and is worth keeping. That the *loop* now hands one over is a different claim, and it is
    `test_the_outline_handler_hands_the_planner_the_world_the_store_holds` that makes it: the
    pair reads as a before and an after only if the after is measured on the live path.
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


# -- Task 2: the twin, and the rails it had to clear ---------------------------------------


def test_a_forged_world_reaches_the_outline_request() -> None:
    """The twin of the blindness pin, and it **fails on `main` at `83de11c`** by construction:
    `test_neither_scene_plan_author_is_told_the_world_the_writer_is_handed` asserts of the same
    payload that exactly none of these values is in it, and that test passes there.

    What has to arrive is not "some world text" — it is the four things a statement would have
    to be written against to put the world to work. Every rule, because a scene that only this
    world could produce is a scene where a rule bites. Every consequence, because
    `plan/world-architect.md` §4 item 5 calls each of them a plot engine. The criterion ladder,
    because a scene that moves somebody up it has to know what it is. And each mystery's
    question with the scene the world scheduled its answer for, because a reveal planned as an
    event is the difference between a book that pays a debt and a book that mentions one.
    """
    candidate, records, premise = pilot_records()
    revision = new_book(BOOK_ID, BRANCH_ID, title=candidate.title, scenes=SCENES)
    beats = beats_for(revision, arc_template(SCENES))
    brief = world_brief.brief_for(records)
    assert brief is not None
    payload = payload_of(
        outline.render_outline_request(
            premise, beats, base=_Base(), world=brief  # type: ignore[arg-type]
        )
    )

    for rule in worlds.rules(records):
        statement = next(
            record.value
            for record in records
            if record.subject == rule and record.predicate == worlds.WORLD_RULE_PREDICATE
        )
        assert str(statement) in payload, f"rule {rule} did not reach the outline request"
    consequences = [
        str(record.value)
        for record in records
        if record.predicate == worlds.CONSEQUENCE_PREDICATE and record.value
    ]
    assert consequences and all(text in payload for text in consequences)
    criteria = worlds.criterion_brief(records)
    assert criteria is not None
    # Line by line: `criterion_brief` is one string with newlines in it and the payload is
    # JSON, so the newlines arrive escaped. Asserting the whole string would fail on the
    # encoding rather than on the content, which is the wrong thing for this test to notice.
    for line in criteria.splitlines():
        assert line in payload, f"the criterion ladder line {line!r} did not reach the request"
    for claim_id, question in worlds.questions(records).items():
        assert question in payload, f"mystery {claim_id} reached the planner without its question"
    # And the four world rules, which are instructions about what to plan and never about names.
    for rule_text in world_brief.WORLD_RULES:
        assert rule_text in payload


def test_a_forged_world_reaches_the_narrative_plan_request() -> None:
    """The same, for the other author of the same sentence.

    `narrative_planner.render_request` rewrites statements under a director's or an Architect's
    directive, and a rewrite that does not know the world replaces a world-aware statement with
    a blind one — which would make the repair depend on which of the two calls happened to
    write a given scene.
    """
    candidate, records, premise = pilot_records()
    brief = world_brief.brief_for(records)
    assert brief is not None
    scene_ids = tuple(f"s{index}" for index in range(1, SCENES + 1))
    entry = architect.directives_for(candidate)[0]
    payload = payload_of(
        narrative_planner.render_request(
            a_plan(premise), a_directive(entry["text"]), scene_ids, world=brief
        )
    )
    assert all(
        str(record.value) in payload
        for record in records
        if record.predicate == worlds.WORLD_RULE_PREDICATE
    )
    assert world_brief.WORLD_RULES[0] in payload


def test_a_book_with_no_world_renders_the_payload_it_always_did() -> None:
    """Boundary 4, and it is bytes rather than an argument.

    The trap is `json.dumps`, which writes `null` for a value that is not there: both existing
    optional keys — `open_promises` and `starting_state` — are *always present* and render as
    `null`, so copying the module's own style would have made every no-world payload a
    different payload. The field is spread in and is absent entirely without a world, and this
    compares the two constructions byte for byte.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=SCENES)
    beats = beats_for(revision, arc_template(SCENES))
    before = outline.render_outline_request(
        NEUTRAL_PREMISE, beats, base=_Base()  # type: ignore[arg-type]
    )
    after = outline.render_outline_request(
        NEUTRAL_PREMISE, beats, base=_Base(), world=None  # type: ignore[arg-type]
    )
    assert before.prompt == after.prompt
    assert before.system == after.system
    assert "world" not in before.prompt

    scene_ids = tuple(f"s{index}" for index in range(1, SCENES + 1))
    plan, directive = a_plan(NEUTRAL_PREMISE), a_directive("Keep it moving.")
    plain = narrative_planner.render_request(plan, directive, scene_ids)
    explicit = narrative_planner.render_request(plan, directive, scene_ids, world=None)
    assert plain.prompt == explicit.prompt
    assert plain.system == explicit.system
    assert "world" not in plain.prompt


def test_a_book_whose_records_this_vocabulary_does_not_know_gets_no_brief() -> None:
    """Absence is free, and it is enforced rather than intended.

    An operator's own flat seed — the shape Serial Pilot 1 was typed in — projects to nothing,
    so `brief_for` returns `None` rather than a brief of `state.describe` notation. The
    alternative would hand a planner machine lines it cannot write an instruction against,
    which is the blocker `plan/state-model-abilities.md` §2 names for the packet and is no
    smaller here.
    """
    flat = [
        lc.StateRecord(
            record_id="rec-1",
            kind=lc.StateRecordKind.ASSERTION,
            subject="silas",
            predicate="is_at",
            value="the assay house",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
    ]
    assert world_brief.brief_for(flat) is None
    assert world_brief.brief_for([]) is None


def test_a_proposed_world_is_not_a_world_a_planner_may_see() -> None:
    """`forge --pick` is the one exit to canon and this is the other end of that rail.

    `architect.records_for` defaults to `PROPOSED`, and a candidate nobody picked is a
    candidate: it reaches no context packet, so it may not reach a plan either. Without this
    the brief would be the one path by which an unpicked world steers a book.
    """
    _, records, _ = pilot_records()
    proposed = [
        lc.StateRecord(
            record_id=record.record_id,
            kind=record.kind,
            subject=record.subject,
            predicate=record.predicate,
            value=record.value,
            object_ref=record.object_ref,
            story_position=record.story_position,
            authority=lc.StateAuthority.PROPOSED,
            pov_visibility=list(record.pov_visibility),
        )
        for record in records
    ]
    assert world_brief.brief_for(proposed) is None


# -- the leak rail --------------------------------------------------------------------------


def test_no_answer_the_book_does_not_reach_appears_anywhere_in_the_brief() -> None:
    """Boundary 3's second clause, and the one with no escape hatch.

    Four of the pilot world's six mysteries are answered at scenes 26, 41, 63 and 92 — past the
    end of an eight-scene opening — so `architect.story_key` mints them no position and the
    packet keeps them hidden for the whole run. A brief that carried those answers would put
    the serial's arc secrets into a plan item on page one, which is worse than the blindness
    this repair exists to end.
    """
    _, records, _ = pilot_records()
    brief = world_brief.brief_for(records)
    assert brief is not None
    payload = json.dumps(brief.to_jsonable(), ensure_ascii=False, sort_keys=True)
    scheduled = worlds.disclosures(records)
    answers = worlds.claims(records)
    arc = [claim for claim in worlds.questions(records) if claim not in scheduled]
    assert len(arc) == 4
    for claim in arc:
        assert answers[claim] not in payload
        assert worlds.questions(records)[claim] in payload, "the question still goes in"
    # And every one of them is marked as not this book's to answer.
    marked = {
        reveal.claim_id for reveal in brief.reveals if reveal.scene is None and not reveal.answer
    }
    assert set(arc) <= marked


def test_an_answer_appears_only_on_the_entry_for_the_scene_that_reveals_it() -> None:
    """Boundary 3's first clause. A planner may be told an answer *to place its reveal*.

    Two of the six mysteries land inside these eight scenes, at 4 and 7 — the two scenes where
    Serial Pilot 2's frozen prompts show the hidden count dropping 20 → 19 → 18. Their answers
    are carried, and they are carried attached to those ordinals rather than loose in the
    facts, so a statement for scene 1 has the question in front of it and the answer nowhere.
    """
    _, records, _ = pilot_records()
    brief = world_brief.brief_for(records)
    assert brief is not None
    answers = worlds.claims(records)
    carried = {reveal.claim_id: reveal for reveal in brief.reveals if reveal.answer}
    assert set(carried) == {"m_holts_date", "m_orrin_last_call"}
    assert carried["m_holts_date"].scene == 4
    assert carried["m_orrin_last_call"].scene == 7
    facts = "\n".join(line for _, lines in brief.groups for line in lines)
    for claim_id, reveal in carried.items():
        assert reveal.answer == answers[claim_id]
        assert answers[claim_id] not in facts, "an answer in the facts is an answer at scene one"


def test_every_claim_hidden_at_scene_one_is_absent_from_the_facts() -> None:
    """Wider than the mysteries, and it has to be: twenty of the pilot world's twenty-eight
    claims are hidden at scene one and only six of them are declared mysteries. The rest are
    cast secrets, a place's secret, two systems' natures and a history's — none owed a reveal,
    none ever to be stated. A brief built from `questions` alone would have leaked fourteen.
    """
    _, records, _ = pilot_records()
    brief = world_brief.brief_for(records)
    assert brief is not None
    payload = json.dumps(brief.to_jsonable(), ensure_ascii=False, sort_keys=True)
    hidden = worlds.undisclosed_claims(records, at=None)
    assert len({record.subject for record in hidden}) == 20
    windows = {"m_holts_date", "m_orrin_last_call"}
    for record in hidden:
        if record.subject in windows:
            continue
        assert str(record.value) not in payload, f"{record.subject} reached a planner"


def test_a_false_belief_is_carried_by_its_holder_and_is_not_a_mystery() -> None:
    """The partition the vocabulary already draws, honoured here rather than re-derived.

    Eight of the pilot world's claims are marked `claim.false`. They are not hidden — a world's
    error belongs to whoever holds it — so their content reaches the packet through the
    `believes` edge with the holder attached, and it reaches the brief the same way. What must
    not happen is one of them appearing under `mysteries`, which would ask a planner to
    schedule the reveal of something that is not true.
    """
    _, records, _ = pilot_records()
    brief = world_brief.brief_for(records)
    assert brief is not None
    wrong = worlds.false_claims(records)
    assert len(wrong) == 8
    assert not (wrong & {reveal.claim_id for reveal in brief.reveals})
    facts = "\n".join(line for _, lines in brief.groups for line in lines)
    assert "believes, wrongly:" in facts


def test_a_record_restricted_to_one_character_never_reaches_a_planner() -> None:
    """`state.visible_to(record, None)` is the packet's own filter and a planner is not a POV.

    A fact about who knows what, handed to a model writing an instruction for everybody, is the
    leak `worlds.project` refuses to fold for the same reason.
    """
    restricted = lc.StateRecord(
        record_id="rec-secret",
        kind=lc.StateRecordKind.ASSERTION,
        subject="r_hidden",
        predicate=worlds.WORLD_RULE_PREDICATE,
        value="Only Silas knows the tide is aimed.",
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=["silas"],
    )
    plain = worlds.world_record(
        "r_open", worlds.WORLD_RULE_PREDICATE, value="History fixes price.",
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    brief = world_brief.brief_for([restricted, plain])
    assert brief is not None
    payload = json.dumps(brief.to_jsonable(), ensure_ascii=False)
    assert "History fixes price." in payload
    assert "Only Silas knows" not in payload


def test_the_rules_handed_to_a_planner_never_ask_for_a_name() -> None:
    """Boundary 1, enforced on the prompt rather than trusted.

    `research/quality-measurement/world_uptake.py` counts how much of a world is *named* on the
    page. A prompt that asked for names would make that counter its own target — the
    shallow-because-easy failure this project refuses — and would do it in the one place where
    nobody would think to look for it afterwards.
    """
    joined = " ".join(world_brief.WORLD_RULES).lower()
    for forbidden in ("name the", "names of", "use the name", "mention the", "refer to the"):
        assert forbidden not in joined
    # What it does ask for: consequences put to work, and a reveal planned as an event.
    assert "consequences" in joined
    assert "event" in joined
    assert "do not explain the world" in joined


def test_the_brief_says_the_same_facts_the_writer_is_handed() -> None:
    """The claim in the module docstring, measured rather than asserted.

    Serial Pilot 2's frozen scene-one drafting prompt carries **229 established facts** and 20
    hidden claims, and `context_omitted` is 0 for the whole book. The brief is built from the
    same projection with the same fallback and the same filters, so it carries the same 229 —
    which is what makes "the planner now sees what the writer sees" a checkable sentence rather
    than a description of intent.
    """
    _, records, _ = pilot_records()
    brief = world_brief.brief_for(records)
    assert brief is not None
    assert brief.facts == 229
    assert brief.criteria is not None
    assert len(brief.reveals) == 6
    assert {name for name, _ in brief.groups} == {
        "rules", "cast", "systems", "institutions", "places", "creatures",
        "carriers", "agencies", "other",
    }


# -- the wiring: from records in a store to the request a provider is handed ----------------


def _outline_job() -> Job:
    payload = {"book_id": BOOK_ID, "branch_id": BRANCH_ID, "plan_epoch": 0}
    return Job(
        job_id="outline-job",
        attempts=0,
        job_kind=outline.BOOK_OUTLINE,
        payload=payload,
        input_digest=input_digest_for(payload),
        priority=outline.OUTLINE_PRIORITY,
    )


class _Capture:
    """A provider that answers a valid outline and keeps what it was asked."""

    def __init__(self, scenes: int) -> None:
        self.requests: list[object] = []
        self.payload = {
            "summary": "outline",
            "rationale": "every scene needs its own errand",
            "expected_outcome": "scenes differ",
            "milestones": [],
            "payoff_windows": [],
            "scenes": [
                {"ordinal": index + 1, "statement": f"Scene {index + 1}: something happens."}
                for index in range(scenes)
            ],
        }

    def resolve(self, call_class: str = "generation"):  # type: ignore[no-untyped-def]
        class _P:
            name = "stub"

        return _P(), Resolution("stub")

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return (
            CompletionResult(
                text="{}",
                provider="stub",
                model="stub-v1",
                usage=Usage(100, 400),
                parsed=self.payload,
                schema_requested=True,
            ),
            Resolution("stub"),
        )


def _seed_world(store: SqliteStore, records: Sequence[lc.StateRecord]) -> None:
    store.record_state_records(BOOK_ID, BRANCH_ID, list(records), created_at="2026-08-22T00:00:00Z")


def test_the_outline_handler_hands_the_planner_the_world_the_store_holds(tmp_path: Path) -> None:
    """The wiring, end to end, because everything above tests the render function directly.

    A repair that works when a test calls `render_outline_request` with a brief and never when
    the loop runs is a repair to a function rather than to a book. This drives
    `make_outline_handler` against a store holding the pilot world's 329 canon records and
    reads what the provider was actually asked.
    """
    candidate, records, premise = pilot_records()
    with SqliteStore.open(tmp_path / "outline.db") as store:
        revision = new_book(BOOK_ID, BRANCH_ID, title=candidate.title, scenes=SCENES)
        store.commit_revision(revision, created_at="2026-08-22T00:00:00Z")
        store.record_plan_items(
            BOOK_ID,
            BRANCH_ID,
            [
                lc.PlanItem(
                    logical_id="premise",
                    kind=lc.PlanKind.PREMISE,
                    text=premise,
                    authority=lc.PlanAuthority.CANONICAL_IN_PROSE,
                    locked=True,
                )
            ],
            created_at="2026-08-22T00:00:00Z",
        )
        _seed_world(store, records)
        planner = _Capture(SCENES)
        outline.make_outline_handler(planner, store, PROJECT_ID)(_outline_job(), 1_760_000_000.0)

    assert planner.requests, "the handler never reached the provider"
    prompt = str(planner.requests[0].prompt)  # type: ignore[attr-defined]
    assert '"world"' in prompt
    for rule in worlds.rules(records):
        statement = next(
            record.value
            for record in records
            if record.subject == rule and record.predicate == worlds.WORLD_RULE_PREDICATE
        )
        assert str(statement) in prompt
    # And the rail holds on the live path, not only in the unit that builds the brief.
    answers = worlds.claims(records)
    for claim in worlds.questions(records):
        if claim in worlds.disclosures(records):
            continue
        assert answers[claim] not in prompt, f"the arc answer {claim} reached a live prompt"


def test_the_outline_handler_of_a_book_with_no_world_asks_what_it_always_asked(
    tmp_path: Path,
) -> None:
    """The other half of boundary 4, on the live path. A book whose store holds no world — every
    book written before `domain/worlds.py`, and both golden fixtures — must reach the provider
    with the request it always reached it with."""
    with SqliteStore.open(tmp_path / "outline.db") as store:
        revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=SCENES)
        store.commit_revision(revision, created_at="2026-08-22T00:00:00Z")
        store.record_plan_items(
            BOOK_ID,
            BRANCH_ID,
            [
                lc.PlanItem(
                    logical_id="premise",
                    kind=lc.PlanKind.PREMISE,
                    text=NEUTRAL_PREMISE,
                    authority=lc.PlanAuthority.CANONICAL_IN_PROSE,
                    locked=True,
                )
            ],
            created_at="2026-08-22T00:00:00Z",
        )
        planner = _Capture(SCENES)
        outline.make_outline_handler(planner, store, PROJECT_ID)(_outline_job(), 1_760_000_000.0)

    prompt = str(planner.requests[0].prompt)  # type: ignore[attr-defined]
    beats = beats_for(
        new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=SCENES), arc_template(SCENES)
    )
    assert "world" not in prompt
    expected = outline.render_outline_request(
        NEUTRAL_PREMISE,
        beats,
        base=_ByRevision(str(planner.requests[0].prompt)),  # type: ignore[attr-defined,arg-type]
    )
    assert prompt == expected.prompt


class _ByRevision:
    """A stand-in whose `plan_revision_id` is read out of the prompt being compared against.

    The revision id is content-addressed over the plan, so a byte comparison against a
    separately built request would fail on that one field and on nothing else — which would
    make this test about hashing rather than about the world. Reading it back is the narrow
    way to hold it fixed without weakening the comparison anywhere else.
    """

    items: tuple = ()

    def __init__(self, prompt: str) -> None:
        payload = json.loads(prompt)
        self.plan_revision_id = str(payload["base_plan_revision_id"])


def test_the_golden_books_produce_no_brief_at_all() -> None:
    """Boundary 4's proof, on the two books this repository grades everything against.

    Neither golden fixture declares a world — `mystery` states arrivals, claims and disinheritance
    and `litrpg` states levels, purchases and quests, and not one of the 35 records between them
    carries a predicate `domain/worlds.py` recognises. So `worlds.project` returns an empty mapping
    for both and `brief_for` returns `None`, and the planner payload for either is the payload it
    was before this feature existed. Asserted rather than assumed, because "untouched by
    construction" is a claim about somebody else's package — `tests/test_worlds.py` makes the same
    argument about the same two fixtures for the packet.
    """
    for fixture_id in contracts_fixtures.FIXTURE_IDS:
        snapshot = lc.parse_artifact(
            lc.StateSnapshot,
            json.loads(contracts_fixtures.fixture_state(fixture_id).read_text(encoding="utf-8")),
        )
        assert snapshot.records, f"the {fixture_id} fixture has no state to test with"
        assert worlds.project(snapshot.records) == {}
        assert world_brief.brief_for(snapshot.records) is None, fixture_id


def test_a_declared_capability_gets_its_own_group_and_not_the_other_bucket() -> None:
    """**The third of the three fixes the inventory needed**, and the smallest.

    A capability is an ordinary subject with an `entity_role`, so before `_ROLE_GROUP` had an
    entry for it `_group_of` fell through to `other` — the bucket the module's own docstring says
    is "never empty by design" and holds a world's history, bonds and cardinality shapes. A
    planner reading a brief would meet what somebody can do filed with the leftovers.

    It sits straight after `cast` because it is a fact about those people: a statement that puts a
    capability to work is a statement about what somebody can do.
    """
    records = [
        lc.StateRecord(
            record_id=f"rec-{i}",
            kind=lc.StateRecordKind.ASSERTION,
            subject=subject,
            predicate=predicate,
            value=value,
            object_ref=object_ref,
            authority=lc.StateAuthority.ACCEPTED_CANON,
            predicate_registry_version=worlds.REGISTRY_VERSION,
        )
        for i, (subject, predicate, value, object_ref) in enumerate(
            [
                ("cap_read_a_seam", worlds.ENTITY_ROLE_PREDICATE, "capability", None),
                ("cap_read_a_seam", "is_a", "he can see where two things were joined", None),
                ("silas", worlds.ENTITY_ROLE_PREDICATE, "cast", None),
                ("silas", worlds.CAN_DO, None, "cap_read_a_seam"),
            ]
        )
    ]
    brief = world_brief.brief_for(records)
    assert brief is not None
    grouped = dict(brief.groups)
    assert "capabilities" in grouped, list(grouped)
    assert any("cap_read_a_seam" in line for line in grouped["capabilities"])
    assert "other" not in grouped or not any(
        "cap_read_a_seam" in line for line in grouped.get("other", ())
    )
    # The person's own line says it in English rather than in notation.
    assert any("silas can do cap_read_a_seam" in line for line in grouped["cast"])
    assert "capabilities" in world_brief.GROUPS
    assert world_brief.GROUPS.index("capabilities") == world_brief.GROUPS.index("cast") + 1
