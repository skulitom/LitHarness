"""The world model: the record patterns, what they project into a packet, and what checks them.

Grades `plan/world-architect.md` §5 items 1, 3, 4, 6 and 7 — the vocabulary, the projection, the
hidden section, the cardinality detector, and the second extractor family. It does **not** grade
whether a forged world is any good; there is no quality ordering over worlds in this project and
`tests/test_architect.py` pins the absence of one.

**The first test in this file is a measurement rather than an assertion about intent.** It runs
the four spellings `plan/state-model-abilities.md` §2 tabulates and records what the detector
does with each, so the correction that note needed — its third row reads 1 and measures 0 — stays
runnable rather than becoming a claim in a document.

The additivity tests are the template `tests/test_context.py`'s summaries suite established: a
book that declares no world must pack **byte-identically** to what it did before this module
existed, and that is asserted rather than argued.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters import contracts_fixtures
from litharness.domain import extraction, worlds
from litharness.domain.context import FACTS, HIDDEN, assemble
from litharness.domain.findings import DetectorInput, Severity
from litharness.domain.integrity import (
    detect_cardinality_violations,
    detect_contradictions,
)
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import Revision, build_revision, node_version_id
from litharness.domain.text import content_hash
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

PREMISE_ITEM = lc.PlanItem(
    logical_id="plan-premise",
    kind=lc.PlanKind.PREMISE,
    text="A junior clerk learns what the ledger is really counting.",
    authority=lc.PlanAuthority.INTENDED,
    locked=True,
)


def canon(record: lc.StateRecord) -> lc.StateRecord:
    """The same record, accepted. `world_record` proposes; canon is what a decision makes."""
    return lc.StateRecord(
        record_id=record.record_id,
        kind=record.kind,
        subject=record.subject,
        predicate=record.predicate,
        value=record.value,
        object_ref=record.object_ref,
        story_position=record.story_position,
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=list(record.pov_visibility),
        evidence=list(record.evidence),
        predicate_registry_version=record.predicate_registry_version,
        note=record.note,
    )


def edge(subject: str, predicate: str, target: str, value: object = None, key: str = "s1"):
    return lc.StateRecord(
        record_id=f"{subject}-{predicate}-{target}-{key}",
        kind=lc.StateRecordKind.RELATIONSHIP,
        subject=subject,
        predicate=predicate,
        object_ref=target,
        value=value,
        story_position=lc.StoryPosition(order_key=key),
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def flat(subject: str, predicate: str, value: object, key: str = "s1"):
    return lc.StateRecord(
        record_id=f"{subject}-{predicate}-{value}-{key}",
        kind=lc.StateRecordKind.ASSERTION,
        subject=subject,
        predicate=predicate,
        value=value,
        story_position=lc.StoryPosition(order_key=key),
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def detector(records) -> DetectorInput:
    return DetectorInput(
        book_id=BOOK_ID, branch_id=BRANCH_ID, logical_id="scene-1", records=tuple(records)
    )


def one_scene_book(text: str = "") -> Revision:
    return build_revision(
        BOOK_ID,
        BRANCH_ID,
        [
            Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
            Node.text_node("scene-1", NodeKind.SCENE, "020", "Ink dried on the page.",
                           parent_logical_id="book"),
            Node(logical_id="scene-2", kind=NodeKind.SCENE, position_key="030",
                 parent_logical_id="book"),
        ],
    )


# --- what the detector actually keys on -----------------------------------------------------


def test_the_edge_cases_the_design_note_measured() -> None:
    """The four spellings of `plan/state-model-abilities.md` §2, run rather than reasoned about.

    **The note's third row is wrong and this is where the correction lives.** It gives
    `ash trait → keen_scent` beside `→ night_sight` as "1, MAJOR, blocking". Measured before the
    edge entered the key, that spelling produced **0**; what produced 1 was the same fact written
    with the trait in `value`. So the thing the detector keyed on was never the edge at all — it
    was whether the two records' annotations differed.

    After the change, an edge pair is two facts here and exclusivity is a thing a world declares.
    """
    two_hands = [
        edge("card_of_ashes", "held_by", "silas"),
        edge("card_of_ashes", "held_by", "marta"),
    ]
    annotated = [
        edge("card_of_ashes", "held_by", "silas", "he took it"),
        edge("card_of_ashes", "held_by", "marta", "she took it"),
    ]
    two_traits = [edge("ash", "trait", "keen_scent"), edge("ash", "trait", "night_sight")]
    as_values = [flat("ash", "trait", "keen_scent"), flat("ash", "trait", "night_sight")]
    moved_at_once = [
        flat("silas", "status_snapshot", {"loop": 1, "day": 1}),
        flat("silas", "status_snapshot", {"loop": 1, "day": 2}),
    ]

    # An edge pair is never a contradiction here, however it is annotated. The second list is
    # the false positive that was being reported before the change.
    assert detect_contradictions(detector(two_hands)) == []
    assert detect_contradictions(detector(annotated)) == []
    assert detect_contradictions(detector(two_traits)) == []

    # A single-slot fact holding two values at one position still is one, which is the whole of
    # what this detector was ever entitled to say.
    assert len(detect_contradictions(detector(as_values))) == 1
    [moved] = detect_contradictions(detector(moved_at_once))
    assert moved.severity is Severity.MAJOR
    assert moved.blocks

    # And one object in two hands becomes visible the moment the world says it is impossible.
    shape = [
        canon(worlds.world_record("one_holder", worlds.TYPE_PREDICATE,
                                  value=worlds.CARDINALITY_CONSTRAINT)),
        canon(worlds.world_record("one_holder", worlds.PREDICATE_PREDICATE, value="held_by")),
        canon(worlds.world_record("one_holder", worlds.SCOPE_PREDICATE, value=worlds.ANY_SCOPE)),
        canon(worlds.world_record("one_holder", worlds.GROUP_KEY_PREDICATE,
                                  value="subject,order_key")),
        canon(worlds.world_record("one_holder", worlds.MAXIMUM_PREDICATE, value=1)),
    ]
    assert detect_cardinality_violations(detector(two_hands)) == []  # no shape, no check
    [violation] = detect_cardinality_violations(detector([*two_hands, *shape]))
    assert violation.severity is Severity.MAJOR
    assert violation.blocks
    assert "marta" in violation.message and "silas" in violation.message
    # Two traits stay ordinary: the shape names `held_by` and nothing else.
    assert detect_cardinality_violations(detector([*two_traits, *shape])) == []


@pytest.mark.parametrize("fixture_id", contracts_fixtures.FIXTURE_IDS)
def test_both_golden_fixtures_stay_silent_under_the_new_key(fixture_id: str) -> None:
    """The negative control that licenses a blocking gate, re-run after the key changed.

    Both fixtures hold zero records with `object_ref` set, so their grouping is untouched by
    construction — asserted here rather than assumed, because "untouched by construction" is a
    claim about the data and the data is somebody else's package.
    """
    snapshot = lc.parse_artifact(
        lc.StateSnapshot,
        json.loads(contracts_fixtures.fixture_state(fixture_id).read_text(encoding="utf-8")),
    )
    assert not [record for record in snapshot.records if record.object_ref]
    assert detect_contradictions(detector(snapshot.records)) == []
    assert detect_cardinality_violations(detector(snapshot.records)) == []


def test_an_undeclared_predicate_is_unchecked_and_that_is_the_price() -> None:
    """A shape names one predicate; every other stays untyped and non-blocking.

    The alternative — a frozen arity table — welds one world's physics into the engine, which is
    the stat sheet's mistake one level down. The cost of the safe direction is stated rather than
    hidden: a world that declares no shape is checked for nothing.
    """
    records = [
        edge("workshop", "owned_by", "silas"),
        edge("workshop", "owned_by", "marta"),
    ]
    assert detect_cardinality_violations(detector(records)) == []
    assert detect_contradictions(detector(records)) == []


def test_a_cardinality_shape_missing_a_part_checks_nothing_and_says_so() -> None:
    """Half a shape is not a shape, and the complaint is at forge time rather than at draft time."""
    partial = [
        canon(worlds.world_record("one_holder", worlds.TYPE_PREDICATE,
                                  value=worlds.CARDINALITY_CONSTRAINT)),
        canon(worlds.world_record("one_holder", worlds.PREDICATE_PREDICATE, value="held_by")),
    ]
    assert worlds.cardinality_shapes(partial) == ()
    complaints = worlds.validate(partial)
    assert any("incomplete shape checks nothing" in complaint for complaint in complaints)


# --- the counters --------------------------------------------------------------------------


def test_consequence_domains_count_domains_rather_than_consequences() -> None:
    """Three consequences all in the economy are one consequence with three faces."""
    records = [
        worlds.world_record("provenance", worlds.WORLD_RULE_PREDICATE, value="history fixes price"),
        worlds.world_record("provenance", worlds.CONSEQUENCE_PREDICATE,
                            object_ref="economy", value="ledgers outvalue vaults"),
        worlds.world_record("provenance", worlds.CONSEQUENCE_PREDICATE,
                            object_ref="economy", value="a receipt is collateral"),
        worlds.world_record("provenance", worlds.CONSEQUENCE_PREDICATE,
                            object_ref="economy", value="assayers set the rate"),
    ]
    assert worlds.consequence_domains(records) == {"provenance": ("economy",)}


def test_manifestation_coverage_is_one_for_a_world_that_declared_nothing() -> None:
    """`declared nothing` and `declared everything and showed none of it` must differ."""
    assert worlds.manifestation_coverage([]).share == 1.0
    unshown = [
        worlds.world_record("provenance", worlds.WORLD_RULE_PREDICATE, value="history fixes price")
    ]
    coverage = worlds.manifestation_coverage(unshown)
    assert coverage.share == 0.0
    assert coverage.missing == ("provenance",)


def test_a_criterion_with_branching_results_prints_no_ladder() -> None:
    """Partial by default: a criterion whose results branch has no ladder, and none is printed."""
    chain = [
        canon(worlds.world_record("grade", worlds.TYPE_PREDICATE, value=worlds.CRITERION)),
        canon(worlds.world_record("grade", worlds.COMPARATOR_PREDICATE, value="ordinal")),
        canon(worlds.world_record("third", worlds.PRECEDES_PREDICATE,
                                  object_ref="second", value="grade")),
        canon(worlds.world_record("second", worlds.PRECEDES_PREDICATE,
                                  object_ref="first", value="grade")),
    ]
    assert worlds.criterion_brief(chain) == "- grade: ordinal — third then second then first"

    branching = [
        *chain[:2],
        canon(worlds.world_record("third", worlds.PRECEDES_PREDICATE,
                                  object_ref="second", value="grade")),
        canon(worlds.world_record("third", worlds.PRECEDES_PREDICATE,
                                  object_ref="sideways", value="grade")),
    ]
    assert worlds.criterion_brief(branching) == "- grade: ordinal"


def test_a_world_that_declares_no_criterion_gets_no_brief() -> None:
    assert worlds.criterion_brief([]) is None


# --- the projection ---------------------------------------------------------------------------


def test_a_world_that_declares_nothing_projects_nothing() -> None:
    """Absence is free, and this is the assertion that makes it so rather than the intention."""
    ordinary = [flat("silas", "is_at", "the assay house"), edge("silas", "knows", "marta")]
    assert worlds.project(ordinary) == {}


def test_a_packet_with_no_world_records_is_byte_identical_to_before() -> None:
    """The additivity test `tests/test_context.py`'s summaries suite is the template for."""
    revision = one_scene_book()
    # `is_a` on purpose: it is the predicate a forged world uses most and the one an operator's
    # own seed already used, so it is the sharpest test of the additivity claim.
    ordinary = [flat("silas", "is_a", "a junior clerk")]
    packet = assemble(revision, "scene-2", plan_items=[PREMISE_ITEM], state_records=ordinary)
    assert packet.sections.get(HIDDEN, ()) == ()
    assert "silas is_a a junior clerk" in packet.render()
    assert "not yet disclosed" not in packet.render()


