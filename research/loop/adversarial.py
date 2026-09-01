"""Mechanical adversaries: the checks a provisional win has to survive before it is a win.

The continuous-loop direction's amendment says a variant does not win an A/B by scoring
better; it wins by scoring better AND surviving a battery built to make the win fail. This
module is that battery's mechanical half. It generalises the sim-readership backtest's
control philosophy — which manufactured its damage and sham arms rather than selecting them
— from blinded corpus pairs to our own draws.

Three kinds of check, all code-only, none of them calling a model:

* **The damage transform.** `ablate.paragraph_shuffle` at full strength on the winning draw,
  then the scorecard's rows again. Setup lands after its payoff and nothing else changes —
  exactly the same paragraphs, reordered. A row that still beats the baseline after its own
  draw has been shuffled is measuring surface, not story.
* **The sham transform.** Two windows of the SAME draw, in the shape `arms.sham_windows`
  fixed for the backtest: drop two leading paragraphs and re-cap. The same draw cannot be
  better than itself, so any separation the rows show between two of its windows is position
  or format bias, and it bounds how much of the real margin means anything.
* **Axis-specific degenerate maxima.** One detector per named scorecard axis, each asking how
  a lazy optimiser would run that particular row to its maximum without writing better
  fiction: furniture spam, checklist stuffing, staccato monotony, opening repetition, cast
  starvation, denominator dilution.

**Every check is a sign test wherever one is possible, and says so when it is not.** The
degenerate maxima are defined as decompositions of a *move* between two draws — the row went
the winning way AND the component that carries the win is the degenerate one AND the
component that would carry a real gain did not move — because a decomposition of a sign needs
no threshold, and this repository's standing lesson is that seven declared bars each named a
quantity that could not do what it said (§81, §85, §87, §89). Where a check has no baseline
to decompose against it fires only on the extreme that needs no threshold, and otherwise
reports its number and stays clear. One check (`checklist_stuffing`) has an outlier form that
does use a constant; it is declared a screening constant, is reported beside every number it
was applied to, and is not a bar — no attainability check was run on it and none is claimed.

Output is a battery record per variant: check, fired/clear, and the number behind it, plus a
plain table. **No aggregate and no verdict.** Nothing here decides whether a variant ships;
the binding rule — provisional win, adversarial battery, survived-or-rejected — is the
harness's and the coordinator's to apply, and this module only reports what fired.

Nothing here is importable from `src/litharness` and nothing here reads a corpus.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_QM = HERE.parent / "quality-measurement"
for _path in (str(_QM), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import ablate  # noqa: E402  # sibling research module, imported by path
import measures_adapter as ma  # noqa: E402  # sibling research module, imported by path
import number_context  # noqa: E402  # sibling research module, imported by path
import progression_cadence  # noqa: E402  # sibling research module, imported by path
import register_census  # noqa: E402  # sibling research module, imported by path

#: Full strength: displace every paragraph. The backtest's damage arm uses 1.0 for the same
#: reason — a partial shuffle leaves a control whose failure to move is ambiguous between "the
#: row is order-blind" and "the damage was too small".
DAMAGE_STRENGTH = 1.0

#: Leading paragraphs the second sham window drops, from `arms.SHAM_OFFSET_PARAGRAPHS`. Kept
#: as its own constant rather than imported because `arms` reaches the RoyalRoad corpus reader
#: on import and this module must not.
SHAM_OFFSET_PARAGRAPHS = 2

#: Family members below which `checklist_stuffing`'s outlier form does not run. Three points
#: cannot locate an outlier and a median absolute deviation over three points is noise.
MIN_FAMILY = 4

#: **A screening constant, not a bar.** Deviations above `median + MAD_K * MAD` are called out
#: for the coordinator's read. No attainability check (range at the real n, direction,
#: independent unit, non-empty subgroup) has been run on it, so it declares nothing about
#: quality and licenses no promotion; it is a place to look. The comparative form of the same
#: check, which needs no constant, runs beside it and is the one to trust.
MAD_K = 3.0

#: Text under this many words is not measured: a "chapter" of one paragraph makes every
#: variance statistic below degenerate, and a check that fires on that is reporting its own
#: fixture.
MIN_WORDS = 120


@dataclass(frozen=True, slots=True)
class Draw:
    """One draw's chapters in reading order, under the id its result folder gave it."""

    draw_id: str
    chapters: tuple[str, ...]

    @property
    def text(self) -> str:
        """Chapters joined the way a reader meets them: one blank line between."""
        return "\n\n".join(self.chapters)

    @property
    def words(self) -> int:
        return len(self.text.split())


