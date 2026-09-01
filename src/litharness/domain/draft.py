"""The shape gate for a generated draft: §4.2 ladder step 1, deterministic and model-free.

`patch.py` gates a *change* to text that already exists. This gates the other case — a
node that has no prose yet receiving its first draft — and the two are deliberately not
the same function, because the interesting rule is the one that separates them.

**A draft may only fill emptiness. Rewriting existing prose must route through
`apply_patch`.** That is what `DraftPolicy.allow_overwrite = False` enforces, and it is
the structural expression of §1a.2 and §12: unchanged text is ineligible for revision
unless a located complaint licenses it, and `apply_patch` is where that license is
checked (`Veto.UNLICENSED_DELETION`). Without this rule the obvious next move once a
handler can generate and commit is "have it improve the scene it just wrote", which is
precisely the open-ended revision loop the plan forbids — with RevisionBench's ~80%
preference for human originals as the measured evidence against it. Relaxing the default
as a convenience would quietly delete that guarantee, so it is a policy field with a safe
default rather than a parameter callers pass casually.

The vetoes are named and structured rather than boolean because §4.2's ladder feeds a
failed gate back into a bounded retry, and "it failed" is not something a retry can act
on. `SHAPE_NOT_CONFORMING` is the one fed directly by the provider layer:
`CompletionResult.conforms` is false when a schema was requested and the answer did not
satisfy it, which is a retryable shape failure and never an exception.
"""

from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass

from litharness.domain.nodes import Node
from litharness.domain.patch import Veto, VetoRecord
from litharness.domain.revision import Revision
from litharness.domain.text import canonicalize
from litharness.domain.voice import EXHIBITION_MARKERS


@dataclass(frozen=True, slots=True)
class DraftPolicy:
    """Deterministic limits. Named so a policy decision record can cite the values used."""

    #: A draft shorter than this is a stub, a refusal, or a truncated stream. The floor is
    #: low on purpose: this is a shape gate, not a quality gate, and §1a.1 warns against
    #: letting a mechanically checkable number stand in for whether the scene lands.
    min_chars: int = 200
    #: Guards against a runaway generation filling the store, not against verbosity.
    max_chars: int = 8000
    #: See the module docstring. Do not flip this to make a caller's life easier.
    allow_overwrite: bool = False
    #: The house genre floor (`domain/genre.py`): a book whose canon cannot speak system voice
    #: is not drafted at all. Enforced by the planner — `plan_progress` reports it and the
    #: selector refuses in front of the spend — rather than by `gate_draft`, because it is a
    #: fact about the book and not about a candidate string, and because a veto here would be
    #: read by `is_draftable`'s three counting callers as "this scene is already written".
    #:
    #: **Default True so a path that forgets it fails closed.** The dangerous direction for a
    #: floor is a surface that silently skips it; a caller that never mentions this gets the
    #: floor, and one that wants a book without a sheet has to say so where a reader can see
    #: it. It lives in the policy for `target_words`' reason — an input that decides whether a
    #: book produces prose at all and appears in no policy record is the invisible input
    #: `policy_config_digest` exists to catch.
    #:
    #: Turning it off is how the suite drafts the golden mystery fixture, which is a book this
    #: house would not publish and exactly what the floor is for.
    require_starting_sheet: bool = True
    #: How long a scene the generator is **asked** for. A target, never a limit: nothing here
    #: checks it, and `gate_draft` keeps refusing only stubs and runaways.
    #:
    #: **It lives in the policy so the decision record cites it.** Measured on the first Book
    #: Zero run, a 3B model wrote a mean of 160 words per scene — 24 scenes came to under
    #: 4,000 words against §17 Stage 3's 50-80k — because nothing ever told it how long a
    #: scene is. An input that shapes every piece of prose in the book and appears in no
    #: policy record is exactly the invisible input `policy_config_digest` exists to catch.
    #:
    #: §1a.1 is the reason it is not a gate. "Beware the metric that is easy *because* it is
    #: shallow": a length floor raised to 900 words would make a scene that rambles for 900
    #: words pass and a taut one fail, which measures nothing about whether the scene lands.
    #: Asking is a generation instruction; refusing would be a quality claim this project has
    #: no evidence for.
    #:
    #: The default sits well under `max_chars`: at roughly six characters per word, 900 words
    #: is ~5,400 characters against a 8,000-character ceiling, so a model that overshoots by a
    #: third is still accepted rather than refused for obeying the instruction.
    target_words: int = 900


