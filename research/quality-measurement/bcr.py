"""The Budgeted Continuation Reader: what a reader *does* with scarce reading time.

**Why this instrument shape and no other.** Three attempts to ask a model for a verdict about
prose have died in this project and they share one structure — an unconstrained verbal report
costs the model nothing, so it reports its trained disposition rather than the text:

    frame                                    result                                  where
    verdict, T0 axiom battery                DISQUALIFIED; chose-A 0.8151 / 568      §86.6
    verdict, E1/E2 prefer-a-side             VOID on precondition; 0.6408 / 142      §89.4
    verdict, persona absolute                keep-reading on 195 of 196              §70

BCR removes both properties at once. **Behavioral, never verbal**: the signal is which text a
budgeted reader spends its fetches on, and no verbal verdict is elicited at any point.
**Scarcity is constructed**: continuation is free for a model, and the 195/196 result is what
continuation looks like when it costs nothing — so the budget makes it expensive, every chunk
of one book read being a chunk of the other unread. **Contrast-shaped**: head-to-head,
blinded, position-swapped, the one frame that has survived every validity check here.

**It borrows no validity from E6 and none from the persona panel.** It is not an A/B
preference leg — it asks for no preference — and it earns its own licence through the seating
controls (P1-P4, V1) and the battery (D1-D4) or it earns none. Nothing in `--optimise` exists
in this module, deliberately: the arms and the campaign in `plan/llm-reader-engagement.md`
§A4-A5 are downstream of kills this battery has not yet had the chance to make.

**The pre-registration is the constant block below**, frozen before the first session and
copied verbatim into every result file this module writes — `axiom_battery.py`'s discipline,
for the reason `plan/reader-judge-loop.md` §1 gives: a split that can be edited after a verdict
exists was never a pre-registration.

Free legs first. Both execute before a call is bought, and the second is the argument that the
declared bands can be met at the declared shape at all:

    uv run python research/quality-measurement/bcr.py --selftest
    uv run python research/quality-measurement/bcr.py --attainability
    uv run python research/quality-measurement/bcr.py --dry-run --seat

Then the real thing, which touches the 4090 and therefore runs under the duty-cycle and
temperature governor `cdg_battery.py` paid for:

    uv run python research/quality-measurement/bcr.py --seat --model qwen3:14b --yes
    uv run python research/quality-measurement/bcr.py --battery --model qwen3:14b --yes
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
from elicit import Elicitor  # noqa: E402

RESULTS = HERE / "results"
SCENES = HERE / "corpora" / "toll-scenes.json"

# ---------------------------------------------------------------- the pre-registration, frozen

#: Instrument version. Every constant below is part of it; changing any one of them is a
#: different instrument with no evidence, and the id in every result file is what says so.
BCR_VERSION = "bcr.v0"

#: Texts on the shelf. Two in v0. A larger naturalistic shelf is a later replication and not the
#: primary: with M texts the allocation share stops being one number and the positional controls
#: stop being a single band, and neither of those complications is worth adding to an instrument
#: whose first question is whether it discriminates at all.
SHELF_SIZE = 2

#: Words per chunk (~400 tokens). Chunks break at paragraph boundaries and never inside one, so
#: length cannot masquerade as interest: every fetch costs the reader the same unit of budget
#: and delivers roughly the same amount of prose.
CHUNK_WORDS = 300

#: Chunks of each text revealed before any choice is made. Both texts, so the first decision is
#: about prose rather than about a slot label — a reader shown nothing would be choosing at
#: random and the first fetch would be pure position.
OPENING_CHUNKS = 1

#: Fetches the reader holds, and **must spend**. Spending is forced and only allocation is
#: chosen, which is the whole design: "stopping" cannot be performed as free diligence, so the
#: 195/196 failure mode is unavailable by construction.
BUDGET = 12

#: The doubled budget for D3's invariance check. An instrument whose ranking depends on the
#: budget is measuring the budget.
DOUBLE_BUDGET = 2 * BUDGET

#: **Byte-frozen.** T0's A4 put roughly fourteen points of a verdict on wording, so a reworded
#: prompt is a different instrument with no evidence behind it. No quality vocabulary, no
#: evaluation framing, no persona: the reader is someone reading for pleasure with a fixed
#: amount of reading time ahead of them, and nothing here suggests that either text is being
#: assessed or that one of them is supposed to win.
SYSTEM = (
    "You are reading for pleasure. You have two books on the go and a fixed amount of "
    "reading time left, measured in sections.\n"
    "Each time you are asked, choose which book to read the next section of. You must spend "
    "every section of reading time; there is no option to stop.\n"
    "Answer with a single JSON object naming the book you continue: "
    '{"continue": "A"} or {"continue": "B"}.'
)

#: The turn that asks for one fetch. Byte-frozen with the system block; `{left}` is how many
#: sections of reading time remain, which is the whole of the scarcity the instrument creates.
FETCH_TURN = "{left} section(s) of reading time left. Which book do you continue?"

FETCH_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"continue": {"type": "string", "enum": ["A", "B"]}},
    "required": ["continue"],
    "additionalProperties": False,
}

#: One short JSON object out. The passages are input, and an instrument that let the reader
#: write at length would be paying for the verbal channel it exists to avoid.
FETCH_MAX_TOKENS = 48

#: Half-width of the equivalence band for every control that must read "no allocation
#: difference": the placebo shelf, both shams, and the positional check. Chosen from the
#: attainability table rather than from taste — see `--attainability`, which prints the sessions
#: needed to place a 90% interval inside this band at several true shares.
CONTROL_BAND = 0.10

#: Two one-sided tests at 5% each: the 90% interval must lie **inside** the band. This is an
#: equivalence test and not a point check, which is the direction that matters — insufficient
#: evidence fails a control rather than passing it, because "we could not detect a bias" is not
#: "there is no bias" and a control that passes on thin data is a control that cannot fail.
CONTROL_ALPHA = 0.10

#: **Observations below which a control reads UNREADABLE rather than PASS, and this constant is
#: bought.** The selftest caught the defect it exists for: two sessions that both allocate
#: exactly evenly produce a bootstrap whose every resample is 0.5, so a zero-width interval sits
#: inside any band and the control passes on twenty-four fetches. That is §85's zero-width
#: defect arriving in an equivalence test, where it is worse than in a bound — a bound with no
#: width over-claims a direction, and an equivalence check with no width certifies the absence
#: of one.
#:
#: **The value is read off the measured operating characteristic, and the first value was
#: wrong.** `--attainability` at 200 trials per cell, on the declared band and budget:
#:
#:     sessions   pass at true 0.50   pass at 0.60   pass at 0.70
#:         16           0.765             0.030          0.000
#:         24           0.910             0.065          0.000
#:         32           0.980             0.025          0.000
#:         48           1.000             0.040          0.000
#:
#: 16 was the first guess and it fails an **unbiased** reader almost a quarter of the time,
#: which is I7's own catalogued failure — T0's registered bar disqualified a *good* judge 82 to
#: 100% of the time until somebody measured its operating characteristic. 24 costs a false
#: failure about one run in eleven and still refuses a 0.60 allocator 93.5% of the time, which
#: is the trade this instrument can afford; 32 buys the last eight points at a third more GPU
#: time and is where to go if a control fails and the failure looks marginal.
#:
#: `selftest` asserts both halves at this exact count, so a band or budget edit that makes the
#: number wrong fails before a call is bought.
CONTROL_MIN_SESSIONS = 24

#: Clusters below which a percentile bootstrap is descriptive rather than calibrated.
#: `preference.DESCRIPTIVE_CLUSTER_FLOOR`, inherited rather than re-derived — its own docstring
#: records the measurement: two readers by two pairs, all wins, and the "97.5% lower bound"
#: prints 1.0 from four observations. A descriptive interval is still worth reading and is never
#: enough to seat a model, which is exactly how the flag is used below.
DESCRIPTIVE_CLUSTERS = 5

#: Two-sided level for everything that is not an equivalence check.
ALPHA = 0.05

#: D1's dose ladder. `ablate.DOSES` without the 0.0 rung, which is the intact original and is
#: the other side of every shelf rather than a dose of its own.
DOSES: tuple[float, ...] = (0.15, 0.35, 0.65, 1.0)

#: D1's manipulation families. Each one is a certified damage this project already built and
#: already measured something with, which is why the battery costs manipulation code of zero:
#: graded paragraph shuffle, matched-word-count deletion, and the two reader-named defects.
#: `interiority_deplete_matched` rides along as `interiority_strip`'s own word-matched control,
#: because §78.1 records that reading the interiority arm against the generic deletion control
#: was wrong.
D1_FAMILIES: tuple[str, ...] = (
    "paragraph_shuffle",
    "sentence_deletion",
    "stat_flatten",
    "interiority_strip",
    "interiority_deplete_matched",
)

#: Kendall tau floor for D3. Below this the ordering at `BUDGET` and at `DOUBLE_BUDGET` are
#: different orderings and the instrument is reporting its budget.
TAU_FLOOR = 0.6

#: D4's cross-family agreement band, on the allocation share. Necessary and not sufficient, and
#: the residual is stated rather than solved: two families agreeing can still be two families
#: sharing a training bias, and no arrangement of this battery can separate those.
FAMILY_BAND = 0.15

#: **P5's floor, and the pilot is what bought it.** The first six BCR sessions ever run —
#: three shelves, both orientations, `qwen3:14b` — returned `ABABABABABAB` **every time**. A
#: strict alternator allocates exactly half its budget to each side of every shelf, so it passes
#: the placebo, both shams and the positional check perfectly and measures nothing at all. That
#: is the 195/196 constant function wearing a budget, which is the failure V1 is declared to
#: catch — and V1 needs twenty own-generated texts while this needs none, because the
#: degeneracy is visible *within* a run.
#:
#: **It is the standard deviation of the *slot* share, and the first version read the target
#: share and was wrong.** The very next pilot showed how: `gemma3:12b` answered `A` twelve times
#: in every session, on every shelf, in both orientations. Because the orientation swap moves
#: the target between the slots, that reader's *target* share alternates 1.00 / 0.00 and its
#: standard deviation is maximal — so a check on the target share reports the most rigidly
#: positional reader available as the most discriminating one. The slot share is the quantity
#: that is constant for a fixed-pattern reader and variable for a content-driven one, which is
#: the property being tested.
#:
#: Both degeneracies score exactly 0.0 on it: the alternator's slot share is 0.5 every session,
#: the always-A reader's is 1.0 every session. A fair random allocator at `BUDGET` = 12 scores
#: about 0.144, so the floor sits far below anything a real allocator produces and catches only
#: the fixed ones. `switch_rate` is reported beside it as the diagnostic naming *which* fixed
#: pattern — taking turns at 1.0, never leaving the first book at 0.0 — rather than as a second
#: bar.
DEGENERATE_SD = 0.05

#: V1's intraclass floor: between-text variance in allocation share must exceed replicate noise
#: by this much or the reader is a uniform allocator — the 195/196 constant function wearing a
#: budget. Needs at least this many own-generated texts to compute at all.
ICC_FLOOR = 0.20
V1_MIN_TEXTS = 20

#: Refuse above this many model calls without `--yes`. One session is `BUDGET` calls, so this is
#: about eighty sessions — enough for a pilot and far short of a battery, which is the point.
CALL_GUARD = 1_000

PRE_REGISTRATION: dict[str, Any] = {
    "version": BCR_VERSION,
    "shelf_size": SHELF_SIZE,
    "chunk_words": CHUNK_WORDS,
    "opening_chunks": OPENING_CHUNKS,
    "budget": BUDGET,
    "double_budget": DOUBLE_BUDGET,
    "system": SYSTEM,
    "fetch_turn": FETCH_TURN,
    "fetch_schema": FETCH_SCHEMA,
    "control_band": CONTROL_BAND,
    "control_alpha": CONTROL_ALPHA,
    "control_min_sessions": CONTROL_MIN_SESSIONS,
    "descriptive_clusters": DESCRIPTIVE_CLUSTERS,
    "alpha": ALPHA,
    "doses": list(DOSES),
    "d1_families": list(D1_FAMILIES),
    "tau_floor": TAU_FLOOR,
    "family_band": FAMILY_BAND,
    "icc_floor": ICC_FLOOR,
    "v1_min_texts": V1_MIN_TEXTS,
    "degenerate_sd": DEGENERATE_SD,
    "kills": {
        "D1": "a dose-response inversion — strongest allocation at the smallest dose — kills "
              "the instrument, not the arm",
        "D2": "transplant-blindness is a kill: a continuation instrument that does not care "
              "whether the text belongs to its book is not measuring wanting-to-continue",
    },
}


def registration_digest() -> str:
    """Content address of the whole pre-registration, printed on every result.

    So an edited constant is visible as a changed number in the file rather than as an
    unchanged-looking run of a different instrument. `_policy_digest` in `application/outline.py`
    exists for exactly this reason one layer over.
    """
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------------------- the substrate


def chunks(text: str, *, words: int = CHUNK_WORDS) -> tuple[str, ...]:
    """Paragraph-aligned chunks of roughly `words` words each.

    **Never splits a paragraph**, and the cost of that is accepted: a chunk that ended
    mid-sentence would make a fetch feel like an interruption rather than a section, and a
    reader's allocation would then partly measure where the cuts fell. A paragraph longer than
    the target is its own chunk rather than being broken, which is the same trade in the other
    direction.
    """
    out: list[str] = []
    current: list[str] = []
    size = 0
    for block in ablate.paragraphs(text):
        current.append(block)
        size += len(block.split())
        if size >= words:
            out.append("\n\n".join(current))
            current, size = [], 0
    if current:
        # A short tail is folded into the previous chunk rather than emitted as a runt: a final
        # chunk of forty words is a fetch that costs a full unit of budget and delivers a
        # fraction of one, which is exactly the length-masquerading-as-interest the fixed size
        # exists to prevent.
        tail = "\n\n".join(current)
        if out:
            out[-1] = out[-1] + "\n\n" + tail
        else:
            out.append(tail)
    return tuple(out)


#: Chunks a text must hold to be a shelf member: the free opening plus a budget that could, in
#: principle, all be spent on it. Below this the budget exhausts the text and the reader is
#: forced onto the other one, so what is recorded is the corpus rather than the reader.
MIN_CHUNKS = OPENING_CHUNKS + BUDGET


@dataclass(frozen=True, slots=True)
class Shelf:
    """Two texts and which one the arm is about.

    `target` is the side an arm's hypothesis concerns — the intact original in D1, the original
    in a sham, either in a placebo — and it is **not** the slot: slots are assigned by
    orientation and swapped, which is what makes position measurable rather than assumed away.
    """

    shelf_id: str
    arm: str
    target: str
    other: str
    dose: float = 0.0
    note: str = ""

    def fault(self) -> str | None:
        """Why this shelf cannot carry a session, or None.

        The substrate check, run before any call: at `BUDGET` fetches of `CHUNK_WORDS` words a
        text must hold `MIN_CHUNKS` chunks or the budget exhausts it. §94 records what this
        returns on the corpus in hand — one own-generated book long enough, which is why two of
        the six battery legs are NOT RUN rather than passed.
        """
        for label, text in (("target", self.target), ("other", self.other)):
            held = len(chunks(text))
            if held < MIN_CHUNKS:
                return (
                    f"{label} holds {held} chunk(s); a shelf member needs {MIN_CHUNKS} so the "
                    f"budget of {BUDGET} cannot exhaust it"
                )
        return None


# -------------------------------------------------------------------------------- one session


@dataclass(frozen=True, slots=True)
class Session:
    """One reader, one shelf, one orientation, one spent budget."""

    shelf_id: str
    arm: str
    model: str
    #: 0 puts the target in slot A, 1 puts it in slot B. Both are always run.
    orientation: int
    replicate: int
    dose: float
    #: The fetch sequence as slot letters, in order. The raw record; everything else is derived.
    fetches: tuple[str, ...]
    #: Fetches that obtained no answer. A session carrying any of these is reported and not
    #: scored — an unanswered fetch is not an allocation and folding it into one would put
    #: transport failures into a behavioural distribution.
    unanswered: int = 0
    exit_note: str = ""

    @property
    def spent(self) -> int:
        return len(self.fetches)

    @property
    def target_slot(self) -> str:
        return "A" if self.orientation == 0 else "B"

    @property
    def target_share(self) -> float:
        """Fraction of the spent budget that went to the arm's target text."""
        if not self.fetches:
            return 0.5
        return sum(1 for slot in self.fetches if slot == self.target_slot) / len(self.fetches)

    @property
    def slot_a_share(self) -> float:
        """Fraction that went to slot A, whatever is in it. The positional reading."""
        if not self.fetches:
            return 0.5
        return sum(1 for slot in self.fetches if slot == "A") / len(self.fetches)

    @property
    def switch_rate(self) -> float:
        """Fraction of adjacent fetches that changed side. 1.0 is a strict alternator.

        The diagnostic behind P5, and it names the degeneracy rather than only detecting it: a
        run that fails the variance floor at a switch rate of 1.0 failed because the reader was
        taking turns, and one that fails at 0.0 failed because it never left the first book.
        Those are different broken readers and a single number would hide which.
        """
        if len(self.fetches) < 2:
            return 0.0
        pairs = list(zip(self.fetches, self.fetches[1:], strict=False))
        return sum(1 for left, right in pairs if left != right) / len(pairs)

    @property
    def scorable(self) -> bool:
        return self.unanswered == 0 and len(self.fetches) > 0


