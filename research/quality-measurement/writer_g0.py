"""G0 for the Writer roster: does the dossier reach the request, and what does it cost?

`plan/writer-roster.md` §6. **This establishes exactly as little as `director-role.md` §4's pilot
did for briefs: the input arrives.** No model is called, nothing is sampled, and no claim about
prose is available from anything here. What it can do is fail — a parameter that is accepted and
never read is a defect this repository has already paid for once, in `render_prompt`'s own
`target_words`, where two lines of signature and call site shipped with a body that never
mentioned it and a commit message reporting a 47% effect from **byte-identical prompts**.

So G0 asks four things:

1. the dossier reaches the system message, and no writer is byte-identical to today's drafter;
2. two different writers produce two different system messages, and the same writer twice
   produces one — the floor `writer_distinctness` will need on a real model;
3. the dossier never lands in the context packet, which is R5's boundary and §3.2's rule;
4. **what it costs**, because a deep dossier rides in the system message of *every scene call*
   for a whole book. At thirty scenes with repairs on top it is the most frequently re-sent text
   in the system, and its size is a budget line rather than a detail.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

from litharness.application.planner import render_prompt  # noqa: E402
from litharness.domain import writers  # noqa: E402
from litharness.domain.beats import SIX_BEAT, Beat  # noqa: E402
from litharness.domain.context import ContextPacket  # noqa: E402

PRE_REGISTRATION: dict[str, Any] = {
    "gate": "G0 wiring",
    "design": "plan/writer-roster.md §6",
    "establishes": "the input arrives and changes the request's bytes; nothing about prose",
    "calls_no_model": True,
    "asks": [
        "does the dossier reach the system message",
        "do two writers differ, and does one writer repeat",
        "does the dossier stay out of the context packet (§3.2, R5)",
        "what does it cost per scene call, and per book",
    ],
    "what_a_pass_does_not_license": "any comparison between writers. That is G1's, behind "
                                    "writer_distinctness on a real model with a real sampler, "
                                    "with the shuffle control in the same run.",
}

#: A book's worth of scene calls, for the cost line. Thirty is `arc_template(30)`'s own shape,
#: and repairs land on top of it rather than instead of it.
SCENES_PER_BOOK = 30


def _packet() -> ContextPacket:
    """A minimal packet. Its contents do not matter; its *boundary* is what G0 checks."""
    return ContextPacket(
        query_id="beat:s1",
        target_logical_id="s1",
        book_id="bk",
        branch_id="br",
        base_revision_id="rev",
    )


def _beat() -> Beat:
    return Beat(
        logical_id="s1",
        ordinal=1,
        of_total=SCENES_PER_BOOK,
        title="The Archive",
        function="setup",
        template_id=SIX_BEAT.template_id,
        story_order_key="s1",
    )


def _render(writer: writers.Writer | None) -> tuple[str, str]:
    return render_prompt(
        _beat(),
        book_title="Test Book",
        packet=_packet(),
        target_words=900,
        writer=writer,
    )


def run() -> dict[str, Any]:
    roster = writers.BUILTIN
    anonymous_system, anonymous_prompt = _render(None)

    rendered = {name: _render(w) for name, w in roster.items()}

    # 1. The dossier arrives, and changes the bytes.
    arrived = {
        name: (
            roster[name].render() in system
            and system != anonymous_system
        )
        for name, (system, _) in rendered.items()
    }

    # 2. Different writers differ; the same writer repeats. The byte-identity floor §89.1 earned.
    systems = {name: system for name, (system, _) in rendered.items()}
    distinct_pairs = len(set(systems.values())) == len(systems)
    repeats = all(_render(w)[0] == systems[name] for name, w in roster.items())

    # 3. The dossier is nowhere in the prompt, which is where the packet lives. §3.2's boundary
    #    is the whole reason the dossier goes in the system message: the packet's contract is
    #    "established and may be relied on", and a novelist's career is not a fact about a story.
    leaked = {
        name: roster[name].render() in prompt or prompt != anonymous_prompt
        for name, (_, prompt) in rendered.items()
    }

    # 4. Cost. Characters rather than tokens: no tokenizer is loaded here and a 4-chars-per-token
    #    rule of thumb would be a number nobody could check. The ratio is what matters.
    overhead = {
        name: len(system) - len(anonymous_system) for name, (system, _) in rendered.items()
    }
    worst = max(overhead, key=lambda k: overhead[k])
    return {
        "pre_registration": PRE_REGISTRATION,
        "roster_size": len(roster),
        "writers": {name: w.writer_id for name, w in roster.items()},
        "dossier_reaches_the_request": all(arrived.values()),
        "every_writer_differs_from_anonymous": all(arrived.values()),
        "writers_differ_from_each_other": distinct_pairs,
        "same_writer_renders_identically": repeats,
        "dossier_absent_from_packet_side": not any(leaked.values()),
        "cost": {
            "anonymous_system_chars": len(anonymous_system),
            "per_writer_overhead_chars": overhead,
            "worst_writer": worst,
            "worst_overhead_chars": overhead[worst],
            "worst_overhead_ratio_vs_anonymous": round(
                overhead[worst] / len(anonymous_system), 3
            ),
            "scenes_per_book": SCENES_PER_BOOK,
            "worst_book_overhead_chars": overhead[worst] * SCENES_PER_BOOK,
            "note": "characters, not tokens: no tokenizer is loaded here, and a "
                    "chars-per-token rule of thumb would be a number nobody could check. "
                    "Repairs re-send the system message and are not counted in scenes_per_book.",
        },
    }


def selftest() -> int:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    report = run()
    check(report["dossier_reaches_the_request"], "a dossier did not reach the system message")
    check(report["writers_differ_from_each_other"], "two writers rendered identically")
    check(report["same_writer_renders_identically"], "one writer rendered two ways")
    check(report["dossier_absent_from_packet_side"], "a dossier reached the packet side (R5)")

    # The control is the anonymous drafter, and it must still be reachable unchanged.
    system, _ = _render(None)
    check(
        system.startswith("You are drafting one scene of a novel."),
        "the no-writer control is no longer the original drafter",
    )
    # R1 rides on every mint, so an illegal dossier cannot enter the roster by any path.
    try:
        writers.build("x", "avoid em dashes and keep sentences short")
        failures.append("an illegal dossier minted")
    except writers.IllegalDossier:
        pass

    for message in failures:
        print(f"FAIL {message}")
    print(f"writer_g0 selftest: {len(failures)} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--out", default=str(HERE / "results" / "writer-g0.json"))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = run()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
