"""Reader personas defined by taste, not by demography, and the prompts that hold them.

The instrument this file supplies half of: a system-prompted model held in a reader persona and
asked what reading a passage was *like*, rather than how to improve it.
`plan/persona-reader-validity.md` is the protocol and `plan/stage-0-decisions.md` §70 the
licensing argument; this module owns the personas and the exact bytes sent as their system
prompts. `elicit.py` owns the calls.

**Taste anchors, not backstories, and the reason is a failure mode rather than a preference.**
A persona described demographically ("a 34-year-old warehouse worker who reads on his commute")
elicits stereotype performance — a model writing what it thinks that person sounds like — which
is a different behaviour wearing the same words as reading. A persona described by *verdicts
with reasons on named published books* is constrained by something checkable: it either
reproduces its own held-out anchors or it does not. Each persona below is a taste, a named set
of things that make it stop, and nothing else.

**Held-out anchors are the fidelity gate, and they gate the persona rather than the text.**
`Anchor.held_out` entries are never rendered into the system prompt. They are asked separately
(`fidelity_probe`), and a persona that cannot reproduce its own held-out verdicts is refit or
dropped before it is allowed to judge anything. The same probe re-asked at a late boundary is
the drift check: a persona that has collapsed into assistant register answers it differently
from the same persona at boundary one, and its late data is quarantined.

**The v0 anchors are authored, and that is a known limitation with a stated expiry.** Nobody
has yet paid a human reader to produce these verdicts, so they are written here rather than
measured — which means persona *fidelity* in gate 0 and gate 1 is fidelity to an authored
taste, not to a reader. That is sufficient for what those gates ask (do the personas separate;
do they respond to engineered damage) and insufficient for the word "calibrated", which gate 2
is what earns. When gate 2 collects human verdicts on named works, they replace these
wholesale; the `authored` flag on every anchor is how a later reader tells which is which.

**Vocabulary is the audit queue's on purpose.** `VERDICTS` is `--keep-reading` /
`--would-stop` / `--not-sure`, matching §1a.5's bar rather than a rubric, so panel output and
human output are comparable in gate 2 without a mapping layer. Sharing the words inherits none
of the standing — §67 demoted that queue to a smoke check.

**Reason codes are a closed set because an open one cannot be falsified.** Every code below
names a defect a repair could target, which is what makes the protocol's interventional test
possible at all: a code is valid only if a repair aimed at it moves the verdict. Free-text
reasons would make that test unrunnable, so stage 1 carries the prose and stage 2 carries a
code from this list.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The forced-choice vocabulary. Deliberately the audit queue's three, deliberately not a
#: 1-5 scale: §1a.5 words this project's own bar as a behaviour ("would keep reading"), and a
#: scale invites a rubric the ledger has no evidence anyone can fill in consistently.
VERDICTS: tuple[str, ...] = ("keep-reading", "would-stop", "not-sure")

#: Reason codes, each naming something a repair could aim at. Split by which verdict they
#: explain, because a code that can attach to either is a code that explains neither — and
#: because the positive side has to exist: a panel that can only say why it stopped cannot
#: report that a passage pulled it forward, and the stop-only version of this instrument would
#: read every improvement as an absence.
STOP_CODES: tuple[str, ...] = (
    "nothing-at-stake",      # failure here would cost nobody anything
    "no-payoff",             # something was set up and did not land
    "lost-track",            # could not follow who, where, or when
    "jargon-wall",           # terms used as if already known
    "numbers-meaningless",   # progression figures that signal nothing
    "flat-voice",            # the people sound interchangeable
    "padding",               # words without movement
)
KEEP_CODES: tuple[str, ...] = (
    "pulled-forward",        # wanted the next scene specifically
    "stakes-real",           # a cost is now credible
    "voice-landed",          # someone sounded like themselves
    "curious",               # an open question worth waiting on
)
REASON_CODES: tuple[str, ...] = (*STOP_CODES, *KEEP_CODES, "none")


@dataclass(frozen=True, slots=True)
class Anchor:
    """One verdict-with-reason on a named published work.

    `held_out` anchors never reach the system prompt — they are the fidelity and drift probe.
    `authored` records that this verdict was written for the instrument rather than collected
    from a reader, which is true of every anchor in v0 and is the field a later reader uses to
    tell an authored taste from a measured one.
    """

    work: str
    verdict: str
    reason_code: str
    reason: str
    held_out: bool = False
    authored: bool = True

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"{self.work}: {self.verdict!r} is not one of {VERDICTS}")
        if self.reason_code not in REASON_CODES:
            raise ValueError(f"{self.work}: {self.reason_code!r} is not a known reason code")


@dataclass(frozen=True, slots=True)
class Persona:
    """A reader, defined by what it reads for and what makes it stop.

    `reads_for` and `drops_on` are one line each on purpose. A long characterisation is a
    long prompt, and prompt length is the lever that most reliably turns a persona into a
    performance — the model starts serving the description instead of the passage, which is
    the caricature failure the protocol's variance decomposition exists to catch.
    """

    persona_id: str
    name: str
    reads_for: str
    drops_on: str
    anchors: tuple[Anchor, ...]

    @property
    def shown_anchors(self) -> tuple[Anchor, ...]:
        return tuple(anchor for anchor in self.anchors if not anchor.held_out)

    @property
    def held_out_anchors(self) -> tuple[Anchor, ...]:
        return tuple(anchor for anchor in self.anchors if anchor.held_out)


# ------------------------------------------------------------------------------ the panel

#: At most four in v0, per the protocol: a panel is not a cast, and personas the data cannot
#: separate are merged rather than kept for flavour. These four are chosen to be separable by
#: construction — each drops on something the other three tolerate — so that a measured
#: inter-persona rank correlation at or above 0.9 is a real finding about the *instrument*
#: rather than a restatement of four near-identical prompts.
PANEL: tuple[Persona, ...] = (
    Persona(
        persona_id="grinder",
        name="the systems reader",
        reads_for="progression that means something — what a number buys, what it costs",
        drops_on="figures that move without changing what anyone can do",
        anchors=(
            Anchor("Cradle (Unsouled)", "keep-reading", "pulled-forward",
                   "advancement is gated on something specific and I could see the gate"),
            Anchor("Mother of Learning", "keep-reading", "curious",
                   "the loop has rules and the rules are being tested rather than described"),
            Anchor("Delve", "keep-reading", "stakes-real",
                   "the arithmetic is load-bearing; a wrong allocation would actually cost him"),
            Anchor("Dungeon Crawler Carl", "keep-reading", "voice-landed",
                   "the system is a character with an agenda, not a status window", held_out=True),
            Anchor("He Who Fights With Monsters", "not-sure", "numbers-meaningless",
                   "the ranks are legible but I cannot yet tell what losing one would mean",
                   held_out=True),
        ),
    ),
    Persona(
        persona_id="stakes",
        name="the consequence reader",
        reads_for="the sense that failure would cost somebody something they cannot replace",
        drops_on="danger that resolves without anyone paying for it",
        anchors=(
            Anchor("Mother of Learning", "keep-reading", "stakes-real",
                   "the reset is not a get-out; what he loses each loop is the relationships"),
            Anchor("The Wandering Inn", "keep-reading", "stakes-real",
                   "people who mattered stay dead and the book does not flinch from it"),
            Anchor("Worth the Candle", "keep-reading", "curious",
                   "the cost of the fantasy is the actual subject"),
            Anchor("Beware of Chicken", "not-sure", "nothing-at-stake",
                   "charming, and I could not find the thing that would hurt to lose",
                   held_out=True),
            Anchor("Super Supportive", "keep-reading", "pulled-forward",
                   "the social risk is as sharp as the physical kind", held_out=True),
        ),
    ),
    Persona(
        persona_id="voice",
        name="the prose reader",
        reads_for="sentences with a person behind them and dialogue that could only be this cast",
        drops_on="interchangeable speech and paragraphs that could belong to any book",
        anchors=(
            Anchor("Worth the Candle", "keep-reading", "voice-landed",
                   "the narrator's self-deception is in the syntax, not just the content"),
            Anchor("Dungeon Crawler Carl", "keep-reading", "voice-landed",
                   "two lines in and I know exactly who is talking"),
            Anchor("The Wandering Inn", "not-sure", "padding",
                   "the voice is real and there is a great deal of prose between its best moments"),
            Anchor("Cradle (Unsouled)", "not-sure", "flat-voice",
                   "clean and functional; the sentences are doing plot rather than character",
                   held_out=True),
            Anchor("Mother of Learning", "not-sure", "flat-voice",
                   "I stayed for the structure, not the line-level writing", held_out=True),
        ),
    ),
    Persona(
        persona_id="newcomer",
        name="the first-time reader",
        reads_for="a story that lets someone in without prior reading",
        drops_on="terms, ranks and systems used as if already known",
        anchors=(
            Anchor("Cradle (Unsouled)", "keep-reading", "curious",
                   "it taught me the rules through someone failing at them"),
            Anchor("Dungeon Crawler Carl", "keep-reading", "pulled-forward",
                   "I did not need to know the genre to know what was at stake"),
            Anchor("He Who Fights With Monsters", "would-stop", "jargon-wall",
                   "ranks and essences arrived faster than meanings"),
            Anchor("The Wandering Inn", "not-sure", "padding",
                   "welcoming, and I could not tell what I was waiting for", held_out=True),
            Anchor("Delve", "would-stop", "numbers-meaningless",
                   "the tables assume I find allocation interesting before I care about anyone",
                   held_out=True),
        ),
    ),
)

BY_ID: dict[str, Persona] = {persona.persona_id: persona for persona in PANEL}


# ----------------------------------------------------------------------------- prompting


def system_prompt(persona: Persona) -> str:
    """The persona's system prompt, byte-stable for a given persona.

    Byte-stability is load-bearing twice over. It is what lets `elicit.py` put a cache
    breakpoint here and have every passage and every sample read the same cached prefix; and it
    is what makes the digest-keyed replay cache honest, since editing this function invalidates
    exactly the records whose prompt it changed.

    **Three instructions carry the protocol and none of them is decoration.** The persona is
    told to report experience rather than advice, because the whole hypothesis is that the
    reader question has never been asked and the expert question is refuted. It is told not to
    guess what the passage is for, because a passage handed to a model for comment announces an
    evaluation — the demand-characteristics threat PLAN.md §10.3 already spends design on,
    arriving by a different road. And it is told to stop when it would stop, because a reader
    who never stops cannot predict stopping, which is the positivity floor the protocol kills
    the panel over.
    """
    anchors = "\n".join(
        f"- {anchor.work}: {anchor.verdict} — {anchor.reason}"
        for anchor in persona.shown_anchors
    )
    # Held-out works are named here **without their verdicts**, and getting this wrong cost a
    # whole run. The first version omitted them entirely, on the theory that a held-out anchor
    # should be invisible to the persona; the fidelity probe then asked about books the prompt
    # had never said it read, and three of four personas answered — correctly and fatally — "I
    # haven't actually read these books." A model's entire reading history *is* this prompt, so
    # holding out the title holds out the premise, and the probe measured whether the persona
    # would confabulate rather than whether its taste is stable. Naming the title while
    # withholding the verdict is the version that tests what §1 says it tests: the persona knows
    # it read the book and has to produce a verdict its stated taste would produce.
    also_read = "\n".join(f"- {anchor.work}" for anchor in persona.held_out_anchors)
    held_block = (
        f"\n\nOther books you have read and have firm opinions about:\n{also_read}"
        if also_read else ""
    )
    return f"""You are a reader. Not a critic, not an editor, not an assistant.