def load_draw(draw_id: str, paths: Iterable[Path]) -> Draw:
    """A draw from chapter files, read in the order given. Order is the caller's to fix.

    Deliberately not a glob: a battery whose chapter order depends on a filesystem listing
    would silently re-run the damage transform on itself.
    """
    return Draw(draw_id=draw_id, chapters=tuple(p.read_text(encoding="utf-8") for p in paths))


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One check's outcome: what it is, whether it fired, and the numbers behind it.

    `fired` is None when the check could not run at all — a missing baseline, too small a
    family, too short a text. A check that could not run is not a check that passed, and
    collapsing the two is how a battery starts reporting silence as safety.
    """

    check: str
    axis: str
    fired: bool | None
    numbers: dict[str, Any]
    basis: str
    note: str = ""


#: Which degenerate maximum belongs to which named scorecard axis. Keys carry both the
#: direction note's prose names and the battery keys the scorecard's substrate ships, so the
#: registry answers whichever vocabulary the caller has. An axis absent from this map is not
#: an error: `checks_for_axis` falls back to the axis-agnostic set and the report records that
#: the axis was unrecognised, which is the graceful degradation this build was asked for while
#: the scorecard track is unmerged.
AXIS_CHECKS: dict[str, tuple[str, ...]] = {
    "progression-cadence": ("furniture_spam", "word_dilution"),
    "cadence": ("furniture_spam", "word_dilution"),
    "cadence_v2": ("furniture_spam", "word_dilution"),
    "diegesis": ("furniture_spam", "checklist_stuffing"),
    "status": ("furniture_spam", "checklist_stuffing"),
    "number-context": ("checklist_stuffing", "word_dilution"),
    "numbers": ("checklist_stuffing", "word_dilution"),
    "numbers_v2": ("checklist_stuffing", "word_dilution"),
    "sentence-statistics": ("staccato_monotony", "opening_repetition"),
    "sentences": ("staccato_monotony", "opening_repetition"),
    "register-gloss": ("word_dilution",),
    "gloss": ("word_dilution",),
    "em_dash": ("word_dilution",),
    "cast-counts": ("cast_starvation",),
    "cast": ("cast_starvation",),
    "proper_nouns_NOT_CAST": ("cast_starvation",),
}

#: Run for every axis, recognised or not: the two transforms plus the one degenerate maximum
#: that applies to any per-1k row whatever it counts.
AXIS_AGNOSTIC: tuple[str, ...] = ("damage_survival", "sham_separation", "word_dilution")


def checks_for_axis(axis: str) -> tuple[tuple[str, ...], bool]:
    """The check names for `axis`, and whether the axis was recognised.

    The flag rides out with the names because a battery run against an unknown axis has done
    strictly less than one run against a known one, and a report that did not say so would
    read as a clean sheet.
    """
    named = AXIS_CHECKS.get(axis, ())
    ordered = list(AXIS_AGNOSTIC)
    ordered.extend(name for name in named if name not in ordered)
    return tuple(ordered), axis in AXIS_CHECKS


# ------------------------------------------------------------------------------- transforms


def damage(text: str) -> str:
    """The winning draw with its paragraphs displaced. Exactly length-preserving."""
    return ablate.paragraph_shuffle(text, DAMAGE_STRENGTH)


def sham_windows(text: str, *, offset: int = SHAM_OFFSET_PARAGRAPHS) -> tuple[str, str] | None:
    """Two different windows of one draw, or None when no honest pair exists.

    Window one is the text; window two drops `offset` leading paragraphs. None when the text
    has no more paragraphs than the offset, and None when the two windows come out equal —
    §120.2's rule, carried over intact: a byte-identical sham cannot move and is therefore no
    control at all, so it is refused rather than reported as a control that stayed clear.
    """
    blocks = [block for block in text.split("\n\n") if block.strip()]
    if len(blocks) <= offset:
        return None
    first = "\n\n".join(blocks)
    second = "\n\n".join(blocks[offset:])
    if not second.strip() or first == second:
        return None
    return first, second


# ------------------------------------------------------------------------------ row plumbing


def flatten(record: Mapping[str, Any], prefix: str = "") -> dict[str, float]:
    """Every numeric leaf of a battery record, under its dotted path.

    Booleans are excluded despite being numbers in Python: a True that arithmetic turns into
    1.0 would be differenced against a False and reported as a movement of one unit.
    """
    out: dict[str, float] = {}
    for key, value in record.items():
        path = f"{prefix}{key}"
        if isinstance(value, Mapping):
            out.update(flatten(value, f"{path}."))
        elif isinstance(value, bool):
            continue
        elif isinstance(value, int | float):
            out[path] = float(value)
    return out


def rows_for_axis(rows: Mapping[str, float], axis: str) -> dict[str, float]:
    """The rows an axis owns: those whose dotted path starts with it, else every row.

    Falling back to every row is deliberate. An unrecognised axis should make the transforms
    look at MORE, not less — a damage check narrowed to nothing would report a clean sheet.
    """
    owned = {name: value for name, value in rows.items() if name.split(".")[0] == axis}
    return owned or dict(rows)


def _direction(winner: float, baseline: float) -> int:
    """+1 when the winner's row is higher, -1 when lower, 0 when they are equal."""
    if winner > baseline:
        return 1
    if winner < baseline:
        return -1
    return 0