def test_a_reified_change_reaches_the_packet_as_one_sentence() -> None:
    """The blocker `plan/state-model-abilities.md` §2 names: five machine lines become English.

    Five records share one subject because a conjunction needs one occurrence identity. Handed to
    a writer unprojected they read as notation; the packet must carry the sentence and must not
    also carry its parts, which would be the same information twice at the generator's expense.
    """
    change = [
        canon(worlds.world_record("change_11", worlds.TYPE_PREDICATE, value=worlds.CHANGE)),
        canon(worlds.world_record("change_11", "actor", object_ref="elin")),
        canon(worlds.world_record("change_11", "precondition", object_ref="hurdle_7")),
        canon(worlds.world_record("change_11", "consumes", object_ref="walnut_stock",
                                  value="three boards")),
        canon(worlds.world_record("change_11", "effect", object_ref="claim_11")),
    ]
    projected = worlds.project(change)
    sentences = [text for text in projected.values() if text]
    assert len(sentences) == 1
    assert "done by elin" in sentences[0]
    assert "costs walnut_stock (three boards)" in sentences[0]

    revision = one_scene_book()
    packet = assemble(revision, "scene-2", plan_items=[PREMISE_ITEM], state_records=change)
    facts = packet.sections[FACTS]
    assert len(facts) == 1
    assert facts[0].text == sentences[0]


