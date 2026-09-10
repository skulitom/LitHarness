"""Default creative inputs, replay, author precedence and provenance through real CLI stages."""

import base64
import json
from dataclasses import replace

import pytest

from litharness import cli
from litharness.application import concept, discovery, world_agent
from litharness.domain.invention import (
    COMBINATIONS,
    LEGACY_VERSION,
    PREFIX_BITS,
    PREFIX_VERSION,
    VERSION,
    InventionSeed,
    make_seed,
)
from tests.test_concept import _discovery, _example, _scripted


def test_seed_deck_and_activity_extension_are_repeatable():
    seed = make_seed("deck", 7, version=LEGACY_VERSION)
    assert seed == make_seed("deck", 7, version=LEGACY_VERSION)
    ingredients = make_seed("deck", 7, actions=False, version=LEGACY_VERSION)
    assert seed.brief.startswith(ingredients.brief)
    assert "First magical success:" in seed.brief
    assert "Further power growth:" in seed.brief
    assert len({make_seed("deck", i, version=LEGACY_VERSION).brief for i in range(100)}) == 100
    for index in (-1, COMBINATIONS, True):
        with pytest.raises(ValueError):
            make_seed("deck", index)
    with pytest.raises(ValueError):
        make_seed("  ")


def test_world_seed_extends_the_same_activity_and_keeps_legacy_replay():
    label = "83a9b641ef6d40ba95e9fb74ccd351a2"
    old = make_seed(label, version=LEGACY_VERSION)
    # Captured before v2 in automatic-seeding-20260910/seeds/actions-0.json.
    assert old.to_jsonable()["brief_sha256"] == (
        "7d0c451f231b7e926592f53e91bac556935b1c861353736fee6c52079ee3fb34"
    )
    current = make_seed(label, version=VERSION)
    assert old.version == LEGACY_VERSION
    assert current.version == VERSION
    assert current.brief.startswith(old.brief + "\nConcrete world starting points:")
    assert current.mode == "actions-world"
    assert "inhabited destinations through these conditions" in current.brief
    assert "Concrete world starting points:" not in old.brief
    assert make_seed(label, actions=False, version=VERSION).mode == "ingredients-world"
    next_world = make_seed(label, 1, version=VERSION)
    assert next_world.brief.split("Concrete world starting points:")[1] != (
        current.brief.split("Concrete world starting points:")[1]
    )
    with pytest.raises(ValueError, match="Unknown invention seed version"):
        make_seed(label, version="invention-seed.v999")


def test_base64_prefix_encodes_the_integer_and_changes_only_the_system_prefix():
    for bits in (PREFIX_BITS, 8192):
        number = (1 << (bits - 1)) + 731
        seed = make_seed(str(number))
        assert seed.version == PREFIX_VERSION
        assert seed.mode == "base64-prefix"
        decoded = base64.b64decode(seed.brief, validate=True)
        assert len(decoded) == bits // 8
        assert int.from_bytes(decoded, "big") == number
        control = discovery.render_request("The author's own story.")
        prefixed = discovery.render_request("The author's own story.", seed=seed)
        assert prefixed == replace(control, system=seed.brief + "\n\n" + control.system)
        assert prefixed.effective_system.startswith(seed.brief + "\n\n")
    named = make_seed("replay-label", 3)
    assert named == make_seed("replay-label", 3)
    assert named != make_seed("replay-label", 4)


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
    numbers = iter(((1 << (PREFIX_BITS - 1)) + 7, (1 << (PREFIX_BITS - 1)) + 101))
    def draw(bits):
        assert bits == PREFIX_BITS
        return next(numbers)
    monkeypatch.setattr(cli.secrets, "randbits", draw)
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
        assert seed.version == PREFIX_VERSION
        stored = concept.Concept.from_text((out / "concept.json").read_text())
        assert stored.invention_seed == seed
        assert printed["invention_seed"] == seed.to_jsonable()
        assert call.seen[0].system.startswith(seed.brief + "\n\n")
        assert all(seed.brief not in r.effective_system + r.prompt for r in call.seen[1:])
        retained.append(seed)
        requests.append(call.seen[0])
    assert retained[0].seed != retained[1].seed
    assert requests[0].system != requests[1].system
    assert requests[0].prompt == requests[1].prompt


@pytest.mark.parametrize("version", [LEGACY_VERSION, VERSION, PREFIX_VERSION])
def test_explicit_seed_replays_and_mechanical_retries_keep_one_invention(
    tmp_path, monkeypatch, version
):
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
                    "--seed-version",
                    version,
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
        assert stored.invention_seed == make_seed("replay", 4, version=version)
    assert requests[0] == requests[1]


@pytest.mark.parametrize("version", [LEGACY_VERSION, VERSION, PREFIX_VERSION])
def test_author_brief_wins_and_seed_receipt_never_becomes_an_editable_instruction(
    tmp_path, monkeypatch, version
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
                "--seed-version",
                version,
                "--out",
                str(out),
            ]
        )
        == cli.EXIT_OK
    )
    assert brief in call.seen[0].prompt
    if version != PREFIX_VERSION:
        assert "author's explicit brief takes precedence" in call.seen[0].prompt
        assert "Adapt or omit any conflicting ingredient" in call.seen[0].prompt
    else:
        assert "Creative starting points" not in call.seen[0].prompt
    assert all(label not in r.prompt and label not in (r.system or "") for r in call.seen)
    saved = concept.Concept.from_text((out / "concept.json").read_text())
    assert saved.author_brief == brief
    assert saved.invention_seed == make_seed(label, version=version)
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
    "flags", [
        ("--seed", " "), ("--seed-index", "-1"), ("--no-seed", "--seed-index", "1"),
        ("--no-seed", "--seed-version", LEGACY_VERSION),
    ]
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