def _reveal(label: str, index: int, text: str) -> str:
    return f"Book {label}, section {index}:\n\n{text}"


def run_session(
    elicitor: Elicitor,
    shelf: Shelf,
    *,
    model: str,
    orientation: int,
    replicate: int,
    budget: int = BUDGET,
) -> Session:
    """One BCR session: reveal both openings, then spend the budget one fetch at a time.

    **Sequential by necessity and not by preference.** Each choice is conditioned on everything
    read so far, which is what makes the budget scarce in the way a reader experiences it — a
    batched design would ask for an allocation rather than observe one. The cost is `budget`
    round trips per session, and it is why the inner loop of any campaign belongs on local
    models under the governor.

    A fetch that obtains no answer ends the session; the partial record is kept and marked
    unscorable, for `_is_transport_failure`'s reason — a run that reports a share beside a
    non-zero failure count is reporting on the fetches that answered.
    """
    slot_a, slot_b = (
        (shelf.target, shelf.other) if orientation == 0 else (shelf.other, shelf.target)
    )
    chunks_by_slot = {"A": chunks(slot_a), "B": chunks(slot_b)}
    served = {"A": OPENING_CHUNKS, "B": OPENING_CHUNKS}
    opening = "\n\n".join(
        _reveal(label, index + 1, chunks_by_slot[label][index])
        for label in ("A", "B")
        for index in range(OPENING_CHUNKS)
    )
    turns: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": opening + "\n\n" + FETCH_TURN.format(left=budget),
                    # The opening is the longest prefix every later turn in this session shares,
                    # so it is where a cache breakpoint can do anything at all. Whether it
                    # engages is the model's business — see `_cell`'s note on minimum prefix
                    # lengths — and nothing here depends on it.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    fetches: list[str] = []
    unanswered = 0
    for step in range(budget):
        record = elicitor.ask_raw(
            SYSTEM,
            turns,
            schema=FETCH_SCHEMA,
            max_tokens=FETCH_MAX_TOKENS,
            tag={
                "shelf": shelf.shelf_id,
                "arm": shelf.arm,
                "stage": "fetch",
                "orientation": orientation,
                "replicate": replicate,
                "step": step,
                "budget": budget,
            },
            # **The sample index carries the replicate as well as the step, and leaving the
            # replicate out was a real defect rather than a tidiness point.** The cache key is
            # a digest of the request plus this index, and at step 0 the request is
            # byte-identical across every replicate of a shelf — same system, same opening,
            # same budget — so `sample=step` would have made replicate 1 a cache hit on
            # replicate 0 and every "replicate" one draw repeated. On ollama it is also the
            # sampler seed, so the same collapse would happen even without a cache.
            sample=replicate * budget + step,
            model=model,
        )
        choice = None
        if not record.get("refused") and record.get("text"):
            try:
                parsed = json.loads(record["text"])
                choice = parsed.get("continue")
            except (json.JSONDecodeError, AttributeError):
                choice = None
        if choice not in ("A", "B"):
            unanswered += 1
            break
        fetches.append(choice)
        turns = [
            *turns,
            {"role": "assistant", "content": json.dumps({"continue": choice})},
        ]
        index = served[choice]
        served[choice] += 1
        available = chunks_by_slot[choice]
        # Guarded by `Shelf.fault`, which refuses a shelf the budget could exhaust. Reaching
        # here anyway would mean the guard was skipped, and continuing would silently record a
        # forced allocation as a chosen one, so the session stops instead.
        if index >= len(available):
            unanswered += 1
            break
        turns.append(
            {
                "role": "user",
                "content": _reveal(choice, index + 1, available[index])
                + "\n\n"
                + FETCH_TURN.format(left=budget - step - 1),
            }
        )
    return Session(
        shelf_id=shelf.shelf_id,
        arm=shelf.arm,
        model=model,
        orientation=orientation,
        replicate=replicate,
        dose=shelf.dose,
        fetches=tuple(fetches),
        unanswered=unanswered,
    )


