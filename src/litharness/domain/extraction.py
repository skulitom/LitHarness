"""§12 step 5: reading state back out of accepted prose.

The gap this closes is structural rather than cosmetic. `domain/integrity.py` implements one
in-process detector, `state.contradiction.v0`, and its docstring names the corruption it
exists to catch: "§12 step 5's extraction writing a record that contradicts one already
accepted — can only happen inside the loop." That extraction did not exist. Records entered
the store only through `cli import`, `EventType.STATE_CANDIDATES_EXTRACTED` had no producer,
and **nothing anywhere in `src/` constructed a `StateRecord`** — so the detector could not
fire, and Stage 2's "repairs triggered by findings" had no in-process trigger to be built on.

**Extraction mints nothing, and that is the whole design.** Not the order key, not the
subject, not the value:

- The **order key** is read back out of the book's own imported evidence (`attested_position`)
  and abstains when the book has not answered. `domain/state.py` forbids deriving one, in
  terms worth repeating: `order_key` is opaque, its author chose it, and *nothing anywhere
  defines a mapping from a manuscript scene to one*. Measured, the obvious `f"s{ordinal}"`
  reproduces the litrpg fixture 19/19 and mis-slices the mystery 2 of 15 — it works on one of
  the two books in the project and fails the one whose genre (an analepsis: scene 5 is
  attested at `s1`) guarantees it. A scheme that is right on your test book and silently
  wrong on the next is worse than abstention.
- The **subject** must already name a subject some canon record uses. A new name is a fact
  about a character the store has never heard of, which is a proposal, not a reading.
- The **value** is the prose's, verbatim, never reconciled against canon. The litrpg fixture's
  scene 4 says `HP 34/30` because §8.3 planted `f-hp-over-max` there. An extractor that
  "corrected" it would erase the defect on the way in — the detector's own input, sanitised
  by its producer.

So the chain is **decision → prose → record**: a recorded policy decision accepted the prose,
and this is a mechanical restatement of that prose asserting nothing the decision did not.
That is why a record from here may carry `ACCEPTED_CANON` without violating §11's rule that
no proposal becomes canon merely because a model returned it — no model returned it. A model
leg would be a different question and is deliberately not built (see PLAN.md §17 Stage 1).

**Reach, stated plainly so a green Stage 1 is not read as more than it is.** This reads system
voice — the `[STATUS]` line LitRPG puts on the page — and nothing else. The mystery fixture
contains no such line and yields zero records; nothing here touches prose-semantic facts like
"Brandt knows about the letter", which need a model. Until the generator is asked to emit
system voice, extraction yields records only for prose that already carries it. What it does
change is that the detector goes from having no producer at all to one that runs on every
accepted scene and demonstrably fires.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain.events import payload_digest
from litharness.domain.text import content_hash

#: The system-voice status line, anchored at the start of a line so it cannot match prose
#: that merely mentions a bracket. The name runs to an em dash, which is how both the fixture
#: and the genre write it; `[^\S\n]` rather than `\s` keeps the match on one line.
STATUS_PATTERN = re.compile(
    r"^\[STATUS\][^\S\n]*(?P<subject>[^\n|]+?)[^\S\n]*—[^\S\n]*"
    r"Level[^\S\n]+(?P<level>\d+)[^\S\n]*\|"
    r"[^\S\n]*HP[^\S\n]+(?P<hp>\d+)/(?P<hp_max>\d+)[^\S\n]*\|"
    r"[^\S\n]*MP[^\S\n]+(?P<mp>\d+)/(?P<mp_max>\d+)[^\S\n]*\|"
    r"[^\S\n]*Gold[^\S\n]+(?P<gold>\d+)",
    re.MULTILINE,
)

#: The predicate every record from this module carries. One predicate, because the detector
#: groups on it and a vocabulary invented here would be a second answer to a question §8.4
#: gives ContinuityEvaluation.
STATUS_PREDICATE = "status_snapshot"

#: Named so a later registry change is a visible version bump rather than a silent reread.
#: Deliberately not the fixtures' `fixture.v1`: these records are this extractor's reading,
#: and borrowing the fixture's version would make them indistinguishable from authored ones.
REGISTRY_VERSION = "litharness.systemvoice.v0"


def normalise_subject(name: str) -> str:
    """A subject id from a prose name. NFC, casefolded, whitespace collapsed to underscores."""
    folded = unicodedata.normalize("NFC", name).strip().casefold()
    return re.sub(r"\s+", "_", folded)


def attested_position(
    records: Sequence[lc.StateRecord], logical_id: str
) -> str | None:
    """The story position this scene is attested at, or None when the book has not said.

    Reads the answer out of the imported snapshot instead of computing it: a canon record
    whose evidence cites this scene is the book's own statement about where the scene sits in
    story time. Ambiguity abstains rather than picking — the mystery's scene 2 is cited by
    records at both `s1` and `s2`, and choosing either would be inventing the very mapping
    `domain/state.py` refuses to invent.

    **None means do not extract, never "extract unplaced".** `detect_contradictions` groups on
    `order_key_of(record) or ""`, so an unplaced record shares a bucket with every other
    unplaced record — the coarsest possible collision scheme wearing the costume of caution.
    """
    keys = {
        key
        for record in records
        if state_mod.is_canon(record) and (key := state_mod.order_key_of(record))
        if any(span.source.logical_id == logical_id for span in record.evidence)
    }
    return next(iter(keys)) if len(keys) == 1 else None


def record_id_for(
    subject: str, predicate: str, order_key: str, value: Mapping[str, object]
) -> str:
    """Content-derived, and **value-sensitive on purpose**.

    A replayed tick must converge rather than accumulate, so the id cannot carry the revision
    or the logical id. But keying on `(subject, predicate, order_key)` alone makes the
    detector permanently unreachable: `record_state_records` is `INSERT OR IGNORE`, so a
    contradicting record would collide with the one it contradicts, insert zero rows, leave
    the old value standing, and report success. Including the value means two disagreeing
    readings are two rows — which is exactly what the detector needs to see them.
    """
    material = payload_digest(
        {"s": subject, "p": predicate, "k": order_key, "v": value}
    )
    return f"rec-x{sha256(material.encode()).hexdigest()[:24]}"


def extract_state(
    text: str,
    *,
    known: Sequence[lc.StateRecord],
    project_id: str,
    book_id: str,
    branch_id: str,
    logical_id: str,
    version_id: str,
    replacing_logical_id: str | None = None,
) -> tuple[lc.StateRecord, ...]:
    """State records read out of one scene's accepted prose.

    Pure: no store, no provider, no clock. `text` must be the **canonicalized** node content
    (`gate_draft` produces it), never the raw provider string — spans and `content_sha256`
    have to live in the NFC+LF coordinate space the contracts package resolves them in, and
    an offset measured against the raw text points at the wrong characters.

    Returns empty rather than raising on anything it cannot read. A scene with no system
    voice is the normal case, not an error.
    """
    order_key = attested_position(known, logical_id)
    if order_key is None:
        return ()
    subjects = {record.subject for record in known if state_mod.is_canon(record)}

    extracted: list[lc.StateRecord] = []
    for match in STATUS_PATTERN.finditer(text):
        subject = normalise_subject(match.group("subject"))
        # A name canon has never used is a claim about someone new, which is a proposal
        # rather than a reading of what the book already established.
        if subject not in subjects:
            continue
        value = {
            "level": int(match.group("level")),
            "hp": int(match.group("hp")),
            "hp_max": int(match.group("hp_max")),
            "mp": int(match.group("mp")),
            "mp_max": int(match.group("mp_max")),
            "gold": int(match.group("gold")),
        }
        # Already established, identically, at this position: the record adds nothing, and
        # writing it anyway costs a permanent duplicate in every later context packet.
        if _already_canon(
            known,
            subject,
            order_key,
            value,
            replacing_logical_id=replacing_logical_id,
        ):
            continue
        start, end = match.span()
        extracted.append(
            lc.StateRecord(
                record_id=record_id_for(subject, STATUS_PREDICATE, order_key, value),
                kind=lc.StateRecordKind.ASSERTION,
                subject=subject,
                predicate=STATUS_PREDICATE,
                value=value,
                story_position=lc.StoryPosition(order_key=order_key),
                authority=lc.StateAuthority.ACCEPTED_CANON,
                pov_visibility=[],
                evidence=[
                    lc.EvidenceSpan(
                        source=lc.ResourceRef(
                            project_id=project_id,
                            book_id=book_id,
                            branch_id=branch_id,
                            logical_id=logical_id,
                            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                            version_id=version_id,
                        ),
                        start=start,
                        end=end,
                        content_sha256=content_hash(text[start:end]),
                    )
                ],
                # No confidence. A regex match has no probability, and a fabricated 1.0 would
                # read downstream as a critic's score rather than as a parse.
                predicate_registry_version=REGISTRY_VERSION,
            )
        )
    return tuple(extracted)


def _already_canon(
    known: Sequence[lc.StateRecord],
    subject: str,
    order_key: str,
    value: Mapping[str, object],
    *,
    replacing_logical_id: str | None = None,
) -> bool:
    return any(
        record.subject == subject
        and record.predicate == STATUS_PREDICATE
        and state_mod.order_key_of(record) == order_key
        and record.value == value
        for record in known
        if state_mod.is_canon(record)
        and not (
            replacing_logical_id is not None
            and any(
                span.source.logical_id == replacing_logical_id
                for span in record.evidence
            )
        )
    )


__all__ = [
    "REGISTRY_VERSION",
    "STATUS_PATTERN",
    "STATUS_PREDICATE",
    "attested_position",
    "extract_state",
    "normalise_subject",
    "record_id_for",
]
