"""Adversarial tests of scoped prerequisite proofs, independent of reader behavior."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import replace
from itertools import product
from pathlib import Path

import pytest

_RESEARCH = Path(__file__).resolve().parents[1] / "research/quality-measurement"
if str(_RESEARCH) not in sys.path:
    sys.path.insert(0, str(_RESEARCH))
probe = pytest.importorskip("prerequisite_certificate")
_SPEC = importlib.util.spec_from_file_location(
    "scoped_prerequisite_run", _RESEARCH / "scoped-prerequisite-20260927/run.py",
)
assert _SPEC and _SPEC.loader
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def _without(text: str, clause) -> str:
    return text[:clause.start] + text[clause.end:]


def test_solver_agrees_with_exhaustive_assignments_and_never_reverses_necessity() -> None:
    atoms = (("amber", "hatch"), ("ivory", "hatch"),
             ("coral", "lamp"), ("azure", "lamp"))
    # This oracle has no dependency on the parser, solver, proof or constructor internals.
    for swapped, observed in product((False, True), product((None, False, True), repeat=4)):
        required = (3, 2) if swapped else (2, 3)
        rules = [
            f"During trial zero, the {atoms[i][0]} hatch is open only while "
            f"the {atoms[required[i]][0]} lamp is lit."
            for i in range(2)
        ]
        facts = []
        for (name, kind), value in zip(atoms, observed, strict=True):
            if value is None:
                continue
            state = ("open" if value else "shut") if kind == "hatch" else (
                "lit" if value else "dark"
            )
            facts.append(f"At noon during trial zero, the {name} {kind} was {state}.")
        possible = [assignment for assignment in product((False, True), repeat=4) if (
            all(value is None or assignment[i] == value for i, value in enumerate(observed))
            and all(not assignment[i] or assignment[required[i]] for i in range(2))
        )]
        proof = probe.solve("\n".join((*rules, *facts)))
        assert proof.consistent == bool(possible)
        if proof.consistent:
            witness = tuple(proof.assignment.get(f"zero/noon/{kind}.{name}", False)
                            for name, kind in atoms)
            assert witness in possible


@pytest.mark.parametrize("bundle", probe.fixture_bundles(), ids=lambda bundle: bundle.identity[:8])
def test_each_constructed_contrast_has_a_minimal_proof_and_equal_surface_features(bundle) -> None:
    assert probe.solve(bundle.original).consistent
    assert probe.solve(bundle.control).consistent
    assert not probe.solve(bundle.damaged).consistent
    core = [clause for clause in bundle.contradiction.clauses
            if clause.identity in bundle.contradiction.core]
    assert len(core) == 3
    statements = [bundle.damaged[clause.start:clause.end] for clause in core]
    assert not probe.solve("\n".join(statements)).consistent
    for index in range(len(statements)):
        assert probe.solve("\n".join(statements[:index] + statements[index + 1:])).consistent
    assert probe.surface(bundle.damaged) == probe.surface(bundle.control)
    assert probe.token_bag(bundle.damaged) == probe.token_bag(bundle.control)
    assert bundle.damage_edit[0] * 10 // len(bundle.original) == (
        bundle.control_edit[0] * 10 // len(bundle.original)
    )
    assert len(bundle.damaged) == len(bundle.control) == len(bundle.original)
    assert bundle.manifest()["logic_certified"]
    assert not bundle.manifest()["ecological_admission"]
    assert not bundle.manifest()["eligible_for_model_run"]


@pytest.mark.parametrize("replacement", ("At dusk during trial zero", "At noon during trial one"))
def test_other_instants_and_trials_cannot_supply_the_missing_prerequisite(replacement) -> None:
    bundle = probe.construct(probe.fixture())
    original = "At noon during trial zero, the coral lamp was dark."
    changed = bundle.damaged.replace(original, replacement + ", the coral lamp was dark.")
    proof = probe.solve(changed)
    assert proof.consistent
    assert proof.assignment["zero/noon/lamp.coral"] is True
    source = bundle.original.replace(original, replacement + ", the coral lamp was dark.")
    with pytest.raises(probe.Refused, match="one_proven_contradiction"):
        probe.construct(source)


def test_removing_the_rule_changes_contradiction_to_an_unknown_consistent_case() -> None:
    bundle = probe.construct(probe.fixture())
    rule = next(clause for clause in bundle.contradiction.clauses
                if clause.kind == "rule" and clause.identity in bundle.contradiction.core)
    assert probe.solve(_without(bundle.damaged, rule)).consistent


def test_control_needs_an_explicit_satisfied_prerequisite_not_just_no_found_conflict() -> None:
    text = probe.fixture().replace("At noon during trial zero, the azure lamp was lit.", "")
    with pytest.raises(probe.Refused, match="control_prerequisite_not_explicitly_satisfied"):
        probe.construct(text)


def test_inconsistent_original_and_ambiguous_proof_evidence_are_refused() -> None:
    bundle = probe.construct(probe.fixture())
    with pytest.raises(probe.Refused, match="source_already_inconsistent"):
        probe.construct(bundle.damaged)
    rule = "During trial zero, the amber hatch is open only while the coral lamp is lit."
    with pytest.raises(probe.Refused, match="proof_clause_not_unique"):
        probe.construct(bundle.original + "\n" + rule)


@pytest.mark.parametrize("extra", (
    'She said, "The hatch was open."',
    "It might have opened.",
    "The rule was false.",
    "The amber hatch was not shut.",
    "At noon during trial zero, the amber lamp was lit.",
    "At noon during trial zero, the coral lamp was open.",
    "An unrelated piece of narration.",
    "The rule has an exception",
))
def test_arbitrary_narration_or_an_exception_cannot_be_dropped_to_get_a_certificate(extra) -> None:
    with pytest.raises(probe.Refused):
        probe.construct(probe.fixture() + "\n" + extra)


def test_quoted_premises_are_not_direct_assertions() -> None:
    text = probe.fixture()
    first = text.splitlines()[0]
    with pytest.raises(probe.Refused, match="unsupported_clause"):
        probe.solve(text.replace(first, f'"{first}"'))


def test_an_opening_event_precondition_does_not_prove_an_open_state_invariant() -> None:
    # The lamp might go dark AFTER opening. That event-only rule is not this grammar's
    # ongoing state restriction, so the parser must not quietly map both to one implication.
    with pytest.raises(probe.Refused, match="unsupported_clause"):
        probe.solve(probe.fixture().replace("hatch is open only while", "hatch opens only while"))


def test_forged_variants_spans_or_proofs_cannot_issue_a_manifest_or_public_packet() -> None:
    original = probe.construct(probe.fixture())
    for forged in (
        replace(original, damaged=original.control, control=original.damaged),
        replace(original, damage_edit=(0, 4)),
        replace(original, contradiction=replace(original.contradiction, consistent=True)),
    ):
        with pytest.raises(probe.Refused, match="certificate_does_not_reproduce"):
            forged.manifest()
        with pytest.raises(probe.Refused, match="certificate_does_not_reproduce"):
            probe.packets((forged,))


def test_public_packets_are_complete_and_hide_proofs_conditions_and_sibling_groups() -> None:
    bundles = probe.fixture_bundles()
    public, private = probe.packets(bundles)
    assert len(public) == 3 * len(bundles)
    assert all(set(packet) == {"presentation_id", "text"} for packet in public)
    assert "certificate_scope" not in json.dumps(public)
    lookup = {packet["presentation_id"]: packet["text"] for packet in public}
    for bundle in bundles:
        keys = private[bundle.identity]
        assert {lookup[key["presentation_id"]] for key in keys["variants"]} == {
            bundle.original, bundle.damaged, bundle.control,
        }
        for span in keys["core"]:
            assert probe.digest(bundle.damaged[span["start"]:span["end"]]) == span["sha256"]


def test_both_edit_roles_are_balanced_over_hatch_identity_and_observation_order() -> None:
    damaged, control = [], []
    for bundle in probe.fixture_bundles():
        clauses = probe.parse(bundle.original)
        damaged.append(next(clause.subject for clause in clauses
                            if clause.value_start == bundle.damage_edit[0]))
        control.append(next(clause.subject for clause in clauses
                            if clause.value_start == bundle.control_edit[0]))
    assert sorted(damaged) == sorted(control)
    assert set(damaged) == {"hatch.amber", "hatch.ivory"}


def test_empty_oversized_and_incomplete_sources_are_refused() -> None:
    for text in ("", " " * 100_001, "No complete assertion", "x" * 100_000):
        with pytest.raises(probe.Refused):
            probe.solve(text)


@pytest.fixture
def source_book(tmp_path):
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.nodes import Node, NodeKind
    from litharness.domain.revision import build_revision
    from tests.conftest import BOOK_ID, BRANCH_ID

    database = tmp_path / "book.db"
    revision = build_revision(BOOK_ID, BRANCH_ID, [
        Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
        Node.text_node(logical_id="scene", kind=NodeKind.SCENE, position_key="010",
                       parent_logical_id="book", content="The lantern flickered in the wind."),
    ])
    with SqliteStore.open(database) as store:
        store.commit_revision(revision, created_at="2026-09-27T00:00:00Z")
    return database


def test_natural_source_is_unchanged_and_shared_loader_only_receives_backup(
    source_book, tmp_path, monkeypatch,
) -> None:
    original = source_book.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    loader = runner.corpus_io.generated_scenes
    received = []

    def checked_loader(path, **kwargs):
        assert path == out / "source.db" and path != source_book
        received.append(path)
        return loader(path, **kwargs)

    monkeypatch.setattr(runner.corpus_io, "generated_scenes", checked_loader)
    result = runner.natural_boundary(source_book, out)
    assert received == [out / "source.db"]
    assert source_book.read_bytes() == original
    assert result["original_sha256_before"] == result["original_sha256_after"]
    assert result["scenes"]
    assert all(scene["disposition"] == "unsupported_source" for scene in result["scenes"])
    private = json.loads((out / "natural-scenes.private.json").read_text(encoding="utf-8"))
    encoded = json.dumps(result)
    assert all(unit["text"] not in encoded for unit in private)


def test_missing_or_lagging_source_is_never_created_or_migrated(source_book, tmp_path) -> None:
    from litharness.adapters.sqlite_store import MigrationsPending

    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        runner.natural_boundary(missing, tmp_path)
    assert not missing.exists()
    with closing(sqlite3.connect(source_book)) as connection:
        connection.execute("DELETE FROM schema_migrations WHERE name = "
                           "(SELECT max(name) FROM schema_migrations)")
        connection.commit()
    before = source_book.read_bytes()
    with pytest.raises(MigrationsPending):
        runner.natural_boundary(source_book, tmp_path)
    assert source_book.read_bytes() == before
    assert not (tmp_path / "source.db").exists()


def test_wrong_revision_is_refused_before_scene_export(source_book, tmp_path, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("an unselected source reached export")

    monkeypatch.setattr(runner.corpus_io, "generated_scenes", forbidden)
    with pytest.raises(ValueError, match="differs from the runbook"):
        runner.natural_boundary(source_book, tmp_path, expected_revision="wrong")


def test_packet_and_backup_outputs_never_overwrite_existing_work(source_book, tmp_path) -> None:
    target = tmp_path / "report.json"
    runner.write(target, {"preserve": True})
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        runner.write(target, {"preserve": False})
    assert target.read_bytes() == before
    snapshot = tmp_path / "source.db"
    snapshot.write_bytes(b"preserve existing snapshot")
    with pytest.raises(FileExistsError):
        runner.natural_boundary(source_book, tmp_path)
    assert snapshot.read_bytes() == b"preserve existing snapshot"
