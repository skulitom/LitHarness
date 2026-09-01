"""The one seam between the adversarial battery and whatever the scorecard turns out to be.

The per-draw scorecard is being built in a sibling track. This module exists so that the
adversarial battery can be written, tested and committed *before* that track lands, and can
then pick it up without an edit: `load_measures()` tries three sources in order and reports
which one answered, so a battery JSON always says what measured it.

1. ``scorecard`` — the eventual module, if it is importable and exposes ``battery(text)``.
2. ``chapter_measures`` — the substrate the scorecard track is building the scorecard on top
   of, same call shape.
3. The local fallback below, built from the instruments already in the repository
   (`progression_cadence`, `number_context`, `register_census`) plus plain text statistics.

**The fallback is not a second scorecard and must never become one.** It computes the few
quantities the degeneracy checks need to decompose a win, nothing else, and it declares no
row the scorecard does not already intend to ship. When the scorecard lands, source 1 wins
and the fallback stops being used for anything but its own tests.

Nothing here is importable from ``src/litharness`` and nothing here reads a corpus: the input
is chapter text the caller already holds. RS1 is untouched because no corpus text enters and
no derived corpus digest leaves.
"""

from __future__ import annotations

import importlib
import itertools
import re
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_QM = HERE.parent / "quality-measurement"
for _path in (str(_QM), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import number_context  # noqa: E402  # sibling research module, imported by path
import progression_cadence  # noqa: E402  # sibling research module, imported by path
import register_census  # noqa: E402  # sibling research module, imported by path

#: Modules tried, in order, before the local fallback. Names only — a missing module is the
#: ordinary case today, not an error.
SCORECARD_MODULES: tuple[str, ...] = ("scorecard", "chapter_measures")

#: The version of the instrument block the checks read. `v2` is the one that recognises our
#: own page contract (§189: v0 was scoring our own status lines at zero), and a degeneracy
#: check that cannot see our furniture is a check that cannot fire on furniture spam.
MEASURE_VERSION = "v2"

_SENTENCE = re.compile(r"(?<=[.!?])[\s\"']+|\n+")
_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

#: Families `progression_cadence.locate` attributes to a run of furniture lines rather than to
#: a move made in prose. Kept as a set of one so the distinction is named where it is used.
FURNITURE_FAMILIES: frozenset[str] = frozenset({"system_block"})

#: The remaining cadence families: a move a sentence of prose had to make.
PROSE_ANCHORED_FAMILIES: frozenset[str] = (
    frozenset(progression_cadence.FAMILIES) - FURNITURE_FAMILIES
)


@dataclass(frozen=True, slots=True)
class Measures:
    """A battery callable plus the name of whatever supplied it."""

    source: str
    battery: Callable[[str], dict[str, Any]]

    def of(self, text: str) -> dict[str, Any]:
        return self.battery(text)


def load_measures(prefer: str | None = None) -> Measures:
    """The first importable battery, else the local fallback. Never raises for absence.

    `prefer` names a module to try ahead of `SCORECARD_MODULES`, which is how a test pins the
    source. A module that imports but exposes no `battery` callable is skipped rather than
    half-used: a partial scorecard would produce rows whose absence the checks would read as
    a number.
    """
    for name in ((prefer,) if prefer else ()) + SCORECARD_MODULES:
        if name is None:
            continue
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        battery = getattr(module, "battery", None)
        if callable(battery):
            return Measures(source=name, battery=battery)
    return Measures(source="local-fallback", battery=local_battery)


# ------------------------------------------------------------------------- the local fallback


def sentence_lengths(text: str) -> list[int]:
    """Word counts of the prose sentences, furniture lines already removed.

    Furniture is dropped first because a status sheet is not a sentence and counting it as a
    two-word one is how a sentence-length statistic learns to reward stuffing.
    """
    prose = progression_cadence.prose_only(text, version=MEASURE_VERSION)
    return [len(piece.split()) for piece in _SENTENCE.split(prose) if piece.strip()]


def opening_words(text: str) -> list[str]:
    """The first word of each prose sentence, lowercased; the repeated-opening substrate."""
    prose = progression_cadence.prose_only(text, version=MEASURE_VERSION)
    openings: list[str] = []
    for piece in _SENTENCE.split(prose):
        found = _WORD.search(piece)
        if found:
            openings.append(found.group(0).lower())
    return openings


def top_opening_share(text: str) -> float | None:
    """Share of prose sentences that open on the single most repeated first word.

    None when there are no sentences: a share of an empty set is not zero, and reporting it as
    zero would make an empty chapter look maximally varied.
    """
    openings = opening_words(text)
    if not openings:
        return None
    counts: dict[str, int] = {}
    for word in openings:
        counts[word] = counts.get(word, 0) + 1
    return max(counts.values()) / len(openings)


def length_cv(text: str) -> float | None:
    """Coefficient of variation of prose sentence length, or None under two sentences.

    A CV rather than a standard deviation because the check compares two drafts of different
    mean length, and a raw deviation falls whenever the mean does.
    """
    lengths = sentence_lengths(text)
    if len(lengths) < 2:
        return None
    mean = statistics.fmean(lengths)
    if not mean:
        return None
    return statistics.pstdev(lengths) / mean


def gap_statistics(events: Sequence[Any], words: int) -> dict[str, float | None]:
    """Where the events fall and how evenly they are spaced — the order-sensitive rows.

    `first_event_fraction` is how far into the chapter the first progression event lands, and
    `gap_cv` is how regular the spacing is. Both are taken from `progression_cadence.measure`'s
    own definitions so a row here and a row on the census mean the same thing. None whenever
    there are too few events to define them; a chapter with one event has no spacing, and
    reporting that as zero would make it look perfectly even.
    """
    offsets = [event.word_offset for event in events]
    gaps = [b - a for a, b in itertools.pairwise(offsets)]
    median_gap = statistics.median(gaps) if gaps else None
    gap_cv: float | None = None
    if len(gaps) >= 2:
        mean_gap = statistics.fmean(gaps)
        gap_cv = (statistics.pstdev(gaps) / mean_gap) if mean_gap else None
    return {
        "first_event_fraction": (offsets[0] / words) if offsets and words else None,
        "median_gap": median_gap,
        "gap_cv": gap_cv,
    }


def local_battery(text: str) -> dict[str, Any]:
    """The quantities the degeneracy checks decompose a win into. Descriptive rows only.

    No aggregate is computed here and none may be added: every value is one instrument's count
    or one plain statistic, and the checks combine them only by comparing signs across drafts.
    """
    cadence = progression_cadence.locate(text, version=MEASURE_VERSION)
    numbers = number_context.measure(text, version=MEASURE_VERSION)
    lengths = sentence_lengths(text)
    words = len(text.split())
    furniture = sum(1 for event in cadence if event.family in FURNITURE_FAMILIES)
    gaps = gap_statistics(cadence, words)
    return {
        "words": words,
        "prose_words": len(progression_cadence.prose_only(text, version=MEASURE_VERSION).split()),
        "cadence": {
            "events": len(cadence),
            "furniture_events": furniture,
            "prose_anchored_events": len(cadence) - furniture,
            # The order-sensitive rows, and the reason they are here. Counting rows survive a
            # paragraph shuffle by construction — the same paragraphs, reordered, hold the same
            # number of anything — so a damage arm run against counts alone can only ever report
            # that everything survived. Where an event FALLS in the chapter, and how evenly the
            # events are spaced, are the quantities a shuffle actually destroys.
            **gaps,
        },
        "numbers": {
            "mentions": numbers.mentions,
            "system_any": numbers.system_any,
            "anchored": numbers.anchored,
            "system_share_of_anchored": numbers.system_share_of_anchored,
        },
        "sentences": {
            "count": len(lengths),
            "mean_words": statistics.fmean(lengths) if lengths else None,
            "length_cv": length_cv(text),
            "top_opening_share": top_opening_share(text),
        },
        "gloss": dict(register_census.gloss_counts(text)),
        "cast": {"proper_nouns": len(register_census.proper_nouns(text))},
        "em_dash": text.count("—"),
    }
