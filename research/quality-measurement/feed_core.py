"""The feed continuation reader's frozen core: registration, prompts, and the session record.

**Why a second instrument beside `bcr.py` rather than an edit to it.** The BCR (stage-0 §94) is
byte-frozen: its constants are its pre-registration, its seating runs were measured against
exactly those bytes, and §120.5 records the house rule — an instrument that has produced numbers
keeps its bytes so the numbers stay reproducible. This module is the successor shape the BCR's
own docstring deferred ("a larger naturalistic shelf is a later replication"), built now on an
operator directive (2026-08-24): *continuation saturated at 195/196 because continuing was free;
give the reader a finite attention budget and a feed — other books mid-stream, the option to
skim a summary at lower cost — and abandonment becomes a revealed preference instead of
politeness. Nobody abandons a book in a vacuum; they abandon it for the next thing in their
feed.*

Three structural moves beyond `bcr.v0`, each priced:

1. **A feed, not a shelf.** Four books, all entered mid-stream: each slot opens with a skimmed
   story-so-far and one full current section, so the first choice is between continuations
   rather than between openings. The datum generalises from a two-way share to a per-slot
   allocation vector; every control band moves from 0.5 to 1/4.
2. **A priced skim.** A full read costs 3 minutes of the budget and reveals the next section; a
   skim costs 1 and reveals a deterministic extract of the next section without consuming it.
   Skimming is how a real feed lets a reader keep a book warm without paying for it — and it is
   also a new artifact channel, so it carries its own control (`fp6`): raise the skim price to
   the read price and a reader that keeps skimming is not economising, and no skim-derived
   number may be read.
3. **Abandonment as the datum.** With forced spending and competitors present, the step after
   which the target book never again receives a full read is a revealed preference. The 195/196
   failure mode — politeness priced at zero — is structurally unavailable: every unit spent on
   the target is a unit no competitor got.

**What this module deliberately is.** The registered constants, the byte-frozen reader-facing
strings, the deterministic skim extract, and the frozen dataclasses every sibling module shares.
No I/O, no model call, no CLI. `feed_substrate.py` builds feeds, `feed_session.py` runs one
session, `feed_controls.py` owns the control arithmetic and the patterned-reader attainability
simulation, `feed_battery.py` is the driver.

**Two lessons from §94.7 are encoded structurally rather than remembered.**
`CONTROL_MIN_SESSIONS` is deliberately `None`: the BCR's first sizing simulated a reader nobody
is (independent coins; real sessions came out perfectly correlated within themselves), and the
corrected number was 2.7x the declared one. The driver must refuse any paid run until the
attainability table — simulated over *patterned* session-level readers — has been read and the
number set in a commit that cites it. And the degeneracy floor is on the **slot**-share vector,
never the target share, because the orientation rotation moves the target between slots and a
rigidly positional reader scores maximal target-share variance (§94.6's second formulation
defect).

**Substrate.** The twenty fitness books (§95.9, 3,918-4,059 words each) hold 11-12 chunks under
the shared chunker — measured by the substrate report, against a first sizing whose naive
words-over-target arithmetic predicted 13 and fit none of them — so the session is sized to the
measured floor: entry at section 3 plus eight worst-case reads is exactly the 11 chunks the
shortest delivered book holds. Published prose enters only behind
the driver's `--published` stamp with the §A6 rename rails; the licensed substrate is this
system's own un-memorised prose.
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
import bcr  # noqa: E402

# ---------------------------------------------------------------- the pre-registration, frozen

#: Instrument version. Every constant below is part of it; changing any one of them is a
#: different instrument with no evidence, and the id in every result file is what says so.
FCR_VERSION = "fcr.v0"

#: Books on the feed. Four is the smallest number that makes "the next thing in the feed" a
#: field rather than a rival: with two books every abandonment is a preference for one
#: alternative, which is the BCR's question; with four it is a preference against the target.
FEED_SIZE = 4

#: Slot letters, in reveal order. The rotation maps feed texts onto these.
SLOTS: tuple[str, ...] = ("A", "B", "C", "D")

#: Budget units ("minutes") a full read of the next section costs.
READ_COST = 3

#: Budget units a skim of the next section costs. The ratio is the instrument's price signal;
#: `fp6` runs sessions with the skim priced at `READ_COST` to check the reader is actually
#: economising rather than performing variety.
SKIM_COST = 1

#: Total budget, and it must be spent — spending is forced and only allocation is chosen, so
#: stopping cannot be performed as free diligence (the 195/196 lesson, inherited from the BCR).
#: 24 = eight full reads; sized with `MIDSTREAM_CHUNK` to the **measured** shelf, not the naive
#: word arithmetic. The delivered fitness books hold 11-12 chunks under the shared chunker
#: (the substrate report over all twenty; paragraph grouping closes a chunk past the word
#: target, so ~3,950 words is 11-12 chunks, not 13), and the first sizing — 27 units entering
#: at section 4 — needed 13 and could run on none of them. A budget that could exhaust a slot
#: would record the corpus rather than the reader.
BUDGET_UNITS = 24

#: Upper bound on actions per session: every unit spent on skims.
MAX_STEPS = BUDGET_UNITS // SKIM_COST

#: Words per chunk, inherited from the sibling instrument rather than re-chosen: the chunker is
#: `bcr.chunks` itself, so length cannot masquerade as interest in either instrument and the two
#: report over the same unit of prose.
CHUNK_WORDS = bcr.CHUNK_WORDS

#: The section (1-based) at which every slot enters the session. All four books are mid-stream
#: and all four enter at the same depth — an asymmetric entry would confound slot with position
#: in the book. Chunks before it are compressed into the opening recap. Three, not four: the
#: entry depth shares the measured 11-chunk floor with the budget above.
MIDSTREAM_CHUNK = 3

#: Chunks a text must hold to sit in a feed: the mid-stream entry point plus a budget that
#: could, in principle, be spent entirely on it in full reads. Skims never consume a section,
#: so they do not raise this.
MIN_CHUNKS_FEED = MIDSTREAM_CHUNK + BUDGET_UNITS // READ_COST

#: Word cap on a skim of one section.
SKIM_WORDS = 60

#: Word cap on the opening story-so-far recap (it compresses several sections, so it is longer
#: than a single-section skim).
RECAP_WORDS = 120

#: **Byte-frozen.** T0's A4 put roughly fourteen points of a verdict on wording, so a reworded
#: prompt is a different instrument with no evidence. No quality vocabulary, no evaluation
#: framing, no persona: a reader mid-way through four books with a fixed amount of reading time,
#: and nothing suggesting any book is being assessed or is supposed to win. The costs stated in
#: prose must agree with `READ_COST` and `SKIM_COST`; `tests/test_feed_core.py` pins both.
SYSTEM = (
    "You are reading for pleasure. You are partway through four books and have a fixed amount "
    "of reading time left, measured in minutes.\n"
    "Each time you are asked, choose one action: read the next section of one book, which "
    "costs 3 minutes, or skim a short summary of the next section of one book, which costs "
    "1 minute. Skimming does not use the section up; reading always shows the full section.\n"
    "You must spend all your reading time; there is no option to stop.\n"
    'Answer with a single JSON object, for example {"action": "read", "book": "A"} or '
    '{"action": "skim", "book": "C"}. The books are A, B, C and D.'
)

#: The turn that asks for one action. Byte-frozen with the system block; `{left}` is the
#: remaining budget, which is the whole of the scarcity the instrument creates.
TURN = "{left} minute(s) of reading time left. What do you do?"

#: Reader-facing reveal formats, frozen here so no sibling module invents bytes of its own.
RECAP = "Book {label}, the story so far, skimmed:\n\n{text}"
REVEAL_READ = "Book {label}, section {index}:\n\n{text}"
REVEAL_SKIM = "Book {label}, section {index}, skimmed:\n\n{text}"

ACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["read", "skim"]},
        "book": {"type": "string", "enum": list(SLOTS)},
    },
    "required": ["action", "book"],
    "additionalProperties": False,
}

#: One short JSON object out. The prose is input; an instrument that let the reader write at
#: length would be paying for the verbal channel it exists to avoid.
ACTION_MAX_TOKENS = 48

#: Half-width of the equivalence band for every control that must read "no allocation
#: difference" — around 1/FEED_SIZE now, not 0.5. Provisional in exactly one sense: the
#: attainability leg prints its operating characteristic before any session is bought.
CONTROL_BAND = 0.10

#: Two one-sided tests at 5% each; the 90% interval must lie inside the band. Equivalence, not
#: a point check: insufficient evidence fails a control rather than passing it.
CONTROL_ALPHA = 0.10

#: **Deliberately None, and the driver must refuse any paid run while it is.** §94.7: the BCR
#: sized its controls from an assumed independent-coin reader, real sessions were internally
#: correlated fixed patterns, and the declared batch could not have met the band at any size
#: this programme had budgeted. The number is read off `feed_controls`' patterned-reader
#: attainability table and set in a commit that cites that table, not before.
CONTROL_MIN_SESSIONS: int | None = None

#: Floor for `fp5`, the non-degeneracy check: the mean over slots of the across-session
#: standard deviation of each slot's read share. On the **slot** share, never the target share
#: — the rotation moves the target between slots, so a rigidly positional reader scores maximal
#: target-share variance and a slot-share check is what stays 0.0 for every fixed pattern
#: (always-one-slot, strict round-robin) while a content-driven allocator moves it.
DEGENERATE_SD = 0.05

#: Refuse above this many model calls without `--yes`. One session is at most `MAX_STEPS`
#: calls, so this is about thirty-seven worst-case sessions — a pilot, far short of a battery.
CALL_GUARD = 1_000

#: Stamped into any result produced with published prose in the feed. Mirrors
#: `persona_battery.py --published`: the licensed substrate is un-memorised own prose; a
#: published competitor rides only with the §A6 rails (both sides entity-renamed, per-text
#: rename-delta measured, exclusions printed) and this warning cannot be un-stamped.
PUBLISHED_WARNING = (
    "published prose in the feed: familiarity is a measured confound (BRIEF.md §2 Pass 6); "
    "rename rails required; this result cannot license anything on its own"
)

PRE_REGISTRATION: dict[str, Any] = {
    "version": FCR_VERSION,
    "feed_size": FEED_SIZE,
    "slots": list(SLOTS),
    "read_cost": READ_COST,
    "skim_cost": SKIM_COST,
    "budget_units": BUDGET_UNITS,
    "max_steps": MAX_STEPS,
    "chunk_words": CHUNK_WORDS,
    "midstream_chunk": MIDSTREAM_CHUNK,
    "min_chunks_feed": MIN_CHUNKS_FEED,
    "skim_words": SKIM_WORDS,
    "recap_words": RECAP_WORDS,
    "system": SYSTEM,
    "turn": TURN,
    "recap_format": RECAP,
    "reveal_read_format": REVEAL_READ,
    "reveal_skim_format": REVEAL_SKIM,
    "action_schema": ACTION_SCHEMA,
    "action_max_tokens": ACTION_MAX_TOKENS,
    "control_band": CONTROL_BAND,
    "control_alpha": CONTROL_ALPHA,
    "control_min_sessions": CONTROL_MIN_SESSIONS,
    "degenerate_sd": DEGENERATE_SD,
    "call_guard": CALL_GUARD,
    "kills": {
        "fp5": "a session set whose slot-share vector is constant across sessions is a fixed "
               "pattern wearing a budget; nothing downstream of it is a measurement",
        "fp6": "a reader whose skim usage does not fall when the skim price equals the read "
               "price is not economising; the skim channel is an artifact and no skim-derived "
               "number may be read",
    },
}


def registration_digest() -> str:
    """Content address of the whole pre-registration, printed on every result.

    So an edited constant is visible as a changed number in the file rather than as an
    unchanged-looking run of a different instrument — `bcr.registration_digest`'s discipline,
    inherited byte for byte in mechanism.
    """
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------------- deterministic skim

_FIRST_SENTENCE = re.compile(r"^(.*?[.!?][\"')\]]*)(?:\s|$)", re.S)

#: Words used of a paragraph that never ends a sentence (headings, fragments).
_FRAGMENT_WORDS = 24


def skim_extract(text: str, *, words: int = SKIM_WORDS) -> str:
    """First sentence of each paragraph, in order, capped at `words` words. Deterministic.

    This is what a skim reveals: mechanical extraction, never model-written prose, so the skim
    channel adds no derived authority and costs no call. A paragraph with no sentence-ending
    punctuation contributes its first `_FRAGMENT_WORDS` words. The cap truncates mid-sentence
    when it must — a skim is a glance, and a glance that grew to fit its material would let
    text length back into a channel priced to be flat.
    """
    out: list[str] = []
    used = 0
    for block in ablate.paragraphs(text):
        stripped = block.strip()
        if not stripped:
            continue
        match = _FIRST_SENTENCE.match(stripped)
        first = match.group(1) if match else " ".join(stripped.split()[:_FRAGMENT_WORDS])
        tokens = first.split()
        if used + len(tokens) >= words:
            out.append(" ".join(tokens[: words - used]))
            used = words
            break
        out.append(first)
        used += len(tokens)
    return " ".join(" ".join(out).split())


def opening_for_slot(label: str, slot_chunks: Sequence[str]) -> str:
    """The mid-stream entry block for one slot: skimmed story-so-far, then one full section.

    Every slot gets exactly this shape, so the first budget decision is between continuations
    of four stories the reader is equally far into — never between an opening and a middle.
    """
    if len(slot_chunks) < MIDSTREAM_CHUNK:
        raise ValueError(
            f"slot {label} holds {len(slot_chunks)} chunk(s); a feed member needs at least "
            f"{MIDSTREAM_CHUNK} to enter mid-stream"
        )
    recap_source = "\n\n".join(slot_chunks[: MIDSTREAM_CHUNK - 1])
    recap = RECAP.format(label=label, text=skim_extract(recap_source, words=RECAP_WORDS))
    current = REVEAL_READ.format(
        label=label, index=MIDSTREAM_CHUNK, text=slot_chunks[MIDSTREAM_CHUNK - 1]
    )
    return recap + "\n\n" + current


# ----------------------------------------------------------------------------- the feed record


def slot_of(index: int, rotation: int) -> str:
    """Slot letter of feed text `index` under `rotation`. Text 0 is always the target."""
    return SLOTS[(index + rotation) % FEED_SIZE]


@dataclass(frozen=True, slots=True)
class FeedSpec:
    """Four texts and which one the arm is about.

    `target` is the text the arm's hypothesis concerns; `others` are the competitors. Neither
    is a slot: slots are assigned by rotation, one session per rotation, which is what makes
    position measurable rather than assumed away — the BCR's two orientations, generalised to
    four.
    """

    feed_id: str
    arm: str
    target: str
    others: tuple[str, ...]
    dose: float = 0.0
    note: str = ""

    def texts(self) -> tuple[str, ...]:
        return (self.target, *self.others)

    def fault(self) -> str | None:
        """Why this feed cannot carry a session, or None. Run before any call."""
        if len(self.others) != FEED_SIZE - 1:
            return f"feed holds {len(self.others) + 1} text(s); the registered size is {FEED_SIZE}"
        for index, text in enumerate(self.texts()):
            held = len(bcr.chunks(text))
            if held < MIN_CHUNKS_FEED:
                name = "target" if index == 0 else f"other{index}"
                return (
                    f"{name} holds {held} chunk(s); a feed member needs {MIN_CHUNKS_FEED} so "
                    f"the mid-stream entry plus a budget of {BUDGET_UNITS} cannot exhaust it"
                )
        return None


@dataclass(frozen=True, slots=True)
class FeedSession:
    """One reader, one feed, one rotation, one spent budget.

    `actions` is the raw record — `("read" | "skim", slot letter)` in order; everything else is
    derived. A session carrying any unanswered step is reported and not scored, for the same
    reason as the BCR: an unanswered step is not an allocation, and folding it into one would
    put transport failures into a behavioural distribution.
    """

    feed_id: str
    arm: str
    model: str
    rotation: int
    replicate: int
    dose: float
    actions: tuple[tuple[str, str], ...]
    unanswered: int = 0
    exit_note: str = ""
    #: The prices this session actually ran at. Registered defaults; the fp6 skim-price
    #: control overrides them, and a record that repriced its own history at the registered
    #: constants would misreport the charge — found by the session task's tests.
    read_cost: int = READ_COST
    skim_cost: int = SKIM_COST

    @property
    def spent_units(self) -> int:
        return sum(
            self.read_cost if action == "read" else self.skim_cost
            for action, _ in self.actions
        )

    @property
    def target_slot(self) -> str:
        return SLOTS[self.rotation % FEED_SIZE]

    def reads_of(self, slot: str) -> int:
        return sum(1 for action, where in self.actions if action == "read" and where == slot)

    def skims_of(self, slot: str) -> int:
        return sum(1 for action, where in self.actions if action == "skim" and where == slot)

    @property
    def total_reads(self) -> int:
        return sum(1 for action, _ in self.actions if action == "read")

    def read_share_of(self, slot: str) -> float:
        """This slot's share of full reads. With no reads at all, neutral at 1/FEED_SIZE."""
        if self.total_reads == 0:
            return 1.0 / FEED_SIZE
        return self.reads_of(slot) / self.total_reads

    @property
    def target_read_share(self) -> float:
        """The primary datum: the target's share of full reads, `bcr`'s S(target) generalised."""
        return self.read_share_of(self.target_slot)

    @property
    def slot_read_shares(self) -> dict[str, float]:
        """Read share by slot letter, whatever sits in each. The positional reading."""
        return {slot: self.read_share_of(slot) for slot in SLOTS}

    @property
    def skim_rate(self) -> float:
        """Fraction of actions that were skims. 0.0 on an empty record."""
        if not self.actions:
            return 0.0
        return sum(1 for action, _ in self.actions if action == "skim") / len(self.actions)

    @property
    def abandonment_step(self) -> int:
        """Index of the last full read of the target, or -1 for a target never read.

        The revealed abandonment position: after this step the reader never again paid full
        price for the target while competitors were on the feed and budget remained.
        """
        last = -1
        for index, (action, where) in enumerate(self.actions):
            if action == "read" and where == self.target_slot:
                last = index
        return last

    @property
    def read_switch_rate(self) -> float:
        """Fraction of adjacent full reads that changed slot, over reads only.

        The degeneracy diagnostic behind `fp5`, naming the pattern rather than only detecting
        it: 1.0 is a strict rotator, 0.0 never left one book. Skims are excluded — a skim is a
        glance, and counting glances as switches would let the cheap channel manufacture
        variety.
        """
        reads = [where for action, where in self.actions if action == "read"]
        if len(reads) < 2:
            return 0.0
        pairs = list(itertools.pairwise(reads))
        return sum(1 for left, right in pairs if left != right) / len(pairs)

    @property
    def repeat_skims(self) -> int:
        """Skims of a slot whose previous touch of that slot was also a skim.

        A repeat skim buys the same preview again (skims never advance a slot), so a reader
        doing it is not economising — reported as a diagnostic beside `fp6`, never forbidden.
        """
        last: dict[str, str] = {}
        count = 0
        for action, where in self.actions:
            if action == "skim" and last.get(where) == "skim":
                count += 1
            last[where] = action
        return count

    @property
    def scorable(self) -> bool:
        return self.unanswered == 0 and len(self.actions) > 0