def test_a_node_with_a_restricted_satellite_is_never_folded() -> None:
    """A fact about who knows what, collapsed into a sentence written for everybody, leaks."""
    restricted = lc.StateRecord(
        record_id="change_12-auth",
        kind=lc.StateRecordKind.RELATIONSHIP,
        subject="change_12",
        predicate="authorized_by",
        object_ref="tempest_oath",
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=["arden"],
    )
    records = [
        canon(worlds.world_record("change_12", worlds.TYPE_PREDICATE, value=worlds.CHANGE)),
        canon(worlds.world_record("change_12", "actor", object_ref="arden")),
        restricted,
    ]
    projected = worlds.project(records)
    assert "" not in projected.values()


# --- the iceberg -------------------------------------------------------------------------------


def secret_world() -> list[lc.StateRecord]:
    return [
        canon(
            worlds.world_record(
                "token_older",
                worlds.CLAIM_CONTENT,
                value="the countdown was started by whoever the tide is aimed at",
            )
        ),
        canon(
            worlds.world_record(
                "token_older_reveal",
                worlds.DISCLOSED_TO,
                value=worlds.READER,
                object_ref="token_older",
                order_key="s07",
            )
        ),
    ]


def test_a_secret_is_carried_under_its_own_heading_and_never_as_a_fact() -> None:
    """The one thing an iceberg is made of, and the section that carries it.

    Two properties, and the second is the one that matters on the page: the claim reaches the
    generator, and it reaches it under an instruction not to state it.
    """
    revision = one_scene_book()
    packet = assemble(
        revision,
        "scene-2",
        plan_items=[PREMISE_ITEM],
        state_records=secret_world(),
        story_time_cutoff="s01",
    )
    assert [item.text for item in packet.sections[HIDDEN]] == [
        "the countdown was started by whoever the tide is aimed at"
    ]
    assert not [
        item for item in packet.sections[FACTS] if "countdown" in item.text
    ]
    rendered = packet.render()
    assert "the reader has not been told" in rendered
    assert "never put it on the page" in rendered


