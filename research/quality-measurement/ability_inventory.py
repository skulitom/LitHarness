"""How many distinct things a book's world says somebody can do, and how many reach the page.

**Descriptive. No bar, no pole, no axis.** Nothing here is registered in `axes.COUNTERS`, nothing
here feeds a prompt or a directive, and nothing here may be read as *a book should have more of
these*. `research/quality-measurement/BRIEF.md` §2 owns the count of metrics this project has
refuted, and stage-0 §81, §85, §87 and §89 record four separate occasions on which a bar was
declared over a quantity that could not do what it said. This produces four numbers per book and
stops.

**What nominated it.** The operator read *A Good Take* and said its progression is *"boring
accounting instead of nine unique abilities or level 9 neural speed system"*
(`plan/reader-read-4.md` §1a). The measurement behind that complaint is in
`ability-inventory-results.md`: across the 24 worlds this project has forged, 135 of 156 criterion
rungs are an insignia other people read, and permission outnumbers capability 104 to 46, because
the forge schema had a slot for what a rung **looks like** and what it **costs** and none for what
it **lets you do**. The vocabulary could hold an inventory; nobody was ever asked for one. Stage-0
§114 records the fix. This is how the fix is read back.

**Zero is a fact about the book and not a defect.** Every book this project has drafted was
drafted before a world could declare a capability, so every book below reports zero declared, zero
held, zero named. That is the correct answer and it is the reason the naming half of this module
is exercised by `--selftest` over a synthetic world rather than by the corpus: a code path whose
only evidence is a zero has not been run.

**The four numbers, per book.**

1. `capabilities_declared` — subjects the world tags `entity_role = capability`.
2. `protagonist_capabilities` — of those, the ones the declared protagonist holds on a `can_do`
   edge. `None`, not `0`, when the book declares no protagonist: *"nobody is the protagonist"* and
   *"the protagonist can do nothing"* are different facts, and every book drafted before stage-0
   §112 is the first (`named_persons.protagonist_share` makes the same distinction for the same
   reason).
3. `capabilities_named` — how many are named anywhere in the drafted prose.
4. `first_named_scene` — per capability, the 1-based scene ordinal at which its name first
   appears, or `null` for one that never does.

**The naming rule is `domain/worlds.py::key_nouns`' rule, applied per subject, and it is crude.**
Id parts over three characters that are not structural noise, plus the inner-capital words of that
subject's own name-bearing records. It imports `_ID_NOISE`, `_NAME_BEARING` and `_INNER_CAPITAL`
from that module rather than restating them, so there is one rule here and not two that drift. It
cannot tell a capability's name from a homograph: a capability called `cap_read_a_seam` matches the
common word *seam* wherever it falls. Reported as measured, never repaired after the fact — fixing
a counter once its answer is known is the failure `platform_priors.py` freezes its matchers to
avoid.

Run:

    uv run python research/quality-measurement/ability_inventory.py --selftest
    uv run python research/quality-measurement/ability_inventory.py \
        --book serial.db --book serial3.db --book serial4.db

Databases are opened `mode=ro`. A census must never be able to write to the run it reads.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

import litharness_contracts as lc  # noqa: E402

from litharness.domain import worlds  # noqa: E402

RESULTS = HERE / "results" / "ability-inventory.json"


@dataclass(frozen=True, slots=True)
class Capability:
    """One declared capability and where it first surfaces in the prose."""

    subject: str
    #: Lower-cased tokens that count as this capability being named. See the module docstring.
    names: tuple[str, ...]
    held_by_protagonist: bool
    first_named_scene: int | None

    @property
    def named(self) -> bool:
        return self.first_named_scene is not None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "names": list(self.names),
            "held_by_protagonist": self.held_by_protagonist,
            "first_named_scene": self.first_named_scene,
        }


@dataclass(frozen=True, slots=True)
class BookCount:
    """One book's four numbers, plus the two facts that make them readable."""

    book: str
    scenes: int
    protagonist: str | None
    capabilities: tuple[Capability, ...]

    @property
    def declared(self) -> int:
        return len(self.capabilities)

    @property
    def held(self) -> int | None:
        """`None` when no protagonist is declared, which is not the same as zero."""
        if self.protagonist is None:
            return None
        return sum(1 for item in self.capabilities if item.held_by_protagonist)

    @property
    def named_on_the_page(self) -> int:
        return sum(1 for item in self.capabilities if item.named)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "book": self.book,
            "scenes": self.scenes,
            "protagonist": self.protagonist,
            "capabilities_declared": self.declared,
            "protagonist_capabilities": self.held,
            "capabilities_named": self.named_on_the_page,
            "capabilities": [item.to_jsonable() for item in self.capabilities],
        }