@dataclass(frozen=True, slots=True)
class DraftOutcome:
    accepted: bool
    vetoes: tuple[VetoRecord, ...] = ()
    revision: Revision | None = None
    node_before: Node | None = None
    node_after: Node | None = None
    chars: int = 0
    #: What arrived, beside what was asked for. `policy_config_digest` records
    #: `target_words`; without these the record cited the instruction and never the result,
    #: and the gap between them is the number that decides whether §17 Stage 3 is reachable.
    #: Measured across every stored run — 45 scenes over six books — the mean scene is 172
    #: words against a 900-word target, 19%, ranging 14% to 40%.
    words: int = 0
    target_words: int = 0

    @property
    def veto_kinds(self) -> tuple[Veto, ...]:
        return tuple(record.veto for record in self.vetoes)


#: The registered mark, read from its one home rather than spelled again here. See
#: `strip_em_dash` for why that matters more than it looks.
_EM_DASH = EXHIBITION_MARKERS["em_dash"]

#: Characters that close a quotation, and the ones that open one. Both carry the straight forms
#: and the curly ones, because a draft arrives in whichever the model reached for and NFC does
#: not fold them together. Written as escapes rather than as themselves: a table of quotation
#: marks is the one place where a reader cannot tell two characters apart by looking.
_CLOSING_QUOTES = "\"'\u2019\u201d"
_OPENING_QUOTES = "\"'\u2018\u201c"

#: A line the book prints as a machine rather than as prose. Same shape as `integrity`'s system
#: block and `library`'s system line, and it is here for one specific reason recorded at
#: `strip_em_dash`: the canon parser's own separator is an em dash.
_SYSTEM_LINE = re.compile(r"^\[[A-Z][A-Z ]*\]")

#: The mark and any whitespace hugging it, without crossing a line.
_AROUND_MARK = re.compile(rf"[^\S\n]*{re.escape(_EM_DASH)}[^\S\n]*")

#: Punctuation that already ends a clause, so a comma after it would be a second one.
_ALREADY_STOPPED = ",;:.!?"