def test_a_disclosed_secret_stops_being_hidden_at_its_window() -> None:
    """A reveal changes disclosure, not past truth — so the claim moves sections, not stores."""
    records = secret_world()
    assert len(worlds.undisclosed_claims(records, at="s01")) == 1
    assert worlds.undisclosed_claims(records, at="s07") == ()
    assert worlds.undisclosed_claims(records, at="s09") == ()


def test_only_a_claim_that_asks_something_owes_a_reveal() -> None:
    """A secret and a mystery are both claims, and only one of them is a scheduled debt.

    The distinction was found by `test_a_clear_world_has_nothing_to_complain_about`: the first
    version of this vocabulary demanded a disclosure position for every claim, which turned a
    character's private secret into a reveal the book had to schedule. A secret stays hidden
    until the story wants it; a mystery that asks a question and never answers it is the promise
    the ledger can never pay.
    """
    secret = [
        canon(worlds.world_record("never_told", worlds.CLAIM_CONTENT, value="nobody finds out"))
    ]
    assert len(worlds.undisclosed_claims(secret)) == 1
    assert worlds.validate(secret) == ()

    mystery = [
        *secret,
        canon(
            worlds.world_record(
                "never_told", worlds.QUESTION_PREDICATE, value="who moved the seal"
            )
        ),
    ]
    assert any("no reveal scene" in complaint for complaint in worlds.validate(mystery))
    # The ordinal is what it owes — a *position* only exists for a scene this book has.
    scheduled = [
        *mystery,
        canon(worlds.world_record("never_told", worlds.REVEAL_SCENE, value=41)),
    ]
    assert worlds.validate(scheduled) == ()
    assert len(worlds.undisclosed_claims(scheduled, at="s8")) == 1


