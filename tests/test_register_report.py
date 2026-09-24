"""Pins for `research/quality-measurement/register_report.py`, the inert register report.

**Hermetic.** Every text below is synthetic, written here to exercise a counter. No corpus is
opened, and the builder runs over a small fictions file written to a temporary folder in the
backtest's own shape. The committed baseline is read only to check that it holds numbers.

**What these tests defend is mostly a refusal.** The report describes and does not decide, so
it has no pass, fail or bar key, and it reads the tells pass's density, never its ceilings.
The market side carries numbers and never text. Money, loot, admin and frame stay four separate
families, and the admin and frame words stay the registered runner's own.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

register_report = pytest.importorskip(
    "register_report",
    reason="research module; needs the quality-measurement directory on the path",
)

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "research/quality-measurement/restored-directions-draw-20260922/run.py"
BANNED = {"pass", "fail", "verdict", "score", "ceiling", "ceilings", "bar", "ok", "threshold"}

#: 32 prose words, then the household-money word, after a heading and a status line the prose
#: normaliser drops.
OPENING = (
    "# A Synthetic Book\n\n## Chapter 1\n\n"
    + " ".join(f"w{i}" for i in range(32))
    + " rent was late again, and the landlord knew it.\n\n"
    "[STATUS] Ada — Grip 1\n\n"
    "She found three gold coins behind the ledger and a permit for the court.\n"
)

CONCEPT: dict[str, Any] = {
    "author_brief": "Everyone on Earth gets one Slot when the System arrives.",
    "person_before": "Ada Vale is a courier in her twenties.",
    "want": "Ada wants her street back.",
    "exception": "Everyone gets one Slot. Ada alone holds a Slot that keeps every Knack she binds "
    "on Earth.",
    "system": {
        "name": "The Lattice",
        "look": "A grey panel lists each Slot and each Knack by name.",
        "manner": "People bind a Knack to their Slot. Using a Knack earns Grade 1, then Grade 2.",
        "pays": "A higher Grade makes a Knack stronger; Ada's first Knack is Brace.",
    },
    "threat": {"what": "Earth has joined another world."},
}
LISTING = (
    "Ada Vale knows her street. Then the Lattice arrives. Brace holds the stair. "
    "Everyone gets one Slot. Hers keeps every Knack she binds. Grade 1 comes fast.\n\n"
    "She wants her street back, before the flood takes it, and she means to cross tonight."
)


def keys_of(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = set(value)
        for item in value.values():
            found |= keys_of(item)
        return found
    if isinstance(value, list):
        return set().union(*(keys_of(item) for item in value)) if value else set()
    return set()


# ------------------------------------------------------------------ percentiles


def test_percentile_is_mid_rank_and_carries_n() -> None:
    place = register_report.percentile(3.0, [1.0, 2.0, 3.0, 3.0, 5.0])
    assert place == {"n": 5, "below": 2, "equal": 2, "mid_rank": 60.0}
    assert register_report.percentile(9.0, [1.0, 2.0])["mid_rank"] == 100.0
    assert register_report.percentile(1.0, [])["mid_rank"] is None


def test_a_small_population_is_printed_as_k_of_n() -> None:
    assert register_report.describe(3.0, [1.0, 2.0, 3.0, 5.0]) == "2 of 4 below, 1 equal"
    assert register_report.describe(0.0, [1.0]) == "0 of 1 below"
    wide = register_report.describe(10.0, [float(i) for i in range(40)])
    assert wide.startswith("n=40 p10") and "mid-rank 26.2" in wide
    assert register_report.describe(1.0, []) == "no reference (empty population)"


# ------------------------------------------------------------------ it decides nothing


def test_the_report_decides_nothing(tmp_path: Path) -> None:
    """A chapter made of nothing but money words still exits 0 and names no verdict."""
    chapter = tmp_path / "chapter.md"
    chapter.write_text("Rent. Pay the rent. Money, cash, wages, bills, the loan.\n", "utf-8")
    listing = tmp_path / "listing.txt"
    listing.write_text("Pay the rent or lose the flat.", "utf-8")
    out = tmp_path / "report.json"
    code = register_report.main(
        [
            "--listing",
            str(listing),
            "--chapter",
            str(chapter),
            "--json",
            str(out),
            "--baseline",
            str(tmp_path / "absent.json"),
            "--table",
            str(tmp_path / "absent-t.json"),
        ]
    )
    assert code == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    for key in keys_of(result):
        assert not set(key.lower().split("_")) & BANNED, key
    assert "decides nothing" in result["header"] and "no bar" in result["header"]
    assert result["baseline"] == "no reference (baseline not built)"


def test_a_missing_input_exits_two(tmp_path: Path) -> None:
    assert register_report.main(["--listing", str(tmp_path / "nope.txt")]) == 2
    assert register_report.main([]) == 2


def test_tells_rows_use_density_not_ceilings() -> None:
    """The tells pass's ceilings drive a rewrite; here only its density is read."""
    tree = ast.parse(Path(register_report.__file__).read_text(encoding="utf-8"))
    used = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "tells"
    }
    assert "density" in used
    assert not used & {"ceilings", "over", "limits_from"}


