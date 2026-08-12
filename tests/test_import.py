"""Getting a book into the store (§17 Stage 1's precondition).

Stage 1 is graded on "the mystery and litrpg fixture books regenerate from premise to
accepted six-scene draft autonomously". Before this module there was no code path anywhere
— not in `src`, not in the CLI, not in this suite — that put either book into a store: the
system was a closed loop with no entry, because `enqueue` requires a `--revision` and the
only thing that minted a revision id was committing one.

Two properties carry most of the weight here, and both are about *not* relaxing something:

* `Revision.from_contract`'s id assertion is the round-trip guarantee of a
  content-addressed store, and it must keep refusing the fixtures. Importing them is a
  different operation, not a loosened version of the same one.
* clearing scene prose is what makes a scene draftable, so the test that matters is not
  "content is None" but "`gate_draft` accepts a draft for every scene" — and its inverse,
  that a `--keep-content` import produces a book with nothing to draft.
"""

from __future__ import annotations

import dataclasses
import json

import litharness_contracts as lc
import pytest

from litharness.adapters import contracts_fixtures
from litharness.domain.draft import gate_draft
from litharness.domain.nodes import LockKind, NodeKind
from litharness.domain.patch import Veto
from litharness.domain.revision import Revision, import_manuscript
from tests.conftest import make_revision, meta

#: Long enough to clear `DraftPolicy.min_chars`, so a refusal means the gate refused the
#: *node*, not the length.
DRAFT = "The lamp guttered and the room went the colour of wet slate. " * 6


def load(fixture_id: str) -> lc.ManuscriptRevision:
    path = contracts_fixtures.fixture_manuscript(fixture_id)
    return lc.parse_artifact(
        lc.ManuscriptRevision, json.loads(path.read_text(encoding="utf-8"))
    )


def as_contract(revision: Revision) -> lc.ManuscriptRevision:
    return revision.to_contract(meta("manuscript_revision", "test-manuscript"))


# --- the two books Stage 1 is graded on ----------------------------------------------


@pytest.mark.parametrize("fixture_id", contracts_fixtures.FIXTURE_IDS)
def test_a_golden_fixture_imports_as_a_root_revision(fixture_id: str) -> None:
    imported = import_manuscript(load(fixture_id))

    assert imported.revision.parent_revision_id is None
    assert len(imported.revision.nodes) == 7
    assert len(imported.cleared) == 6
    assert imported.kept_locked == ()


@pytest.mark.parametrize("fixture_id", contracts_fixtures.FIXTURE_IDS)
def test_every_scene_is_draftable_after_import(fixture_id: str) -> None:
    """The point of the whole exercise. Six scenes per book, twelve across both."""
    imported = import_manuscript(load(fixture_id))

    scenes = [node for node in imported.revision.nodes if node.kind is NodeKind.SCENE]
    assert len(scenes) == 6
    for scene in scenes:
        outcome = gate_draft(imported.revision, scene.logical_id, DRAFT)
        assert outcome.accepted, (scene.logical_id, outcome.veto_kinds)


@pytest.mark.parametrize("fixture_id", contracts_fixtures.FIXTURE_IDS)
def test_keeping_the_content_yields_a_book_with_nothing_to_draft(fixture_id: str) -> None:
    """The inverse of the test above, and the reason clearing is the default rather than a
    convenience: an import that preserves the source prose looks like a book and cannot
    take a single draft job."""
    imported = import_manuscript(load(fixture_id), preserve_content=True)

    assert imported.cleared == ()
    scenes = [node for node in imported.revision.nodes if node.kind is NodeKind.SCENE]
    for scene in scenes:
        outcome = gate_draft(imported.revision, scene.logical_id, DRAFT)
        assert not outcome.accepted
        assert outcome.veto_kinds == (Veto.TARGET_HAS_NO_CONTENT,)


@pytest.mark.parametrize("fixture_id", contracts_fixtures.FIXTURE_IDS)
def test_structure_survives_the_import(fixture_id: str) -> None:
    """Titles, ordering and parentage are the frame generation happens inside; only the
    prose is regenerated."""
    source = load(fixture_id)
    imported = import_manuscript(source)

    by_id = {node.logical_id: node for node in imported.revision.nodes}
    assert by_id["book"].kind is NodeKind.BOOK
    assert by_id["book"].position_key == "000"
    assert [node.logical_id for node in imported.revision.in_reading_order()] == [
        "book", "scene-1", "scene-2", "scene-3", "scene-4", "scene-5", "scene-6",
    ]
    for original in source.nodes:
        node = by_id[original.logical_id]
        assert node.title == original.title
        assert node.position_key == original.position_key
        assert node.parent_logical_id == original.parent_logical_id


# --- what is deliberately not relaxed --------------------------------------------------