def test_a_false_belief_is_never_carried_as_a_hidden_truth() -> None:
    """The heading says *true*. A character's error under it instructs the writer to honour it."""
    wrong = [
        canon(worlds.world_record("silas_belief", worlds.CLAIM_CONTENT,
                                  value="the ledger only counts coin")),
        canon(worlds.world_record("silas_belief", worlds.CLAIM_FALSE, value=True)),
        canon(worlds.world_record("silas", worlds.BELIEVES, object_ref="silas_belief")),
    ]
    assert worlds.undisclosed_claims(wrong) == ()
    packet = assemble(
        one_scene_book(), "scene-2", plan_items=[PREMISE_ITEM], state_records=wrong
    )
    assert packet.sections.get(HIDDEN, ()) == ()
    texts = [item.text for item in packet.sections[FACTS]]
    assert texts == ["silas believes, wrongly: the ledger only counts coin"]


def test_pov_visibility_is_not_how_a_secret_is_carried() -> None:
    """§0.1 row 2, demonstrated rather than cited.

    A claim written into `pov_visibility` reaches **no** packet at all when no POV is named,
    which is the opposite of what a secret the writer must honour is for. The hidden section is
    the answer because it is orthogonal to access control rather than a reuse of it.
    """
    overloaded = lc.StateRecord(
        record_id="rec-overloaded",
        kind=lc.StateRecordKind.ASSERTION,
        subject="token_older",
        predicate=worlds.CLAIM_CONTENT,
        value="the countdown was started by whoever the tide is aimed at",
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=["nobody"],
    )
    packet = assemble(
        one_scene_book(), "scene-2", plan_items=[PREMISE_ITEM], state_records=[overloaded]
    )
    assert packet.sections.get(HIDDEN, ()) == ()
    assert packet.sections[FACTS] == ()
    assert any("not visible to POV" in omission.reason for omission in packet.omitted)


def test_a_hidden_fact_that_will_not_fit_is_recorded_rather_than_dropped_quietly() -> None:
    """A scene drafted against a secret it was not given is wrong in a way no repair reaches."""
    long_secret = canon(
        worlds.world_record("big", worlds.CLAIM_CONTENT, value="answer " * 400)
    )
    packet = assemble(
        one_scene_book(),
        "scene-2",
        plan_items=[PREMISE_ITEM],
        state_records=[long_secret],
        token_budget=1700,
        reserved_output=1500,
    )
    assert packet.sections[HIDDEN] == ()
    assert any(omission.reason == "budget: hidden" for omission in packet.omitted)


# --- the second extractor family ----------------------------------------------------------------


GRAPH_DECLARATION = {
    "label": "SYSTEM",
    "edges": [
        {"phrase": "is bonded to", "predicate": "bonded_with"},
        {"phrase": "now holds", "predicate": "possessed_by"},
        {"phrase": "is recognised as", "predicate": "recognized_by"},
    ],
}