# ---------------------------------------------------------------------------------- the checks


def damage_survival(
    winner: Draw, axis: str, measures: ma.Measures, baseline: Draw | None
) -> CheckResult:
    """Does the win survive the winning draw's own paragraph shuffle?

    With a baseline the test needs no threshold: shuffle the winner, re-measure, and ask
    whether each row still moves away from the baseline in the same direction it did before.
    A row that does is a row the ordering of the story did not produce.

    With no baseline the only threshold-free statement left is exact invariance, so the check
    fires on rows the shuffle does not move at all and reports the rest as numbers.
    """
    shuffled = damage(winner.text)
    if shuffled == winner.text:
        return CheckResult(
            check="damage_survival", axis=axis, fired=None, numbers={}, basis=SURVIVAL_BASIS,
            note="too few paragraphs to displace; an unmoved damage arm is no control",
        )
    intact_rows = rows_for_axis(flatten(measures.of(winner.text)), axis)
    shuffled_rows = rows_for_axis(flatten(measures.of(shuffled)), axis)
    detail: dict[str, Any] = {}
    survived: list[str] = []
    if baseline is None:
        for name, value in intact_rows.items():
            after = shuffled_rows.get(name)
            detail[name] = {"intact": value, "shuffled": after}
            if after is not None and after == value:
                survived.append(name)
        note = "no baseline: fires only on rows the shuffle leaves exactly unchanged"
    else:
        base_rows = rows_for_axis(flatten(measures.of(baseline.text)), axis)
        for name, value in intact_rows.items():
            base = base_rows.get(name)
            after = shuffled_rows.get(name)
            if base is None or after is None:
                detail[name] = {"intact": value, "shuffled": after, "baseline": base}
                continue
            won = _direction(value, base)
            still = _direction(after, base)
            detail[name] = {
                "intact": value, "shuffled": after, "baseline": base,
                "margin": value - base, "shuffled_margin": after - base,
            }
            if won != 0 and still == won:
                survived.append(name)
        note = ""
    return CheckResult(
        check="damage_survival", axis=axis, fired=bool(survived),
        numbers={"rows": detail, "survived_rows": sorted(survived)},
        basis=SURVIVAL_BASIS, note=note,
    )


