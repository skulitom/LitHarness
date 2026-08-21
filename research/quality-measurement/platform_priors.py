"""Royal Road platform claims as dose-response manipulation families (D1P).

**Every family here is a hypothesis, never a rule.** An author in the platform's top ~1% told
the operator what sells on Royal Road; the claims were distilled on 2026-08-21 and are recorded
in `plan/royalroad-platform-priors.md` with a stage-0 entry at §104. This module turns the
load-bearing ones into manipulations of *our own generated prose*, so a budgeted reader can be
asked what each one does to allocation. A null is a result and is recorded as one; nothing below
is ever compiled into a drafting directive by this module.

**Why these are D1P and not D1, and the distinction is the whole design.** `bcr.D1_FAMILIES` is
*certified damage* — paragraph shuffle, matched deletion, stat flatten, interiority strip —
whose sign nobody disputes, which is why a dose-response inversion there kills **the
instrument**. Nothing here is certified damage. "Lyrical prose is a liability on this platform"
is a claim about a readership, and the manipulation's sign is exactly what is under test. So:

    D1   certified damage      an inversion kills the INSTRUMENT   runs first, seats the reader
    D1P  platform priors       an inversion kills the FAMILY       runs second, on a seated model

A D1P family may only be read on a model that has already passed §A2 seating and D1 on certified
damage. Read the other way round the two are indistinguishable: a family that moves nothing
could be a false claim or a blind reader, and there would be no way to tell which.

**The lanes, and why a manipulation gets one or the other.**

    blend    the model rewrites the whole scene under one instruction, paragraph-aligned;
             a dose takes the first `k` *changed* paragraphs from the rewrite, front-first,
             nested (0.15's set is inside 0.35's is inside 0.65's is inside 1.0's)
    insert   the model writes `K` new paragraphs; a dose inserts the first `k` of them at
             declared boundaries, and the original prose survives byte-for-byte

Dose grows **from the front** because every claim in this set is about the opening — chapters
one and two, the browse funnel, early wins. A dose that damaged the middle first would be a
different manipulation from the one the claims describe.

**The placebo is not optional and it is the ruler.** `platform_placebo` runs the same paragraph
contract with an inert instruction (fix any typos). Whatever a revision pass does on its own —
drift, house-style creep, unprompted improvement — shows up there, and no family certifies
except against it: a family must change more than the placebo changed, and must move its own
frozen signature counter further than the placebo moved it. That is `repair_generation.py`'s
floor discipline, reused rather than reinvented.

**Own-generated substrate only** (BRIEF §2 Pass 6): a scoring model's familiarity with published
text swings a model-based measure harder than real damage does, so the substrate is
`corpora/toll-scenes.json` — this system's own prose, un-memorised by construction. **RS1
holds**: no anchor or contrast text enters this module in any direction, and nothing this module
produces may enter a drafting, revision or planning prompt.

The signature matchers, the dose ladders, the insert names and the generation tasks are frozen
**above** the first call and covered by `registration_digest()`. A matcher written after reading
the rewrites would be fitted to its own output, which is the failure
`cadence_discrimination.CADENCE_MATCHER` is frozen to prevent one module over.

    uv run python research/quality-measurement/platform_priors.py --selftest
    uv run python research/quality-measurement/platform_priors.py --plan
    uv run python research/quality-measurement/platform_priors.py --generate --yes
    uv run python research/quality-measurement/platform_priors.py --certify
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
from authorship_tells import features, strip_system  # noqa: E402
from elicit import digest  # noqa: E402
from writer_states import Generator, system_voice_survival  # noqa: E402

RESULTS = HERE / "results"
SCENES = HERE / "corpora" / "toll-scenes.json"

#: Bumped whenever anything the pre-registration covers changes. A result file carrying a
#: different version is a different instrument and its numbers are not comparable.
PLATFORM_VERSION = "platform-priors-v0"

#: The dose ladder, `bcr.DOSES` restated so this module does not import a 1,600-line battery to
#: read four floats. `selftest` asserts the two are equal, so a divergence fails before a call.
DOSES: tuple[float, ...] = (0.15, 0.35, 0.65, 1.0)

#: Minimum changed paragraphs a blend rewrite must produce for the ladder to have four distinct
#: rungs. Below this the top doses collapse onto each other and the family has no dose-response
#: to show — recorded as a fault rather than served as a shelf whose rungs are duplicates.
MIN_ELIGIBLE = len(DOSES)

#: Insert ladders, explicit rather than computed. `round(dose * K)` collapses two rungs onto one
#: at every K this family set wants (0.35 x 4 rounds to 1, the same as 0.15 x 4), and a ladder
#: whose middle rungs are the same manipulation is a dose-response study with three doses
#: wearing four labels.
FLOOD_LADDER: dict[float, int] = {0.15: 1, 0.35: 2, 0.65: 4, 1.0: 6}
POV_LADDER: dict[float, int] = {0.15: 1, 0.35: 2, 0.65: 3, 1.0: 4}

#: Names the flood arm introduces, frozen so certification can count them rather than guess at
#: what a proper noun is. Invented, generic-fantasy, and checked against the host scene: a name
#: the scene already uses is a fault, because then the arm is not introducing a new character.
FLOOD_NAMES: tuple[str, ...] = (
    "Halveth Orne", "Kessa Dray", "Marrow Fen", "Ilbrec Sant", "Nuala Whitt", "Tarrin Coble",
)

#: The second point of view the fragment arm interleaves. One name, so every fragment is the
#: same head and the manipulation is "a second POV" rather than "several".
POV_NAME = "Sedra Coyle"

# ------------------------------------------------------------------- frozen signature matchers
#
# Each family owns exactly one counter that must move in a declared direction for a rewrite to
# certify. They live here, above the tasks, because a counter chosen after reading a rewrite is a
# rubric fitted to its own answers. Everything else in `panel()` is reported and in no bar.

_SIMILE = re.compile(r"\b(?:like a|like the|as if|as though)\b", re.IGNORECASE)
_WIN = re.compile(
    r"\b(?:won|wins|winning|succeed\w*|success\w*|managed to|earned|gained|profit\w*|"
    r"solved|saved|right about|correct|worked|paid off|impress\w*)\b",
    re.IGNORECASE,
)
_SETBACK = re.compile(
    r"\b(?:failed|failure|fails|lost|loses|losing|mistak\w*|wrong|humiliat\w*|shame\w*|"
    r"mock\w*|jeer\w*|sneer\w*|laughed at|refused|denied|ruin\w*|worse|beaten|useless|"
    r"worthless)\b",
    re.IGNORECASE,
)
_EXPOSITION = re.compile(
    r"\b(?:had (?:been|once|always|long)|years (?:earlier|before|ago)|ever since|"
    r"long before|it was said|the reason (?:was|for)|which meant|in those days|by tradition|"
    r"the history of|was known (?:as|for)|originally|had come to be|for centuries)\b",
    re.IGNORECASE,
)
_PRESENT_AUX = re.compile(r"\b(?:is|are|am|has|have|does|do|isn't|aren't)\b", re.IGNORECASE)
_PAST_AUX = re.compile(r"\b(?:was|were|had|did|wasn't|weren't|hadn't|didn't)\b", re.IGNORECASE)


def _per_1k(pattern: re.Pattern[str], text: str) -> float:
    return 1000.0 * len(pattern.findall(text)) / max(len(text.split()), 1)


def lyric_index(text: str) -> float:
    """Purple-prose signature: similes, -ly adverbs and participial openings, per 1k words.

    Three structural counts rather than a word list, deliberately. A lexicon of "purple" words
    would be a list of the words this module's own prompt tends to produce, and the counter
    would then be measuring the prompt. Simile density, adverb density and front-loaded
    participles are properties of *sentence shape* that a lyricalising rewrite moves whatever
    vocabulary it reaches for.
    """
    surface = features(text)
    return round(
        surface["adverb_ly_per_1k"] + surface["participle_open_per_1k"] + _per_1k(_SIMILE, text),
        3,
    )


def panel(text: str) -> dict[str, float]:
    """Every counter, reported per variant. Only the family's own signature is ever a bar.

    The others ride along as the cross-contamination readout: a suffering rewrite that also
    tripled the simile rate has changed two things, and a family that certifies while moving
    another family's signature further than its own is an ambiguous manipulation. Reported
    beside the verdict, never folded into it — `bcr`'s tripwire-panel discipline at variant
    grain.
    """
    stripped = strip_system(text)
    surface = features(stripped)
    return {
        "lyric_index": lyric_index(stripped),
        "setback_per_1k": round(_per_1k(_SETBACK, stripped), 3),
        "win_per_1k": round(_per_1k(_WIN, stripped), 3),
        "exposition_per_1k": round(_per_1k(_EXPOSITION, stripped), 3),
        "present_aux_per_1k": round(_per_1k(_PRESENT_AUX, stripped), 3),
        "past_aux_per_1k": round(_per_1k(_PAST_AUX, stripped), 3),
        "dialogue_ratio": round(surface["dialogue_ratio"], 4),
        "em_per_1k": round(surface["em_per_1k"], 3),
        "interior_per_1k": round(surface["interior_per_1k"], 3),
        "words": float(len(text.split())),
    }


# --------------------------------------------------------------------------------- the families


@dataclass(frozen=True, slots=True)
class Family:
    """One platform claim, as a manipulation with a pre-registered reading.

    `confirms`, `refutes` and `null` are three outcomes named before the first session, so that
    whichever one arrives it was already a declared result rather than a story told afterwards.
    `kills` is the fourth and it is about the manipulation rather than about the claim.
    """

    key: str
    claim: str
    lane: str
    task: str
    signature: str
    signature_direction: str
    confirms: str
    refutes: str
    null: str
    kills: str
    cost: str


#: Paragraph-aligned rewrite contract. The alignment is what buys the dose ladder: with a 1:1
#: index map the changed set is *discovered* rather than requested, so a dose is a set of the
#: model's own edits and never a second instruction the model could read differently at each
#: rung.
BLEND_CONTRACT = """\
Return the scene as a numbered list of paragraphs. Emit every paragraph of the original, in the
original order, with the original count. Begin each one with [[n]] where n is that paragraph's
number in the original, counting from 1. Put each paragraph on one line.