def declared_book(order_key: str = "s01") -> list[lc.StateRecord]:
    """A book that declares a graph line and one subject, attested at `order_key`."""
    node = one_scene_book().node("scene-1")
    assert node.content is not None
    return [
        lc.StateRecord(
            record_id="rec-graph-line",
            kind=lc.StateRecordKind.WORLD_RULE,
            subject="book",
            predicate=worlds.GRAPH_LINE_PREDICATE,
            value=GRAPH_DECLARATION,
            authority=lc.StateAuthority.AUTHOR_LOCKED,
        ),
        lc.StateRecord(
            record_id="rec-silas",
            kind=lc.StateRecordKind.ASSERTION,
            subject="silas",
            predicate="is_a",
            value="a junior clerk",
            story_position=lc.StoryPosition(order_key=order_key),
            authority=lc.StateAuthority.ACCEPTED_CANON,
            evidence=[
                lc.EvidenceSpan(
                    source=lc.ResourceRef(
                        project_id=PROJECT_ID,
                        book_id=BOOK_ID,
                        branch_id=BRANCH_ID,
                        logical_id="scene-1",
                        kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                    ),
                    start=0,
                    end=3,
                    content_sha256=content_hash(node.content[0:3]),
                )
            ],
        ),
    ]


@pytest.mark.parametrize(
    "label,phrase,predicate",
    [
        ("SYSTEM", "is bonded to", "bonded_with"),
        ("NOTICE", "now holds", "possessed_by"),
        ("LEDGER", "owes a debt to", "owes"),
    ],
)
def test_a_declared_graph_line_round_trips(label: str, phrase: str, predicate: str) -> None:
    """Fill the template, parse it back, get the edge — the property the status line has.

    The template and the pattern derive from one declaration, which is what keeps the
    instruction and the parser the same statement. Asserted over any declaration rather than
    over the one that happened to be written down.
    """
    line = extraction.parse_graph_line(
        {"label": label, "edges": [{"phrase": phrase, "predicate": predicate}]}
    )
    rendered = line.render("Silas Marrow", phrase, "Ember Fox")
    match = line.pattern.search(rendered)
    assert match is not None
    assert match.group("subject") == "Silas Marrow"
    assert match.group("phrase") == phrase
    assert match.group("object") == "Ember Fox"
    assert line.label in line.template


def test_a_longer_phrase_wins_over_a_shorter_one_inside_it() -> None:
    """`holds` inside `no longer holds` must not decide the predicate."""
    line = extraction.parse_graph_line(
        {
            "label": "SYSTEM",
            "edges": [
                {"phrase": "holds", "predicate": "possessed_by"},
                {"phrase": "no longer holds", "predicate": "lost"},
            ],
        }
    )
    match = line.pattern.search("[SYSTEM] Silas no longer holds the token")
    assert match is not None
    assert match.group("phrase") == "no longer holds"


def test_a_graph_line_that_is_a_paragraph_is_refused_and_degrades_to_absence() -> None:
    """The declaration the first forged world actually produced, kept runnable.

    Asked for a printed line form, one world returned a `label` of "one dry season in the Kettle
    Basin" and eight "phrases" that were clauses of a story. Well-formed JSON, accepted by every
    type check, and a parser that could never match a line any scene would print — the silent
    failure `MalformedSheet` exists to prevent, one family over.

    It degrades to **absence** rather than raising, because unlike a sheet there is no default
    waiting behind it: a book with no graph line is a legitimate and common state, so the cost
    is a lost capability rather than a book read in the wrong form. `cmd_new` says so; the draft
    path is never stalled by it.
    """
    paragraph = {
        "label": "one dry season in the Kettle Basin",
        "edges": [
            {"phrase": "the register writes a year beside a name", "predicate": "records"},
            {
                "phrase": "everyone under the cut line moves up one place",
                "predicate": "promotes",
            },
        ],
    }
    with pytest.raises(extraction.MalformedGraphLine, match="bracket tag"):
        extraction.parse_graph_line(paragraph)
    with pytest.raises(extraction.MalformedGraphLine, match="verb phrase"):
        extraction.parse_graph_line({"label": "SYSTEM", "edges": paragraph["edges"]})

    declared = [
        canon(worlds.world_record("book", worlds.GRAPH_LINE_PREDICATE, value=paragraph))
    ]
    assert extraction.graph_line_for(declared) is None
    fault = extraction.graph_line_fault(declared)
    assert fault is not None and "bracket tag" in fault
    # And nothing raises on the path a drafted scene takes.
    assert (
        extraction.extract_graph_facts(
            "[SYSTEM] Silas is bonded to Ember Fox",
            known=declared,
            project_id=PROJECT_ID,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            logical_id="scene-1",
            version_id="v1",
            order_key="s01",
        )
        == ()
    )


