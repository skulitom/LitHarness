"""Default creative inputs, replay, author precedence and provenance through real CLI stages."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from litharness import cli
from litharness.application import concept, discovery, world_agent
from litharness.domain.invention import COMBINATIONS, InventionSeed, make_seed
from tests.test_concept import _discovery, _example, _scripted


def test_seed_deck_and_activity_extension_are_repeatable():
    seed = make_seed("deck", 7)
    assert seed == make_seed("deck", 7)
    ingredients = make_seed("deck", 7, actions=False)
    assert seed.brief.startswith(ingredients.brief)
    assert "First magical success:" in seed.brief
    assert "Further power growth:" in seed.brief
    assert len({make_seed("deck", i).brief for i in range(100)}) == 100
    for index in (-1, COMBINATIONS, True):
        with pytest.raises(ValueError):
            make_seed("deck", index)
    with pytest.raises(ValueError):
        make_seed("  ")


def test_seed_receipt_keeps_older_bytes_and_refuses_missing_or_corrupt_data():
    seed = replace(make_seed("retained"), version="older-version")
    assert InventionSeed.from_payload(seed.to_jsonable()) == seed
    for changed in (
        {},
        {**seed.to_jsonable(), "index": False},
        {**seed.to_jsonable(), "brief": "changed"},
    ):
        with pytest.raises(ValueError):
            InventionSeed.from_payload(changed)


def test_default_concepts_receive_fresh_seeds_and_preserve_json_output(
    tmp_path, monkeypatch, capsys
):
    labels = iter(("first-default", "second-default"))
    monkeypatch.setattr(
        cli, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex=next(labels)))
    )
    retained, requests = [], []
    for index in range(2):
        call = _scripted(_discovery(), _example(), {"edits": []})
        monkeypatch.setattr(cli, "_completion_call", call)
        out = tmp_path / str(index)
        assert (
            cli.main(
                [
                    "--database",
                    str(tmp_path / f"{index}.db"),
                    "concept",
                    "--out",
                    str(out),
                    "--json",
                ]
            )
            == cli.EXIT_OK
        )
        printed = json.loads(capsys.readouterr().out)
        seed = InventionSeed.from_payload(json.loads((out / "invention-seed.json").read_text()))
        stored = concept.Concept.from_text((out / "concept.json").read_text())
        assert stored.invention_seed == seed
        assert printed["invention_seed"] == seed.to_jsonable()
        assert seed.brief in call.seen[0].prompt
        assert all(seed.brief not in r.prompt for r in call.seen[1:])
        retained.append(seed)
        requests.append(call.seen[0])
    assert retained[0].seed != retained[1].seed
    assert requests[0].prompt != requests[1].prompt


def test_explicit_seed_replays_and_mechanical_retries_keep_one_invention(tmp_path, monkeypatch):
    requests = []
    for index in range(2):
        call = _scripted(_discovery(), None, _example(), {"edits": []})
        monkeypatch.setattr(cli, "_completion_call", call)
        out = tmp_path / str(index)
        assert (
            cli.main(
                [
                    "--database",
                    str(tmp_path / f"{index}.db"),
                    "concept",
                    "--seed",
                    "replay",
                    "--seed-index",
                    "4",
                    "--out",
                    str(out),
                ]
            )
            == cli.EXIT_OK
        )
        assert len([r for r in call.seen if r.profile == discovery.PROFILE]) == 1
        assert call.seen[1] == call.seen[2]
        requests.append(call.seen[0])
        stored = concept.Concept.from_text((out / "concept.json").read_text())
        assert stored.invention_seed == make_seed("replay", 4)
    assert requests[0] == requests[1]


def test_author_brief_wins_and_seed_receipt_never_becomes_an_editable_instruction(
    tmp_path, monkeypatch
):
    label = "SEED_LABEL_MUST_NOT_ENTER_PROMPTS"
    # The development model cannot replace the caller's receipt.
    answer = {**_example(), "invention_seed": {"brief": "MODEL_FORGED_SEED"}}
    call = _scripted(_discovery(), answer, {"edits": []})
    monkeypatch.setattr(cli, "_completion_call", call)
    out = tmp_path / "concept"
    brief = "A quiet science-fiction romance on a moon, with no battles or magic."
    assert (
        cli.main(
            [
                "--database",
                str(tmp_path / "book.db"),
                "concept",
                "--brief",
                brief,
                "--seed",
                label,
                "--out",
                str(out),
            ]
        )
        == cli.EXIT_OK
    )
    assert brief in call.seen[0].prompt
    assert "author's explicit brief takes precedence" in call.seen[0].prompt
    assert "Adapt or omit any conflicting ingredient" in call.seen[0].prompt
    assert all(label not in r.prompt and label not in (r.system or "") for r in call.seen)
    saved = concept.Concept.from_text((out / "concept.json").read_text())
    assert saved.author_brief == brief
    assert saved.invention_seed == make_seed(label)
    assert "MODEL_FORGED_SEED" not in saved.to_text()
    editable, protected = saved.precision_material()
    assert not any(k.startswith("invention_seed") for k in editable | protected)
    assert saved.with_precision_edits({"edits": []}).invention_seed == saved.invention_seed
    assert label not in world_agent.render_seed_request("A listing.", concept=saved).prompt
    assert "invention_seed" not in saved.for_outline()
    assert label not in json.dumps(saved.for_outline())
    assert saved.invention_seed.brief not in saved.render()
    assert concept.Concept.from_payload(_example()).invention_seed is None


def test_no_seed_is_an_explicit_control_and_clears_a_stale_receipt(tmp_path, monkeypatch):
    call = _scripted(_discovery(), _example(), {"edits": []})
    monkeypatch.setattr(cli, "_completion_call", call)
    out = tmp_path / "concept"
    out.mkdir()
    (out / "invention-seed.json").write_text(json.dumps(make_seed("old").to_jsonable()))
    assert (
        cli.main(
            [
                "--database",
                str(tmp_path / "book.db"),
                "concept",
                "--no-seed",
                "--out",
                str(out),
            ]
        )
        == cli.EXIT_OK
    )
    assert call.seen[0] == discovery.render_request("")
    assert json.loads((out / "invention-seed.json").read_text()) is None
    assert concept.Concept.from_text((out / "concept.json").read_text()).invention_seed is None


@pytest.mark.parametrize(
    "flags", [("--seed", " "), ("--seed-index", "-1"), ("--no-seed", "--seed-index", "1")]
)
def test_invalid_seed_refuses_before_opening_a_store(tmp_path, flags):
    db = tmp_path / "absent.db"
    assert cli.main(["--database", str(db), "concept", *flags]) == cli.EXIT_FAULT
    assert not db.exists()


def test_seed_is_retained_when_the_first_provider_call_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_completion_call", lambda *a, **k: (None, "provider unavailable"))
    out = tmp_path / "concept"
    assert (
        cli.main(
            [
                "--database",
                str(tmp_path / "book.db"),
                "concept",
                "--seed",
                "retry-me",
                "--out",
                str(out),
            ]
        )
        == cli.EXIT_FAULT
    )
    assert InventionSeed.from_payload(json.loads((out / "invention-seed.json").read_text())) == (
        make_seed("retry-me")
    )
    assert not (out / "concept.json").exists()
