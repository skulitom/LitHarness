"""Evidence challenges cannot manufacture semantic admission from a quotation hit."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.promises import PROMISE_PAID, Promise
from litharness.domain.revision import build_revision
from litharness.domain.text import content_hash


@pytest.fixture
def challenge(monkeypatch):
    root = Path(__file__).resolve().parents[1] / "research/quality-measurement"
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "promise_challenge_test", root / "promise_payoff_challenge.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def answer(*quotes):
    return {"candidates": [{"quotes": list(quotes), "connection": "An unverified hypothesis."}]}


def test_exact_citation_is_not_an_entailment_or_admission(challenge):
    task = challenge.fixture_tasks()[0]
    located = challenge.locate(task, answer(task["expected"]))
    assert located[0]["located"]
    assert challenge.control_passed(task, located)
    assert set(located[0]) == {"located", "spans", "problems", "connection_sha256"}
    assert task["expected"] not in json.dumps(located)


@pytest.mark.parametrize("fault", ["invented", "ambiguous", "earlier", "mixed"])
def test_entire_chain_is_invalid_when_any_anchor_fails(challenge, fault):
    task = challenge.fixture_tasks()[0]
    quote = task["expected"]
    if fault == "invented":
        result = challenge.locate(task, answer("This never appears in the book."))
    elif fault == "ambiguous":
        task["passage"] += "\n" + quote
        result = challenge.locate(task, answer(quote))
    elif fault == "earlier":
        result = challenge.locate(task, answer(task["opening"]))
    else:
        result = challenge.locate(task, answer(quote, "Invented second link."))
    assert not result[0]["located"]
    assert not challenge.control_passed(task, result)


def test_synthetic_controls_can_fail_in_both_directions(challenge):
    for task in challenge.fixture_tasks():
        correct = challenge.locate(task, answer(task["expected"])) if task["expected"] else []
        assert challenge.control_passed(task, correct)
        wrong = [] if task["expected"] else challenge.locate(task, answer(task["passage"][-20:]))
        assert not challenge.control_passed(task, wrong)


def test_request_does_not_reveal_private_condition_or_expected_evidence(challenge):
    task = challenge.fixture_tasks()[0]
    task.update(condition="secret_condition", item_id="secret_id", expected="hidden_gold")
    req = challenge.request(task)
    text = req.prompt + req.effective_system
    assert all(value not in text for value in ("secret_condition", "secret_id", "hidden_gold"))
    assert not req.allowed_tools
    assert req.schema == challenge.SCHEMA
    assert req.model == challenge.MODEL
    assert "connection" in text


def source_book(challenge, tmp_path):
    from promise_payoff_builder import build_from_database

    opening = "Rook promised to return the key."
    payment = "Rook returned the bronze key."
    contents = [
        opening + "\n\n" + "The road lay silent. " * 100,
        payment + "\n\nSnow covered the narrow road.\n\nRain crossed the silent yard.",
        "Afterwards the key changed hands again.",
    ]
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="000010")]
    nodes += [
        Node.text_node(f"s{i}", NodeKind.SCENE, f"{i:05}0", text, parent_logical_id="book")
        for i, text in enumerate(contents, 1)
    ]
    revision = build_revision("test", "main", tuple(nodes))
    promise = Promise(
        promise_id="prm-key",
        subject="key",
        description="return key",
        opened_at_key="s000001",
        due_key="s000002",
        opened_by_revision=revision.revision_id,
        status=PROMISE_PAID,
        paid_at_key="s000002",
        paid_by_revision=revision.revision_id,
        opened_logical_id="s1",
        opened_start=0,
        opened_end=len(opening),
        opened_content_hash=content_hash(contents[0]),
        paid_logical_id="s2",
        paid_start=0,
        paid_end=len(payment),
        paid_content_hash=content_hash(contents[1]),
    )
    with SqliteStore.open(tmp_path / "book.db") as store:
        store.commit_revision(revision, created_at="2026-09-22T00:00:00Z")
        store.record_promise("test", "main", promise)
    build_from_database(tmp_path / "book.db", tmp_path / "construction", source_group="test-world")
    return tmp_path / "construction", contents, payment


def test_full_book_search_preserves_suffix_and_maps_each_deletion_exactly(challenge, tmp_path):
    source, contents, payment = source_book(challenge, tmp_path)
    tasks = challenge.make_tasks(source)
    book = [t for t in tasks if "control" not in t]
    assert len(book) == 6
    variants = {t["condition"]: t for t in book if t["task"] == "fulfilment"}
    full = "\n\n".join(contents)
    assert variants["clean"]["passage"] == full
    assert all(contents[-1] in t["passage"] for t in book)
    assert payment not in variants["payment"]["passage"]
    assert payment in variants["control"]["passage"]
    assert variants["whitespace"]["passage"].split() == full.split()
    for task in book:
        if task["task"] == "dependency":
            start, end = task["removal_span"]
            assert full[start:end] == task["removed"]
            assert variants[task["condition"]]["passage"] == full[:start] + full[end:]
    assert tasks == challenge.make_tasks(source)
    assert len({t["task_id"] for t in tasks}) == len(tasks)


@pytest.mark.parametrize("name", ["keys.private.json", "source.db", "packets.public.json"])
def test_changed_construction_is_rejected(challenge, tmp_path, name):
    source, _, _ = source_book(challenge, tmp_path)
    with (source / name).open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="Changed"):
        challenge.make_tasks(source)


def test_each_budget_stops_dispatch_at_ceiling(challenge):
    assert not challenge.stopped(0, 0, 0, 0)
    assert challenge.stopped(27, 0, 0, 0)
    assert challenge.stopped(0, 1_600_000, 0, 0)
    assert challenge.stopped(0, 0, 8, 0)
    assert challenge.stopped(0, 0, 0, 3600)


def test_empty_search_cannot_certify_absence_or_harmlessness(challenge, tmp_path, monkeypatch):
    from litharness.domain.generation import CompletionResult

    local, here = tmp_path / "local", tmp_path / "report"
    local.mkdir()
    here.mkdir()
    task = challenge.fixture_tasks()[0] | {
        "task_id": "test", "item_id": "book-item", "condition": "clean",
    }
    monkeypatch.setattr(challenge, "LOCAL", local)
    monkeypatch.setattr(challenge, "HERE", here)
    monkeypatch.setattr(challenge, "verify", dict)
    monkeypatch.setattr(challenge, "write_claim", lambda status: None)
    challenge.write_json(local / "tasks.private.json", [task])
    challenge.write_json(local / "run.json", {})
    result = CompletionResult(
        text='{"candidates":[]}', provider="fake", model="fake", parsed={"candidates": []}
    )
    rows = [
        {"task_id": "isolation", "result": asdict(replace(result, text="NONE"))},
        {
            "task_id": "test",
            "request_sha256": challenge.payload_digest(asdict(challenge.request(task))),
            "result": asdict(result),
        },
    ]
    (local / "raw.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    challenge.analyse()
    report = json.loads((here / "observations.json").read_text())
    assert report["complete"] and report["isolation_passed"]
    assert not report["absence_certified"] and not report["semantic_admission"]
    assert not report["production_authority"]
    assert report["controls_passed"] == 0
    assert report["items"][0]["disposition"] == "semantic_review_required_no_admission"
