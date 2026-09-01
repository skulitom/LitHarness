"""Run the existing code-only instruments over one chapter-1 text per draw.

**Operator diagnostics, not research** (§95's sanctioned channel; `BRIEF.md` governs what may
become evidence and nothing here asks to). **No new metric is minted.** Every counter below is
imported from where it already lives; the two exceptions are marked `REIMPLEMENTED` and
`NOT-AN-INSTRUMENT` in the output and in `plan/agent-impact/draw-battery.md`, and both say why.

**No model reads anything here.** Regex and arithmetic over text, end to end. No corpus is
opened, so RS1 is untouched, and nothing under `src/litharness/` imports this file.

What is reused, and from where:

| quantity | reused from |
| --- | --- |
| words | `len(text.split())`, the pipeline's own idiom (`application/export.py:57`) |
| inference-gloss tiers | `register_census.gloss_counts` |
| proper nouns | `register_census.proper_nouns` |
| progression events | `progression_cadence.measure` |
| number families | `number_context.measure` |
| em dashes | `voice.exhibition_census` |
| sentences | `voice.sentences` |
| `[STATUS]` lines | `statusline.parse_status_line` |
| machinery names in prose | `schema_words.named_in` |

Two quantities have no instrument in the repo and are computed here under a flag:

- **`chain_*` (REIMPLEMENTED).** §180.1 ran its census with "a crude script that is not kept",
  so there is no §180 counter to reuse. The definition below is transcribed from §180.1's own
  sentence -- sentences split on terminal punctuation, and per sentence a count of coordinated
  joins (commas plus free-standing *and*) -- and the bound is §180.3's fourth action. Because the
  original script is gone, **these levels are not comparable with §180.1's published
  distribution**; only the columns of this table are comparable with each other.
- **`proper_nouns` (NOT-AN-INSTRUMENT for cast size).** §175 shipped a prompt bound and
  `domain/staging.py` says in its own docstring that no count of drafted prose was built. The
  proper-noun counter reused here is a strict superset of named characters -- it also catches
  places, institutions and system names -- so it is reported as proper nouns and never as cast.

**Two instruments are read at TWO VERSIONS each, and both versions are reported.** The first
battery found `progression_cadence` and `number_context`'s system half blind to this project's
own `[STATUS]` page contract, so their v0 rows are zeros that mean *unmeasured*. The answer
shipped as a second registered version rather than an edit: `cadence_v2` and `numbers_v2` below
carry their own registration digests, the v0 keys beside them are unchanged and still the only
ones any market number may be read against, and nothing pools the two. A v2 count is not a
better book; it is the same page seen by a detector that can read one of its lines.

    uv run python plan/agent-impact/scripts/draw_battery.py --artifact-root C:/DEV/LitHarness

Re-runnable: it reads text files and writes JSON to stdout. It writes nothing else and needs no
database, no corpus and no network.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
RESEARCH = REPO / "research" / "quality-measurement"


def _load(name: str) -> Any:
    """Import a `research/quality-measurement` module by path.

    That directory is not a package and its modules import each other by bare name, so the
    directory goes on `sys.path` once and the modules are then ordinary imports.
    """
    if str(RESEARCH) not in sys.path:
        sys.path.insert(0, str(RESEARCH))
    spec = importlib.util.spec_from_file_location(name, RESEARCH / f"{name}.py")
    if spec is None or spec.loader is None:  # pragma: no cover - path is fixed
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


#: Every per-chapter measure this runner reports now lives in one module, so this runner and
#: `research/quality-measurement/scorecard.py` cannot drift apart. The functions were lifted
#: verbatim, and `plan/agent-impact/scripts/battery.json` still validates byte-for-byte -- the
#: refactor moved code and changed no number. `chapter_measures` carries the reuse table, the
#: prose/system boundary note, and the `REIMPLEMENTED` / `NOT-AN-INSTRUMENT` flags.
chapter_measures = _load("chapter_measures")

battery = chapter_measures.battery
chain_profile = chapter_measures.chain_profile
prose_only = chapter_measures.prose_only
sentence_profile = chapter_measures.sentence_profile
status_profile = chapter_measures.status_profile

# --------------------------------------------------------------------------- the draws

#: `(draw id, shelf-or-archive path relative to the artifact root)`, in draw order. Every path
#: is the chapter 1 the coordinating record names; the archives are the redraw families' earlier
#: copies, kept because two draws of one title share a slug (pilot 15b §7, stage-0 §172).
DRAWS: tuple[tuple[str, str], ...] = (
    ("p14", "book-library/unlicensed-weather/chapters/Chapter1.txt"),
    ("p15-d1", "runs/pilots/pilot15/shelf-draw-1/chapters/Chapter1.txt"),
    ("p15-d2", "runs/pilots/pilot15/shelf-draw-2/chapters/Chapter1.txt"),
    ("p15-d3", "runs/pilots/pilot15/shelf-draw-3/chapters/Chapter1.txt"),
    ("p15-d4", "book-library/what-the-kettle-remembers/chapters/Chapter1.txt"),
    ("p16", "book-library/reading-the-ladder-wrong/chapters/Chapter1.txt"),
    ("p18-d2", "runs/pilots/pilot18/shelf-draw-2/chapters/Chapter1.txt"),
    ("p18-d3", "book-library/the-station-keeps-score--435c41f9/chapters/Chapter1.txt"),
)

#: Optional context columns, pre-redesign. Cheap because they are the same two file reads.
CONTEXT: tuple[tuple[str, str], ...] = (
    ("p12", "book-library/patch-notes-for-the-apocalypse/chapters/Chapter1.txt"),
    ("p13", "book-library/the-rainwright-s-apprentice-has-no-licence/chapters/Chapter1.txt"),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        default="C:/DEV/LitHarness",
        help="checkout holding the untracked shelf and pilot archives",
    )
    parser.add_argument(
        "--context", action="store_true", help="also measure the pre-redesign context columns"
    )
    parser.add_argument(
        "--out",
        default="",
        help="write JSON here as UTF-8; a shell redirect of stdout uses the console codepage "
        "on this box and mangles the em dash in the recorded status lines",
    )
    args = parser.parse_args(argv)

    root = Path(args.artifact_root)
    rows = list(DRAWS) + (list(CONTEXT) if args.context else [])
    out: dict[str, Any] = {}
    for draw, relative in rows:
        path = root / relative
        if not path.is_file():
            out[draw] = {"error": f"missing: {path}"}
            continue
        text = path.read_text(encoding="utf-8")
        out[draw] = {"path": relative} | battery(text)
    rendered = json.dumps(out, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