Copy byte-for-byte, with no change of any kind: any paragraph the instruction below does not
reach, and every line in the system voice (**bold** announcements and [STATUS] blocks) wherever
it stands.

Return only the numbered list: no title, no preamble, no commentary.

Tonight's revision has one purpose:
{task}"""

#: Insert contract. The original is untouched by construction here, which is a stronger
#: certification than any blend family can offer: whatever the reader does with these shelves, it
#: is not reacting to prose that was rewritten out from under it.
INSERT_CONTRACT = """\
Below is a scene from a serialized novel you are drafting. Do not rewrite it.

Write {count} new paragraphs to be inserted into it. Begin each one with [[n]], numbered from 1,
each on one line. Each paragraph is two to four sentences, in the scene's own voice, tense and
person.

Return only the numbered list: no title, no preamble, no commentary.

{task}"""

AUTHOR_SYSTEM = (
    "You are the author of the scene below, midway through drafting a serialized LitRPG "
    "novel, returning tonight to revise your own pages."
)

PLACEBO = "platform_placebo"

FAMILIES: tuple[Family, ...] = (
    Family(
        key="purple_prose_dose",
        claim="RR3: literary/atmospheric prose that steals the show is a liability",
        lane="blend",
        task=(
            "Make the prose lyrical. Reach for extended imagery, simile, cadence and sensory "
            "dwelling; let a sentence take its time. Every event, its order, the point of view "
            "and every plot fact stay exactly as they are. Add no new facts. Leave spoken "
            "dialogue as it stands."
        ),
        signature="lyric_index",
        signature_direction="up",
        confirms="allocation against the lyrical side increases with dose",
        refutes=(
            "allocation against the *intact* side increases with dose — the platform claim "
            "does not hold on this reader and the general craft prior does"
        ),
        null="no monotone movement and the dose-1.0 interval contains 0.5",
        kills=(
            "an inversion (largest effect at dose 0.15, shrinking after) says the rung set is "
            "not a dose of one thing; the family is withdrawn, the instrument is untouched"
        ),
        cost=(
            "the two-sided reading is mandatory here: the platform claim and the general craft "
            "prior point in opposite directions, so a one-sided registration would have made "
            "one of the two answers unreportable"
        ),
    ),
    Family(
        key="suffering_load",
        claim="RR4: early MC torture/humiliation without adjacent triumphs bleeds readers",
        lane="blend",
        task=(
            "Wherever the scene gives him a win, a gain, or a moment of visible competence, "
            "give him a setback of the same size in the same place instead: he fails, loses, or "
            "is humiliated in front of someone. Keep the setting, the cast, the order of "
            "events, the point of view and the paragraph the change lands in. Do not compensate "
            "with a win anywhere else."
        ),
        signature="setback_per_1k",
        signature_direction="up",
        confirms="allocation against the setback-loaded side increases with dose",
        refutes=(
            "allocation toward the setback-loaded side increases with dose — early cost reads "
            "as stakes rather than as bleeding"
        ),
        null="no monotone movement and the dose-1.0 interval contains 0.5",
        kills="an inversion across the ladder withdraws the family",
        cost=(
            "inverting an outcome mid-scene can contradict what a later paragraph assumes, so "
            "at high dose this family carries a continuity defect the intact side does not. "
            "That is a confound with `paragraph_shuffle`'s territory and it is stated rather "
            "than designed away: the honest reading of a confirm here is 'setbacks *or* the "
            "incoherence they introduce', and separating the two needs a coherence-matched "
            "control this session does not build"
        ),
    ),
    Family(
        key="info_dump_dose",
        claim="RR1/RR3: info dumps and lecture-y openings kill trust in ch.1-2",
        lane="blend",
        task=(
            "Turn what the scene shows into what it explains. Where something happens on the "
            "page — an action, an exchange, a thing done — report it to the reader instead as "
            "background: history, rules, definitions, summary. Keep the same facts in the same "
            "order and add no new ones."
        ),
        signature="exposition_per_1k",
        signature_direction="up",
        confirms="allocation against the expository side increases with dose",
        refutes="allocation toward the expository side increases with dose",
        null="no monotone movement and the dose-1.0 interval contains 0.5",
        kills="an inversion across the ladder withdraws the family",
        cost=(
            "summary is shorter than scene, so this arm is the one most likely to change word "
            "count; `certify` records the ratio and the `words` row in the panel is where a "
            "length confound would show. §78's lesson is that a length-blind guard reports "
            "nothing"
        ),
    ),
    Family(
        key="character_flood",
        claim="RR1: many named characters at once in ch.1-2 is an amateur signal",
        lane="insert",
        task=(
            "Each paragraph introduces one new named character into the scene for the first "
            "time, with a name, a role and one distinguishing detail. Use these names, one per "
            "paragraph, in this order: {names}. Introduce and no more: nothing is resolved, no "
            "plot advances, nobody already in the scene changes."
        ),
        signature="named_introductions",
        signature_direction="up",
        confirms="allocation against the flooded side increases with the number of names",
        refutes="allocation toward the flooded side increases with the number of names",
        null="no monotone movement and the six-name interval contains 0.5",
        kills="an inversion across the ladder withdraws the family",
        cost=(
            "pure insertion, so the original survives byte-for-byte — but the arm adds words, "
            "and word count is the incumbent that correlates with everything (§1a.1). The "
            "length-matched control this family owes is `pov_fragment` at a matched insert "
            "budget, which adds comparable words and no new names"
        ),
    ),
    Family(
        key="pov_fragment",
        claim="RR6: multi-POV is hard mode; readers want one MC to root for",
        lane="insert",
        task=(
            "Each paragraph reports the same span of events from inside the head of {pov_name}, "
            "a second character present at or near them, in close third person and the scene's "
            "own tense. Name {pov_name} in every paragraph. Report what that character notices, "
            "wants and withholds; introduce no new events."
        ),
        signature="pov_paragraphs",
        signature_direction="up",
        confirms="allocation against the interleaved side rises with the number of fragments",
        refutes="allocation toward the interleaved side rises with the number of fragments",
        null="no monotone movement and the four-fragment interval contains 0.5",
        kills="an inversion across the ladder withdraws the family",
        cost=(
            "also pure insertion, and it doubles as `character_flood`'s length control: both "
            "add paragraphs to the same scenes, only one adds names"
        ),
    ),
    Family(
        key="tense_shift",
        claim="RR6: present tense is hard mode",
        lane="blend",
        task=(
            "Put the scene in the present tense. Change nothing else: the same words wherever "
            "tense does not force a change, the same sentences, the same paragraph breaks, the "
            "same person and point of view."
        ),
        signature="present_aux_per_1k",
        signature_direction="up",
        confirms="allocation against the present-tense side increases with dose",
        refutes="allocation toward the present-tense side increases with dose",
        null="no monotone movement and the dose-1.0 interval contains 0.5",
        kills="an inversion across the ladder withdraws the family",
        cost=(
            "**this family's ladder measures two different things and the registration says so "
            "before it runs.** At dose 1.0 the variant is a present-tense scene, which is the "
            "claim. At every dose below it part of the scene is present and the rest is past, "
            "which is *tense instability* — a different manipulation, and one nobody claimed "
            "anything about. So the confirmatory reading is the dose-1.0 interval, and the "
            "ladder is a shape reading about instability, reported under its own name"
        ),
    ),
)

BY_KEY: dict[str, Family] = {family.key: family for family in FAMILIES}

#: The inert arm. Not a `Family` because it has no claim, no direction and no shelf: it is the
#: ruler every family is measured against and it never reaches a reader.
PLACEBO_TASK = (
    "Correct any spelling or typographical errors you find. A paragraph that contains none is "
    "copied byte-for-byte. There may be nothing to correct."
)

ARMS: tuple[str, ...] = (*(family.key for family in FAMILIES), PLACEBO)

PRE_REGISTRATION: dict[str, Any] = {
    "version": PLATFORM_VERSION,
    "tier": "D1P",
    "runs_only_on": (
        "a model already seated under bcr §A2 and already through D1 on certified damage; read "
        "on an unseated model a null is indistinguishable from a blind reader"
    ),
    "substrate": "own-generated prose only (corpora/toll-scenes.json or --book-db)",
    "channel": (
        "behavioural (BCR allocation) only. No verdict slot, no preference leg, no rating. "
        "§89.4 stands at 4,676-to-1 and nothing here routes through it"
    ),
    "doses": list(DOSES),
    "flood_ladder": {str(key): value for key, value in FLOOD_LADDER.items()},
    "pov_ladder": {str(key): value for key, value in POV_LADDER.items()},
    "dose_grows": "from the front of the span; every claim in this set is about the opening",
    "nesting": "each dose's changed set contains the set below it, asserted by `certify`",
    "placebo": (
        "platform_placebo is the floor: a family certifies only if it changed more than the "
        "placebo changed and moved its own signature further than the placebo moved it"
    ),
    "reading": {
        "confirmatory": (
            "the top-rung shelf's clustered allocation interval, two-sided; confirm, refute and "
            "null are three pre-declared outcomes and each family names which is which"
        ),
        "shape": (
            "isotonic fit over the four rungs. At the declared six sessions per intermediate "
            "rung the per-point sd is about 0.16, so only a gross inversion is visible and no "
            "subtle non-monotonicity is claimed"
        ),
        "multiplicity": (
            "each family reports its own interval at alpha 0.05 and the six-family adjusted "
            "level 0.00833 prints beside it. Any sentence about the *set* uses the adjusted "
            "level; there is no pooled headline"
        ),
    },
    "kill_asymmetry": (
        "an inversion in D1P withdraws the FAMILY, never the instrument. BCR's licence comes "
        "from D1 on certified damage, and a false claim about a readership is not evidence "
        "about a reader"
    ),
    "signatures": {
        family.key: f"{family.signature} must move {family.signature_direction}"
        for family in FAMILIES
    },
    "rs1": "no anchor or contrast text enters or leaves this module in any direction",
    "generation_side": (
        "nothing this module produces may enter a drafting, revision or planning prompt; the "
        "variants exist to be read by an instrument and for nothing else"
    ),
}


def registration_digest() -> str:
    """Content address of the pre-registration, the tasks, the ladders and the matchers.

    Printed on every artifact. A result file whose digest differs from the module's is a result
    from a different instrument, and the check is one comparison rather than a diff of prose.
    """
    return digest(
        {
            "pre_registration": PRE_REGISTRATION,
            "families": [
                {
                    "key": family.key,
                    "lane": family.lane,
                    "task": family.task,
                    "signature": family.signature,
                    "direction": family.signature_direction,
                }
                for family in FAMILIES
            ],
            "placebo_task": PLACEBO_TASK,
            "blend_contract": BLEND_CONTRACT,
            "insert_contract": INSERT_CONTRACT,
            "system": AUTHOR_SYSTEM,
            "flood_names": list(FLOOD_NAMES),
            "pov_name": POV_NAME,
            "matchers": [
                _SIMILE.pattern, _WIN.pattern, _SETBACK.pattern,
                _EXPOSITION.pattern, _PRESENT_AUX.pattern, _PAST_AUX.pattern,
            ],
        }
    )


# ------------------------------------------------------------------------------- the mechanics


class ContractError(ValueError):
    """A generation that did not come back in the shape the contract asked for."""


class MissingVariant(LookupError):
    """A family was asked for a scene it has no usable generation for.

    Raised rather than returned-unchanged on purpose. `bcr.battery_shelves` drops a shelf whose
    two sides are identical, so a silent no-op would delete a family from a battery *mid-run* and
    the result file would read as though the family had been asked and had nothing to say. An
    unasked kill is not a passed one.
    """


_MARKER = re.compile(r"\[\[\s*(\d+)\s*\]\]")


def parse_numbered(raw: str) -> dict[int, str]:
    """Split a `[[n]]`-marked response into an index map.

    Segment-based rather than line-based: a model that wraps one paragraph over two lines is
    obeying the contract in substance, and a line-splitting parser would report a contract
    failure that is really a newline. Everything between one marker and the next belongs to it.
    """
    marks = list(_MARKER.finditer(raw))
    out: dict[int, str] = {}
    for position, mark in enumerate(marks):
        end = marks[position + 1].start() if position + 1 < len(marks) else len(raw)
        body = raw[mark.end() : end].strip()
        if body:
            out[int(mark.group(1))] = body
    return out


def ordered(indexed: Mapping[int, str], expected: int) -> list[str]:
    """`expected` paragraphs in order, or a `ContractError` naming what was missing."""
    missing = [index for index in range(1, expected + 1) if index not in indexed]
    if missing:
        raise ContractError(
            f"contract asked for {expected} numbered paragraph(s); "
            f"{len(missing)} missing (first: {missing[0]})"
        )
    extra = sorted(index for index in indexed if index < 1 or index > expected)
    if extra:
        raise ContractError(f"response carries out-of-range index/indices {extra[:5]}")
    return [indexed[index] for index in range(1, expected + 1)]


def separator(text: str) -> str:
    """The paragraph convention `text` itself uses.

    `ablate.paragraphs` adapts to either convention and `ablate._join` writes back with a single
    newline, which downgrades a blank-line corpus — a layout change §78 measured a panel
    reacting to. Every rebuild here writes back the separator it read.
    """
    return "\n\n" if "\n\n" in text.strip() else "\n"


def dose_counts(total: int, doses: Sequence[float] = DOSES) -> list[int]:
    """How many units each rung takes: strictly increasing, capped at `total`.

    Strictly increasing is enforced rather than hoped for. `round(0.15 * 5)` and
    `round(0.35 * 5)` are both 1, and two rungs carrying the identical variant would be the same
    evidence counted twice — `ablate.variants`' deduplication lesson, arriving one level up where
    the duplicate would be silent instead of dropped.
    """
    out: list[int] = []
    previous = 0
    for dose in doses:
        count = max(1, round(dose * total), previous + 1)
        out.append(min(count, total))
        previous = out[-1]
    return out


def _vdc(index: int) -> float:
    """Van der Corput base 2. 1 -> 0.5, 2 -> 0.25, 3 -> 0.75, 4 -> 0.125 ..."""
    fraction, out = 1.0, 0.0
    while index:
        fraction /= 2.0
        out += fraction * (index % 2)
        index //= 2
    return out


def spread_boundaries(blocks: int, count: int) -> list[int]:
    """`count` distinct insertion boundaries, spread and **prefix-nested**.

    Prefix-nesting is the property the dose ladder needs: the boundaries used at one fragment are
    the first of the boundaries used at four, so raising the dose adds fragments and never moves
    the ones already there. A bisection sequence gives that for free; evenly-spaced positions
    recomputed per count do not, and the difference is whether two rungs differ by a dose or by a
    rearrangement.
    """
    picked: list[int] = []
    index = 1
    while len(picked) < count and index < 4 * max(blocks, 1) + 8:
        position = min(max(round(_vdc(index) * blocks), 1), max(blocks - 1, 1))
        if position not in picked:
            picked.append(position)
        index += 1
    return picked


def front_boundaries(blocks: int, count: int) -> list[int]:
    """`count` boundaries from the front: after paragraph 1, then 2, then 3.

    The flood arm's positions, because the claim is about the *opening* — introductions scattered
    through a scene are not the thing chapter one is accused of doing.
    """
    return [position for position in range(1, blocks) if position <= count][:count]


def insert(blocks: Sequence[str], pieces: Sequence[str], boundaries: Sequence[int]) -> list[str]:
    """Place `pieces[i]` before `blocks[boundaries[i]]`. The originals are untouched."""
    plan: dict[int, list[str]] = {}
    for piece, boundary in zip(pieces, boundaries, strict=True):
        plan.setdefault(boundary, []).append(piece)
    out: list[str] = []
    for position, block in enumerate(blocks):
        out.extend(plan.get(position, ()))
        out.append(block)
    for position in sorted(index for index in plan if index >= len(blocks)):
        out.extend(plan[position])
    return out


def changed_indices(original: Sequence[str], rewritten: Sequence[str]) -> list[int]:
    """Which paragraphs the rewrite actually touched, in document order.

    Discovered rather than requested. The instruction says what to change; this says what
    changed, and the gap between the two is the model's — which is what the placebo is for.
    """
    return [index for index, block in enumerate(original) if block != rewritten[index]]


# ------------------------------------------------------------------------------ variant building


@dataclass
class Generated:
    """One cached generation, parsed into the pieces a variant is built from."""

    family: str
    scene: str
    pieces: list[str] = field(default_factory=list)
    fault: str = ""


@dataclass
class Variants:
    """Everything built from one generation cache, addressed by scene-text digest.

    Keyed by the digest of the scene rather than by its unit id, so a battery reading a scene out
    of a different database still resolves it — the text is the identity, the same rule
    `Elicitor`'s cache key follows.
    """

    by_scene: dict[str, dict[str, Generated]] = field(default_factory=dict)

    def add(self, scene_text: str, generated: Generated) -> None:
        self.by_scene.setdefault(digest(scene_text), {})[generated.family] = generated

    def get(self, scene_text: str, family: str) -> Generated:
        found = self.by_scene.get(digest(scene_text), {}).get(family)
        if found is None or found.fault:
            why = found.fault if found else "no generation in the cache"
            raise MissingVariant(
                f"{family} has no usable variant for this scene ({why}); build one with "
                "`platform_priors.py --generate --yes`"
            )
        return found

    def covered(self, scene_text: str, family: str) -> bool:
        """Can every rung of `family` actually be built for this scene?

        Not merely "is there a record": the top rung is built. A scene with too few paragraphs to
        carry six insertions has a perfectly good generation and no fourth rung, and finding that
        out in session four hundred of a governed GPU run is the failure this exists to move to
        registration time.
        """
        try:
            for dose in DOSES:
                build(self, family, scene_text, dose)
        except (MissingVariant, IndexError, ValueError, KeyError):
            return False
        return True

    def scenes(self) -> int:
        return len(self.by_scene)


def build(variants: Variants, family_key: str, scene: str, dose: float) -> str:
    """The dosed variant of one scene for one family. Deterministic given the cache."""
    family = BY_KEY[family_key]
    blocks = ablate.paragraphs(scene)
    joiner = separator(scene)
    pieces = variants.get(scene, family_key).pieces
    if family.lane == "blend":
        eligible = changed_indices(blocks, pieces)
        counts = dose_counts(len(eligible))
        take = set(eligible[: counts[DOSES.index(dose)]])
        return joiner.join(
            pieces[index] if index in take else block for index, block in enumerate(blocks)
        )
    ladder = FLOOD_LADDER if family_key == "character_flood" else POV_LADDER
    count = ladder[dose]
    boundaries = (
        front_boundaries(len(blocks), count)
        if family_key == "character_flood"
        else spread_boundaries(len(blocks), count)
    )
    return joiner.join(insert(blocks, pieces[:count], boundaries))


def book_text(scenes: Sequence[tuple[str, str]]) -> str:
    """The book as one text, joined exactly as `bcr.load_text` joins it.

    Restated rather than imported so this module does not pull a battery in to concatenate a
    list — and asserted against `bcr.load_text` in the selftest, because a shelf whose target is
    assembled differently from the corpus the instrument was seated on is a different corpus.
    """
    return "\n\n".join(text for _, text in scenes)


def build_book(variants: Variants, family_key: str, scenes: Sequence[tuple[str, str]],
               dose: float) -> str:
    """The dosed variant of a whole book. **This is the grain a BCR shelf actually reads.**

    A shelf member needs `bcr.MIN_CHUNKS` chunks — about 3,900 words — and one own-generated
    scene is 912. So a scene-grain variant cannot be served: the budget would exhaust it and what
    the session recorded would be the corpus rather than the reader. Generation stays per scene
    because a scene is the size a single rewrite can hold; the *dose* is applied across the
    assembled book, front-first, which is also what the claims describe — the manipulation lands
    in chapters one and two first and reaches the end of the book only at full dose.

    Each lane counts its own units, and each counts them front-first:

        blend            eligible paragraphs, pooled across the book in reading order
        character_flood  declared names, all of them into the opening scene: "many at once"
                         is a property of one place, not of a book-wide sprinkle
        pov_fragment     scenes carrying a fragment; a second POV is a book-level property,
                         so the dose is how much of the book is written in two heads
    """
    joiner = "\n\n"
    family = BY_KEY[family_key]
    rendered = [text for _, text in scenes]
    if family.lane == "blend":
        pooled: list[tuple[int, int]] = []
        blocks_by_scene: list[list[str]] = []
        pieces_by_scene: list[list[str]] = []
        for index, (_, text) in enumerate(scenes):
            blocks = ablate.paragraphs(text)
            pieces = variants.get(text, family_key).pieces
            blocks_by_scene.append(blocks)
            pieces_by_scene.append(pieces)
            pooled.extend((index, position) for position in changed_indices(blocks, pieces))
        take = set(pooled[: dose_counts(len(pooled))[DOSES.index(dose)]]) if pooled else set()
        for index, (_, text) in enumerate(scenes):
            rendered[index] = separator(text).join(
                pieces_by_scene[index][position] if (index, position) in take else block
                for position, block in enumerate(blocks_by_scene[index])
            )
        return joiner.join(rendered)
    if family_key == "character_flood":
        opening = scenes[0][1]
        rendered[0] = build(variants, family_key, opening, dose)
        return joiner.join(rendered)
    carrying = dose_counts(len(scenes))[DOSES.index(dose)]
    for index in range(carrying):
        text = scenes[index][1]
        blocks = ablate.paragraphs(text)
        piece = variants.get(text, family_key).pieces[:1]
        rendered[index] = separator(text).join(
            insert(blocks, piece, spread_boundaries(len(blocks), 1))
        )
    return joiner.join(rendered)


# ------------------------------------------------------------------------------- certification


def placebo_floor(variants: Variants, scene: str) -> dict[str, Any]:
    """The placebo's own movement on this scene: the band every family is read against."""
    blocks = ablate.paragraphs(scene)
    try:
        generated = variants.get(scene, PLACEBO)
    except MissingVariant:
        return {"changed": 0.0, "signature_drift": {}, "available": False}
    rebuilt = separator(scene).join(generated.pieces)
    before, after = panel(scene), panel(rebuilt)
    return {
        "changed": round(
            len(changed_indices(blocks, generated.pieces)) / max(len(blocks), 1), 4
        ),
        "signature_drift": {
            family.key: round(
                after.get(family.signature, 0.0) - before.get(family.signature, 0.0), 3
            )
            for family in FAMILIES
            if family.signature in before
        },
        "available": True,
    }


