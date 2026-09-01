"""The opening-parity driver, exercised end to end on a fake elicitor.

`research/opening-parity/run.py` reuses `house_panel` and adds stimulus construction, the
recognition probes, a fixed pair plan and a summary. These tests drive the whole path with
canned answers and tiny texts: no model, no corpus, no book-library, nothing under
`src/litharness/`. What they pin is the part a paid run cannot check about itself — that the
pair plan is fixed by the manifest, that the two arms cut the way PREREG says, that a probe
hit lands a stimulus in the recognised stratum rather than dropping it, and that the summary
carries no key that reads as a verdict.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sibling in (
    REPO_ROOT / "research" / "opening-parity",
    REPO_ROOT / "research" / "sim-readership-backtest",
    REPO_ROOT / "research" / "quality-measurement",
):
    if str(sibling) not in sys.path:
        sys.path.insert(0, str(sibling))

import house_panel  # noqa: E402
import population  # noqa: E402
import run as parity  # noqa: E402


def _paragraphs(prefix: str, count: int, words: int = 12) -> str:
    return "\n\n".join(
        " ".join(f"{prefix}{p}w{w}" for w in range(words)) for p in range(count)
    )


class FakeElicitor:
    """Answers every stage-2 turn `A`, every probe `unknown` unless told to recognise a label."""

    def __init__(self, recognise: set[str] | None = None) -> None:
        self.recognise = recognise or set()
        self.calls = 0
        self.transport_failures = 0
        self.api_calls = 0
        self.replayed = 0

    def ask_raw(
        self, system: str, turns: list[dict[str, Any]], *, schema: dict[str, object] | None,
        max_tokens: int, tag: dict[str, Any], sample: int = 0, model: str | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        self.api_calls += 1
        if tag.get("stage") == "probe":
            label = str(tag.get("stimulus", "")).split(":", 1)[-1]
            if tag.get("probe") == "title" and label in self.recognise:
                return {"text": "Summit Two"}
            return {"text": "unknown"}
        if schema is None:
            return {"text": "A opens on a person; B opens on a place."}
        return {"text": json.dumps({"continue": "A", "reason": "hooked-by-other"})}

    def spend(self) -> dict[str, int | float]:
        return {"equivalent_usd": round(self.calls * 0.001, 4)}

    def close(self) -> None:
        return None


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    root = tmp_path
    # Blurbs never mention the fake titles: blinding strips a title wherever it appears, and
    # a blurb that named one would be testing the blinder rather than the driver.
    files = {
        "ours-one": (_paragraphs("o1p", 6), "A cook opens a door and reads what is there " * 4),
        "ours-two": (_paragraphs("o2p", 6), "A mender opens a door and reads what is there " * 4),
        "summit-one": (_paragraphs("s1p", 6), "A clerk opens a door and reads what is there " * 4),
        "summit-two": (_paragraphs("s2p", 6), None),
    }
    rows: dict[str, list[dict[str, Any]]] = {"ours": [], "summits": []}
    for label, (chapter, blurb) in files.items():
        (root / f"{label}.ch1.txt").write_text(chapter, encoding="utf-8")
        row: dict[str, Any] = {
            "label": label, "chapter": f"{label}.ch1.txt", "blurb": None,
            "title": label.replace("-", " ").title(), "author": "someone",
        }
        if blurb is not None:
            (root / f"{label}.blurb.txt").write_text(blurb, encoding="utf-8")
            row["blurb"] = f"{label}.blurb.txt"
        rows["ours" if label.startswith("ours") else "summits"].append(row)
    payload = {
        **rows,
        "calibration": {
            "opening": [["summit-one", "summit-two"], ["ours-one", "ours-two"]],
            "listing": [["ours-one", "ours-two"]],
        },
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(manifest: Path, tmp_path: Path, elicitor: FakeElicitor, *extra: str) -> dict[str, Any]:
    out = tmp_path / "out"
    code = parity.main(
        [
            "--manifest", str(manifest), "--root", str(tmp_path), "--out", str(out),
            "--max-usd", "50", "--max-sessions", "1000", "--workers", "2", *extra,
        ],
        elicitor_factory=lambda cache, model: elicitor,
    )
    assert code == 0
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


def test_the_pair_plan_is_fixed_by_the_manifest(manifest: Path, tmp_path: Path) -> None:
    root = tmp_path
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    built = parity.build_all(payload, root, tmp_path / "out")
    # The listing arm skips the summit without a blurb rather than fabricating one.
    assert set(built["opening"]) == {"ours-one", "ours-two", "summit-one", "summit-two"}
    assert set(built["listing"]) == {"ours-one", "ours-two", "summit-one"}
    pairs = parity.plan_pairs(payload, built)
    kinds = [(p.arm, p.kind) for p in pairs]
    assert kinds.count(("opening", "ours-vs-summit")) == 4
    assert kinds.count(("listing", "ours-vs-summit")) == 2
    assert kinds.count(("opening", "summit-vs-summit")) == 1
    assert kinds.count(("opening", "ours-vs-ours")) == 1
    assert kinds.count(("listing", "ours-vs-ours")) == 1
    # Ours is always file A in a versus pair; the both-orders rotation happens inside the cell.
    assert all(p.label_a.startswith("ours") for p in pairs if p.kind == "ours-vs-summit")


def test_the_two_arms_cut_as_registered(manifest: Path, tmp_path: Path) -> None:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    entry = parity.Entry.from_row(payload["ours"][0], "ours", tmp_path)
    opening = parity.build_stimulus(entry, "opening", tmp_path / "stim")
    listing = parity.build_stimulus(entry, "listing", tmp_path / "stim")
    assert opening is not None and listing is not None
    # Six 12-word paragraphs are under both cuts, so the opening shows the chapter whole and
    # the listing shows blurb + chapter; the blurb is what separates the two shapes.
    assert opening.text == opening.entry.chapter.read_text(encoding="utf-8")
    assert listing.text.startswith("A cook opens a door")
    assert listing.text.endswith(opening.text)
    assert opening.truth == ""  # nothing follows a whole chapter
    long_entry = parity.Entry(
        label="long", side="ours", chapter=tmp_path / "long.txt", blurb=None,
        title="Long", author="x",
    )
    long_entry.chapter.write_text(_paragraphs("L", 200, words=10), encoding="utf-8")
    cut = parity.build_stimulus(long_entry, "opening", tmp_path / "stim")
    assert cut is not None
    assert parity.OPENING_WORDS <= cut.words < parity.OPENING_WORDS + 10
    assert cut.truth.split()[0].startswith("L")
    # A chapter with no paragraph break near the cut cannot be length-matched, and the driver
    # refuses it by name rather than showing a persona one side twice the length of the other.
    wall_entry = parity.Entry(
        label="wall", side="summit", chapter=tmp_path / "wall.txt", blurb=None,
        title="Wall", author="x",
    )
    wall_entry.chapter.write_text(" ".join(f"W{i}" for i in range(2500)), encoding="utf-8")
    with pytest.raises(house_panel.ForbiddenOutput, match="paragraph boundary"):
        parity.build_stimulus(wall_entry, "opening", tmp_path / "stim")
    # A chapter saved with one newline per paragraph and no blank lines is paragraphed on
    # those newlines and cut like any other; one saved with blank lines is left as it is.
    single = parity.Entry(
        label="single", side="summit", chapter=tmp_path / "single.txt", blurb=None,
        title="Single", author="x",
    )
    single.chapter.write_text(
        "\n".join(" ".join(f"S{p}w{w}" for w in range(10)) for p in range(200)), encoding="utf-8"
    )
    cut_single = parity.build_stimulus(single, "opening", tmp_path / "stim")
    assert cut_single is not None
    assert parity.OPENING_WORDS <= cut_single.words < parity.OPENING_WORDS + 10
    assert "\n\n" in cut_single.text
    assert parity._paragraphed("a\n\nb\n") == "a\n\nb\n"


def test_a_full_run_writes_shares_and_no_verdict(manifest: Path, tmp_path: Path) -> None:
    summary = _run(manifest, tmp_path, FakeElicitor())
    assert house_panel.forbidden_keys(summary) == []
    assert summary["exploratory"] is True
    assert summary["provenance"] == house_panel.PROVENANCE
    opening = summary["arms"]["opening"]
    per_pair = len(population.POPULATION) * 2
    pooled = opening["ours_vs_summit_pooled"]
    assert pooled["pairs"] == 4
    assert pooled["returned"] == 4 * per_pair
    # The fake answers slot A every time: ours is A in order 0 and B in order 1, so ours is
    # chosen exactly half the time and the first-slot share is 1.0 — a void reading.
    assert pooled["ours_share_of_decided"] == 0.5
    assert pooled["first_slot_share"] == 1.0
    assert opening["positional_void_reading"] is True
    assert opening["calibration"]["summit-vs-summit"]["pairs"] == 1
    assert opening["calibration"]["ours-vs-ours"]["pairs"] == 1
    assert set(opening["by_ours"]) == {"ours-one", "ours-two"}
    assert set(opening["by_summit"]) == {"summit-one", "summit-two"}
    assert summary["arms"]["listing"]["ours_vs_summit_pooled"]["pairs"] == 2
    out = tmp_path / "out"
    assert (out / "summary.md").exists()
    assert (out / "opening" / "pair-ours-one--summit-one.json").exists()
    assert (out / "stimuli" / "opening-summit-two.txt").exists()
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert "VOID READING" in md
    # Every probe came back `unknown`, so every stimulus is clean and no pair is in the
    # recognised stratum.
    assert all(p["classification"] == "clean" for p in summary["probes"])
    assert opening["ours_vs_summit_recognised_stratum"]["pairs"] == 0


def test_a_probe_hit_moves_the_summit_to_the_recognised_stratum(
    manifest: Path, tmp_path: Path
) -> None:
    summary = _run(manifest, tmp_path, FakeElicitor(recognise={"summit-two"}))
    probes = {(p["arm"], p["label"]): p for p in summary["probes"]}
    assert probes[("opening", "summit-two")]["classification"] == "recognised"
    assert probes[("opening", "summit-two")]["hits"] == ["title"]
    assert probes[("opening", "summit-one")]["classification"] == "clean"
    opening = summary["arms"]["opening"]
    assert opening["ours_vs_summit_recognised_stratum"]["pairs"] == 2
    assert opening["ours_vs_summit_clean_stratum"]["pairs"] == 2
    strata = {
        (r["file_b"], r["stratum"]) for r in opening["pairs"] if r["kind"] == "ours-vs-summit"
    }
    assert ("summit-two", "recognised") in strata
    assert ("summit-one", "clean") in strata


def test_a_run_refuses_without_both_ceilings(manifest: Path, tmp_path: Path) -> None:
    code = parity.main(
        [
            "--manifest", str(manifest), "--root", str(tmp_path), "--out", str(tmp_path / "out"),
            "--max-usd", "5",
        ],
        elicitor_factory=lambda cache, model: FakeElicitor(),
    )
    assert code == 1
    assert not (tmp_path / "out" / "summary.json").exists()


def test_a_dry_run_builds_stimuli_and_constructs_no_elicitor(
    manifest: Path, tmp_path: Path
) -> None:
    def refuse(cache: Path, model: str) -> Any:
        raise AssertionError("an elicitor was constructed on a dry run")

    code = parity.main(
        [
            "--manifest", str(manifest), "--root", str(tmp_path), "--out", str(tmp_path / "out"),
            "--dry-run",
        ],
        elicitor_factory=refuse,
    )
    assert code == 0
    assert (tmp_path / "out" / "stimuli" / "listing-ours-one.txt").exists()