# ------------------------------------------------------------------ money, by position


def test_money_first_window_and_position() -> None:
    row = register_report.chapter_measures_row(OPENING)
    assert row["household_money_first_hit_at_word"] == 32
    assert row["household_money_first150"] == 2  # rent, landlord
    assert row["loot_currency_first150"] == 2  # gold, coins
    assert row["admin_first150"] == 1  # ledger
    assert row["frame_first150"] == 2  # permit, court
    assert row["household_money_per_1k"] > 0 and row["frame_per_1k"] > 0
    # Four families, four keys each time: never a pooled "money" count.
    assert not any(key.startswith("money") for key in row)


def test_the_status_line_and_heading_are_not_prose() -> None:
    prose = register_report.chapter_prose(OPENING)
    assert "[STATUS]" not in prose and "Synthetic Book" not in prose
    assert prose.split()[0] == "w0"


def test_admin_and_frame_lists_match_the_registered_runner() -> None:
    spec = importlib.util.spec_from_file_location("restored_directions_register_pin", RUNNER)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    assert register_report.ADMIN_LEXICON == runner.ADMIN_LEXICON
    assert register_report.FRAME_LEXICON == runner.FRAME_LEXICON


def test_the_four_families_share_no_word() -> None:
    names = [set(words) for words in register_report.FAMILIES.values()]
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            assert not first & second


def test_paragraph_normaliser_is_applied_to_both_sides() -> None:
    """A market chapter saved one newline per paragraph measures as the same text with blank
    lines, because both sides go through the one `chapter_prose`."""
    blank = "He ran.\n\nShe stayed. The rent was due.\n\n“Go,” she said.\n"
    single = blank.replace("\n\n", "\n")
    assert register_report.chapter_prose(blank) == register_report.chapter_prose(single)
    assert register_report.chapter_measures_row(blank) == register_report.chapter_measures_row(
        single
    )


# ------------------------------------------------------------------ listing shape


def test_listing_shape_rows_name_the_books_own_mechanics() -> None:
    rows = register_report.listing_rows(LISTING, concept=CONCEPT, task="Write a listing.")
    shape = rows["shape"]
    # Knack and Slot are the system text's; Brace is named there too; Grade is its unit.
    assert shape["mechanic_names"] == ["Brace", "Grade", "Knack", "Slot"]
    # Earth comes from the author's brief and the system text never uses it.
    assert "Earth" not in shape["mechanic_names"]
    assert shape["system_named"] is True
    # The exception opens on what everyone gets; the listing says it at sentence 4.
    assert shape["exception_at"]["sentence"] == 4
    assert shape["exception_at"]["text"] == "Everyone gets one Slot."
    assert shape["first_sentence"] == "Ada Vale knows her street."
    assert shape["last_sentence"].startswith("She wants her street back")
    assert shape["task_echo"] == {"longest_shared_run_words": 0, "against": "supplied task"}
    assert rows["measures"]["short_run"] == 6
    assert rows["measures"]["digits"] == 1


def test_short_run_counts_consecutive_sentences_of_twelve_words_or_fewer() -> None:
    long = " ".join(["word"] * 13) + "."
    parts = ["One fact.", "Two facts.", "Three facts.", long, "Four.", "Five."]
    assert register_report.short_run(parts) == 3
    assert register_report.short_run([long]) == 0
    assert register_report.short_run([" ".join(["word"] * 12) + "."]) == 1


def test_without_a_task_the_echo_is_read_against_the_live_listing_task() -> None:
    task = register_report.live_listing_task()
    assert "LitRPG" in task
    echo = register_report.listing_rows(task)["shape"]["task_echo"]
    assert echo["against"] == "live concept listing task"
    assert echo["longest_shared_run_words"] == register_report.voice.longest_shared_run(task, task)
    assert echo["longest_shared_run_words"] > 50