SURVIVAL_BASIS = (
    "a row that still moves the winning way after the winning draw's own paragraphs are "
    "shuffled is measuring surface rather than story"
)


def sham_separation(
    winner: Draw, axis: str, measures: ma.Measures, baseline: Draw | None
) -> CheckResult:
    """How far do two windows of the SAME draw separate on these rows?

    The same draw cannot be better than itself, so the sham separation is a floor under what
    counts as a real margin. Fires when a row separates two windows of one draw by at least as
    much as it separated the winner from its baseline: that row's margin is inside its own
    position-and-format noise.
    """
    windows = sham_windows(winner.text)
    if windows is None:
        return CheckResult(
            check="sham_separation", axis=axis, fired=None, numbers={}, basis=SHAM_BASIS,
            note="no distinct second window; a byte-identical sham is no control (§120.2)",
        )
    first_rows = rows_for_axis(flatten(measures.of(windows[0])), axis)
    second_rows = rows_for_axis(flatten(measures.of(windows[1])), axis)
    base_rows: dict[str, float] = {}
    winner_rows: dict[str, float] = {}
    if baseline is not None:
        base_rows = rows_for_axis(flatten(measures.of(baseline.text)), axis)
        winner_rows = rows_for_axis(flatten(measures.of(winner.text)), axis)
    detail: dict[str, Any] = {}
    swamped: list[str] = []
    for name, value in first_rows.items():
        other = second_rows.get(name)
        if other is None:
            continue
        sham_delta = abs(value - other)
        entry: dict[str, Any] = {"window_a": value, "window_b": other, "sham_delta": sham_delta}
        if name in base_rows and name in winner_rows:
            margin = abs(winner_rows[name] - base_rows[name])
            entry["real_margin"] = margin
            # A row with no margin is not a win being defended, so it cannot be swamped:
            # reporting `0 >= 0` as a swamped row would fill the check with rows on which the
            # two arms simply agreed.
            if margin > 0 and sham_delta >= margin:
                swamped.append(name)
        detail[name] = entry
    if baseline is None:
        return CheckResult(
            check="sham_separation", axis=axis, fired=None, numbers={"rows": detail},
            basis=SHAM_BASIS,
            note="no baseline: the sham separation is reported, with no margin to compare it to",
        )
    return CheckResult(
        check="sham_separation", axis=axis, fired=bool(swamped),
        numbers={"rows": detail, "swamped_rows": sorted(swamped)}, basis=SHAM_BASIS,
    )


SHAM_BASIS = (
    "a row that separates two windows of one draw by as much as it separated the winner from "
    "its baseline has a margin inside its own position-and-format noise"
)


def _cadence_split(text: str) -> tuple[int, int, int]:
    """(furniture events, prose-anchored events, words) for one text."""
    events = progression_cadence.locate(text, version=ma.MEASURE_VERSION)
    furniture = sum(1 for event in events if event.family in ma.FURNITURE_FAMILIES)
    return furniture, len(events) - furniture, len(text.split())


def _per_1k(count: int, words: int) -> float:
    return (count * 1000 / words) if words else 0.0