def _blend_faults(blocks: Sequence[str], generated: Generated, floor: Mapping[str, Any],
                  row: dict[str, Any]) -> list[str]:
    faults: list[str] = []
    eligible = changed_indices(blocks, generated.pieces)
    row["eligible"] = len(eligible)
    row["changed_fraction"] = round(len(eligible) / max(len(blocks), 1), 4)
    if len(eligible) < MIN_ELIGIBLE:
        faults.append(
            f"only {len(eligible)} changed paragraph(s); the ladder needs {MIN_ELIGIBLE}"
        )
    if row["changed_fraction"] <= float(floor.get("changed", 0.0)):
        faults.append(
            f"changed {row['changed_fraction']} of paragraphs against the placebo's "
            f"{floor.get('changed')}: not distinguishable from a revision pass"
        )
    counts = dose_counts(len(eligible)) if eligible else []
    if len(set(counts)) != len(counts):
        faults.append(f"rung counts {counts} are not strictly increasing")
    return faults


def _insert_faults(family_key: str, blocks: Sequence[str], generated: Generated,
                   row: dict[str, Any]) -> list[str]:
    faults: list[str] = []
    ladder = FLOOD_LADDER if family_key == "character_flood" else POV_LADDER
    wanted = max(ladder.values())
    row["pieces"] = len(generated.pieces)
    if len(generated.pieces) < wanted:
        faults.append(f"{len(generated.pieces)} inserted paragraph(s); the ladder needs {wanted}")
    boundaries = (
        front_boundaries(len(blocks), wanted)
        if family_key == "character_flood"
        else spread_boundaries(len(blocks), wanted)
    )
    if len(boundaries) < wanted:
        faults.append(f"the scene offers {len(boundaries)} distinct boundaries for {wanted}")
    return faults