# ------------------------------------------------------------------ provenance


def receipt(system: str, prompt: str, page: str) -> dict[str, Any]:
    return {"request": {"system": system, "prompt": prompt}, "result": {"text": page}}


def test_provenance_names_each_words_first_source(tmp_path: Path) -> None:
    system = (
        "You love rivers.\n\nYou are drafting one scene of a novel. Write prose.\n\n"
        "World rules and limits — facts:\n- Bridges need a surviving pier."
    )
    prompt = (
        "Premise: A courier.\n\nWho is in this story:\nada (the protagonist)\n\n"
        "The story so far, in full:\n\n[scene-1]\nAda crossed the weir.\n\n"
        "Now write A Book: scene-2 — chapter 1.\nIntended changes:\n- Ada tests the "
        "surviving pier."
    )
    page = (
        "Ada crossed back over the weir to the surviving pier and its lowest tread. "
        f"Ada{register_report.APOSTROPHE}s hands didn't shake.\n"
    )
    calls = tmp_path / "calls"
    calls.mkdir()
    (calls / "0001-chapter.json").write_text(json.dumps(receipt(system, prompt, page)), "utf-8")
    probe = {
        "request": {"system": None, "prompt": "Reply with the single word OK."},
        "result": {"text": "OK"},
    }
    (calls / "0002-chapter.json").write_text(json.dumps(probe), "utf-8")
    traced = register_report.provenance(tmp_path)
    assert [scene["scene"] for scene in traced] == ["scene-2"]
    words = traced[0]["words"]
    assert words["pier"]["first_source"] == "system:world_rules"
    assert words["surviving"]["sources"] == ["system:world_rules", "prompt:scene_brief"]
    assert words["weir"]["first_source"] == "prompt:prior_prose"
    # A possessive is its noun; a contraction is never a content word.
    assert words["ada"]["count"] == 2 and "didn't" not in words
    assert words["ada"]["sources"] == [
        "prompt:cast_facts",
        "prompt:prior_prose",
        "prompt:scene_brief",
    ]
    assert words["tread"] == {"count": 1, "first_source": "none", "sources": []}
    assert "tread" in traced[0]["model_supplied_words"]
    sequences = traced[0]["sequences"]
    assert sequences["surviving pier"]["first_source"] == "system:world_rules"
    assert sequences["lowest tread"] == {"first_source": "none", "sources": []}
    # Every sequence is labelled, the model's own included; the counts add up to the whole.
    assert traced[0]["echoed_sequences"] + traced[0]["model_supplied_sequences"] == len(sequences)


def test_the_trace_prints_a_words_sequences_with_their_source(tmp_path: Path) -> None:
    system = "You are drafting one scene of a novel.\n\nWorld rules and limits — a surviving pier."
    prompt = "Premise: A courier.\n\nNow write A Book: scene-1 — chapter 1.\n- Cross."
    page = "She stood on the surviving pier, on its lowest surviving tread.\n"
    (tmp_path / "calls").mkdir()
    (tmp_path / "calls" / "0001-chapter.json").write_text(
        json.dumps(receipt(system, prompt, page)), "utf-8"
    )
    text = register_report.render(
        register_report.report(draw=tmp_path), trace_words=["surviving", "tread"]
    )
    assert "surviving pier <- system:world_rules" in text
    assert "lowest surviving tread <- none" in text
    assert "tread: count 1, first source none" in text


# ------------------------------------------------------------------ the builder


def fiction_rows(
    fiction_id: str,
    *,
    tags: list[str],
    warnings: list[str],
    chapters: list[str],
    released: str = "2021-05-01",
    description: str | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "fiction_id": fiction_id,
            "title": f"Synthetic {fiction_id}",
            "author": f"author-{fiction_id}",
            "tags": json.dumps(tags),
            "warnings": json.dumps(warnings),
            "description": description
            or ("A synthetic blurb with enough words to clear the backtest's floor " * 3),
            "status": "ONGOING",
            "followers": 50,
            "total_views": 5000,
            "average_views": 5000 / len(chapters),
            "chapter_id": f"{fiction_id}-{index}",
            "chapter_title": f"Chapter {index}",
            "release_datetime": f"{released}T00:0{index}:00",
            "text": text,
        }
        for index, text in enumerate(chapters, start=1)
    ]