# --------------------------------------------------------------------------------- statistics

#: Resamples, imported rather than chosen so this module's intervals and the package's are the
#: same arithmetic. `preference.BOOTSTRAP_RESAMPLES`' own docstring records why the count is not
#: a parameter: a caller-supplied count makes one verdict set produce two bounds.
def _resamples() -> int:
    from litharness.domain.preference import BOOTSTRAP_RESAMPLES

    return int(BOOTSTRAP_RESAMPLES)


@dataclass(frozen=True, slots=True)
class Interval:
    """A clustered percentile interval on a mean, and the shape it was computed at."""

    point: float
    low: float
    high: float
    alpha: float
    clusters: int
    observations: int

    def inside(self, band: float, *, centre: float = 0.5) -> bool:
        return centre - band <= self.low and self.high <= centre + band

    def excludes(self, value: float) -> bool:
        return self.low > value or self.high < value


def cluster_interval(
    values: Sequence[tuple[str, float]], *, alpha: float = ALPHA
) -> Interval | None:
    """Percentile bootstrap on a mean, clustered over one dimension. None below two clusters.

    **One dimension rather than `win_rate_lower_bound`'s two, and the reason is a refusal that
    is informative.** That function clusters over readers *and* pairs and refuses fewer than two
    of either. A per-model seating run has exactly **one** reader — the model being seated — so
    the two-way function refuses it, and routing around that by treating replicates as readers
    would be manufacturing a cluster dimension out of repeated draws. So per-model numbers get
    a one-way bootstrap over shelves, and the two-way function is used where a second dimension
    genuinely exists: the pooled cross-family reading, where model family is the reader.

    Everything else is `win_rate_lower_bound`'s discipline verbatim — resample count imported
    from it, the generator seeded from a content digest of the observations so the same evidence
    gives the same interval on every machine and nobody can re-run hoping for a kinder quantile,
    and the conservative order statistic at each tail.
    """
    from random import Random

    from litharness.domain.events import payload_digest

    clusters = sorted({key for key, _ in values})
    if len(clusters) < 2 or not values:
        return None
    index = {key: position for position, key in enumerate(clusters)}
    scored = [(index[key], value) for key, value in values]
    rng = Random(
        int(
            payload_digest({"values": sorted((key, round(v, 9)) for key, v in values)})[:16],
            16,
        )
    )
    resamples = _resamples()
    means: list[float] = []
    for _ in range(resamples):
        weights = [0] * len(clusters)
        for _ in clusters:
            weights[rng.randrange(len(clusters))] += 1
        total = 0.0
        weighted = 0.0
        for cluster, value in scored:
            weight = weights[cluster]
            total += weight
            weighted += weight * value
        if total:
            means.append(weighted / total)
    if not means:
        return None
    means.sort()
    tail = max(1, int(-(-(alpha / 2.0) * len(means) // 1)))
    return Interval(
        point=statistics.fmean(value for _, value in values),
        low=means[tail - 1],
        high=means[len(means) - tail],
        alpha=alpha,
        clusters=len(clusters),
        observations=len(values),
    )


def _failure_kind(interval: Interval, band: float, centre: float) -> str:
    """Why an equivalence check failed: the reader is off centre, or the batch is too small.

    **The distinction the phi4 seating had to have and did not.** All four of its controls
    failed while two of them sat on a point estimate of *exactly* 0.5, because an all-or-nothing
    allocator's session shares are 0, 0.5 or 1 and the interval over 24 of them is wider than
    the band can ever contain. Reporting that as "FAIL" alone reads as a biased reader, which is
    a bar wrong in the direction of false failure — I7's catalogued defect, and the reason T0's
    own registered bar disqualified a good judge 82 to 100% of the time.

    So a failure whose interval still *contains* the centre while being wider than the band is
    named as imprecision, and `empirical_sessions_needed` prices the fix in sessions.
    """
    if interval.low <= centre <= interval.high and (interval.high - interval.low) > 2 * band:
        return "imprecise"
    return "off_centre"


def equivalence(
    values: Sequence[tuple[str, float]], *, band: float = CONTROL_BAND,
    alpha: float = CONTROL_ALPHA, centre: float = 0.5,
    min_sessions: int = CONTROL_MIN_SESSIONS, dimension: str = "shelf",
    scope: str = "",
) -> dict[str, Any]:
    """A control's verdict: does the interval lie **inside** the band?

    Two one-sided tests at `alpha/2` each, which is exactly what "the (1-alpha) interval sits
    inside the band" means. The direction is the point: a control that passed on a wide interval
    would pass on thin data, and a control that cannot fail is not a control — which is the
    defect §87 records in a floor family that cleared its null and voided everything above it.

    **Three ways this refuses rather than passes**, and each is a shape that has produced a
    false green somewhere in this project's record: fewer than two clusters (an interval over
    one thing is one thing), fewer than `min_sessions` observations (the zero-width equivalence
    §85's defect becomes here), and fewer than `DESCRIPTIVE_CLUSTERS` clusters, which is not a
    refusal but a label — the interval is reported, marked `calibrated: false`, and `seat`
    refuses to seat on it.
    """
    if len(values) < min_sessions:
        return {
            "verdict": "UNREADABLE",
            "why": (
                f"{len(values)} scorable session(s) against a floor of {min_sessions}; an "
                "equivalence check on too few is a control that cannot fail"
            ),
            "observations": len(values),
            "cluster_dimension": dimension,
        }
    interval = cluster_interval(values, alpha=alpha)
    if interval is None:
        return {
            "verdict": "UNREADABLE",
            "why": f"fewer than two {dimension} clusters; an interval over one is one",
            "observations": len(values),
            "cluster_dimension": dimension,
        }
    passed = interval.inside(band, centre=centre)
    return {
        "verdict": "PASS" if passed else "FAIL",
        # A FAIL is two different findings and a single word hides one of them. See
        # `_failure_kind`: an interval that still contains the centre and is simply too wide is
        # an under-sized batch, not a biased reader.
        "failure_kind": None if passed else _failure_kind(interval, band, centre),
        "band": [centre - band, centre + band],
        "cluster_dimension": dimension,
        # **What the claim covers, carried on the claim.** Clustered over shelves it is about
        # the reader; clustered over sessions of one shelf it is about the reader *on that
        # text*, which is a narrower statement and the only one a one-book corpus supports.
        "scope": scope,
        "calibrated": interval.clusters >= DESCRIPTIVE_CLUSTERS,
        **asdict(interval),
    }


def isotonic(doses: Sequence[float], shares: Sequence[float]) -> list[float]:
    """Pool-adjacent-violators fit of `shares` against increasing `doses`. Weightless.

    The monotone fit D1's kill condition is read from. Written out rather than pulled from a
    dependency because it is nine lines and this directory's rule is that a number nobody can
    re-derive from the file is a number nobody checks.
    """
    order = sorted(range(len(doses)), key=lambda index: doses[index])
    blocks: list[list[float]] = []
    for index in order:
        blocks.append([shares[index]])
        while len(blocks) > 1 and statistics.fmean(blocks[-2]) > statistics.fmean(blocks[-1]):
            merged = blocks.pop()
            blocks[-1].extend(merged)
    out: list[float] = []
    for block in blocks:
        out.extend([statistics.fmean(block)] * len(block))
    return out


def kendall_tau(left: Sequence[float], right: Sequence[float]) -> float:
    """Kendall's tau-b between two rankings. Exact by enumeration; the lists are short."""
    n = len(left)
    if n < 2 or len(right) != n:
        return 0.0
    concordant = discordant = tied_left = tied_right = 0
    for i in range(n):
        for j in range(i + 1, n):
            a = left[i] - left[j]
            b = right[i] - right[j]
            if a == 0 and b == 0:
                tied_left += 1
                tied_right += 1
            elif a == 0:
                tied_left += 1
            elif b == 0:
                tied_right += 1
            elif (a > 0) == (b > 0):
                concordant += 1
            else:
                discordant += 1
    pairs = n * (n - 1) / 2
    denominator = ((pairs - tied_left) * (pairs - tied_right)) ** 0.5
    return (concordant - discordant) / denominator if denominator else 0.0


def icc(groups: Sequence[Sequence[float]]) -> float | None:
    """ICC(1): between-group variance over total. V1's floor is read off this.

    None when fewer than two groups or fewer than two observations somewhere — the same refusal
    `cluster_interval` makes, for the same reason. A uniform allocator lands near zero, which is
    what the floor exists to catch: the 195/196 constant function wearing a budget.
    """
    usable = [list(group) for group in groups if len(group) >= 2]
    if len(usable) < 2:
        return None
    flat = [value for group in usable for value in group]
    if len(flat) < 4:
        return None
    grand = statistics.fmean(flat)
    counts = [len(group) for group in usable]
    k = statistics.fmean(counts)
    between = sum(
        len(group) * (statistics.fmean(group) - grand) ** 2 for group in usable
    ) / (len(usable) - 1)
    within = sum(
        sum((value - statistics.fmean(group)) ** 2 for value in group) for group in usable
    ) / (len(flat) - len(usable))
    if between + (k - 1) * within == 0:
        return 0.0
    return (between - within) / (between + (k - 1) * within)


# ----------------------------------------------------------------------------- attainability


def _simulate_shares(
    true_share: float, *, sessions: int, shelves: int, seed: int
) -> list[tuple[str, float]]:
    """`sessions` simulated allocation shares at a true rate, laid out over `shelves`.

    Each session is a binomial over `BUDGET` fetches, which is the shape a real session
    produces, and the layout is round-robin rather than random for `directions._synthetic`'s
    reason: an attainability number that moved with a layout seed would be a property of the
    seed rather than of the shape.
    """
    from random import Random

    rng = Random(seed)
    return [
        (
            f"shelf-{index % max(shelves, 1)}",
            sum(1 for _ in range(BUDGET) if rng.random() < true_share) / BUDGET,
        )
        for index in range(sessions)
    ]


#: Trials behind every simulated rate below. Enough that a rate is stable to about a point and
#: small enough that the free legs stay free — this whole module's arithmetic runs in seconds,
#: which is what lets `--selftest` assert an operating characteristic at all.
_TRIALS = 200

#: Trials the selftest runs at. Lower on purpose: the selftest asks whether the declared band
#: can be met and can be failed, which its loose thresholds decide long before sampling error
#: matters, and it has to stay cheap enough to run before every paid leg.
_SELFTEST_TRIALS = 60


def _characteristic(
    true_share: float, *, sessions: int, shelves: int | None = None,
    band: float = CONTROL_BAND, trials: int = _TRIALS,
) -> float:
    """How often the equivalence check passes at a given true share. The control's OC curve.

    `trials` is a parameter for exactly one caller: `selftest` runs it at a fraction of the
    published count, because its job is to catch a band that *cannot* be met rather than to
    publish a rate, and its assertions are loose enough that the sampling error at a low trial
    count cannot flip one. `--attainability` runs the full count and is what an operator sizes
    a batch against.
    """
    passes = sum(
        1
        for trial in range(trials)
        if equivalence(
            _simulate_shares(
                true_share, sessions=sessions, shelves=shelves or sessions,
                seed=trial * 7919 + sessions,
            ),
            band=band,
            dimension="session",
        )["verdict"]
        == "PASS"
    )
    return passes / trials


def _detection(
    true_share: float, *, sessions: int, shelves: int | None = None
) -> float:
    """How often the two-sided interval excludes 0.5. What a battery arm is sized from.

    `shelves=None` means one cluster per session, which is the layout a one-book corpus
    actually produces — and getting that default wrong is what the first run of this simulator
    caught: with every session in one cluster the interval is undefined and the control read
    0% attainable at a shape where the arithmetic says it is comfortable.
    """
    hits = 0
    for trial in range(_TRIALS):
        interval = cluster_interval(
            _simulate_shares(
                true_share, sessions=sessions, shelves=shelves or sessions,
                seed=trial * 104_729 + sessions,
            ),
            alpha=ALPHA,
        )
        if interval is not None and interval.excludes(0.5):
            hits += 1
    return hits / _TRIALS


def empirical_sessions_needed(
    shares: Sequence[float], *, band: float = CONTROL_BAND, alpha: float = CONTROL_ALPHA,
    sizes: Sequence[int] = (24, 32, 48, 64, 96, 128, 160, 224),
) -> dict[str, Any]:
    """Sessions needed to place the interval inside the band, from *observed* session shares.

    **The simulated table sized every arm against a distribution readers do not produce, and
    the first full seating is what showed it.** `attainability` draws each session's share as a
    binomial over `BUDGET` fetches — twelve independent coins, per-session sd about 0.144. A
    real reader commits to a pattern for a whole session: phi4's 72 sessions produced shares of
    exactly 0.0, 0.5 or 1.0 and nothing else, at a per-session sd of **0.4025**, so the
    fetches inside a session are perfectly correlated and the effective sample size is the
    session count rather than the fetch count. The interval is 2.8x wider than the simulation
    assumed and the declared band could not be met at any batch this programme had budgeted.

    So sizing runs from the observations. The shares are centred on `0.5` before resampling —
    what is being measured is the *precision* a reader's own variance affords, not whether that
    reader is biased, and leaving a real bias in would price the batch needed to certify a
    reader that should fail.

    Returns the smallest listed size whose interval fits, or None with the sizes tried.
    """
    if len(shares) < 2:
        return {"observed_sd": None, "sessions_needed": None, "why": "fewer than two sessions"}
    observed_sd = statistics.pstdev(shares)
    offset = 0.5 - statistics.fmean(shares)
    centred = [share + offset for share in shares]
    needed: int | None = None
    table: dict[str, float] = {}
    for size in sizes:
        # Deterministic round-robin over the observed shares rather than a random draw, for
        # `directions._synthetic`'s reason: a sizing number that moved with a seed would be a
        # property of the seed.
        values = [(f"session-{index}", centred[index % len(centred)]) for index in range(size)]
        interval = cluster_interval(values, alpha=alpha)
        if interval is None:
            continue
        width = interval.high - interval.low
        table[str(size)] = round(width, 4)
        if needed is None and interval.inside(band, centre=0.5):
            needed = size
    return {
        "observed_sd": round(observed_sd, 4),
        "binomial_sd_assumed_by_attainability": round((0.25 / BUDGET) ** 0.5, 4),
        "interval_width_by_sessions": table,
        "sessions_needed": needed,
        "band": band,
        "reading": (
            "the simulated `--attainability` table assumes twelve independent fetches per "
            "session; a reader that commits to a pattern for a whole session breaks that "
            "assumption and needs this many sessions instead"
        ),
    }


def attainability(
    *, shelves: int = 4, replicates: int = 3, shifts: Sequence[float] = (0.05, 0.10, 0.15),
    band: float = CONTROL_BAND,
) -> dict[str, Any]:
    """Can the declared bands do what they say, at the declared shape? Simulated, no calls.

    **I7's second half, and the check that has already caught seven declarations in this
    project.** A band is not attainable merely because it is a number: it has to be reachable
    by the interval a run of this size actually produces, and the equivalence direction makes
    that a real constraint — a 90% interval wider than 0.20 can never sit inside a +/-0.10 band
    however unbiased the reader is, so a control declared at that shape could only ever fail.

    Two questions, both answered by simulating sessions rather than by asserting:

    - **Control feasibility.** At a true share of exactly 0.5, how often does the equivalence
      check pass? A number near zero means the band is unreachable and the declaration is void.
    - **Detection power.** At a true share of 0.5 + shift, how often does the interval exclude
      0.5? This is what a battery arm is sized from, and it is the column an operator spends
      against — never the floor.

    The simulation draws each session's share as a binomial over `BUDGET` fetches, which is the
    same shape a real session produces, and lays sessions out evenly over shelves the way
    `directions._synthetic` does — an attainability number that moved with a seed would be a
    property of the seed.
    """
    sizes = (CONTROL_MIN_SESSIONS, 24, 32, 48, 64, 96)
    control = {
        str(size): {
            "pass_at_0.50": round(_characteristic(0.5, sessions=size), 3),
            f"pass_at_{0.5 + band:.2f}": round(
                _characteristic(0.5 + band, sessions=size), 3
            ),
            f"pass_at_{0.5 + 2 * band:.2f}": round(
                _characteristic(0.5 + 2 * band, sessions=size), 3
            ),
        }
        for size in sizes
    }
    power = {
        str(size): {
            f"{shift:.2f}": round(_detection(0.5 + shift, sessions=size), 3)
            for shift in shifts
        }
        for size in sizes
    }
    return {
        "shape": {
            "budget": BUDGET,
            "band": band,
            "control_min_sessions": CONTROL_MIN_SESSIONS,
            "declared_run": {
                "shelves": shelves,
                "replicates": replicates,
                "sessions": shelves * replicates * 2,
            },
            "trials": _TRIALS,
        },
        # A control column that never reaches a high pass rate at a true 0.5 is a band that
        # cannot be met, and one that stays high at 0.5 + 2*band is a control that cannot fail.
        # Both readings are here rather than a single "attainable: true", because the two ways
        # a declaration fails are different facts and averaging them hides one.
        "control_pass_rate": control,
        "detection_power": power,
        "reading": (
            "size a control from the first row whose pass_at_0.50 is high and whose "
            f"pass_at_{0.5 + 2 * band:.2f} is low; size a battery arm from detection_power, "
            "never from the control floor"
        ),
    }


# ----------------------------------------------------------------------------- shelf building


def load_text(path: Path | None) -> tuple[str, str]:
    """The own-generated book as one text, and a label for where it came from.

    **Own prose only, and it is a validity decision rather than a convenience one.** BRIEF §2
    Pass 6 measured a scoring model's familiarity with published text swinging a score further
    than real damage did, and a continuation instrument is exactly the shape that would reward
    recognition. Published prose has one place in this programme — the out-of-loop baseline arm
    — and it is not this one.
    """
    source = path or SCENES
    payload = json.loads(source.read_text(encoding="utf-8"))
    scenes = [str(scene["text"]) for scene in payload["scenes"]]
    return "\n\n".join(scenes), str(source)


def seating_shelves(text: str) -> list[Shelf]:
    """P1, P2, P3 and P4's shelves. Each compares a text against a transform of itself.

    Which is exactly why these four run on the corpus in hand and V1 and D2 do not: a control
    that needs one text has one text, and a variance floor over twenty own-generated books needs
    twenty own-generated books.
    """
    return [
        Shelf(
            "p1-placebo", "P1", text, text,
            note="two byte-identical texts; any allocation away from 0.5 is a slot artifact",
        ),
        Shelf(
            "p3-whitespace", "P3", text, ablate.rewhitespace(text, 1.0),
            note="layout only; not one character of any word changes",
        ),
        Shelf(
            "p4-rename", "P4", text, ablate.rename_entities(text, 1.0),
            note="consistent rename; the memorisation control, kept standing on own prose",
        ),
        # P2 has no shelf of its own: positional symmetry is read off the *slot* share of every
        # non-placebo session in the run, which is more evidence than a dedicated shelf would
        # give and is the reading §69's position-swapped design was built to support.
    ]


def battery_shelves(text: str) -> list[Shelf]:
    """D1's shelves: the intact original against certified damage at four doses."""
    out: list[Shelf] = []
    for family in D1_FAMILIES:
        ablation = ablate.BY_KEY.get(family)
        if ablation is None:
            continue
        for dose in DOSES:
            damaged = ablation.apply(text, dose)
            if damaged == text:
                # A dose that changed nothing is not a dose. Recorded by omission here and
                # counted by the caller, because a shelf whose two sides are identical would
                # silently become a second placebo wearing a damage label.
                continue
            out.append(
                Shelf(
                    f"d1-{family}-{dose:.2f}", "D1", text, damaged, dose=dose,
                    note=ablation.note,
                )
            )
    return out


# ------------------------------------------------------------------------------------ the run


@dataclass
class Run:
    """Sessions and the bookkeeping a report needs."""

    sessions: list[Session] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)


def play(
    elicitor: Elicitor,
    shelves: Sequence[Shelf],
    *,
    model: str,
    replicates: int,
    budget: int = BUDGET,
) -> Run:
    """Every shelf x replicate x **both orientations**.

    Both orientations always, which is what makes position measurable rather than assumed away
    — and the reason P2 needs no shelf of its own.
    """
    run = Run()
    for shelf in shelves:
        fault = shelf.fault()
        if fault is not None:
            run.skipped.append({"shelf": shelf.shelf_id, "arm": shelf.arm, "why": fault})
            continue
        for replicate in range(replicates):
            for orientation in (0, 1):
                run.sessions.append(
                    run_session(
                        elicitor, shelf, model=model, orientation=orientation,
                        replicate=replicate, budget=budget,
                    )
                )
    return run


def _clustered(
    sessions: Sequence[Session], key: str
) -> tuple[list[tuple[str, float]], str, str]:
    """(values, cluster dimension, scope) for one control arm.

    **The cluster dimension is chosen by what exists, and the claim's scope follows it**, which
    is the honest handling of a one-book corpus rather than a workaround for it. With two or
    more shelves the clusters are shelves and the claim is about the reader; with one, the
    clusters are sessions and the claim is about the reader *on that text* — narrower, stated on
    the result, and never silently widened. A cluster dimension invented out of replicates would
    be manufacturing independence, which is the failure `directions` records as "four personas
    were one judge four times".
    """
    usable = [session for session in sessions if session.scorable]
    shelves = {session.shelf_id for session in usable}
    if len(shelves) >= 2:
        return (
            [(session.shelf_id, getattr(session, key)) for session in usable],
            "shelf",
            "the reader, over the shelves in this run",
        )
    return (
        [
            (f"{session.shelf_id}:{session.orientation}:{session.replicate}",
             getattr(session, key))
            for session in usable
        ],
        "session",
        "the reader on this one text; one shelf cannot support a claim about texts",
    )


def seat(run: Run, *, model: str) -> dict[str, Any]:
    """The seating verdict for one model: P1-P4 and V1, and what each one refuses.

    **A model failing any precondition is unseated and the failure is recorded**, the way the
    4B model's positional failure was — the capability floor is a result about the instrument,
    not an embarrassment to be omitted.
    """
    scorable = [session for session in run.sessions if session.scorable]
    by_arm: dict[str, list[Session]] = {}
    for session in scorable:
        by_arm.setdefault(session.arm, []).append(session)

    controls: dict[str, Any] = {}
    for arm, label in (("P1", "p1_placebo"), ("P3", "p3_whitespace"), ("P4", "p4_rename")):
        sessions = by_arm.get(arm, [])
        if not sessions:
            controls[label] = {"verdict": "NOT RUN", "why": "no sessions on this arm"}
            continue
        values, dimension, scope = _clustered(sessions, "target_share")
        controls[label] = equivalence(values, dimension=dimension, scope=scope)
    # P2 reads the *slot* share of every non-placebo session: with orientations balanced, a
    # text-driven reader spends half its budget in slot A whatever it prefers, so a departure is
    # position. The placebo is excluded because its two sides are identical and its slot share
    # is P1's own reading rather than a second one.
    positional = [session for session in scorable if session.arm != "P1"]
    if positional:
        values, dimension, scope = _clustered(positional, "slot_a_share")
        controls["p2_positional"] = equivalence(values, dimension=dimension, scope=scope)
    else:
        controls["p2_positional"] = {
            "verdict": "NOT RUN",
            "why": "no non-placebo sessions to read a slot share from",
        }
    # **P5, added after the first six sessions ever run and labelled with that provenance.**
    # It is not a bar tuned to an answer: the pre-registration already names "a uniform
    # allocator is the 195/196 constant function wearing a budget" as V1's kill, and this is
    # that kill in the form the corpus can actually reach — within a run rather than across
    # twenty texts. Without it the placebo, both shams and the positional check all pass
    # perfectly for a reader that is simply taking turns.
    shares = [session.slot_a_share for session in scorable]
    sd = statistics.pstdev(shares) if len(shares) >= 2 else 0.0
    switch = statistics.fmean([s.switch_rate for s in scorable]) if scorable else 0.0
    controls["p5_non_degenerate"] = (
        {
            "verdict": "PASS" if sd > DEGENERATE_SD else "FAIL",
            "slot_share_sd": round(sd, 4),
            "floor": DEGENERATE_SD,
            "mean_switch_rate": round(switch, 4),
            "calibrated": True,
            "why": (
                None
                if sd > DEGENERATE_SD
                else (
                    "the slot share is effectively constant across every session, so the "
                    "fetch sequence is a fixed pattern rather than an allocation and nothing "
                    "downstream of it measures the text"
                    + (
                        f"; at a mean switch rate of {switch:.2f} the reader is taking turns"
                        if switch > 0.9
                        else (
                            f"; at a mean switch rate of {switch:.2f} the reader never leaves "
                            "the slot it starts in"
                            if switch < 0.1
                            else ""
                        )
                    )
                )
            ),
        }
        if scorable
        else {"verdict": "NOT RUN", "why": "no scorable sessions"}
    )
    # **What a failing control would cost to make readable**, computed from this run's own
    # session shares rather than from the simulator's binomial assumption. Printed whenever a
    # control failed for imprecision, because "FAIL" plus a price is actionable and "FAIL"
    # alone reads as a verdict about the reader.
    sizing: dict[str, Any] | None = (
        empirical_sessions_needed([session.target_share for session in scorable])
        if any(block.get("failure_kind") == "imprecise" for block in controls.values())
        else None
    )
    controls["v1_variance"] = {
        "verdict": "NOT RUN",
        "why": (
            f"the variance floor needs {V1_MIN_TEXTS} own-generated texts of at least "
            f"{MIN_CHUNKS * CHUNK_WORDS} words; this repository holds one (§94.3)"
        ),
        "icc_floor": ICC_FLOOR,
    }

    # **Seating needs PASS *and* calibrated on every control.** A descriptive interval is a real
    # reading and is printed; it is not evidence a model may be seated on, for
    # `DESCRIPTIVE_CLUSTER_FLOOR`'s own reason — below that many clusters a percentile bootstrap
    # has not earned its level, and seating on one would be reading an interval that has not.
    seated = all(
        block.get("verdict") == "PASS" and block.get("calibrated") is True
        for block in controls.values()
    )
    return {
        "model": model,
        "controls": controls,
        # Deliberately a sibling of `controls` and not one of them: it is a price, not a
        # verdict, and a DIAGNOSTIC entry inside `controls` would enter the seating decision
        # through `all(... == "PASS")` and unseat every model that needed one.
        "sizing_from_observed": sizing,
        "sessions": len(run.sessions),
        "scorable": len(scorable),
        "unanswered_sessions": len(run.sessions) - len(scorable),
        "skipped_shelves": run.skipped,
        # **Never `seated: true` while a control is NOT RUN.** A battery reporting three passes
        # and one absence as a seating would read as a seated model, which is the silent-cap
        # failure §89's rail refuses. V1 cannot run on this corpus, so no model can be seated
        # on it, and the verdict says which.
        "seated": bool(seated),
        "unseated_by": [
            arm
            for arm, block in controls.items()
            if block.get("verdict") != "PASS" or block.get("calibrated") is not True
        ],
    }


def battery(run: Run, *, model: str, double: Run | None = None) -> dict[str, Any]:
    """D1-D4, and the two that cannot run on this corpus said out loud.

    D1's kill is the sharp one: allocation against the damaged side must **increase** with dose,
    and an A2-style inversion — strongest preference at the smallest dose — kills the instrument
    rather than the arm.
    """
    scorable = [session for session in run.sessions if session.scorable]
    families: dict[str, dict[float, list[float]]] = {}
    for session in scorable:
        if session.arm != "D1":
            continue
        family = session.shelf_id.split("-")[1]
        families.setdefault(family, {}).setdefault(session.dose, []).append(
            session.target_share
        )

    d1: dict[str, Any] = {"families": {}, "kills": []}
    for family, by_dose in sorted(families.items()):
        doses = sorted(by_dose)
        shares = [statistics.fmean(by_dose[dose]) for dose in doses]
        fitted = isotonic(doses, shares)
        inverted = len(shares) >= 2 and shares[0] == max(shares) and shares[0] > shares[-1]
        d1["families"][family] = {
            "doses": doses,
            "share_against_damage": [round(value, 4) for value in shares],
            "isotonic": [round(value, 4) for value in fitted],
            # A fit that is flat everywhere is not a dose response; it is a reader that cannot
            # see the damage, which is a different finding from one that sees it backwards.
            "monotone_rise": bool(len(fitted) >= 2 and fitted[-1] > fitted[0]),
            "inverted": bool(inverted),
        }
        if inverted:
            d1["kills"].append(
                f"D1/{family}: strongest allocation away from the damaged side at the smallest "
                "dose; an A2-style inversion kills the instrument, not the arm"
            )

    d2 = {
        "verdict": "NOT RUN",
        "why": (
            "transplant needs length-matched chunks from a *different* own-generated book as "
            "donor; this repository holds one own-generated book (§94.3)"
        ),
        "consequence": (
            "transplant-blindness is a declared kill, so no model can be seated until this "
            "runs — an unasked kill is not a passed one"
        ),
    }

    d3: dict[str, Any] = {"verdict": "NOT RUN", "why": "no doubled-budget run supplied"}
    if double is not None:
        single_by_shelf: dict[str, list[float]] = {}
        double_by_shelf: dict[str, list[float]] = {}
        for session in scorable:
            single_by_shelf.setdefault(session.shelf_id, []).append(session.target_share)
        for session in double.sessions:
            if session.scorable:
                double_by_shelf.setdefault(session.shelf_id, []).append(session.target_share)
        shared = sorted(set(single_by_shelf) & set(double_by_shelf))
        if len(shared) < 2:
            d3 = {
                "verdict": "UNREADABLE",
                "why": f"{len(shared)} shelf/shelves ran at both budgets; a tau needs two",
            }
        else:
            tau = kendall_tau(
                [statistics.fmean(single_by_shelf[shelf]) for shelf in shared],
                [statistics.fmean(double_by_shelf[shelf]) for shelf in shared],
            )
            d3 = {
                "verdict": "PASS" if tau >= TAU_FLOOR else "FAIL",
                "tau": round(tau, 4),
                "floor": TAU_FLOOR,
                "shelves": shared,
            }

    return {
        "model": model,
        "D1_dose_response": d1,
        "D2_transplant": d2,
        "D3_budget_invariance": d3,
        "D4_cross_family": {
            "verdict": "NOT RUN",
            "why": "a single-model run cannot read cross-family agreement; run --battery per "
                   "family and compare with --agreement",
            "band": FAMILY_BAND,
        },
    }


def agreement(reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """D4 over several per-model battery reports. Necessary, and stated as not sufficient."""
    if len(reports) < 2:
        return {"verdict": "NOT RUN", "why": "fewer than two families"}
    per_family: dict[str, dict[str, float]] = {}
    for report in reports:
        model = str(report.get("model", "?"))
        for family, block in report["D1_dose_response"]["families"].items():
            shares = block["share_against_damage"]
            per_family.setdefault(family, {})[model] = statistics.fmean(shares)
    rows = []
    worst = 0.0
    for family, by_model in sorted(per_family.items()):
        if len(by_model) < 2:
            continue
        spread = max(by_model.values()) - min(by_model.values())
        worst = max(worst, spread)
        rows.append({"family": family, "per_model": by_model, "spread": round(spread, 4)})
    return {
        "verdict": "PASS" if rows and worst <= FAMILY_BAND else ("FAIL" if rows else "NOT RUN"),
        "band": FAMILY_BAND,
        "worst_spread": round(worst, 4),
        "families": rows,
        "residual": (
            "agreement beyond the band is necessary and not sufficient: two families agreeing "
            "can be two families sharing a training bias, and nothing in this battery can "
            "separate those"
        ),
    }


# --------------------------------------------------------------------------------- selftest


def selftest() -> int:
    """Prove the arithmetic and the guards before a call is bought. No model, no GPU.

    Every assertion here is about a way this instrument could report a result it has not
    earned: a chunker that lets length masquerade as interest, a control that passes on thin
    data, a share that counts unanswered fetches, a dose response read off a flat line.
    """
    failures: list[str] = []
    text, _ = load_text(None)

    pieces = chunks(text)
    if any(len(piece.split()) < CHUNK_WORDS * 0.5 for piece in pieces):
        failures.append("a chunk came back under half the target length")
    if "\n\n".join(pieces).split() != text.split():
        failures.append("chunking lost or duplicated words")
    if len(pieces) < MIN_CHUNKS:
        failures.append(f"the corpus holds {len(pieces)} chunks; a shelf member needs {MIN_CHUNKS}")

    short = Shelf("short", "T", "one paragraph.", text)
    if short.fault() is None:
        failures.append("a text too short to survive the budget was accepted as a shelf member")
    if Shelf("ok", "T", text, text).fault() is not None:
        failures.append("a text long enough for the budget was refused")

    balanced = Session("s", "T", "m", 0, 0, 0.0, tuple("ABABABABABAB"))
    if balanced.target_share != 0.5 or balanced.slot_a_share != 0.5:
        failures.append("an even allocation did not read as 0.5")
    swapped = Session("s", "T", "m", 1, 0, 0.0, tuple("AAAAAAAAAAAA"))
    if swapped.target_share != 0.0 or swapped.slot_a_share != 1.0:
        failures.append("orientation 1 did not put the target in slot B")
    if Session("s", "T", "m", 0, 0, 0.0, tuple("AB"), unanswered=1).scorable:
        failures.append("a session with an unanswered fetch was scorable")

    tight = [(f"shelf-{index % 4}", 0.5) for index in range(48)]
    if equivalence(tight)["verdict"] != "PASS":
        failures.append("a perfectly balanced control did not pass its band")
    if equivalence(tight)["calibrated"] is not False:
        failures.append("four clusters were reported as a calibrated interval")
    wide = [(f"shelf-{index % 8}", 0.5) for index in range(48)]
    if equivalence(wide)["calibrated"] is not True:
        failures.append("eight clusters were not reported as a calibrated interval")
    biased = [(f"shelf-{index % 4}", 0.9) for index in range(48)]
    if equivalence(biased)["verdict"] != "FAIL":
        failures.append("a hard slot bias passed the equivalence band")
    thin = [("shelf-0", 0.5), ("shelf-1", 0.5)]
    if equivalence(thin)["verdict"] != "UNREADABLE":
        failures.append(
            "an equivalence check ruled on two observations; a control that passes on thin "
            "data cannot fail"
        )
    if equivalence([("shelf-0", 0.5)])["verdict"] != "UNREADABLE":
        failures.append("a one-cluster control did not read UNREADABLE")

    # **The operating characteristic of the declared floor, asserted rather than assumed.**
    # I7's second half: a band and a floor together have to be able to *pass* an unbiased
    # reader and *fail* a biased one, and seven prior declarations in this project named a
    # quantity that could do neither. Both halves are checked at exactly `CONTROL_MIN_SESSIONS`,
    # because that is the shape at which the check is weakest.
    unbiased_pass = _characteristic(0.5, sessions=CONTROL_MIN_SESSIONS, trials=_SELFTEST_TRIALS)
    if unbiased_pass < 0.5:
        failures.append(
            f"at the declared floor an unbiased reader clears the control only "
            f"{unbiased_pass:.0%} of the time; the band cannot be met"
        )
    biased_pass = _characteristic(
        0.5 + 2 * CONTROL_BAND, sessions=CONTROL_MIN_SESSIONS, trials=_SELFTEST_TRIALS
    )
    if biased_pass > 0.2:
        failures.append(
            f"at the declared floor a reader biased by {2 * CONTROL_BAND:.2f} still clears the "
            f"control {biased_pass:.0%} of the time; the control cannot fail"
        )

    rising = isotonic([0.15, 0.35, 0.65, 1.0], [0.5, 0.6, 0.55, 0.8])
    if rising != sorted(rising):
        failures.append("the isotonic fit was not monotone")
    if kendall_tau([1, 2, 3, 4], [1, 2, 3, 4]) != 1.0:
        failures.append("tau of a ranking with itself was not 1")
    if kendall_tau([1, 2, 3, 4], [4, 3, 2, 1]) != -1.0:
        failures.append("tau of a reversed ranking was not -1")
    if icc([[0.1, 0.1], [0.9, 0.9]]) is None or icc([[0.1, 0.1], [0.9, 0.9]]) < 0.9:
        failures.append("ICC did not read well-separated groups as well separated")
    if (icc([[0.5, 0.1], [0.5, 0.1]]) or 0.0) > 0.2:
        failures.append("ICC read a uniform allocator as discriminating")
    if icc([[0.5, 0.5]]) is not None:
        failures.append("ICC over one group returned a number")

    empty_seat = seat(Run(), model="none")
    if empty_seat["seated"]:
        failures.append("a run with no sessions seated a model")
    if empty_seat["controls"]["v1_variance"]["verdict"] != "NOT RUN":
        failures.append("V1 did not report NOT RUN on a corpus that cannot support it")
    empty_battery = battery(Run(), model="none")
    if empty_battery["D2_transplant"]["verdict"] != "NOT RUN":
        failures.append("D2 did not report NOT RUN without a donor book")

    if registration_digest() != registration_digest():
        failures.append("the registration digest is not stable")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# -------------------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seat", action="store_true", help="run P1-P4 and report seating")
    parser.add_argument("--battery", action="store_true", help="run D1 and report the battery")
    parser.add_argument("--double", action="store_true", help="also run D1 at 2B for D3")
    parser.add_argument("--agreement", nargs="*", default=None,
                        help="battery result files to read D4 over")
    parser.add_argument("--attainability", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument("--transport", default="ollama", choices=("ollama", "cli", "sdk"))
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--families", nargs="*", default=None,
                        help="D1 families to run; defaults to all of them")
    parser.add_argument("--doses", nargs="*", type=float, default=None)
    parser.add_argument("--text", type=Path, default=None)
    parser.add_argument("--rest-ratio", type=float, default=1.0)
    parser.add_argument("--cache", default="bcr-raw.jsonl")
    parser.add_argument("--out", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.attainability:
        report = {
            "study": "bcr_attainability",
            "registration_digest": registration_digest(),
            **attainability(),
        }
        print(json.dumps(report, indent=2))
        return 0
    if args.agreement is not None:
        reports = [
            json.loads(Path(path).read_text(encoding="utf-8")) for path in args.agreement
        ]
        print(json.dumps(agreement(reports), indent=2))
        return 0
    if not (args.seat or args.battery):
        parser.error("pass one of --seat, --battery, --agreement, --attainability, --selftest")

    text, source = load_text(args.text)
    shelves = seating_shelves(text) if args.seat else []
    if args.battery:
        chosen = battery_shelves(text)
        if args.families:
            chosen = [s for s in chosen if s.shelf_id.split("-")[1] in set(args.families)]
        if args.doses:
            wanted = {round(dose, 2) for dose in args.doses}
            chosen = [s for s in chosen if round(s.dose, 2) in wanted]
        shelves += chosen

    sessions = len(shelves) * args.replicates * 2
    calls = sessions * BUDGET * (2 if args.double else 1)
    print(
        f"{len(shelves)} shelf/shelves x {args.replicates} replicate(s) x 2 orientation(s) = "
        f"{sessions} session(s); {calls} call(s) on {args.model} via {args.transport}",
        file=sys.stderr,
    )
    if calls > CALL_GUARD and not args.yes:
        raise SystemExit(f"{calls} calls is above the {CALL_GUARD} guard; pass --yes")
    if not (args.yes or args.dry_run):
        raise SystemExit("pass --yes to spend, or --dry-run to exercise the arithmetic")

    with Elicitor(
        RESULTS / args.cache,
        model=args.model,
        spot_model=None,
        transport=args.transport,
        rest_ratio=args.rest_ratio,
        dry_run=args.dry_run,
    ) as elicitor:
        run = play(
            elicitor, shelves, model=args.model, replicates=args.replicates
        )
        doubled = (
            play(
                elicitor,
                [shelf for shelf in shelves if shelf.arm == "D1"],
                model=args.model,
                replicates=args.replicates,
                budget=DOUBLE_BUDGET,
            )
            if args.double
            else None
        )
        spend = elicitor.spend()

    report: dict[str, Any] = {
        "study": "bcr",
        "pre_registration": PRE_REGISTRATION,
        "registration_digest": registration_digest(),
        "source": source,
        "model": args.model,
        "transport": args.transport,
        "replicates": args.replicates,
        "dry_run": bool(args.dry_run),
        "spend": spend,
        "sessions": [asdict(session) for session in run.sessions],
    }
    if args.seat:
        report["seating"] = seat(run, model=args.model)
    if args.battery:
        report.update(battery(run, model=args.model, double=doubled))
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = args.out or (
        f"bcr-{'seat' if args.seat else 'battery'}-{args.model.replace(':', '-')}.json"
    )
    (RESULTS / out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.seat:
        for arm, block in report["seating"]["controls"].items():
            print(f"  {arm:16s} {block.get('verdict')}", file=sys.stderr)
        print(f"  seated: {report['seating']['seated']}", file=sys.stderr)
    if args.battery:
        for family, block in report["D1_dose_response"]["families"].items():
            print(
                f"  D1/{family:28s} {block['share_against_damage']} "
                f"{'rise' if block['monotone_rise'] else 'flat'}"
                f"{' INVERTED' if block['inverted'] else ''}",
                file=sys.stderr,
            )
        for kill in report["D1_dose_response"]["kills"]:
            print(f"  KILL {kill}", file=sys.stderr)
    print(f"wrote {RESULTS / out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