def furniture_spam(winner: Draw, axis: str, baseline: Draw | None) -> CheckResult:
    """A cadence or diegesis gain carried by status furniture rather than by prose.

    The degenerate maximum for a progression-cadence row is to print more status blocks: the
    event count rises, the reading experience does not. The decomposition separates the two —
    events located inside a furniture run against events a sentence of prose had to make — and
    fires when the total rose, the furniture component rose, and the prose-anchored component
    did not. No threshold: three signs.

    With no baseline the only threshold-free extreme is a draw whose every located event is
    furniture, so that is what it fires on, and the share is reported either way.
    """
    win_furn, win_prose, win_words = _cadence_split(winner.text)
    numbers: dict[str, Any] = {
        "winner_furniture_per_1k": _per_1k(win_furn, win_words),
        "winner_prose_anchored_per_1k": _per_1k(win_prose, win_words),
        "winner_furniture_share": (
            win_furn / (win_furn + win_prose) if (win_furn + win_prose) else None
        ),
    }
    if baseline is None:
        share = numbers["winner_furniture_share"]
        return CheckResult(
            check="furniture_spam", axis=axis,
            fired=(share == 1.0 and win_furn > 0), numbers=numbers, basis=FURNITURE_BASIS,
            note="no baseline: fires only where every located event is furniture",
        )
    base_furn, base_prose, base_words = _cadence_split(baseline.text)
    numbers.update({
        "baseline_furniture_per_1k": _per_1k(base_furn, base_words),
        "baseline_prose_anchored_per_1k": _per_1k(base_prose, base_words),
    })
    total_rose = _per_1k(win_furn + win_prose, win_words) > _per_1k(
        base_furn + base_prose, base_words
    )
    furniture_rose = numbers["winner_furniture_per_1k"] > numbers["baseline_furniture_per_1k"]
    prose_flat = (
        numbers["winner_prose_anchored_per_1k"] <= numbers["baseline_prose_anchored_per_1k"]
    )
    numbers.update(
        {"total_rose": total_rose, "furniture_rose": furniture_rose, "prose_flat": prose_flat}
    )
    return CheckResult(
        check="furniture_spam", axis=axis,
        fired=total_rose and furniture_rose and prose_flat,
        numbers=numbers, basis=FURNITURE_BASIS,
    )


FURNITURE_BASIS = (
    "the cadence gain decomposes into status furniture while the events a sentence of prose "
    "had to make did not rise"
)


def _system_density(text: str) -> tuple[float, float | None]:
    """(system mentions per 1,000 words, system share of anchored mentions)."""
    measured = number_context.measure(text, version=ma.MEASURE_VERSION)
    return measured.per_1k(measured.system_any), measured.system_share_of_anchored


def checklist_stuffing(
    winner: Draw, axis: str, baseline: Draw | None, family: Sequence[Draw] = ()
) -> CheckResult:
    """System-noun density run up until the page is a checklist.

    Two forms, and the comparative one is the one to trust. **Comparative** (no constant): the
    system density rose against the baseline while the mundane anchors it should sit among did
    not — the share of anchored mentions that are system mentions rose. **Outlier** (uses the
    screening constant `MAD_K`): the winner is the family maximum and sits above
    median + MAD_K x MAD of the draw family. The outlier form runs only at `MIN_FAMILY`
    members or more and is reported beside the constant it used, so a reader can discount it.
    """
    win_density, win_share = _system_density(winner.text)
    numbers: dict[str, Any] = {
        "winner_system_per_1k": win_density,
        "winner_system_share_of_anchored": win_share,
    }
    fired = False
    notes: list[str] = []

    if baseline is not None:
        base_density, base_share = _system_density(baseline.text)
        numbers.update({
            "baseline_system_per_1k": base_density,
            "baseline_system_share_of_anchored": base_share,
        })
        if win_share is not None and base_share is not None:
            comparative = win_density > base_density and win_share > base_share
            numbers["comparative_fired"] = comparative
            fired = fired or comparative
        else:
            notes.append("comparative form: nothing anchored on one side, so no share to compare")
    else:
        notes.append("comparative form: no baseline")

    densities = [_system_density(draw.text)[0] for draw in family]
    if len(densities) >= MIN_FAMILY:
        median = statistics.median(densities)
        mad = statistics.median([abs(value - median) for value in densities])
        cutoff = median + MAD_K * mad
        outlier = win_density >= max(densities) and win_density > cutoff
        numbers.update({
            "family_n": len(densities), "family_median": median, "family_mad": mad,
            "screening_cutoff": cutoff, "screening_constant_MAD_K": MAD_K,
            "outlier_fired": outlier,
        })
        fired = fired or outlier
    else:
        numbers["family_n"] = len(densities)
        notes.append(f"outlier form: family of {len(densities)} is under MIN_FAMILY={MIN_FAMILY}")

    ran = "comparative_fired" in numbers or "outlier_fired" in numbers
    return CheckResult(
        check="checklist_stuffing", axis=axis, fired=fired if ran else None,
        numbers=numbers, basis=CHECKLIST_BASIS, note="; ".join(notes),
    )