def five_chapters(opening_word: str, base_word: str) -> list[str]:
    return [
        f"The {opening_word} sat on the table. He paid the rent.\n\nShe left.",
        "Chapter two words.",
        "Chapter three words.",
        f"The {base_word} and the river again.",
        "The river ran. The river rose.",
    ]


@pytest.fixture()
def built(tmp_path: Path) -> dict[str, Any]:
    fictions = {
        "101": fiction_rows(
            "101",
            tags=["LitRPG"],
            warnings=[],
            chapters=five_chapters("zanzibarquux", "basemarkerword"),
        ),
        "102": fiction_rows(
            "102",
            tags=["Progression", "Magic"],
            warnings=[],
            chapters=five_chapters("quuxopening", "basemarkertwo"),
        ),
        "103": fiction_rows(
            "103",
            tags=["Romance"],
            warnings=[],
            chapters=five_chapters("romanceword", "romancebase"),
        ),
        "104": fiction_rows(
            "104",
            tags=["LitRPG"],
            warnings=["AI-Assisted Content"],
            released="2025-03-01",
            chapters=five_chapters("aiopening", "aibase"),
        ),
        "105": fiction_rows(
            "105",
            tags=["LitRPG"],
            warnings=[],
            chapters=five_chapters("quarantinedword", "quarantinedbase"),
        ),
    }
    source = tmp_path / "fictions.json"
    source.write_text(json.dumps(fictions, ensure_ascii=False), encoding="utf-8")
    rivals = tmp_path / "rivals.json"
    rivals.write_text(
        json.dumps(
            [
                {
                    "listing": "A rival listing about a system and a rank.",
                    "genre": "litrpg",
                    "source": "royalroad:201",
                },
                {"listing": "A romance listing.", "genre": "romance", "source": "royalroad:202"},
                {"listing": "A quarantined listing.", "genre": "litrpg", "source": "royalroad:105"},
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "baseline.json"
    table = tmp_path / "derived" / "freq.json"
    baseline = register_report.build_baseline(
        fictions=source,
        rivals=rivals,
        out=out,
        table_out=table,
        quarantined=frozenset({105}),
    )
    return {"baseline": baseline, "out": out, "table": table, "tmp": tmp_path}


def test_builder_filters_genre_quarantine_and_declared_ai(built: dict[str, Any]) -> None:
    rivals, fictions = built["baseline"]["sources"]
    assert (rivals["kept"], rivals["refused"]) == (1, {"genre": 1, "quarantined": 1})
    assert fictions["kept"] == 2
    assert fictions["refused"] == {"declared_ai": 1, "genre": 1, "quarantined": 1}
    assert built["baseline"]["metrics"]["chapter_one"]["prose_words"]["n"] == 2


def test_chapter_ones_are_never_in_the_frequency_base(built: dict[str, Any]) -> None:
    table = json.loads(built["table"].read_text(encoding="utf-8"))
    assert table["unigrams"]["basemarkerword"] == 1
    assert table["unigrams"]["river"] == 6  # chapters four and five of the two kept fictions
    for held_out in ("zanzibarquux", "quuxopening", "two", "three"):
        assert held_out not in table["unigrams"]
    assert not any("romance" in word or word.startswith("ai") for word in table["unigrams"])


def test_the_base_starts_after_chapter_three_even_behind_a_prologue() -> None:
    corpus = register_report.backtest_corpus()
    rows = fiction_rows(
        "301",
        tags=["LitRPG"],
        warnings=[],
        chapters=["A prologue.", "One.", "Two.", "Three.", "Four."],
    )
    titles = ["Prologue", "Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4"]
    for row, title in zip(rows, titles, strict=True):
        row["chapter_title"] = title
    fiction = corpus.fiction_from_rows(rows)
    opening = corpus.chapters_1_to_3(fiction)
    assert [chapter.text for chapter in opening] == ["One.", "Two.", "Three."]
    later = register_report.later_chapters(fiction, opening)
    assert [chapter.text for chapter in later] == ["Four."]


def test_a_market_opening_is_read_without_its_own_fiction() -> None:
    """Our book is never in the base, so a market chapter one is read with its own fiction's
    later chapters taken out: a word the book coined does not make its opening read common."""
    table = {
        "unigrams": {"glimmerstone": 40, "the": 960},
        "unigram_total": 1000,
        "bigrams": {},
        "bigram_total": 1000,
    }
    prose = "The glimmerstone."
    assert register_report.friction_row(prose, table)["friction_rare_per_1k"] == 0.0
    own = register_report.OwnCounts(unigrams=Counter({"glimmerstone": 40}), unigram_total=40)
    assert register_report.friction_row(prose, table, own)["friction_rare_per_1k"] == 500.0


def test_the_baseline_holds_numbers_and_no_market_text(built: dict[str, Any]) -> None:
    raw = built["out"].read_text(encoding="utf-8")
    for marker in ("zanzibarquux", "Synthetic 101", "author-101", "rival listing", "river"):
        assert marker not in raw
    for population in built["baseline"]["metrics"].values():
        for column in population.values():
            assert all(isinstance(value, int | float) for value in column["values"])
            assert column["values"] == sorted(column["values"])


def test_the_builder_never_reads_book_library() -> None:
    assert not any("book-library" in str(path) for path in register_report.BUILDER_INPUTS)
    source = Path(register_report.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert not any("book-library" in literal for literal in literals[1:])


def test_the_builder_runs_only_under_its_own_box_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sustained job over a 1.96 GB file shares the box only under the lock: the builder
    checks for a holder line of its own and never takes the lock itself."""
    holder = tmp_path / "box.lock" / "holder"
    monkeypatch.setattr(register_report, "BOX_LOCK_HOLDER", holder)
    monkeypatch.setattr(register_report, "BUILDER_INPUTS", (tmp_path / "absent.json",))

    def never(**_: Any) -> dict[str, Any]:
        raise AssertionError("the builder ran")

    monkeypatch.setattr(register_report, "build_baseline", never)
    assert register_report.main(["--build-baseline"]) == 2
    assert "runs only under the box lock" in capsys.readouterr().err and not holder.exists()
    holder.parent.mkdir()
    holder.write_text("chapter-one: coordinator, read-21 draw 1\n", encoding="utf-8")
    assert register_report.main(["--build-baseline"]) == 2
    assert "held by: chapter-one" in capsys.readouterr().err
    holder.write_text("register-baseline: coordinator, 14:00\n", encoding="utf-8")
    assert register_report.main(["--build-baseline"]) == 2
    assert "missing input" in capsys.readouterr().err, "past the lock, to the input check"


def test_the_market_row_reads_a_built_baseline(built: dict[str, Any]) -> None:
    result = register_report.report(
        chapter=OPENING, baseline_path=built["out"], table_path=built["table"]
    )
    cell = result["chapter"]["market"]["household_money_first_hit_at_word"]["chapter_one"]
    assert cell["n"] == 2 and "of 2 below" in cell["cell"]
    assert result["chapter"]["frequency_base"] == "derived table present"
    rare = result["chapter"]["rarest_words"]
    prose_words = set(
        register_report.register_census.tokens(register_report.chapter_prose(OPENING))
    )
    assert rare and all(row["word"] in prose_words for row in rare)


def test_a_baseline_built_under_other_word_lists_gives_no_reference(
    built: dict[str, Any], tmp_path: Path
) -> None:
    stale = json.loads(built["out"].read_text(encoding="utf-8"))
    stale["registration_digest"] = "0" * 16
    path = tmp_path / "stale.json"
    path.write_text(json.dumps(stale), encoding="utf-8")
    baseline, reason = register_report.load_baseline(path)
    assert baseline is None and "is not the live" in reason


def test_the_committed_baseline_is_numbers_only() -> None:
    path = register_report.BASELINE
    if not path.is_file():
        pytest.skip("baseline not built on this checkout")
    baseline = json.loads(path.read_text(encoding="utf-8"))

    def strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [s for item in value.values() for s in strings(item)]
        if isinstance(value, list):
            return [s for item in value for s in strings(item)]
        return []

    assert all(len(text) <= 200 for text in strings(baseline))
    assert not strings(baseline["metrics"])
    assert baseline["registration_digest"] == register_report.registration_digest()


# ------------------------------------------------------------------ streaming reader


def test_the_streaming_reader_survives_every_chunk_boundary(tmp_path: Path) -> None:
    payload = {
        "1": [{"text": "café “quoted” — dash", "n": 1}],
        "22": [{"text": "second"}, {"text": "third, with [brackets] and {braces}"}],
    }
    path = tmp_path / "f.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for chunk in (1, 2, 3, 7, 64, 1 << 20):
        read = dict(register_report.iter_fiction_rows(path, chunk_chars=chunk))
        assert read == payload, chunk
