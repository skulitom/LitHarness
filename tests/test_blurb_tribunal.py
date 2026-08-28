"""blurb_tribunal's frozen bytes and registered definitions, checked without calls.

What this file pins: the asks and schemas are the registered bytes (detection phrasing with
an explicit empty-list permission; a defend schema whose 0 pairs only with an empty quote),
the strict one-shape parsing on both malformed defend pairings, the survival logic (a valid
defense kills, a fabricated one does not and is counted), a returned flag that does not
locate in the target listing being dropped and counted, dedupe across draws with draw
support kept on the row, the per-target floor rule surviving as an inspectable signature, the
prose-firewall row shapes for ours versus market targets, and the dry-run's exact stage-1 /
bounded stage-2 arithmetic. What it does not establish: anything about any model's flagging —
no call happens here, and nothing under `derived/`, `results/` or `corpora/` is read or
written.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent.parent / "research" / "quality-measurement"
if str(_HERE) not in sys.path:  # house pattern; conftest inserts it too, this is defensive
    sys.path.insert(0, str(_HERE))

blurb_shelf = pytest.importorskip(
    "blurb_shelf",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
blurb_tribunal = pytest.importorskip(
    "blurb_tribunal",
    reason="research module; imported by path, skipped where research/ is unavailable",
)

TARGET_LISTING = "the ward held through the gate and his mana was a patch of notes."

DRAWS = [
    ["patch of notes", "wholly absent phrase"],
    ["patch of notes"],
    ["patch of notes", "ward held"],
    [],
]


def _row(index: int, words: int) -> dict[str, object]:
    listing = " ".join(f"w{index}t{token}" for token in range(words))
    return {
        "title": f"Title {index}",
        "listing": f"{listing}.",
        "followers": 1000 - index,
        "source": f"high{index}",
    }


def _references() -> list[dict[str, object]]:
    refs = [_row(100 + i, 41) for i in range(blurb_tribunal.N_REFERENCES)]
    refs[1]["listing"] = "a construction that works the same way appears here."
    return refs


DEFENSES = {
    "patch of notes": {"parallel": "works the same way", "from_listing": 2},
    "ward held": {"parallel": "never written anywhere at all", "from_listing": 1},
}


# ------------------------------------------------------------------------- the frozen bytes


def test_the_frozen_bytes_are_the_registered_ones() -> None:
    assert blurb_tribunal.SYSTEM == blurb_shelf.SYSTEM
    assert "Quote every phrase in the listing under reading" in blurb_tribunal.ASK_FLAG
    assert "An empty list is a normal answer." in blurb_tribunal.ASK_FLAG
    assert "Here is a phrase: {phrase}." in blurb_tribunal.ASK_DEFEND
    assert "If none does, answer 0." in blurb_tribunal.ASK_DEFEND


def test_the_schemas_are_closed_over_the_registered_fields() -> None:
    flags = blurb_tribunal.FLAG_SCHEMA
    assert flags["required"] == ["flags"] and flags["additionalProperties"] is False
    assert flags["properties"]["flags"]["maxItems"] == blurb_tribunal.FLAG_MAX_ITEMS == 8
    defend = blurb_tribunal.DEFEND_SCHEMA
    assert defend["required"] == ["parallel", "from_listing"]
    assert defend["additionalProperties"] is False
    number = defend["properties"]["from_listing"]
    assert number["minimum"] == 0 and number["maximum"] == blurb_tribunal.N_REFERENCES == 5


def test_the_defend_prompt_shows_the_phrase_alone_and_never_the_target() -> None:
    refs = [_row(i, 40) for i in range(blurb_tribunal.N_REFERENCES)]
    rendered = blurb_tribunal.render_defend_prompt(refs, "patch of notes")
    assert "patch of notes" in rendered and "w9t0" not in rendered


def test_a_reference_shelf_holds_five_high_rows_and_never_the_target() -> None:
    high = [_row(i, 40 + i) for i in range(30)]
    shelf = blurb_tribunal.reference_shelf(high, high[3])
    assert len(shelf) == blurb_tribunal.N_REFERENCES
    assert all(blurb_tribunal.identity(row) != blurb_tribunal.identity(high[3]) for row in shelf)


# ------------------------------------------------------------------------ the strict parses


def test_defend_parse_rejects_both_malformed_pairings_strictly() -> None:
    named_without_quote = '{"parallel":"","from_listing":2}'
    quote_with_zero = '{"parallel":"a b","from_listing":0}'
    assert blurb_tribunal.parse_defense(named_without_quote) is None
    assert blurb_tribunal.parse_defense(quote_with_zero) is None


def test_defend_parse_refuses_every_other_shape_but_the_one_registered() -> None:
    assert blurb_tribunal.parse_defense('{"parallel":"a","from_listing":6}') is None
    assert blurb_tribunal.parse_defense('{"parallel":"a","from_listing":true}') is None
    assert blurb_tribunal.parse_defense('{"parallel":"a","from_listing":"2"}') is None
    assert blurb_tribunal.parse_defense('{"parallel":"a","from_listing":2,"x":0}') is None
    assert blurb_tribunal.parse_defense("not json") is None
    assert blurb_tribunal.parse_defense("") is None
    zero = {"parallel": "", "from_listing": 0}
    pair = {"parallel": "a b", "from_listing": 3}
    assert blurb_tribunal.parse_defense(json.dumps(zero)) == zero
    assert blurb_tribunal.parse_defense(json.dumps(pair)) == pair


def test_flag_parse_is_one_shape_with_no_partial_credit() -> None:
    good = json.dumps({"flags": ["  a   b  ", ""]})
    assert blurb_tribunal.parse_flags(good) == ["a b"], "collapse whitespace, drop blanks"
    over = json.dumps({"flags": ["ok"] * (blurb_tribunal.FLAG_MAX_ITEMS + 1)})
    assert blurb_tribunal.parse_flags(over) is None
    assert blurb_tribunal.parse_flags('{"flags":["a"],"x":1}') is None
    assert blurb_tribunal.parse_flags('{"flags":"a"}') is None
    assert blurb_tribunal.parse_flags('{"flags":[7]}') is None
    assert blurb_tribunal.parse_flags("not json") is None


# ------------------------------------------------------- the mechanism, hand-derived fixtures


def test_an_unlocated_returned_flag_is_dropped_and_counted() -> None:
    collected = blurb_tribunal.collect_flags(DRAWS, TARGET_LISTING)
    assert collected["unlocated"] == 1
    keys = [row["key"] for row in collected["flags"]]
    assert "wholly absent phrase" not in keys


def test_dedupe_merges_identical_flags_across_draws_and_keeps_draw_support() -> None:
    collected = blurb_tribunal.collect_flags(DRAWS, TARGET_LISTING)
    by_key = {row["key"]: row["support"] for row in collected["flags"]}
    assert by_key == {"patch of notes": 3, "ward held": 1}


def test_a_valid_defense_kills_a_flag_and_a_fabricated_one_does_not() -> None:
    report = blurb_tribunal.tribunal(
        TARGET_LISTING, DRAWS, DEFENSES, _references(), is_ours=False
    )
    assert report["valid_defenses"] == 1 and report["fabricated_defenses"] == 1
    outcomes = sorted(row["outcome"] for row in report["flags"])
    assert outcomes == ["fabricated", "valid"]
    assert report["surviving_flags"] == 1
    expected = 100 * 1 / len(TARGET_LISTING.split())
    assert report["surviving_per_100_words"] == pytest.approx(expected)


def test_a_missing_or_failed_defense_kills_nothing_and_stays_out_of_ka() -> None:
    report = blurb_tribunal.tribunal(
        TARGET_LISTING,
        DRAWS,
        dict.fromkeys(("patch of notes", "ward held")),
        _references(),
        is_ours=False,
    )
    assert report["surviving_flags"] == 2
    assert report["ka_rate"] is None and report["defenses_answered"] == 0


def test_the_cap_keeps_stage_two_bounded_at_max_items_per_target() -> None:
    tokens = [f"t{n}" for n in range(14)]
    listing = " ".join(tokens)
    draws = [[token] for token in tokens]  # every draw finds one distinct located flag
    refs = [_row(i, 41) for i in range(blurb_tribunal.N_REFERENCES)]
    report = blurb_tribunal.tribunal(listing, draws, {}, refs, is_ours=False)
    assert report["unique_flags"] == blurb_tribunal.FLAG_MAX_ITEMS == 8
    assert report["dropped_over_cap"] == len(tokens) - blurb_tribunal.FLAG_MAX_ITEMS


def test_floors_are_per_target_and_no_function_accepts_two_targets_rows() -> None:
    other = "his certainties were a ledger of receipts stacked beside the door of the shop."
    first = blurb_tribunal.tribunal(TARGET_LISTING, DRAWS, {}, _references(), is_ours=False)
    second = blurb_tribunal.tribunal(other, DRAWS, {}, _references(), is_ours=False)
    assert first != second, "two targets' mechanisms must stay two summaries"
    # ONE target per call, by construction: the mechanism's first parameter is one listing,
    # and its docstring says so — there is no function anywhere that pools two shams' rows.
    parameters = inspect.signature(blurb_tribunal.tribunal).parameters
    assert next(iter(parameters)) == "listing"
    assert "ONE target" in (blurb_tribunal.tribunal.__doc__ or "")


# ------------------------------------------------------------------------- the prose firewall


def test_a_market_target_row_carries_offsets_only_and_no_third_party_prose() -> None:
    report = blurb_tribunal.tribunal(
        TARGET_LISTING, DRAWS, DEFENSES, _references(), is_ours=False
    )
    blob = json.dumps(report)
    for leak in ("patch", "notes", "ward", "held", "works the same way"):
        assert leak not in blob, f"a market-target row leaked the prose fragment {leak!r}"
    flagged = [row["flag"] for row in report["flags"]]
    assert all("verbatim" not in record for record in flagged)
    assert any(record.get("located") for record in flagged)


def test_an_ours_target_flag_row_is_verbatim_while_parallels_stay_offset_only() -> None:
    report = blurb_tribunal.tribunal(TARGET_LISTING, DRAWS, {}, _references(), is_ours=True)
    flagged = {row["flag"].get("verbatim") for row in report["flags"]}
    assert "patch of notes" in flagged, "our own listings' spans are ours to commit"
    assert "works the same way" not in json.dumps(report), (
        "a parallel names a MARKET listing — offsets even on an ours-target row"
    )


# ------------------------------------------------------------------------------- KD and KG


def test_kd_is_mean_pairwise_jaccard_of_the_draws_flagged_token_sets() -> None:
    # Hand-derived over the six pairs of four sets: j(ab,ab)=1; j(ab,{})=0 four times;
    # j({},{})=1 (two draws that both flagged nothing agree, trivially) → 2/6. The first
    # version of this fixture had one empty set and imagined an empty-empty pair that did
    # not exist; the gate caught the arithmetic, not the function.
    sets = [frozenset("ab"), frozenset("ab"), frozenset(), frozenset()]
    assert blurb_tribunal.flag_agreement(sets) == pytest.approx(2 / 6)
    assert blurb_tribunal.flag_agreement([frozenset(), frozenset()]) == pytest.approx(1.0)
    assert blurb_tribunal.flag_agreement([frozenset("a")]) is None


def test_kg_counts_pairs_where_low_survives_more_than_high() -> None:
    stat = blurb_tribunal.kg_statistic([(0.60, 0.20), (0.50, 0.30), (0.40, 0.35)])
    assert stat["wins"] == 3 and stat["share"] == pytest.approx(1.0)
    lo, hi = stat["bootstrap_interval"]
    assert 0.0 <= lo <= hi <= 1.0


# ------------------------------------------------------------------------------- the CLI


def test_run_refuses_to_spend_without_the_gated_run_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert blurb_tribunal.main(["--run", "--yes"]) == 1
    err = capsys.readouterr().err
    assert "--i-am-the-gated-run" in err


def test_dry_run_prints_exact_stage_one_and_bounded_stage_two_worst_case_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    high_path = tmp_path / "high.json"
    low_path = tmp_path / "low.json"
    high_path.write_text(json.dumps([_row(i, 30 + i) for i in range(24)]), encoding="utf-8")
    # One sham plus two pairs: pair 0's HIGH partner IS the sham (word counts allow), pair
    # 1's partner joins as an extra sham-leg target — every pair measured on both sides.
    low_rows = [
        {
            "title": f"Low {i}",
            "listing": " ".join(f"lw{t}" for t in range(20 + i)) + ".",
            "followers": i,
            "source": f"low{i}",
        }
        for i in range(3)
    ]
    low_path.write_text(json.dumps(low_rows), encoding="utf-8")
    argv = [
        "--dry-run",
        "--pool",
        str(high_path),
        str(low_path),
        "--shams",
        "1",
        "--pairs",
        "2",
    ]
    assert blurb_tribunal.main(argv) == 0
    out = capsys.readouterr().out
    # targets = 1 sham + 2 gradient LOW + 1 extra partner sham = 4.
    assert "stage 1: 16 calls exactly: K=4 x 4 target(s)" in out
    assert "stage 2: between 0 and 32 calls (worst case first)" in out
    assert "total: between 16 and 48 calls, worst case first" in out


def test_build_targets_refuses_two_targets_that_would_share_one_name(tmp_path: Path) -> None:
    """`run` keys reports and the raw sidecar by name, so a collision replaces, never merges.

    The first run paid for nineteen targets and reported seventeen (stage-0 §145). Refusing
    in `build_targets` puts the failure before the registry exists and before any spend.
    """
    high = [_row(i, 30 + i) for i in range(24)]
    low = [
        {
            "title": f"Low {i}",
            "listing": " ".join(f"lw{t}" for t in range(20 + i)) + ".",
            "followers": i,
            "source": f"low{i}",
        }
        for i in range(2)
    ]
    twins = [
        {"name": "overview", "title": "", "listing": "one listing."},
        {"name": "overview", "title": "", "listing": "a different listing entirely."},
    ]
    with pytest.raises(ValueError, match="duplicate target name"):
        blurb_tribunal.build_targets(high, low, 1, 1, twins)


def test_the_dry_run_carries_the_paid_runs_own_text_names_and_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two books' `overview.txt` are two targets in the rehearsal, as they are in the run."""
    high_path = tmp_path / "high.json"
    low_path = tmp_path / "low.json"
    high_path.write_text(json.dumps([_row(i, 30 + i) for i in range(24)]), encoding="utf-8")
    low_path.write_text(
        json.dumps(
            [
                {
                    "title": "Low 0",
                    "listing": " ".join(f"lw{t}" for t in range(20)) + ".",
                    "followers": 0,
                    "source": "low0",
                }
            ]
        ),
        encoding="utf-8",
    )
    texts = []
    for slug in ("a-good-take", "patch-notes-for-earth"):
        path = tmp_path / slug / "overview.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"the {slug} listing.", encoding="utf-8")
        texts.append(str(path))

    argv = ["--dry-run", "--pool", str(high_path), str(low_path), "--shams", "1", "--pairs", "1"]
    assert blurb_tribunal.main([*argv, "--texts", *texts]) == 0
    out = capsys.readouterr().out
    # 1 sham + 1 gradient LOW + 2 ours = 4; the two overviews are counted separately.
    assert "targets: 4 (1 gradient, 2 ours, 1 sham)" in out
    assert "stage 1: 16 calls exactly: K=4 x 4 target(s)" in out


def test_the_selftest_passes() -> None:
    assert blurb_tribunal.selftest() == 0