def names_of(records: Sequence[lc.StateRecord], subject: str) -> tuple[str, ...]:
    """Every lower-cased token that counts as `subject` being named on the page.

    `worlds.key_nouns`' rule with its scope narrowed from the world to one subject, reusing that
    module's own three constants so the two cannot drift apart.
    """
    names: set[str] = set()
    for part in subject.split("_"):
        if len(part) > 3 and part not in worlds._ID_NOISE:
            names.add(part.casefold())
    for record in records:
        if record.subject != subject or record.predicate not in worlds._NAME_BEARING:
            continue
        text = record.value if isinstance(record.value, str) else ""
        for word in worlds._INNER_CAPITAL.findall(text):
            names.add(word.casefold())
    return tuple(sorted(names))


def _folded_tokens(text: str) -> set[str]:
    """Whitespace tokens, edge punctuation and case removed. `named_persons._folded_tokens`'
    rule; restated rather than imported because that module carries a locator this one does
    not use and importing it would drag the whole thing in."""
    return {
        word.strip(".,;:!?\"'()[]\N{RIGHT SINGLE QUOTATION MARK}").casefold()
        for word in text.split()
    }


def first_named_scene(names: Sequence[str], scenes: Sequence[str]) -> int | None:
    """The 1-based ordinal of the earliest scene naming any of `names`, or `None`.

    `scenes` arrives in reading order, so this is position in the book rather than position in
    whatever order a database happened to return.
    """
    wanted = set(names)
    if not wanted:
        return None
    for ordinal, text in enumerate(scenes, start=1):
        if wanted & _folded_tokens(text):
            return ordinal
    return None


def count(
    book: str, records: Sequence[lc.StateRecord], scenes: Sequence[str]
) -> BookCount:
    """The four numbers over one book's canon and one book's prose, in reading order."""
    declared = worlds.capabilities(records)
    protagonists = worlds.entities_with_role(records, "protagonist")
    protagonist = protagonists[0] if protagonists else None
    held = frozenset(worlds.capabilities_of(records, protagonist)) if protagonist else frozenset()
    return BookCount(
        book=book,
        scenes=len(scenes),
        protagonist=protagonist,
        capabilities=tuple(
            Capability(
                subject=subject,
                names=(names := names_of(records, subject)),
                held_by_protagonist=subject in held,
                first_named_scene=first_named_scene(names, scenes),
            )
            for subject in declared
        ),
    )


# -- reading a book off disk -----------------------------------------------------------------


def canon_of(path: Path) -> tuple[lc.StateRecord, ...]:
    """Every `accepted_canon` state record in a book database, read-only.

    `record_json` carries the whole record and `lc.from_jsonable` is the hydration
    `adapters/sqlite_store.py:1081` uses, so a record read here is the record the book's own
    detectors saw. Retracted rows are excluded, which is what `is_canon` does downstream anyway.
    """
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT record_json FROM state_records "
            "WHERE authority = 'accepted_canon' AND retracted_by_revision_id IS NULL"
        ).fetchall()
    finally:
        connection.close()
    return tuple(
        lc.from_jsonable(lc.StateRecord, json.loads(row["record_json"])) for row in rows
    )


def prose_of(path: Path) -> dict[str, list[str]]:
    """Drafted scenes per work, in reading order. `corpus_io.generated_scenes` is the loader
    `CONTRIBUTING.md` names, and `Unit.position` is the ordinal a scene actually holds."""
    import corpus_io

    units = corpus_io.generated_scenes(path, min_words=0)
    return {
        work_id: [unit.text for unit in sorted(scenes, key=lambda item: item.position)]
        for work_id, scenes in corpus_io.by_story(units, min_chapters=1).items()
    }


def read_book(path: Path) -> BookCount:
    """One database's four numbers.

    A database holding two works pools their prose, and that is stated rather than hidden: the
    canon table is keyed by `book_id` and every pilot database this project has produced holds
    exactly one book, so pooling has never yet happened. `works` in the payload is what would
    show it if it ever did.
    """
    by_work = prose_of(path)
    scenes = [text for _, texts in sorted(by_work.items()) for text in texts]
    return count(path.name, canon_of(path), scenes)


# -- the self-test, which is where the naming half is actually exercised -----------------------