def _signature_faults(family: Family, scene: str, variant: str, generated: Generated,
                      before: Mapping[str, float], after: Mapping[str, float],
                      floor: Mapping[str, Any], row: dict[str, Any]) -> list[str]:
    """Did the instruction land, by more than the placebo drifted? The one bar per family."""
    faults: list[str] = []
    if family.signature in before:
        delta = after[family.signature] - before[family.signature]
        drift = float(dict(floor.get("signature_drift") or {}).get(family.key, 0.0))
        row["signature"] = {
            "name": family.signature,
            "direction": family.signature_direction,
            "before": before[family.signature],
            "after": after[family.signature],
            "delta": round(delta, 3),
            "placebo_drift": round(drift, 3),
        }
        moved = delta if family.signature_direction == "up" else -delta
        if moved <= abs(drift):
            faults.append(
                f"{family.signature} moved {delta:+.3f} against a placebo drift of "
                f"{drift:+.3f}: the instruction did not land"
            )
    elif family.key == "character_flood":
        used = [name for name in FLOOD_NAMES if name in variant]
        present = [name for name in FLOOD_NAMES if name in scene]
        row["signature"] = {"name": "named_introductions", "names_used": len(used)}
        if present:
            faults.append(f"the host scene already names {present}")
        if len(used) < max(FLOOD_LADDER.values()):
            faults.append(
                f"{len(used)} of {max(FLOOD_LADDER.values())} declared names reached the variant"
            )
    elif family.key == "pov_fragment":
        wanted = max(POV_LADDER.values())
        carried = sum(1 for piece in generated.pieces[:wanted] if POV_NAME in piece)
        row["signature"] = {"name": "pov_paragraphs", "fragments_naming_pov": carried}
        if POV_NAME in scene:
            faults.append(f"the host scene already names {POV_NAME}")
        if carried < wanted:
            faults.append(f"{carried} of {wanted} fragments name {POV_NAME}")
    return faults