CHECKLIST_BASIS = (
    "system nouns crowd out the mundane anchors they should sit among, or the draw is a "
    "density outlier against its own family"
)


def staccato_monotony(winner: Draw, axis: str, baseline: Draw | None) -> CheckResult:
    """A sentence-length win bought by writing every sentence the same length.

    The degenerate maximum for a sentence-statistics row is uniform short sentences. The
    decomposition: the mean fell (the row moved the way a shorter-sentence rule rewards) AND
    the coefficient of variation fell with it (the writing stopped varying). A real
    improvement moves the mean without flattening the distribution, so the two signs together
    are the signature and neither alone fires.
    """
    win_lengths = ma.sentence_lengths(winner.text)
    numbers: dict[str, Any] = {
        "winner_sentences": len(win_lengths),
        "winner_mean_words": statistics.fmean(win_lengths) if win_lengths else None,
        "winner_length_cv": ma.length_cv(winner.text),
    }
    if baseline is None:
        return CheckResult(
            check="staccato_monotony", axis=axis, fired=None, numbers=numbers,
            basis=STACCATO_BASIS,
            note="no baseline: a variance collapse is only visible as a movement",
        )
    base_lengths = ma.sentence_lengths(baseline.text)
    numbers.update({
        "baseline_sentences": len(base_lengths),
        "baseline_mean_words": statistics.fmean(base_lengths) if base_lengths else None,
        "baseline_length_cv": ma.length_cv(baseline.text),
    })
    win_cv, base_cv = numbers["winner_length_cv"], numbers["baseline_length_cv"]
    win_mean, base_mean = numbers["winner_mean_words"], numbers["baseline_mean_words"]
    if None in (win_cv, base_cv, win_mean, base_mean):
        return CheckResult(
            check="staccato_monotony", axis=axis, fired=None, numbers=numbers,
            basis=STACCATO_BASIS, note="under two sentences on one side; no variance to compare",
        )
    mean_fell = win_mean < base_mean
    cv_fell = win_cv < base_cv
    numbers.update({"mean_fell": mean_fell, "cv_fell": cv_fell})
    return CheckResult(
        check="staccato_monotony", axis=axis, fired=mean_fell and cv_fell,
        numbers=numbers, basis=STACCATO_BASIS,
    )


STACCATO_BASIS = (
    "the sentence mean fell and the variation fell with it: the row moved because the writing "
    "stopped varying, not because it got shorter where shortness earned it"
)


def opening_repetition(winner: Draw, axis: str, baseline: Draw | None) -> CheckResult:
    """Sentences that all start the same way — the other staccato maximum.

    A separate check from `staccato_monotony` because it is a separate defect with a separate
    number: length can vary perfectly while every sentence opens on the same pronoun. Fires
    when the most repeated opening word's share rose against the baseline.
    """
    win_share = ma.top_opening_share(winner.text)
    numbers: dict[str, Any] = {"winner_top_opening_share": win_share}
    if baseline is None:
        return CheckResult(
            check="opening_repetition", axis=axis, fired=None, numbers=numbers,
            basis=OPENING_BASIS, note="no baseline: a repetition spike is a movement",
        )
    base_share = ma.top_opening_share(baseline.text)
    numbers["baseline_top_opening_share"] = base_share
    if win_share is None or base_share is None:
        return CheckResult(
            check="opening_repetition", axis=axis, fired=None, numbers=numbers,
            basis=OPENING_BASIS, note="no prose sentences on one side",
        )
    return CheckResult(
        check="opening_repetition", axis=axis, fired=win_share > base_share,
        numbers=numbers, basis=OPENING_BASIS,
    )


OPENING_BASIS = "a larger share of prose sentences open on the same single word"