def _synthetic() -> tuple[tuple[lc.StateRecord, ...], list[str]]:
    """A world declaring three capabilities and a protagonist holding two, with prose naming one.

    Hand-built rather than forged so this module has no dependency on `application/architect`,
    and deliberately asymmetric: one capability named in scene 2 and not scene 1, one never
    named, one held but unnamed. A counter that reports 3 / 2 / 1 / scene 2 over this has run
    every branch that the corpus's zeros leave dark.
    """

    def record(subject: str, predicate: str, **kwargs: Any) -> lc.StateRecord:
        return lc.StateRecord(
            record_id=f"rec-{subject}-{predicate}-{kwargs.get('object_ref') or ''}",
            kind=lc.StateRecordKind.ASSERTION,
            subject=subject,
            predicate=predicate,
            authority=lc.StateAuthority.ACCEPTED_CANON,
            predicate_registry_version=worlds.REGISTRY_VERSION,
            **kwargs,
        )

    records = (
        record("silas", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
        record("silas", worlds.ENTITY_ROLE_PREDICATE, value="protagonist"),
        record("cap_read_a_seam", worlds.ENTITY_ROLE_PREDICATE, value="capability"),
        record("cap_price_unseen", worlds.ENTITY_ROLE_PREDICATE, value="capability"),
        record("cap_sign_for_another", worlds.ENTITY_ROLE_PREDICATE, value="capability"),
        record("silas", worlds.CAN_DO, object_ref="cap_read_a_seam"),
        record("silas", worlds.CAN_DO, object_ref="cap_price_unseen"),
    )
    prose = [
        "He worked the counter all morning and signed nothing.",
        "The seam showed itself the way it always did, and he read it.",
    ]
    return records, prose


def selftest() -> int:
    """Every claim this module makes about itself, run rather than asserted in prose."""
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        print(f"  {'ok  ' if ok else 'FAIL'}  {claim}")
        if not ok:
            failures.append(claim)

    records, prose = _synthetic()
    result = count("synthetic", records, prose)
    check("three capabilities declared", result.declared == 3)
    check("the protagonist holds two", result.held == 2)
    check("one is named on the page", result.named_on_the_page == 1)
    by_id = {item.subject: item for item in result.capabilities}
    check(
        "the named one is first named in scene 2",
        by_id["cap_read_a_seam"].first_named_scene == 2,
    )
    check("a held but unnamed capability reports None", by_id["cap_price_unseen"].named is False)
    check(
        "an unheld capability is not counted as held",
        by_id["cap_sign_for_another"].held_by_protagonist is False,
    )
    check(
        "structural id parts are not names",
        "for" not in by_id["cap_sign_for_another"].names,
    )
    # A book with no protagonist reports None rather than zero, which is the distinction the
    # module docstring makes and the reason `held` is not an int.
    faceless = count(
        "faceless", tuple(r for r in records if r.value != "protagonist"), prose
    )
    check("no protagonist reports None and not zero", faceless.held is None)
    check("and still counts what the world declared", faceless.declared == 3)
    # The absent case: a world with no capabilities reports zero everywhere, which is the answer
    # every book that exists gives.
    empty = count("empty", tuple(r for r in records if "cap_" not in r.subject), prose)
    check("no capabilities reports zero declared", empty.declared == 0)
    check("and zero held rather than None, because a protagonist exists", empty.held == 0)

    print(f"\n{len(failures)} failing" if failures else "\nall claims hold")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    parser.add_argument(
        "--book",
        action="append",
        default=[],
        help="a book database, relative to the repository root or absolute. Repeatable.",
    )
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.book:
        parser.error("--book or --selftest")

    books: list[dict[str, Any]] = []
    for entry in args.book:
        path = Path(entry) if Path(entry).is_absolute() else REPO / entry
        if not path.exists():
            books.append({"book": entry, "status": "NOT RUN", "reason": "no such database"})
            continue
        books.append({"status": "read", **read_book(path).to_jsonable()})

    payload = {
        "instrument": "ability_inventory",
        "reports": "capabilities declared, held by the protagonist, named on the page, "
        "and the scene each is first named in",
        "declares": "no bar, no pole, no axis; descriptive only",
        "books": books,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    for book in books:
        if book.get("status") != "read":
            print(f"{book['book']}: NOT RUN — {book['reason']}")
            continue
        held = book["protagonist_capabilities"]
        print(
            f"{book['book']}: {book['scenes']} scenes, "
            f"{book['capabilities_declared']} declared, "
            f"{'none declared' if held is None else held} held by "
            f"{book['protagonist'] or '(no protagonist)'}, "
            f"{book['capabilities_named']} named on the page"
        )
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