def test_a_book_that_declares_no_graph_line_extracts_no_edges() -> None:
    """Absence is free: the second family costs a book that never asked for it exactly nothing."""
    assert extraction.graph_line_for([]) is None
    assert (
        extraction.extract_graph_facts(
            "[SYSTEM] Silas is bonded to Ember Fox",
            known=[],
            project_id=PROJECT_ID,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            logical_id="scene-1",
            version_id="v1",
            order_key="s01",
        )
        == ()
    )


def test_the_graph_line_declaration_never_reaches_a_packet() -> None:
    """What configures the telling is not part of the told — the sheet's rule, applied again."""
    packet = assemble(
        one_scene_book(),
        "scene-2",
        plan_items=[PREMISE_ITEM],
        state_records=declared_book(),
    )
    assert not [item for item in packet.sections[FACTS] if "phrase" in item.text]
    assert not [omission for omission in packet.omitted if omission.item_id == "rec-graph-line"]


def test_a_page_minted_subject_arrives_proposed_and_reaches_no_packet() -> None:
    """Identity minting and factual promotion are separate decisions, and this is the first half."""
    known = declared_book()
    [minted] = extraction.extract_graph_facts(
        "[SYSTEM] Silas is bonded to Ember Fox",
        known=known,
        project_id=PROJECT_ID,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="scene-1",
        version_id="v1",
        order_key="s01",
    )
    assert minted.subject == "silas"
    assert minted.object_ref == "ember_fox"
    assert minted.predicate == "bonded_with"
    assert minted.authority is lc.StateAuthority.PROPOSED
    assert minted.predicate_registry_version == extraction.GRAPH_REGISTRY_VERSION

    packet = assemble(
        one_scene_book(), "scene-2", plan_items=[PREMISE_ITEM], state_records=[*known, minted]
    )
    assert not [item for item in packet.sections[FACTS] if "ember_fox" in item.text]


def test_repetition_does_not_promote_and_later_causal_reuse_does() -> None:
    """The rule §6 item 1 names, in the narrowest form a reader made of regexes can check."""
    known = declared_book()
    [proposal] = extraction.extract_graph_facts(
        "[SYSTEM] Silas is bonded to Ember Fox",
        known=known,
        project_id=PROJECT_ID,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="scene-1",
        version_id="v1",
        order_key="s01",
    )
    later = [*known, proposal]

    # Saying it again mints nothing and promotes nothing.
    repeated = extraction.extract_graph_facts(
        "[SYSTEM] Silas is bonded to Ember Fox",
        known=later,
        project_id=PROJECT_ID,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="scene-2",
        version_id="v2",
        order_key="s02",
    )
    assert repeated == ()
    assert extraction.promotions(later, repeated, order_key="s02") == ()

    # Using an endpoint again to do something else is the evidence that counts.
    reuse = extraction.extract_graph_facts(
        "[SYSTEM] Silas now holds the ash token",
        known=later,
        project_id=PROJECT_ID,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="scene-2",
        version_id="v2",
        order_key="s02",
    )
    assert len(reuse) == 1
    [promoted] = extraction.promotions(later, reuse, order_key="s02")
    assert promoted.subject == "silas"
    assert promoted.predicate == "bonded_with"
    assert promoted.object_ref == "ember_fox"
    assert promoted.authority is lc.StateAuthority.ACCEPTED_CANON
    assert promoted.record_id != proposal.record_id
    assert "promoted at s02" in (promoted.note or "")