def certify(variants: Variants, scene: str, family_key: str, *,
            floor: Mapping[str, Any]) -> dict[str, Any]:
    """Every deterministic check one (family, scene) owes, and the faults it failed.

    `floor` is the placebo's own numbers on this scene: `changed` is the fraction of paragraphs a
    do-nothing revision pass moved, and `signature_drift` is how far it moved this family's
    signature counter. A family that stayed inside either has not been shown to have done
    anything its instruction asked for, and serving that shelf would put a reader in front of two
    texts whose difference is drafting noise.

    **Certification is a statement about the manipulation and none at all about the claim.**
    """
    family = BY_KEY[family_key]
    blocks = ablate.paragraphs(scene)
    row: dict[str, Any] = {"family": family_key, "lane": family.lane, "paragraphs": len(blocks)}
    try:
        generated = variants.get(scene, family_key)
    except MissingVariant as error:
        return {**row, "certified": False, "faults": [str(error)]}

    faults = (
        _blend_faults(blocks, generated, floor, row)
        if family.lane == "blend"
        else _insert_faults(family_key, blocks, generated, row)
    )

    try:
        variant = build(variants, family_key, scene, DOSES[-1])
    except (MissingVariant, IndexError, ValueError, KeyError) as error:
        return {**row, "certified": False, "faults": [*faults, f"build failed: {error}"]}

    before, after = panel(scene), panel(variant)
    row["panel_before"] = before
    row["panel_after"] = after
    row["word_ratio"] = round(after["words"] / max(before["words"], 1.0), 4)

    if family.lane == "insert":
        # Pure insertion is checkable and is checked: every original paragraph must survive
        # byte-for-byte inside the variant. A model that "helpfully" edited the host scene while
        # writing its inserts would otherwise ship as a clean insert arm.
        lost = [index for index, block in enumerate(blocks) if block not in variant]
        if lost:
            faults.append(f"{len(lost)} original paragraph(s) did not survive insertion")

    survival = system_voice_survival(scene, variant)
    row["system_voice"] = survival
    if survival["kept"] != survival["spans"]:
        faults.append(f"{survival['spans'] - survival['kept']} protected span(s) did not survive")

    faults.extend(
        _signature_faults(family, scene, variant, generated, before, after, floor, row)
    )

    # Every rung distinct. Two rungs that render the same bytes are one dose wearing two labels,
    # and `bcr` would score the duplicate as a second independent shelf.
    try:
        rendered = {build(variants, family_key, scene, dose) for dose in DOSES}
    except (MissingVariant, IndexError, ValueError, KeyError):
        rendered = set()
    row["distinct_rungs"] = len(rendered)
    if len(rendered) != len(DOSES):
        faults.append(f"{len(rendered)} distinct rung(s) of {len(DOSES)}")

    row["certified"] = not faults
    row["faults"] = faults
    return row