def strip_em_dash(text: str) -> tuple[str, int]:
    """`text` with the em dash rewritten out of its prose, and how many were rewritten.

    **Why this is mechanical and not a sentence in `house`.** The em dash is the one prose
    defect on this project's list that is a *character*, and it is the one the operator has
    now named twice with no drafting rule ever written against it in between — read 1's own
    axis, returning at read 11. A clause in `house.CLARITY` would cost a demand at every role
    that stands on the floor, would land inert at the ones that write no prose, and would be
    the project instructing about a **registered prose axis** in the one text that reaches
    every prose call — which is the act `directors._CRAFT_INSTRUCTION` and
    `writers.legal_dossier` refuse a brief and a dossier for, done at a larger address. This
    function asserts nothing in any prompt about what good prose is. It removes a character
    after the model has finished, and it cannot drift.

    **The mark has one home and this is not it.** `voice.EXHIBITION_MARKERS["em_dash"]` is the
    registered mark, and this reads it rather than spelling it again, so the character a
    dossier is refused for carrying and the character a draft has removed can never diverge.

    **What is kept, and it is a device rather than a habit.** An em dash immediately before a
    closing quote or at the end of a line, or immediately after an opening quote, is speech
    being cut off. Measured over the ten drafted books on the shelf, that is a sixth of every
    em dash in the prose and no substitution preserves it: a comma there makes an interruption
    into a clause, and an ellipsis makes it into a trailing-off, which is a different thing
    happening to a different character. The other five sixths are the spaced habit and all of
    them go. *Immediately* is load-bearing — a space between the quote and the mark makes it
    the habit again.

    **What it must not touch, and the failure would have been silent.** `extraction`'s canon
    parser keys on a bare U+2014 as the `[STATUS]` line's own separator, with no alternation;
    rewriting that one would leave a scene that renders a status panel and extracts no state,
    which is exactly the shape that module's docstring warns is indistinguishable from a scene
    that established nothing. So a line the book prints as a machine is passed through
    untouched, and `tests/test_sentence_structure.py` is what holds that.

    **A comma, because a comma is the one replacement that is always grammatical.** A full stop
    would make a fragment of whatever followed a dash that was not joining two clauses, and a
    rewrite that can produce ungrammatical prose is worse than the mark. It is also the
    operation this project's own research side already certified as the em-dash repair, so
    production and the instrument do the same thing rather than two things. Where the text
    before the mark already ends on a stop, the mark leaves a space and no second comma.

    Returns the count as well as the text so a caller can put it on the record: the point of
    recording it is that removing the mark from the prose would otherwise remove the only way
    anybody could later see how often the model reached for it.
    """
    if _EM_DASH not in text:
        return text, 0

    removed = 0

    def rewrite(line: str) -> str:
        if _SYSTEM_LINE.match(line) or _EM_DASH not in line:
            return line

        def replace(match: re.Match[str]) -> str:
            nonlocal removed
            index = match.start() + match.group().index(_EM_DASH)
            before = line[index - 1] if index > 0 else ""
            after = line[index + 1] if index + 1 < len(line) else ""
            if after == "" or after in _CLOSING_QUOTES or before in _OPENING_QUOTES:
                return match.group()
            removed += 1
            stopped = line[:index].rstrip()[-1:]
            return " " if stopped in _ALREADY_STOPPED else ", "

        return _AROUND_MARK.sub(replace, line)

    return "\n".join(rewrite(line) for line in text.split("\n")), removed


#: Markdown emphasis and heading markers, which a model reaches for as naturally as it reaches
#: for the em dash and which a pastable chapter prints as asterisks and hashes. Pilot 21's
#: first draw put `**Nobody**` on the page (`plan/serial-pilot-21.md` §5.1). Strong emphasis
#: first so its markers are not read as two italic runs; the italic form refuses a run that
#: opens or closes on a space, so a scene-break line of spaced asterisks is not emphasis.
_STRONG = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_EMPHASIS = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
_HEADING = re.compile(r"^#{1,6}[ \t]+")


def strip_markup(text: str) -> tuple[str, int]:
    """`text` with markdown emphasis and heading markers removed from its prose, and how many.

    `strip_em_dash`'s sibling and held to its rules: mechanical, after the model has finished,
    asserting nothing in any prompt; a line the book prints as a machine passes through
    untouched, because `[STATUS]` and its kin are parsed by character; and the count comes back
    so the record can say how often the model reached for the markers. The words inside the
    markers are kept exactly — only the markup goes.
    """
    if "*" not in text and "#" not in text:
        return text, 0
    removed = 0

    def rewrite(line: str) -> str:
        nonlocal removed
        if _SYSTEM_LINE.match(line):
            return line
        line, headings = _HEADING.subn("", line)
        line, strong = _STRONG.subn(r"\1", line)
        line, emphasis = _EMPHASIS.subn(r"\1", line)
        removed += headings + strong + emphasis
        return line

    return "\n".join(rewrite(line) for line in text.split("\n")), removed


