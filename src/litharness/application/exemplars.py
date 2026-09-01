"""The exemplar shelf: openings the operator placed, shown to the writer for how the shelf sounds.

**This is the one place corpus prose crosses to the generation side, and it crosses under the
operator's decision of 2026-09-02** (stage-0 §196), which reversed RS1 for exactly this: chapter
ones and blurbs the operator placed on the shelf by hand, read at draft time from a directory
outside the repository, shown to the writer as register and never as story. Fifteen reads had
named one register from fifteen directions, every clause written against it moved one shape and
left the register, and the one lever never pulled was showing the writer the target. The read
that decided it is `plan/reader-read-15.md`.

**What the reversal does not do, and each of these is enforced rather than promised.**

- No exemplar text is ever committed. The shelf lives under a gitignored directory the operator
  names (`--exemplars`, `LITHARNESS_EXEMPLARS`); nothing here writes a file, and the leak audit
  over every committed blob still runs.
- No exemplar text may reach the page. `gate_exemplar_leak` refuses any draft that shares a run
  of `LEAK_RUN_WORDS` consecutive words with any exemplar shown, deterministically, on the same
  ladder every other deterministic gate blocks on — the borrowing control `voice_binding`
  registered at §89.5 and `domain/voice.py` carries as `longest_shared_run`, one rung stricter
  in words because a chapter is longer than a passage.
- The measurement side loses the anchors. A book drafted with a shelf cannot be read by a panel
  against the openings it was shown; `research/opening-parity/PREREG.md` §6 records which
  summits stay held out.
- Absent a shelf, every prompt is byte-identical to what it was: `render_prompt` adds nothing,
  the listing adds nothing, the ladder runs no extra gate, and the job payload carries no
  `exemplars` key. That is the control every measurement of this is read against.

The shelf is data, not a rule: the writer is told what the block is and what may not be taken
from it, and nothing about how to write.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from litharness.domain.patch import Veto
from litharness.domain.policy import GateKind, GateOutcome, VerdictSource
from litharness.domain.voice import longest_shared_run

#: The file each exemplar folder must hold, and the one it may.
CHAPTER_FILE = "Chapter1.txt"
BLURB_FILE = "blurb.txt"
#: An optional file at the shelf root: `{"order": ["PrimalHunter", ...]}` names which folders
#: come first; folders it does not name follow in name order.
ORDER_FILE = "exemplars.json"

#: How many exemplars a writer is shown by default. Two, because the operator named two first
#: and a scene call already carries a world; `--exemplars-limit` moves it.
DEFAULT_LIMIT = 2

#: Where an exemplar chapter is cut, in words, extended to the paragraph boundary. The two
#: openings the operator named first run 1,563 and 1,631 words and are shown whole; a longer
#: one is cut so that one exemplar cannot crowd out the other.
CHAPTER_WORDS = 2000

#: The longest run of consecutive words a draft may share with a shown exemplar. Eight: `voice`
#: refuses a rewrite at six against one shown passage, and this is one text against two
#: chapters of another writer's, so the bar sits two words higher and still catches a lifted
#: clause — two texts about different things share an eight-word run essentially never.
LEAK_RUN_WORDS = 8

#: The rule id every leak gate row carries.
LEAK_GATE = "exemplar.leak.v0"

#: The heading the block carries in the prompt, and the one sentence the system carries when a
#: shelf is shown. Material and a prohibition, nothing about how to write: the block says whose
#: it is and what it is for, and the sentence says what may not be taken from it.
OPENINGS_HEADING = (
    "How this shelf sounds: the opening chapters of two other books on it, by other writers. "
    "Nothing in them is true of this book."
)
BLURBS_HEADING = (
    "How this shelf's listings sound: the listings of other books on it, by other writers. "
    "Nothing in them is true of this book."
)
SHELF_SYSTEM = (
    "The chapters under the heading that says how this shelf sounds are other writers' and are "
    "true of nothing in this book: no name, place, thing or line of theirs may appear in yours."
)

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


@dataclass(frozen=True, slots=True)
class Exemplar:
    """One placed opening: its folder name, a readable title, the chapter as shown, the blurb."""

    name: str
    title: str
    chapter: str
    blurb: str | None
    digest: str
    words: int

    def record(self) -> dict[str, object]:
        """What the job payload says about this exemplar: identity and size, never the text."""
        return {"name": self.name, "title": self.title, "digest": self.digest, "words": self.words}


@dataclass(frozen=True, slots=True)
class Shelf:
    """The exemplars shown to a writer, in the order they are shown."""

    root: Path
    exemplars: tuple[Exemplar, ...]

    def record(self) -> list[dict[str, object]]:
        return [exemplar.record() for exemplar in self.exemplars]

    @property
    def digest(self) -> str:
        material = "\x00".join(exemplar.digest for exemplar in self.exemplars)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _title_of(folder: str) -> str:
    return " ".join(part for part in _CAMEL.split(folder) if part).strip() or folder


def _paragraphed(raw: str) -> str:
    """A chapter saved with one newline per paragraph, re-separated by blank lines."""
    if "\n\n" in raw or "\n" not in raw.strip():
        return raw
    return re.sub(r"\n+", "\n\n", raw.strip()) + "\n"


def _first_words(text: str, limit: int) -> str:
    """The first `limit` words extended to the next paragraph boundary; the whole text if short."""
    paragraphs = text.split("\n\n")
    seen = 0
    for index, paragraph in enumerate(paragraphs):
        seen += len(paragraph.split())
        if seen >= limit:
            return "\n\n".join(paragraphs[: index + 1])
    return text


def _ordered(root: Path, folders: Sequence[Path]) -> list[Path]:
    order_file = root / ORDER_FILE
    named: list[str] = []
    if order_file.is_file():
        loaded = json.loads(order_file.read_text(encoding="utf-8"))
        named = [str(item) for item in loaded.get("order", [])] if isinstance(loaded, dict) else []
    by_name = {folder.name: folder for folder in folders}
    first = [by_name[name] for name in named if name in by_name]
    rest = sorted((folder for folder in folders if folder.name not in named), key=lambda f: f.name)
    return [*first, *rest]


def load_shelf(
    root: Path | None, *, limit: int = DEFAULT_LIMIT, chapter_words: int = CHAPTER_WORDS
) -> Shelf | None:
    """The shelf under `root`, or `None` for no root — the control.

    A folder is an exemplar when it holds `Chapter1.txt`; a shelf with none raises, because a
    directory the operator named that shows the writer nothing is a misconfiguration and not a
    control. Order is `exemplars.json`'s, then name order; `limit` takes the first that many.
    """
    if root is None:
        return None
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"exemplar shelf {root} is not a directory")
    folders = [path for path in root.iterdir() if path.is_dir() and (path / CHAPTER_FILE).is_file()]
    if not folders:
        raise FileNotFoundError(f"exemplar shelf {root} holds no folder with {CHAPTER_FILE}")
    exemplars: list[Exemplar] = []
    for folder in _ordered(root, folders)[: max(0, limit)]:
        raw = _paragraphed((folder / CHAPTER_FILE).read_text(encoding="utf-8")).strip()
        if not raw:
            raise ValueError(f"{folder / CHAPTER_FILE} is empty")
        chapter = _first_words(raw, chapter_words)
        blurb_path = folder / BLURB_FILE
        blurb = blurb_path.read_text(encoding="utf-8").strip() if blurb_path.is_file() else None
        exemplars.append(
            Exemplar(
                name=folder.name,
                title=_title_of(folder.name),
                chapter=chapter,
                blurb=blurb or None,
                digest=hashlib.sha256(chapter.encode("utf-8")).hexdigest()[:16],
                words=len(chapter.split()),
            )
        )
    if not exemplars:
        return None
    return Shelf(root=root, exemplars=tuple(exemplars))


def render_openings(shelf: Shelf) -> str:
    """The block the scene writer is shown, headed with whose it is and what it is for."""
    parts = [OPENINGS_HEADING]
    for exemplar in shelf.exemplars:
        parts.append(f"— {exemplar.title}, chapter one —\n{exemplar.chapter}")
    return "\n\n".join(parts)


def render_blurbs(shelf: Shelf) -> str | None:
    """The listings block for the listing writer, or `None` when no exemplar carries a blurb."""
    blurbs = [exemplar for exemplar in shelf.exemplars if exemplar.blurb]
    if not blurbs:
        return None
    parts = [BLURBS_HEADING]
    parts.extend(f"— {exemplar.title} —\n{exemplar.blurb}" for exemplar in blurbs)
    return "\n\n".join(parts)


def leak(candidate: str, shelf: Shelf, *, limit: int = LEAK_RUN_WORDS) -> tuple[str, int] | None:
    """(exemplar title, run length) for the longest shared run at or over `limit`, else `None`."""
    worst: tuple[str, int] | None = None
    for exemplar in shelf.exemplars:
        run = longest_shared_run(candidate, exemplar.chapter)
        if run >= limit and (worst is None or run > worst[1]):
            worst = (exemplar.title, run)
    return worst


def gate_exemplar_leak(candidate: str, shelf: Shelf | None) -> GateOutcome | None:
    """§4.2's ladder, one rung further: nothing shown as register may reach the page as text.

    `None` when no shelf was shown, so a book drafted without one carries no extra gate row —
    the control. Otherwise a row is written whether it passed or failed, and a failure carries
    the exemplar and the run length so the refusal is legible. Blocking and deterministic, for
    `progression._outcome`'s reason: the verdict is arithmetic over two texts.
    """
    if shelf is None:
        return None
    found = leak(candidate, shelf)
    if found is None:
        passed = True
        detail = f"no run of {LEAK_RUN_WORDS} words is shared with any exemplar shown"
    else:
        title, run = found
        passed = False
        detail = (
            f"shares a run of {run} consecutive words with {title}, which was shown as "
            f"register and may not be taken as text (limit {LEAK_RUN_WORDS})"
        )
    return GateOutcome(
        gate=GateKind.INTEGRITY,
        rule_or_critic_id=LEAK_GATE,
        passed=passed,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        vetoes=() if passed else (Veto.EXEMPLAR_LEAK,),
        detail=detail,
    )


__all__ = [
    "BLURBS_HEADING",
    "CHAPTER_WORDS",
    "DEFAULT_LIMIT",
    "LEAK_GATE",
    "LEAK_RUN_WORDS",
    "OPENINGS_HEADING",
    "SHELF_SYSTEM",
    "Exemplar",
    "Shelf",
    "gate_exemplar_leak",
    "leak",
    "load_shelf",
    "render_blurbs",
    "render_openings",
]