# ------------------------------------------------------------------------------ bcr integration


def as_ablation(variants: Variants, family_key: str) -> ablate.Ablation:
    """Bridge one family into the shape `bcr.battery_shelves` reads.

    **`Ablation.sign` is being borrowed and the borrowing is declared.** Its contract says -1 is a
    degrader and that there is deliberately no +1, because nothing in `ablate.py` claims to
    improve prose. A platform prior claims neither: it names the side a readership is *said* to
    like less, which is the hypothesis under test. -1 is used because it puts the manipulated text
    on the side `bcr`'s arithmetic expects the damage to be, and the note carried onto every shelf
    says what it actually is — so no result file can read as certified damage.
    """
    family = BY_KEY[family_key]

    def apply(text: str, strength: float) -> str:
        rung = min(DOSES, key=lambda dose: abs(dose - strength))
        return build(variants, family_key, text, rung)

    return ablate.Ablation(
        key=family_key,
        item=None,
        sign=-1,
        preserves_length=False,
        apply=apply,
        note=f"D1P platform prior, HYPOTHESISED not certified damage — {family.claim}",
    )


def register(variants: Variants, texts: Sequence[str], *,
             families: Sequence[str] | None = None,
             into: dict[str, ablate.Ablation] | None = None) -> dict[str, list[str]]:
    """Install families into `ablate.BY_KEY` after checking coverage, or raise.

    Coverage is checked **before** anything is installed, because the alternative is a battery
    that discovers a missing variant partway through a governed GPU run. A family that cannot
    build every rung for every text is refused by name, and the refusal is the artifact.

    **This is scene-grain, and on its own it does not make `bcr --battery` run D1P.**
    `bcr.battery_shelves` iterates the frozen `D1_FAMILIES` tuple rather than everything in
    `ablate.BY_KEY`, and a shelf member has to be book-length anyway. `shelves()` below is the
    real integration point; this exists for scene-grain consumers and as the coverage guard.
    """
    chosen = list(families or [family.key for family in FAMILIES])
    gaps = {
        key: [digest(text)[:12] for text in texts if not variants.covered(text, key)]
        for key in chosen
    }
    missing = {key: value for key, value in gaps.items() if value}
    if missing:
        raise MissingVariant(
            "no usable variant for: "
            + "; ".join(f"{key} ({len(value)} scene(s))" for key, value in sorted(missing.items()))
        )
    target = ablate.BY_KEY if into is None else into
    for key in chosen:
        target[key] = as_ablation(variants, key)
    return gaps


def shelves(variants: Variants, scenes: Sequence[tuple[str, str]], *,
            families: Sequence[str] | None = None) -> tuple[list[Any], list[dict[str, Any]]]:
    """D1P's shelves, in `bcr.Shelf` shape: the intact book against each family at each dose.

    Returns `(shelves, skipped)` and **nothing is dropped silently**. A family with an
    uncertified scene, a rung that renders the intact book, or a member too short for the budget
    comes back in `skipped` with the reason, so a run that covers four families out of six says
    so in its own artifact rather than looking like a six-family run that found nothing.

    The arm is labelled `D1P`, not `D1`, so `bcr`'s own report can never pool a hypothesis with
    certified damage.
    """
    import bcr

    intact = book_text(scenes)
    chosen = list(families or [family.key for family in FAMILIES])
    built: list[Any] = []
    skipped: list[dict[str, Any]] = []
    for key in chosen:
        uncertified = [
            scene_id
            for scene_id, text in scenes
            if not certify(variants, text, key, floor=placebo_floor(variants, text))["certified"]
        ]
        if uncertified:
            skipped.append({"family": key, "why": f"uncertified scene(s): {uncertified[:3]}"})
            continue
        rungs: dict[float, str] = {}
        try:
            for dose in DOSES:
                rungs[dose] = build_book(variants, key, scenes, dose)
        except (MissingVariant, IndexError, ValueError, KeyError) as error:
            skipped.append({"family": key, "why": f"build failed: {error}"})
            continue
        if len(set(rungs.values())) != len(DOSES) or intact in rungs.values():
            skipped.append({"family": key, "why": "rungs are not four distinct non-intact books"})
            continue
        for dose, variant in rungs.items():
            shelf = bcr.Shelf(
                f"d1p-{key}-{dose:.2f}", "D1P", intact, variant, dose=dose,
                note=f"HYPOTHESISED, not certified damage — {BY_KEY[key].claim}",
            )
            fault = shelf.fault()
            if fault:
                skipped.append({"family": key, "dose": dose, "why": fault})
                continue
            built.append(shelf)
    return built, skipped


# ---------------------------------------------------------------------------------- generation