def draft_block(
    revision: Revision,
    logical_id: str,
    *,
    policy: DraftPolicy | None = None,
) -> VetoRecord | None:
    """The *structural* veto that would refuse a first draft of this node, or None.

    Structural means: a property of the target, knowable before any text exists. Length and
    schema conformance are properties of the *candidate* and stay in `gate_draft`.

    **This function exists so a planner cannot disagree with the gate.** Selection has to
    ask "is this node draftable" and the gate has to ask "may this draft land", and if those
    are two implementations they will drift — and the drift is not benign. `CONTENT_LOCKED`
    and `TARGET_HAS_NO_CONTENT` are in neither `RETRYABLE` nor `REGENERABLE`, so `decide`
    escalates them on the first attempt and `_settle` parks the unit *and files an
    exception*. A selector that offered a node the gate would refuse would therefore fill
    the queue §4.3 reserves for the director with work nobody asked a human about. One
    function, two callers, no drift possible.
    """
    policy = policy or DraftPolicy()
    try:
        node = revision.node(logical_id)
    except KeyError:
        return VetoRecord(Veto.UNKNOWN_TARGET, f"no node {logical_id} in revision")

    if node.tombstoned:
        return VetoRecord(Veto.UNKNOWN_TARGET, f"node {logical_id} is tombstoned")

    if node.lock.freezes_content:
        return VetoRecord(
            Veto.CONTENT_LOCKED,
            f"node {logical_id} is {node.lock.value}-locked and its content is frozen",
        )

    if node.content is not None and not policy.allow_overwrite:
        return VetoRecord(
            Veto.TARGET_HAS_NO_CONTENT,
            f"node {logical_id} already carries {len(node.content)} characters; "
            "a rewrite needs a located complaint and must go through apply_patch",
        )
    return None


def is_draftable(
    revision: Revision, logical_id: str, *, policy: DraftPolicy | None = None
) -> bool:
    """Whether a first draft of this node could land. The planner's precondition."""
    return draft_block(revision, logical_id, policy=policy) is None


def gate_draft(
    revision: Revision,
    logical_id: str,
    text: str,
    *,
    conforms: bool = True,
    policy: DraftPolicy | None = None,
) -> DraftOutcome:
    """Gate ``text`` as the first draft of ``logical_id``, or refuse it with named vetoes.

    Returns the new revision on acceptance; it does not persist anything. Committing is
    the Conductor's job, because only the Conductor can put the revision, its events and
    the job's status change in one transaction.
    """
    policy = policy or DraftPolicy()

    # `conforms` is checked before the structural block only so a malformed answer reports
    # as a retryable shape failure rather than as a property of the target.
    if not conforms:
        node = None
        with suppress(KeyError):
            node = revision.node(logical_id)
        return DraftOutcome(
            False,
            (
                VetoRecord(
                    Veto.SHAPE_NOT_CONFORMING,
                    "provider answer did not satisfy the requested schema",
                ),
            ),
            node_before=node,
        )

    blocked = draft_block(revision, logical_id, policy=policy)
    if blocked is not None:
        node = None
        with suppress(KeyError):
            node = revision.node(logical_id)
        return DraftOutcome(False, (blocked,), node_before=node)

    node = revision.node(logical_id)
    canonical = canonicalize(text)
    if not canonical.strip():
        return DraftOutcome(
            False,
            (VetoRecord(Veto.EMPTY_DRAFT, "draft is empty or whitespace only"),),
            node_before=node,
        )

    vetoes: list[VetoRecord] = []
    if len(canonical) < policy.min_chars:
        vetoes.append(
            VetoRecord(
                Veto.LENGTH_MOVEMENT,
                f"draft is {len(canonical)} chars, below the floor of {policy.min_chars}",
            )
        )
    if len(canonical) > policy.max_chars:
        vetoes.append(
            VetoRecord(
                Veto.LENGTH_MOVEMENT,
                f"draft is {len(canonical)} chars, above the ceiling of {policy.max_chars}",
            )
        )
    if vetoes:
        return DraftOutcome(False, tuple(vetoes), node_before=node)

    updated = node.with_content(canonical)
    return DraftOutcome(
        accepted=True,
        revision=revision.replacing([updated]),
        node_before=node,
        node_after=updated,
        chars=len(canonical),
        words=len(canonical.split()),
        target_words=policy.target_words,
    )


__all__ = [
    "DraftOutcome",
    "DraftPolicy",
    "draft_block",
    "gate_draft",
    "is_draftable",
    "strip_em_dash",
]
