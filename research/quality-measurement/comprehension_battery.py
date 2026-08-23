"""Does a premise mean anything? Four readers restate it independently and we measure agreement.

**The operator's design, 2026-08-23**: *"Maybe we need to somehow test reader comprehension too?
like if they can accurately explain what they read in different words then it has meaning."*

It arrived after six forged premises drew six specific complaints, and the complaints are all one
complaint: *"'every wonder is alive, small and kept in a crock' — makes no sense, what is alive?
what is a crock? what counts as a wonder?"*, *"'a cracked man in a warm room who doesn't know her
name' — do you know what this means? I think nobody does"*, *"'four grafts on a root that feeds
two' — absolute nonsense"*. Every one of those is a **comprehension** failure, and no instrument
in this repository could see it: `pitch_battery` asks which of two texts a reader prefers, and a
reader can prefer the one that confused them less without ever saying what confused them.

**Why this is admissible where preference is not.** §87—§89 measured the verdict channel — asked
to prefer a side — running 4,676x position over text, and E1/E2 are recorded VOID. What survived
is **E6, name the difference**: a model reporting *what is there* rather than *which is better*.
Restating a premise in your own words is E6's shape, and it has a property preference never had:
**the answers can be checked against each other without a judge.** Four readers who understood the
same thing produce overlapping content words; four readers who understood nothing produce four
different guesses. The scorer here is set arithmetic, not a model.

**What it measures and what it cannot.** Agreement is not quality — four readers can agree
perfectly about a premise nobody would read. It is the floor under quality: a premise its own
target readers cannot restate consistently has failed before taste is reached. `did_not_follow` is
the actionable half, and it is the operator's second ask — *"we should get some sort of direction
help out of readers, so even if they reject, we know what to do"*.

Pre-registration: `plan/pitch-reader-validity.md` §7. Scoring is deterministic; no model judges.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from elicit import Elicitor  # noqa: E402
from personas import GENRE_PANEL  # noqa: E402

#: Function words carry no content and every reader uses them, so leaving them in would floor the
#: agreement score at whatever English costs. Deliberately a plain list rather than a dependency.
_STOP = frozenset("""
a an the and or but if of to in on at by for with from into over under about as is are was were
be been being it its this that these those he she they them his her their him you your i we our
not no nor so then than there here when while what which who whom whose how why can could will
would shall should may might must do does did done have has had having get gets got make makes
made just very really some any all one two both each other more most much many few own same up
down out off again once only also because before after during through between against
""".split())  # noqa: SIM905 — a word list is prose, and reads as prose

_WORD = re.compile(r"[a-z][a-z'-]*")

ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["can_do", "in_the_way", "expect_next", "undefined_words", "open_questions"],
    "properties": {
        "can_do": {
            "type": "string",
            "description": "In your own words: what can this person do that nobody else can? "
                           "One or two plain sentences. Do not reuse the text's phrasing.",
        },
        "in_the_way": {
            "type": "string",
            "description": "In your own words: what is in the way, or what does it cost them?",
        },
        "expect_next": {
            "type": "string",
            "description": "What kind of book is this, and what do you expect to happen next?",
        },
        # **Two lists, because one list measured two things and the run showed it.** The first
        # version asked for "anything you could not follow" and a human-written reference pitch
        # drew five items — every one of them a question the book would obviously answer ("what
        # does the AI actually do for him", "is that a hard rule or flavour text"), which is what
        # a pitch is *for*. Our own premises drew a different species entirely: "I don't know
        # what a whip is", "what does take-back-to-green mean", "what the Cooling Yard is". One
        # counter could not separate a withheld hook from an unexplained word, so the reference
        # item landed mid-table and the number meant less than the text under it.
        "undefined_words": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Words or phrases used as if you already knew them, where you were "
                           "never told what they mean. Quote each one. Empty list if none.",
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things you expect the book itself to answer later — a hook, a "
                           "withheld fact, something you want to read on for. These are not "
                           "faults. Quote each one. Empty list if none.",
        },
    },
}


def content(text: str) -> set[str]:
    """Content words of one answer. The whole scorer, and it is set arithmetic on purpose."""
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def agreement(answers: list[str]) -> float:
    """Mean pairwise Jaccard over content words — how much four readers said the same thing.

    Jaccard rather than a model-scored similarity, because the moment a model scores the
    agreement the instrument inherits every validity problem the panel has. Two readers who
    understood one premise reach for the same nouns; two who understood nothing reach for their
    own. It is blunt, and blunt is the point: it cannot flatter a premise it does not understand.
    """
    sets = [content(a) for a in answers if a and a.strip()]
    sets = [s for s in sets if s]
    if len(sets) < 2:
        return 0.0
    scores = [
        len(a & b) / len(a | b)
        for a, b in itertools.combinations(sets, 2)
        if a | b
    ]
    return round(statistics.fmean(scores), 4) if scores else 0.0


def load_items(forge_paths: list[Path], extra: list[Path]) -> list[dict[str, str]]:
    items = []
    for path in forge_paths:
        for candidate in json.loads(path.read_text(encoding="utf-8"))["candidates"]:
            items.append({
                "item_id": f"{path.parent.name}:{candidate['index'] + 1}",
                "title": candidate["title"],
                "text": candidate["premise"],
                "source": "forged",
            })
    for reference in extra:
        # **A human-written reference item, and what it is not.** The operator's own worked
        # example, included so the scores below have a point of comparison written by a person
        # rather than only forged ones. It is a *stimulus*, not a label: nothing scores our
        # premises against it, no bar is set from it, and §95 is untouched — the operator's
        # judgments stay direction, and this is a text they wrote rather than a verdict they gave.
        items.append({
            "item_id": f"reference:{reference.stem.replace('reference-pitch', 'operator')}",
            "title": reference.stem,
            "text": reference.read_text(encoding="utf-8").strip(),
            "source": "human-written reference",
        })
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forge", nargs="*", default=[])
    parser.add_argument("--reference", nargs="*", default=[],
                        help="human-written pitches as comparison items; pass the same pitch "
                             "twice, once damaged, to get a within-text control")
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--transport", choices=("cli", "sdk", "ollama"), default="cli")
    parser.add_argument("--cache", default="comprehension-raw.jsonl")
    parser.add_argument("--out", default="comprehension.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    items = load_items([Path(p) for p in args.forge], [Path(r) for r in args.reference])
    planned = len(items) * len(GENRE_PANEL)
    print(f"{len(items)} item(s) x {len(GENRE_PANEL)} reader(s) = {planned} call(s)",
          file=sys.stderr)
    if args.dry_run:
        for item in items:
            print(f"  {item['item_id']:<20} {item['title'][:40]:<40} "
                  f"{len(item['text'].split()):4d} words", file=sys.stderr)
        return

    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    started = time.time()
    rows: list[dict[str, Any]] = []

    with Elicitor(results_dir / args.cache, model=args.model, spot_model=None,
                  transport=args.transport) as elicitor:
        for item in items:
            answers: dict[str, dict[str, Any]] = {}
            for persona in GENRE_PANEL:
                turns = [{
                    "role": "user",
                    "content": (
                        f"{item['text']}\n\n---\n\n"
                        "That is the back-cover copy of a book you just picked up. Answer in "
                        "your own words, as if telling a friend — do not quote the text back."
                    ),
                }]
                record = elicitor.ask(
                    persona, turns, schema=ANSWER_SCHEMA, max_tokens=700,
                    tag={"item": item["item_id"], "persona": persona.persona_id},
                )
                text = record.get("text") or ""
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = {}
                answers[persona.persona_id] = parsed
                print(f"  {item['item_id']:<20} {persona.persona_id:<10} "
                      f"undefined={len(parsed.get('undefined_words') or []):2d} "
                      f"hooks={len(parsed.get('open_questions') or [])}", file=sys.stderr)

            unclear = {
                pid: list(a.get("undefined_words") or []) for pid, a in answers.items()
            }
            hooks = {
                pid: list(a.get("open_questions") or []) for pid, a in answers.items()
            }
            rows.append({
                "item_id": item["item_id"],
                "title": item["title"],
                "source": item["source"],
                "words": len(item["text"].split()),
                "agreement_can_do": agreement([a.get("can_do", "") for a in answers.values()]),
                "agreement_in_the_way": agreement(
                    [a.get("in_the_way", "") for a in answers.values()]
                ),
                "agreement_expect_next": agreement(
                    [a.get("expect_next", "") for a in answers.values()]
                ),
                "readers_confused": sum(1 for v in unclear.values() if v),
                "unclear_items": sum(len(v) for v in unclear.values()),
                "unclear_by_reader": unclear,
                # Reported beside the faults and never added to them: a premise that leaves a
                # reader with questions it plans to answer is working, not broken.
                "readers_with_open_questions": sum(1 for v in hooks.values() if v),
                "open_questions_by_reader": hooks,
                "answers": answers,
            })
        spend = elicitor.spend()

    rows.sort(key=lambda r: -r["agreement_can_do"])
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "panel": [p.persona_id for p in GENRE_PANEL],
        "panel_model": args.model,
        "scorer": "mean pairwise Jaccard over content words; no model scores agreement",
        "items": rows,
        "spend": spend,
        "wall_seconds": round(time.time() - started, 1),
    }
    (results_dir / args.out).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    head = ("\n" + "item".ljust(20) + "can_do".rjust(8) + "in_way".rjust(8)
            + "next".rjust(8) + "confused".rjust(10) + "unclear".rjust(9) + "  title")
    print(head)
    for row in rows:
        print(f"{row['item_id']:<20} {row['agreement_can_do']:7.3f} "
              f"{row['agreement_in_the_way']:7.3f} {row['agreement_expect_next']:7.3f} "
              f"{row['readers_confused']:>7}/4 {row['unclear_items']:8d}  {row['title'][:34]}")


if __name__ == "__main__":
    main()