def cast_starvation(winner: Draw, axis: str, baseline: Draw | None) -> CheckResult:
    """A cast-count win bought by emptying the page of people.

    "Too many names" is a real recurring family, so a cast row rewards fewer of them — and its
    degenerate maximum is a chapter with nobody in it. Fires when the distinct proper-noun
    count fell while the word count did not: the page did not get tighter, it got emptier.
    """
    win_names = len(register_census.proper_nouns(winner.text))
    numbers: dict[str, Any] = {"winner_proper_nouns": win_names, "winner_words": winner.words}
    if baseline is None:
        return CheckResult(
            check="cast_starvation", axis=axis, fired=None, numbers=numbers, basis=CAST_BASIS,
            note="no baseline: an emptied page is only visible against a fuller one",
        )
    base_names = len(register_census.proper_nouns(baseline.text))
    numbers.update({"baseline_proper_nouns": base_names, "baseline_words": baseline.words})
    names_fell = win_names < base_names
    words_held = winner.words >= baseline.words
    numbers.update({"names_fell": names_fell, "words_held": words_held})
    return CheckResult(
        check="cast_starvation", axis=axis, fired=names_fell and words_held,
        numbers=numbers, basis=CAST_BASIS,
    )


CAST_BASIS = (
    "the distinct proper-noun count fell while the word count did not: the page got emptier "
    "rather than tighter"
)


def word_dilution(
    winner: Draw, axis: str, measures: ma.Measures, baseline: Draw | None
) -> CheckResult:
    """Any per-1k row improved by inflating the denominator rather than fixing the numerator.

    The one degenerate maximum that belongs to every density row whatever it counts: write
    more words and every per-1,000-word count falls. Fires on rows where the density fell, the
    raw count did NOT fall, and the word count rose. Three signs, no threshold, and it applies
    to em dashes, glosses and system nouns alike.
    """
    if baseline is None:
        return CheckResult(
            check="word_dilution", axis=axis, fired=None, numbers={"winner_words": winner.words},
            basis=DILUTION_BASIS, note="no baseline: dilution is a movement of the denominator",
        )
    win_rows = rows_for_axis(flatten(measures.of(winner.text)), axis)
    base_rows = rows_for_axis(flatten(measures.of(baseline.text)), axis)
    words_rose = winner.words > baseline.words
    detail: dict[str, Any] = {}
    diluted: list[str] = []
    for name, count in win_rows.items():
        base_count = base_rows.get(name)
        if base_count is None or name.endswith(("words", "count", "_n")):
            continue
        win_density = _per_1k(int(count), winner.words) if count == int(count) else None
        base_density = (
            _per_1k(int(base_count), baseline.words) if base_count == int(base_count) else None
        )
        if win_density is None or base_density is None:
            continue
        entry = {
            "winner_count": count, "baseline_count": base_count,
            "winner_per_1k": win_density, "baseline_per_1k": base_density,
        }
        detail[name] = entry
        if words_rose and win_density < base_density and count >= base_count:
            diluted.append(name)
    return CheckResult(
        check="word_dilution", axis=axis, fired=bool(diluted),
        numbers={
            "winner_words": winner.words, "baseline_words": baseline.words,
            "words_rose": words_rose, "rows": detail, "diluted_rows": sorted(diluted),
        },
        basis=DILUTION_BASIS,
    )


DILUTION_BASIS = (
    "the per-1,000-word rate fell while the raw count did not, on a draw that simply got "
    "longer: the denominator moved, not the writing"
)


# ------------------------------------------------------------------------------- the battery