@pytest.mark.parametrize("fixture_id", contracts_fixtures.FIXTURE_IDS)
def test_the_id_is_rebuilt_and_the_source_id_kept_as_provenance(fixture_id: str) -> None:
    """Contracts mints UUID5 ids; this package computes a sha256 content address. They
    differ by construction, which is why import rebuilds rather than asserts."""
    source = load(fixture_id)
    imported = import_manuscript(source)

    assert imported.source_revision_id == source.revision_id
    assert imported.revision.revision_id != source.revision_id
    assert len(imported.revision.revision_id) == 64  # a sha256 hex digest, not a UUID


@pytest.mark.parametrize("fixture_id", contracts_fixtures.FIXTURE_IDS)
def test_from_contract_still_refuses_the_fixtures(fixture_id: str) -> None:
    """The regression guard on the whole design. `from_contract`'s assertion is the
    corruption check for artifacts *this* system wrote, and the cheap way to make the
    fixtures load would have been to weaken it. If this test ever passes silently, that is
    what happened."""
    with pytest.raises(ValueError, match="does not match the serialized one"):
        Revision.from_contract(load(fixture_id))


def test_a_round_trip_of_our_own_artifact_still_holds() -> None:
    """The other half: what `from_contract` is *for* keeps working."""
    revision = make_revision()
    assert Revision.from_contract(as_contract(revision)).revision_id == revision.revision_id


@pytest.mark.parametrize("fixture_id", contracts_fixtures.FIXTURE_IDS)
def test_a_node_whose_hash_disagrees_with_its_text_is_refused(fixture_id: str) -> None:
    """The integrity check that actually does the work, and the one that catches a
    manuscript decoded with the wrong codec. Mutated in memory so the check is shown to be
    sensitive rather than merely present."""
    source = load(fixture_id)
    scene = next(node for node in source.nodes if node.content)
    tampered = dataclasses.replace(scene, content=(scene.content or "") + " And then nothing.")
    mutated = dataclasses.replace(
        source, nodes=[tampered if n.logical_id == scene.logical_id else n for n in source.nodes]
    )

    with pytest.raises(ValueError, match="content_sha256 does not match"):
        import_manuscript(mutated)


def test_a_non_root_manuscript_is_refused() -> None:
    """Its parent is not in this store, and `lineage` walks parents until it reaches one —
    so a re-parented import would produce a revision that fails `verify` the first time
    anyone asked for its history."""
    child = make_revision().replacing([])

    with pytest.raises(ValueError, match="not in this store"):
        import_manuscript(as_contract(child))


def test_a_content_locked_scene_is_not_cleared_and_is_reported() -> None:
    """`replace` bypasses `with_content`'s lock check, so the lock has to be honoured
    explicitly here. Reported rather than silently skipped: this scene cannot be drafted
    and an operator who is not told sees an import that 'worked'."""
    revision = make_revision()
    locked = dataclasses.replace(revision.node("scene-3"), lock=LockKind.CONTENT)
    source = dataclasses.replace(
        as_contract(revision.replacing([locked])), parent_revision_id=None
    )

    imported = import_manuscript(source)

    assert imported.kept_locked == ("scene-3",)
    assert "scene-3" not in imported.cleared
    assert imported.revision.node("scene-3").content is not None
    outcome = gate_draft(imported.revision, "scene-3", DRAFT)
    assert outcome.veto_kinds == (Veto.CONTENT_LOCKED,)


def test_canonicalization_leaves_the_litrpg_em_dashes_alone() -> None:
    """Every litrpg scene carries a U+2014, which is the material the CLI's encoding test
    is built on (`test_cli.py`). Canonicalization runs NFC over ingested text, so pin here
    that it is not the thing that would alter them."""
    imported = import_manuscript(load("litrpg"), preserve_content=True)

    for index in range(1, 7):
        assert "—" in (imported.revision.node(f"scene-{index}").content or "")


# --- finding the fixtures --------------------------------------------------------------


def test_a_missing_checkout_names_the_variable_that_fixes_it(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(contracts_fixtures, "_candidate_roots", lambda: [tmp_path])

    with pytest.raises(contracts_fixtures.FixturesUnavailable, match="LITHARNESS_CONTRACTS_ROOT"):
        contracts_fixtures.fixture_manuscript("mystery")


def test_an_unknown_fixture_lists_the_ones_that_exist() -> None:
    with pytest.raises(contracts_fixtures.FixturesUnavailable, match="mystery, litrpg"):
        contracts_fixtures.fixture_manuscript("thriller")


def test_a_directory_without_the_manuscript_is_not_a_checkout(monkeypatch, tmp_path) -> None:
    """Every link in the discovery chain is checked against the artifact, not the directory
    name — a path that exists but holds no manuscript is not the contracts checkout, and
    accepting it would fail three layers further down."""
    empty = tmp_path / "litharness-contracts"
    (empty / "fixtures" / "golden" / "mystery").mkdir(parents=True)
    real = contracts_fixtures.fixture_manuscript("mystery")
    monkeypatch.setattr(contracts_fixtures, "_candidate_roots", lambda: [empty, real.parents[3]])

    assert contracts_fixtures.fixture_manuscript("mystery") == real