def scene_texts(path: Path, *, limit: int | None = None) -> list[tuple[str, str]]:
    """(unit_id, text) from the committed export. `--book-db` goes through `corpus_io`."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [(str(scene["unit_id"]), str(scene["text"])) for scene in payload["scenes"]]
    return rows[:limit] if limit else rows


def expected_pieces(family_key: str, scene: str) -> int:
    if family_key == PLACEBO:
        return len(ablate.paragraphs(scene))
    family = BY_KEY[family_key]
    if family.lane == "blend":
        return len(ablate.paragraphs(scene))
    ladder = FLOOD_LADDER if family_key == "character_flood" else POV_LADDER
    return max(ladder.values())


def prompt_for(family_key: str, scene: str) -> str:
    """The exact user turn for one arm. Pure, so a plan can price a run without a transport."""
    if family_key == PLACEBO:
        return BLEND_CONTRACT.format(task=PLACEBO_TASK) + f"\n\n---\n\n{scene}"
    family = BY_KEY[family_key]
    if family.lane == "blend":
        return BLEND_CONTRACT.format(task=family.task) + f"\n\n---\n\n{scene}"
    count = expected_pieces(family_key, scene)
    task = family.task.format(names=", ".join(FLOOD_NAMES[:count]), pov_name=POV_NAME)
    blocks = len(ablate.paragraphs(scene))
    return (
        INSERT_CONTRACT.format(count=count, task=task)
        + f"\n\n---\n\n{scene}\n\n(The scene has {blocks} paragraphs.)"
    )


def load_cache(path: Path, scenes: Sequence[tuple[str, str]]) -> Variants:
    """Rebuild `Variants` from the append-only generation cache. No calls.

    A record that does not satisfy its contract lands as a `fault` rather than being dropped:
    `--certify` then reports the family as uncertified with the reason, which is the difference
    between "the model could not do this" and "nobody asked".
    """
    variants = Variants()
    if not path.is_file():
        return variants
    by_id = dict(scenes)
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        family, scene_id = record.get("family"), record.get("scene")
        text = by_id.get(scene_id)
        if not family or text is None:
            continue
        if record.get("refused") or not record.get("text"):
            variants.add(text, Generated(family, scene_id, fault="refused or empty generation"))
            continue
        try:
            pieces = ordered(parse_numbered(record["text"]), expected_pieces(family, text))
        except ContractError as error:
            variants.add(text, Generated(family, scene_id, fault=str(error)))
            continue
        variants.add(text, Generated(family, scene_id, pieces=pieces))
    return variants


def generate(args: argparse.Namespace, scenes: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """Every arm over every scene, sequentially, under a spend ceiling checked per call.

    Sequential rather than pooled: §89.5 records 390 transport failures from two `claude -p` jobs
    running beside each other, and a variant set that has to be rebuilt is a variant set whose
    digests move. The cache is per generation, so an interrupted run resumes for free — the
    checkpoint-per-unit rule this box needs.
    """
    stopped = ""
    with Generator(RESULTS / args.cache, model=args.model, dry_run=args.dry_run) as generator:
        for scene_id, text in scenes:
            for arm in ARMS:
                spent = generator.spend().get("equivalent_usd", 0.0)
                if spent >= args.ceiling_usd:
                    stopped = f"ceiling ${args.ceiling_usd:.2f} reached at ${spent:.2f}"
                    break
                generator.generate(
                    {"family": arm, "scene": scene_id},
                    AUTHOR_SYSTEM,
                    prompt_for(arm, text),
                    dry_text="\n".join(
                        f"[[{index + 1}]] (dry run: no model was called)"
                        for index in range(expected_pieces(arm, text))
                    ),
                )
            if stopped:
                break
        return {
            "spend": generator.spend(),
            "api_calls": generator.api_calls,
            "replayed": generator.replayed,
            "stopped": stopped,
        }


# ------------------------------------------------------------------------------------ selftest


def _attainability(alpha: float, half_width: float) -> tuple[int | None, float | None]:
    """Sessions per family needed to reach `half_width`, from the only seated reader's shares.

    **This is I7's check and it is why the confirmatory bar is stated at 0.15 rather than 0.05.**
    `bcr.attainability` simulates twelve independent fetches per session; the one model ever
    seated (phi4) produced session shares of exactly 0.0, 0.5 or 1.0 at an sd of 0.4039, so the
    real interval is far wider than the simulator's. Sizing runs from the observations, per the
    RUNBOOK's rule, and returns `None` when no listed size reaches the width — which is the
    reading a bar naming an unreachable quantity should produce.
    """
    import bcr

    observed = RESULTS / "bcr-seat-phi4.json"
    if not observed.is_file():
        return None, None
    payload = json.loads(observed.read_text(encoding="utf-8"))
    shares = [
        sum(1 for fetch in session["fetches"] if fetch == "A") / len(session["fetches"])
        for session in payload.get("sessions", [])
        if session.get("fetches")
    ]
    if len(shares) < 2:
        return None, None
    offset = 0.5 - statistics.fmean(shares)
    centred = [share + offset for share in shares]
    for size in (24, 48, 64, 96, 128, 160, 224, 320, 448, 640):
        interval = bcr.cluster_interval(
            [(f"s{index}", centred[index % len(centred)]) for index in range(size)], alpha=alpha
        )
        if interval is not None and (interval.high - interval.low) / 2 <= half_width:
            return size, round(statistics.pstdev(shares), 4)
    return None, round(statistics.pstdev(shares), 4)


_SELFTEST_SCENE = (
    "One. He walked to the gate and did not stop.\n\n"
    "Two. The keeper counted the coins twice.\n\n"
    "Three. He had been here before and it had cost him.\n\n"
    "[STATUS] wren — Level 2 | HP 18/22 | MP ?/? | Gold ?\n\n"
    "Four. She wondered whether the debt would ever close.\n\n"
    "Five. The road went on past the lintel.\n\n"
    "Six. He paid, and walked through, and did not look back."
)


def _selftest_variants(scene: str) -> Variants:
    """A cache built by hand: a clean blend arm, an inert placebo and both insert arms."""
    blocks = ablate.paragraphs(scene)
    rewrite = list(blocks)
    for index in (0, 1, 2, 4, 5):
        rewrite[index] = rewrite[index] + " It was, in some sense, seemingly true."
    variants = Variants()
    variants.add(scene, Generated("purple_prose_dose", "s1", pieces=rewrite))
    variants.add(scene, Generated(PLACEBO, "s1", pieces=list(blocks)))
    variants.add(
        scene,
        Generated(
            "character_flood", "s1",
            pieces=[f"{name} was there too, and said nothing." for name in FLOOD_NAMES],
        ),
    )
    variants.add(
        scene,
        Generated(
            "pov_fragment", "s1",
            pieces=[
                f"{POV_NAME} watched, and counted to {index}, and said nothing."
                for index in range(max(POV_LADDER.values()))
            ],
        ),
    )
    return variants


def selftest() -> int:
    """Every invariant that can be checked without a model, before a call is bought."""
    import bcr

    failures: list[str] = []
    if tuple(bcr.DOSES) != DOSES:
        failures.append(f"the dose ladder {DOSES} has drifted from bcr's {tuple(bcr.DOSES)}")

    for name, ladder in (("flood", FLOOD_LADDER), ("pov", POV_LADDER)):
        values = [ladder[dose] for dose in DOSES]
        if values != sorted(set(values)):
            failures.append(f"the {name} ladder {values} is not strictly increasing")

    for total in range(MIN_ELIGIBLE, 40):
        counts = dose_counts(total)
        if counts != sorted(set(counts)):
            failures.append(f"dose_counts({total}) = {counts} is not strictly increasing")
            break

    wide = spread_boundaries(20, 4)
    for count in (1, 2, 3):
        if spread_boundaries(20, count) != wide[:count]:
            failures.append(f"spread_boundaries is not prefix-nested at count {count}")
            break

    scene = _SELFTEST_SCENE
    blocks = ablate.paragraphs(scene)
    variants = _selftest_variants(scene)

    rungs = [build(variants, "purple_prose_dose", scene, dose) for dose in DOSES]
    if len(set(rungs)) != len(DOSES):
        failures.append("two blend rungs rendered identical bytes")
    if blocks[3] not in rungs[-1]:
        failures.append("a protected system-voice paragraph did not survive the blend")
    moved = [len(changed_indices(blocks, ablate.paragraphs(rung))) for rung in rungs]
    if moved != sorted(set(moved)):
        failures.append(f"blend rung change counts {moved} are not strictly increasing")

    for dose in DOSES:
        flooded = build(variants, "character_flood", scene, dose)
        if any(block not in flooded for block in blocks):
            failures.append(f"character_flood at dose {dose} lost an original paragraph")
            break
        if sum(1 for name in FLOOD_NAMES if name in flooded) != FLOOD_LADDER[dose]:
            failures.append(f"character_flood at dose {dose} carries the wrong name count")
            break

    try:
        build(variants, "tense_shift", scene, 1.0)
    except MissingVariant:
        pass
    else:
        failures.append("a family with no generation built a variant instead of raising")

    try:
        register(variants, [scene], families=["tense_shift"], into={})
    except MissingVariant:
        pass
    else:
        failures.append("register installed a family it has no variants for")

    installed: dict[str, ablate.Ablation] = {}
    register(variants, [scene], families=["purple_prose_dose"], into=installed)
    if "HYPOTHESISED" not in installed["purple_prose_dose"].note:
        failures.append("the bridged ablation does not declare that its sign is a hypothesis")

    floor = placebo_floor(variants, scene)
    if floor["changed"] != 0.0:
        failures.append(f"an identical placebo reported {floor['changed']} changed")
    certified = certify(variants, scene, "purple_prose_dose", floor=floor)
    if not certified["certified"]:
        failures.append(f"a clean blend arm did not certify: {certified['faults']}")

    inert = Variants()
    inert.add(scene, Generated("purple_prose_dose", "s1", pieces=list(blocks)))
    inert.add(scene, Generated(PLACEBO, "s1", pieces=list(blocks)))
    if certify(inert, scene, "purple_prose_dose", floor=placebo_floor(inert, scene))["certified"]:
        failures.append("a rewrite identical to the original certified")

    nameless = Variants()
    nameless.add(scene, Generated("character_flood", "s1", pieces=["No names here."] * 6))
    nameless.add(scene, Generated(PLACEBO, "s1", pieces=list(blocks)))
    if certify(nameless, scene, "character_flood",
               floor=placebo_floor(nameless, scene))["certified"]:
        failures.append("a flood arm carrying none of the declared names certified")

    try:
        ordered(parse_numbered("[[1]] a\n[[3]] c"), 3)
    except ContractError:
        pass
    else:
        failures.append("a response missing paragraph 2 parsed as complete")

    lyrical = "He strolled to the gate, luminous and slow, like a tide coming in, endlessly."
    if lyric_index(lyrical) <= lyric_index(blocks[0]):
        failures.append("the lyric signature did not move on a lyricalised sentence")

    # Book grain, which is the grain a shelf reads. Two properties: the joiner agrees with the
    # one the instrument was seated on, and the rungs are four distinct books none of which is
    # the intact one.
    book = [(f"s{index}", scene) for index in range(4)]
    if book_text(book) != "\n\n".join([scene] * 4):
        failures.append("book_text does not join the way bcr.load_text joins")
    if bcr.load_text(SCENES)[0] != book_text(scene_texts(SCENES)):
        failures.append("book_text and bcr.load_text disagree on the committed corpus")
    for key in ("purple_prose_dose", "character_flood", "pov_fragment"):
        books = [build_book(variants, key, book, dose) for dose in DOSES]
        if len(set(books)) != len(DOSES):
            failures.append(f"{key} does not render four distinct books")
        if book_text(book) in books:
            failures.append(f"{key} rendered the intact book at some dose")

    # A book too short to carry four distinct POV rungs must be REFUSED, not collapsed. Two
    # scenes give `dose_counts` nothing to work with above the second rung, and a shelf set that
    # served the same book at three doses would count one observation three times.
    short = [("s0", scene), ("s1", scene)]
    _, skipped = shelves(variants, short, families=["pov_fragment"])
    if not skipped:
        failures.append("a two-scene book built four pov_fragment rungs instead of being skipped")

    adjusted = 0.05 / len(FAMILIES)
    sessions, observed_sd = _attainability(adjusted, 0.15)
    if observed_sd is None:
        print("attainability: NOT RUN — results/bcr-seat-phi4.json is absent", file=sys.stderr)
    elif sessions is None:
        failures.append(
            f"no listed session count reaches a 0.15 half-width at alpha {adjusted:.5f}; the "
            "confirmatory bar names a quantity it cannot reach"
        )
    else:
        print(
            f"attainability: {sessions} sessions per family reach a 0.15 half-width at alpha "
            f"{adjusted:.5f}, on an observed per-session sd of {observed_sd}",
            file=sys.stderr,
        )

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# ----------------------------------------------------------------------------------------- cli


def _report(scenes: Sequence[tuple[str, str]], variants: Variants,
            args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    floors: dict[str, Any] = {}
    for scene_id, text in scenes:
        floor = placebo_floor(variants, text)
        floors[scene_id] = floor
        for family in FAMILIES:
            rows.append({"scene": scene_id, **certify(variants, text, family.key, floor=floor)})
    by_family = {
        family.key: {
            "certified": sum(
                1 for row in rows if row["family"] == family.key and row["certified"]
            ),
            "scenes": sum(1 for row in rows if row["family"] == family.key),
            "faults": sorted(
                {fault for row in rows if row["family"] == family.key for fault in row["faults"]}
            )[:6],
        }
        for family in FAMILIES
    }
    return {
        "study": "platform_priors",
        "version": PLATFORM_VERSION,
        "registration_digest": registration_digest(),
        "pre_registration": PRE_REGISTRATION,
        "families": [
            {
                "key": family.key, "claim": family.claim, "lane": family.lane,
                "signature": family.signature, "direction": family.signature_direction,
                "confirms": family.confirms, "refutes": family.refutes, "null": family.null,
                "kills": family.kills, "cost": family.cost,
            }
            for family in FAMILIES
        ],
        "source": args.book_db or args.scenes_json,
        "model": args.model,
        "scene_count": len(scenes),
        "placebo_floor": floors,
        "by_family": by_family,
        "rows": rows,
        "reading": (
            "certification is a statement about the MANIPULATION and none about the claim. A "
            "certified family is one whose variants are what they say they are; whether the "
            "platform prior holds is a question for a seated reader, and D1P runs only after D1 "
            "on certified damage has passed on that reader"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenes-json", default=str(SCENES))
    parser.add_argument("--book-db", default=None, help="own-generated book database instead")
    parser.add_argument("--book", default=None)
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--scenes", type=int, default=None, help="cap the scene count")
    parser.add_argument("--model", default="claude-opus-5")
    parser.add_argument("--ceiling-usd", type=float, default=25.0)
    parser.add_argument("--cache", default="platform-priors-raw.jsonl")
    parser.add_argument("--out", default="platform-priors.json")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--certify", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.book_db:
        from corpus_io import generated_scenes

        units = generated_scenes(args.book_db, book=args.book, min_words=args.min_words)
        scenes = [(unit.unit_id, unit.text) for unit in units]
    else:
        scenes = scene_texts(Path(args.scenes_json))
    if args.scenes:
        scenes = scenes[: args.scenes]
    if not scenes:
        raise SystemExit("no scenes; nothing to manipulate")

    planned = len(scenes) * len(ARMS)
    print(
        f"{len(scenes)} scene(s) x {len(ARMS)} arm(s) = {planned} generation(s) on {args.model}; "
        f"at §85's measured $0.2316 per generation that is about ${planned * 0.2316:.2f}, "
        f"against a ${args.ceiling_usd:.2f} ceiling",
        file=sys.stderr,
    )
    print(f"registration {registration_digest()[:16]}", file=sys.stderr)

    if args.generate:
        if not (args.yes or args.dry_run):
            raise SystemExit("pass --yes to spend, or --dry-run to exercise the plumbing")
        outcome = generate(args, scenes)
        print(
            f"generated {outcome['api_calls']}, replayed {outcome['replayed']}, spend "
            f"${outcome['spend'].get('equivalent_usd', 0.0):.2f}"
            + (f" — STOPPED: {outcome['stopped']}" if outcome["stopped"] else ""),
            file=sys.stderr,
        )

    if not (args.certify or args.generate):
        print(
            "plan only; pass --generate --yes to spend, or --certify to score the cache",
            file=sys.stderr,
        )
        return 0

    report = _report(scenes, load_cache(RESULTS / args.cache, scenes), args)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for key, block in report["by_family"].items():
        print(f"  {key:<22} {block['certified']}/{block['scenes']} certified", file=sys.stderr)
    print(f"wrote {RESULTS / args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