@dataclass(frozen=True, slots=True)
class BatteryReport:
    """One variant's battery: what was checked, what fired, and the numbers behind each.

    Deliberately carries no aggregate and no overall outcome. Whether a fired check rejects a
    variant is the harness's and the coordinator's decision under the direction note's binding
    rule; this record's whole job is to be the evidence that decision reads.
    """

    variant: str
    axis: str
    axis_recognised: bool
    measures_source: str
    baseline: str | None
    family: tuple[str, ...]
    results: tuple[CheckResult, ...]
    preference: dict[str, Any] = field(default_factory=dict)

    @property
    def fired(self) -> tuple[str, ...]:
        return tuple(r.check for r in self.results if r.fired)

    @property
    def not_run(self) -> tuple[str, ...]:
        return tuple(r.check for r in self.results if r.fired is None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "axis": self.axis,
            "axis_recognised": self.axis_recognised,
            "measures_source": self.measures_source,
            "baseline": self.baseline,
            "family": list(self.family),
            "preference": self.preference,
            "checks": [asdict(result) for result in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    def table(self) -> str:
        """The plain table: one line per check, its state, and its headline number."""
        state = {True: "FIRED", False: "clear", None: "not-run"}
        width = max((len(r.check) for r in self.results), default=5)
        lines = [f"{'check'.ljust(width)}  state    detail"]
        for result in self.results:
            headline = result.note or _headline(result.numbers)
            lines.append(f"{result.check.ljust(width)}  {state[result.fired]:<7}  {headline}")
        return "\n".join(lines)


def _headline(numbers: Mapping[str, Any]) -> str:
    """The scalar numbers of a result, comma-joined; nested row detail stays in the JSON."""
    parts = [
        f"{key}={value:.3g}" if isinstance(value, float) else f"{key}={value}"
        for key, value in numbers.items()
        if isinstance(value, int | float | bool) or value is None
    ]
    return ", ".join(parts) if parts else "see JSON"


#: Signature-dispatch for the checks. Each entry says exactly which inputs its check consumes,
#: so `run_battery` never has to know what any individual check needs.
PreferenceProbe = Callable[[str, str], dict[str, Any]]


def run_battery(
    winner: Draw,
    axis: str,
    *,
    baseline: Draw | None = None,
    family: Sequence[Draw] = (),
    measures: ma.Measures | None = None,
    preference: PreferenceProbe | None = None,
) -> BatteryReport:
    """Every check the axis calls for, against one provisional winner.

    `preference` is the panel probe, and it is optional because it is the only part of this
    battery that costs money: when it is supplied the intact draw and its shuffled copy go to
    the panel as the damage arm's paid half, and when it is not the report records that the
    preference half was not purchased rather than omitting it. Nothing in this module ever
    constructs a transport.

    Raises ValueError for a winner under `MIN_WORDS`: every variance statistic below degenerates
    on a text that short, and a battery that fires on its own fixture is worse than none.
    """
    if winner.words < MIN_WORDS:
        raise ValueError(
            f"draw {winner.draw_id!r} has {winner.words} words, under MIN_WORDS={MIN_WORDS}; "
            "variance statistics degenerate below this and the battery refuses rather than "
            "reporting its own fixture"
        )
    resolved = measures or ma.load_measures()
    names, recognised = checks_for_axis(axis)
    results: list[CheckResult] = []
    for name in names:
        if name == "damage_survival":
            results.append(damage_survival(winner, axis, resolved, baseline))
        elif name == "sham_separation":
            results.append(sham_separation(winner, axis, resolved, baseline))
        elif name == "word_dilution":
            results.append(word_dilution(winner, axis, resolved, baseline))
        elif name == "furniture_spam":
            results.append(furniture_spam(winner, axis, baseline))
        elif name == "checklist_stuffing":
            results.append(checklist_stuffing(winner, axis, baseline, family))
        elif name == "staccato_monotony":
            results.append(staccato_monotony(winner, axis, baseline))
        elif name == "opening_repetition":
            results.append(opening_repetition(winner, axis, baseline))
        elif name == "cast_starvation":
            results.append(cast_starvation(winner, axis, baseline))
        else:  # pragma: no cover - AXIS_CHECKS and the dispatch are edited together
            raise KeyError(f"no dispatch for check {name!r}")

    probe: dict[str, Any] = {"purchased": False, "note": "panel preference not purchased"}
    if preference is not None:
        shuffled = damage(winner.text)
        probe = {"purchased": True, "damage_arm": preference(winner.text, shuffled)}

    return BatteryReport(
        variant=winner.draw_id, axis=axis, axis_recognised=recognised,
        measures_source=resolved.source,
        baseline=baseline.draw_id if baseline else None,
        family=tuple(draw.draw_id for draw in family),
        results=tuple(results), preference=probe,
    )