def test_a_forged_world_does_not_look_like_an_authors_vocabulary() -> None:
    """A merge-interaction defect: neither side of it is wrong alone.

    `has_story_vocabulary` asks whether the book already carries order keys **somebody else**
    chose, and abstains from placing anything if so. An Architect's reveal positions are dated —
    but `architect.story_key` mints them in `beats_for`'s own width from the book's own scene
    count, which is what stage-0 §107.9.1 defect 10 was fixed to guarantee. Left out of
    `OWN_POSITION_VERSIONS` they would read as a foreign numbering, `stated_position` would
    abstain for the whole book, and §12 step 5 would extract nothing from any scene — the
    silence measured for the seeded-interiority case, arriving by a fourth door.
    """
    dated = lc.StateRecord(
        record_id="rec-reveal",
        kind=lc.StateRecordKind.RELATIONSHIP,
        subject="m_the_tide_reveal",
        predicate=worlds.DISCLOSED_TO,
        value=worlds.READER,
        object_ref="m_the_tide",
        story_position=lc.StoryPosition(order_key="s4"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        predicate_registry_version=worlds.REGISTRY_VERSION,
    )
    assert not extraction.has_story_vocabulary([dated])
    assert extraction.stated_position([dated], "s1") == "s1"

    # The second family's own readings are the same case.
    graph = lc.StateRecord(
        record_id="rec-edge",
        kind=lc.StateRecordKind.RELATIONSHIP,
        subject="silas",
        predicate="bonded_with",
        object_ref="ember_fox",
        story_position=lc.StoryPosition(order_key="s2"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        predicate_registry_version=extraction.GRAPH_REGISTRY_VERSION,
    )
    assert not extraction.has_story_vocabulary([graph])

    # And a dated record that declares nothing still counts as somebody else's, unchanged.
    authored = lc.StateRecord(
        record_id="rec-authored",
        kind=lc.StateRecordKind.ASSERTION,
        subject="silas",
        predicate="is_at",
        value="the assay house",
        story_position=lc.StoryPosition(order_key="s1"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    assert extraction.has_story_vocabulary([authored])
    assert extraction.stated_position([authored], "s1") is None


def test_extract_state_runs_both_families_from_one_call_site() -> None:
    """A graph reader wired into three of four call sites would work depending on the arm."""
    known = declared_book()
    revision = one_scene_book()
    node = revision.node("scene-1")
    records = extraction.extract_state(
        "[SYSTEM] Silas is bonded to Ember Fox",
        known=known,
        project_id=PROJECT_ID,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="scene-1",
        version_id=node_version_id(node),
    )
    assert [record.predicate for record in records] == ["bonded_with"]


# --- identity -----------------------------------------------------------------------------------


def test_a_world_record_is_content_addressed_on_its_edge() -> None:
    """Two edges from one subject under one predicate are two facts, and two ids."""
    first = worlds.world_record("ash", "trait", object_ref="keen_scent")
    second = worlds.world_record("ash", "trait", object_ref="night_sight")
    assert first.record_id != second.record_id
    assert first.record_id == worlds.world_record("ash", "trait", object_ref="keen_scent").record_id


def test_an_architect_id_addresses_the_brief_it_was_built_from() -> None:
    assert worlds.architect_id_for("a world of salvage law") == worlds.architect_id_for(
        "a world of salvage law"
    )
    assert worlds.architect_id_for("a") != worlds.architect_id_for("b")
    assert worlds.is_machine_author(worlds.machine_author(worlds.architect_id_for("x")))
    assert not worlds.is_machine_author(None)
    assert not worlds.is_machine_author("")


def test_a_world_record_defaults_to_a_proposal() -> None:
    """The rail is the default rather than something each call site has to remember."""
    assert worlds.world_record("x", "is_a", value="y").authority is lc.StateAuthority.PROPOSED


def test_the_validator_names_a_role_a_world_invented_for_itself() -> None:
    stray = [worlds.world_record("thing", worlds.ENTITY_ROLE_PREDICATE, value="artefact")]
    assert any("'artefact'" in complaint for complaint in worlds.validate(stray))