What you read for: {persona.reads_for}
What makes you put a book down: {persona.drops_on}

Books you have read, and what you did with them:
{anchors}{held_block}

How you answer:
- Report what reading was like for you. Not what would improve it, not what the writer should
  do differently. If you catch yourself giving advice, you have answered the wrong question.
- Do not speculate about why you are being shown this passage or what it is being tested for.
  Read it as what it is: the next part of a book you picked up.
- You are allowed to be bored, confused, or done. If you would stop reading, say so. A reader
  who never stops is no use to anybody.
- You have not read this book before. You do not know where it goes.
- Answer briefly and in your own register. No headings, no bullet lists, no summaries of the
  plot back to yourself."""


STAGE1_QUESTION = (
    "You've just read this. What's going on for you?"
)

STAGE2_QUESTION = (
    "Two things, quickly.\n\n"
    "First: right now, would you keep reading, would you stop, or are you not sure?\n\n"
    "Second: the single thing that most decided that, from this list — "
    "{codes}, or none if nothing on the list fits."
)


def stage1_turn(passage: str) -> str:
    """The unprimed turn. Deliberately names no categories.

    Stage 1 exists so the vocabulary is not planted in the asking: a reader asked "would you
    keep reading?" first will answer stage 2 by defending stage 1. Its output is recorded as
    colour and never calibrated.
    """
    return f"{passage}\n\n---\n\n{STAGE1_QUESTION}"


def stage2_turn() -> str:
    """The forced-choice turn, asked only after stage 1 has been answered."""
    listed = ", ".join(f"`{code}`" for code in REASON_CODES if code != "none")
    return STAGE2_QUESTION.format(codes=listed)


#: JSON Schema for the calibrated half. Closed (`additionalProperties: false`) and fully
#: `required` because the API's structured-output guarantee needs both, and because an absent
#: field defaulting to something benign is exactly how §69's recognition check turned out to be
#: bypassable by omission.
STAGE2_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "reason_code": {"type": "string", "enum": list(REASON_CODES)},
    },
    "required": ["verdict", "reason_code"],
    "additionalProperties": False,
}


# ------------------------------------------------------------------- pairwise elicitation

#: The pairwise choice. `neither` exists because forcing a choice between two texts a reader
#: genuinely cannot separate manufactures signal; the tie policy that handles it is declared
#: before the first comparison, which is §61's pre-registration (2) one instrument over.
PAIR_CHOICES: tuple[str, ...] = ("A", "B", "neither")

PAIR_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "choice": {"type": "string", "enum": list(PAIR_CHOICES)},
        "reason_code": {"type": "string", "enum": list(REASON_CODES)},
    },
    "required": ["choice", "reason_code"],
    "additionalProperties": False,
}

PAIR_QUESTION = (
    "Two passages. Which one would you rather keep reading — A, B, or neither if you truly "
    "cannot separate them?\n\nThen the single thing that most decided it, from this list: "
    "{codes}, or none if nothing on the list fits."
)


def pair_turn(text_a: str, text_b: str) -> str:
    """One blinded comparison, presented without saying what the pair is.

    **Why the absolute question was replaced.** Gate 0 measured the three-way verdict returning
    `keep-reading` on 195 of 196 draws across ten passages and two model tiers — a constant
    function, every variance statistic undefined. This project had already learned that lesson in
    its human channel: §61's raw model judges died to positional artifacts and the answer was
    blinded, position-swapped pairwise comparison, which is what §69 built. A forced choice
    produces variance by construction, and it is also the only standing §70 concluded a persona
    panel could ever earn — selection between candidates, never absolute refusal of one text.

    **The demand characteristic this creates, and the control that answers it.** For a gate-1
    pair the two passages are one scene and its manipulated copy, so they are near-identical and
    a reader will notice. The risk is that noticing turns the task into diff-spotting — an
    editing frame, which is the §1a.2 question this whole programme exists to avoid. Nothing in
    the wording invites a comparison of *edits*: it asks which the reader would rather keep
    reading, not what changed. And the risk is measurable rather than argued away, because the
    placebo arms sit in the same schedule — a diff-spotter detects a character rename exactly as
    readily as a de-stake, so a panel that separates real damage while sitting at chance on the
    shams is choosing on content. That is `evaluate.selftest`'s `change-detector` oracle, and it
    is why the sham control exists at all.

    There is no stage 1 here. Its purpose was to keep the category out of the asking, and a
    forced choice between two texts plants no category — the reader is handed no vocabulary to
    agree with, only two passages.
    """
    listed = ", ".join(f"`{code}`" for code in REASON_CODES if code != "none")
    return (
        f"PASSAGE A\n\n{text_a}\n\n---\n\nPASSAGE B\n\n{text_b}\n\n---\n\n"
        + PAIR_QUESTION.format(codes=listed)
    )


def fidelity_probe(persona: Persona) -> tuple[str, dict[str, object]] | None:
    """Ask a persona for its own held-out anchor verdicts. Also the drift probe.

    Returns `(user_turn, schema)`, or None for a persona with no held-out anchors. Asked before
    any passage — a persona that cannot reproduce these is refit or dropped, because persona
    fidelity is validated before the persona validates anything — and re-asked at a late
    boundary, where a changed answer means the persona has drifted and its late data is
    quarantined rather than pooled.

    The works are named without their anchor verdicts, which is the whole point: the verdicts
    are the answer being checked, and a probe that shows its own answer checks nothing.
    """
    held = persona.held_out_anchors
    if not held:
        return None
    works = "\n".join(f"- {anchor.work}" for anchor in held)
    turn = (
        "Before we go on, some books you've read. For each, would you keep reading, would you "
        "stop, or are you not sure — and the one thing that most decided it?\n\n"
        f"{works}"
    )
    schema = {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "work": {"type": "string"},
                        "verdict": {"type": "string", "enum": list(VERDICTS)},
                        "reason_code": {"type": "string", "enum": list(REASON_CODES)},
                    },
                    "required": ["work", "verdict", "reason_code"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    }
    return turn, schema


def anchor_agreement(persona: Persona, answers: list[dict[str, str]]) -> dict[str, object]:
    """Score a `fidelity_probe` response against the held-out anchors.

    Verdict agreement is the gate; reason agreement is reported beside it and deliberately not
    gated on. A persona can reach the right verdict for a reason it did not state — the
    protocol's confabulation kill condition is about exactly that gap — so requiring both here
    would fail personas for a defect this probe cannot distinguish from paraphrase.
    """
    # Matched case- and whitespace-insensitively: the answer's `work` is free text the model
    # echoes back, and the first run lost every comparison for three personas before the real
    # cause (see `system_prompt`) was visible underneath. An exact-string join is a silent zero.
    expected = {anchor.work.casefold().strip(): anchor for anchor in persona.held_out_anchors}
    matched = verdict_hits = reason_hits = 0
    detail: list[dict[str, object]] = []
    for answer in answers:
        anchor = expected.get(str(answer.get("work", "")).casefold().strip())
        if anchor is None:
            continue
        matched += 1
        verdict_ok = answer.get("verdict") == anchor.verdict
        reason_ok = answer.get("reason_code") == anchor.reason_code
        verdict_hits += verdict_ok
        reason_hits += reason_ok
        detail.append({
            "work": anchor.work,
            "expected_verdict": anchor.verdict,
            "got_verdict": answer.get("verdict"),
            "verdict_ok": verdict_ok,
            "expected_reason": anchor.reason_code,
            "got_reason": answer.get("reason_code"),
            "reason_ok": reason_ok,
        })
    return {
        "persona": persona.persona_id,
        "held_out": len(expected),
        "matched": matched,
        "verdict_agreement": round(verdict_hits / matched, 4) if matched else 0.0,
        "reason_agreement": round(reason_hits / matched, 4) if matched else 0.0,
        "detail": detail,
    }


if __name__ == "__main__":
    for persona in PANEL:
        held = ", ".join(anchor.work for anchor in persona.held_out_anchors)
        print(f"=== {persona.persona_id} ({persona.name})")
        print(f"    shown {len(persona.shown_anchors)}, "
              f"held out {len(persona.held_out_anchors)}: {held}")
    print(f"\nverdicts: {VERDICTS}")
    print(f"reason codes: {len(REASON_CODES)} "
          f"({len(STOP_CODES)} stop, {len(KEEP_CODES)} keep, none)")
    print(f"\n--- system prompt for {PANEL[0].persona_id} ---\n{system_prompt(PANEL[0])}")
