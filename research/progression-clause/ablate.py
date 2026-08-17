"""§55.1's named experiment: hold the schedule fixed, vary the progression clause.

**The measurement this answers.** §55 built a progression schedule, `progression_target` read
it, and `render_prompt` put the next milestone in front of every scene. §55.1 then measured
what the generator did with it: gold moved at s03 and s07 and then nothing moved for
twenty-three scenes, hp/mp/level never moved at all — *movement, not progression*. The
mechanism was complete; the outcome was decided by one sentence of prompt wording that nobody
had measured. §51.1 is the same shape and the same fix: an instruction the record called
ignored had never been sent, and once sent, *how it was worded* moved `phi4` 324 -> 458 bare
and 324 -> 611 when it named what the length was for.

**Why this is not run as five more books.** §55.1's own metric is distinct extracted states
across a 30-scene book, which is ~1 GPU-hour per draw and cannot separate the wording from the
thirty other things that vary across a book. The instruction's effect is a *per-scene*
question, so this holds the book fixed and draws the same scene repeatedly. A real prefix is
drafted once; every arm then writes scene N+1 from a byte-identical checkpoint — same packet,
same status example, same milestone, same scene plan, same sampler, same seed sequence. The
only difference between two arms is the clause.

**Where the draw is taken, and it is not scene 1.** §55.1 measured the failure as *mid-book*:
the model took the first milestone and then stopped. A draw at scene 1 would measure the case
that already works. The prefix is drafted to the scene before the first milestone the run
ignored, and the draw is taken there.

**Five arms, and the first two are the controls.**

- `Z_none` — no progression clause at all. §52's baseline: this is what the ledger does when
  nothing asks it to move, and without it "arm A moved it 2/8 times" says nothing.
- `A_current` — the shipped wording, verbatim. Asserted byte-identical against
  `render_prompt` itself, so this arm is the production system rather than a paraphrase of it.
- `B_bare` — the hedges removed and nothing put in their place. Separates "the hedge is the
  problem" from "the wording needs to say more".
- `C_commitment` — the milestone as something this scene is partly responsible for landing.
- `D_purpose` — names what the movement is *for*, which is the shape that beat bare on length.

**The Goodhart control, stated because this metric invites exactly one.** "Did a number move"
is trivially satisfiable by an arm that orders the model to change a number, and a number that
moves with no event behind it is §1a.3 item 2's characteristic failure wearing the costume of a
fix — the same trap `progression_cost` died in (BRIEF §2: "the cheapest repair that satisfies
the metric *is the disease*"). So no arm is allowed to say "change a number", two mechanical
counter-metrics are recorded beside the movement — `jumped` (the draw landed exactly on the
milestone, i.e. the schedule was copied rather than approached) and `invented` (a max or a
field the sheet does not hold was altered) — and **every draw's full prose is written to disk**
so the question the numbers cannot answer, whether the page earns the change, is answerable by
reading rather than by assertion.

Nothing here is imported by the package and nothing here gates anything. Local Ollama only, so
running it spends no quota and no money.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import litharness_contracts as lc  # noqa: E402

from litharness.adapters.sqlite_store import SqliteStore  # noqa: E402
from litharness.application.planner import packet_for, render_prompt  # noqa: E402
from litharness.domain.beats import arc_template, beats_for  # noqa: E402
from litharness.domain.draft import DraftPolicy, is_draftable  # noqa: E402
from litharness.domain.extraction import (  # noqa: E402
    STATUS_FIELDS,
    STATUS_PATTERN,
    STATUS_PREDICATE,
    progression_target,
    system_voice_example,
)
from litharness.domain.generation import PROFILES, Sampler  # noqa: E402
from litharness.domain.plans import scene_plan_for  # noqa: E402
from litharness.domain import state as state_mod  # noqa: E402
from litharness.providers.base import CompletionRequest  # noqa: E402
from litharness.providers.ollama import OllamaProvider  # noqa: E402

# --- the book under measurement ----------------------------------------------------------

#: A debt premise, because §55's live schedule was one and the clause under test is about
#: numbers that have somewhere to go. A premise with no economy would make every arm look the
#: same for a reason that is not the wording.
PREMISE = (
    "Rook owes the Vane House forty gold he does not have, and the interest is a level of "
    "his own he cannot afford to lose. He takes contracts in the underlevels to clear it: "
    "each one pays, each one costs him blood or mana he has no way to replace quickly, and "
    "the House keeps moving the number. He can clear the debt or he can stay whole."
)

SCENES = 30
TITLE = "The Vane Ledger"

SEED_VALUES = {"level": 1, "hp": 18, "hp_max": 18, "mp": 4, "mp_max": 4, "gold": 12}

#: The fields a scene may move. `hp_max`/`mp_max` are deliberately excluded: a scene that
#: raises its own ceiling is inventing a level-up the sheet did not schedule, and counting that
#: as movement would reward the failure `invented` exists to catch.
MUTABLE = ("level", "hp", "mp", "gold")


def seed_snapshot(book_id: str, branch_id: str) -> dict[str, Any]:
    """A starting character sheet with no story position — §17 Stage 3's precondition 1."""
    return {
        "meta": {
            "schema_version": "1.2.0",
            "artifact_id": "00000000-0000-5000-8000-000000000001",
            "artifact_kind": "state_snapshot",
            "created_at": "2026-08-17T00:00:00Z",
            "actor": "progression-clause-ablation",
            "tool": {"name": "litharness-research", "version": "0.1.0"},
            "source_revisions": [],
            "dependencies": [],
            "warnings": [],
        },
        "book_id": book_id,
        "branch_id": branch_id,
        "revision_id": "00000000-0000-5000-8000-000000000002",
        "records": [
            {
                "record_id": "rec-seed-rook",
                "kind": "assertion",
                "subject": "rook",
                "predicate": STATUS_PREDICATE,
                "value": dict(SEED_VALUES),
                "authority": "accepted_canon",
                "pov_visibility": [],
                "evidence": [],
                "predicate_registry_version": "fixture.v1",
            }
        ],
    }


# --- the arms ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Arm:
    key: str
    #: `None` is the no-clause control. Otherwise a template taking the rendered milestone.
    clause: str | None
    why: str


ARMS: tuple[Arm, ...] = (
    Arm(
        key="Z_none",
        clause=None,
        why="§52's baseline: what the ledger does when nothing asks it to move.",
    ),
    Arm(
        key="A_current",
        clause=(
            " The book's plan has the state reaching this later on:\n"
            "{p}\n"
            "Move it toward that in this scene where the events warrant it; do not jump "
            "to it, and do not move it for no reason on the page."
        ),
        why="The shipped wording, verbatim. §55.1: hedged three times, and the sum is stasis.",
    ),
    Arm(
        key="B_bare",
        clause=(
            " The book's plan has the state reaching this later on:\n"
            "{p}\n"
            "Move the state toward that in this scene."
        ),
        why="The hedges removed and nothing put in their place. Isolates the hedge.",
    ),
    Arm(
        key="C_commitment",
        clause=(
            " The book's plan has the state reaching this by a later scene:\n"
            "{p}\n"
            "This scene is one of the scenes that gets it there. Write the event that moves "
            "the state, and end on the state that event leaves true."
        ),
        why="The milestone as a commitment this scene is partly responsible for landing.",
    ),
    Arm(
        key="D_purpose",
        clause=(
            " The book's plan has the state reaching this later on:\n"
            "{p}\n"
            "The distance between where the state stands now and that line is what the "
            "reader is following: it is the cost being paid and the ground being gained. "
            "Close some of that distance here by putting the event that closes it on the "
            "page — an earning, a spending, a wound, a drain — rather than by reporting a "
            "new number. Do not close all of it at once."
        ),
        why="Names what the movement is *for*. §51.1's shape, the one that beat bare on length.",
    ),
)


def render_arm(
    arm: Arm,
    beat: Any,
    *,
    book_title: str | None,
    packet: Any,
    status_example: str | None,
    target_words: int,
    scene_plan: str | None,
    progression: str | None,
) -> tuple[str, str]:
    """`render_prompt` with the progression clause swapped, and nothing else touched.

    Reconstructed rather than monkey-patched so the substitution is visible, and checked
    against the real function for the two arms it can be checked against — `Z_none` is
    `progression=None` and `A_current` is the shipped clause. An arm that drifted from
    production would make every comparison a comparison with something nobody runs.
    """
    system, prompt = render_prompt(
        beat,
        book_title=book_title,
        packet=packet,
        status_example=status_example,
        target_words=target_words,
        progression=None,
        scene_plan=scene_plan,
    )
    if arm.clause is None or progression is None:
        return system, prompt

    reference, _ = render_prompt(
        beat,
        book_title=book_title,
        packet=packet,
        status_example=status_example,
        target_words=target_words,
        progression=progression,
        scene_plan=scene_plan,
    )
    # The clause is inserted where `render_prompt` inserts it: after the status instruction
    # and before the length instruction. Splitting on the no-clause rendering finds that seam
    # without hard-coding either neighbour's wording.
    head, _, tail = system.partition(" Write approximately ")
    tail = f" Write approximately {tail}" if tail else ""
    rebuilt = head + arm.clause.format(p=progression) + tail

    if arm.key == "A_current" and rebuilt != reference:
        raise SystemExit(
            "A_current is not byte-identical to render_prompt; the control arm is not the "
            "shipped system.\n--- rebuilt ---\n"
            f"{rebuilt}\n--- reference ---\n{reference}"
        )
    return rebuilt, prompt


# --- reading a draw ------------------------------------------------------------------------


def parse_status(text: str) -> dict[str, int] | None:
    """The last status line in the scene, as ints. `None` when the scene wrote none.

    The *last*, because a scene that opens by restating the sheet and closes on what it left
    true is answering the instruction; taking the first would score the restatement.
    """
    matches = list(STATUS_PATTERN.finditer(text or ""))
    if not matches:
        return None
    group = matches[-1].groupdict()
    return {field: int(group[field]) for field in STATUS_FIELDS}


def score(
    drawn: dict[str, int] | None, current: dict[str, int], milestone: dict[str, int]
) -> dict[str, Any]:
    """What one draw did to the ledger, against the state it started from and its target."""
    if drawn is None:
        return {"extractable": False}
    moved = {f: drawn[f] - current[f] for f in MUTABLE if f in drawn and f in current}
    want = {f: milestone[f] - current[f] for f in MUTABLE if f in milestone and f in current}
    toward = {
        f: (delta != 0 and want.get(f, 0) != 0 and (delta > 0) == (want[f] > 0))
        for f, delta in moved.items()
    }
    overshot = {
        f: (want.get(f, 0) != 0 and abs(moved[f]) > abs(want[f])) for f in moved
    }
    return {
        "extractable": True,
        "values": drawn,
        "delta": moved,
        "fields_moved": sum(1 for d in moved.values() if d != 0),
        "moved": any(d != 0 for d in moved.values()),
        "fields_toward": sum(1 for v in toward.values() if v),
        "toward": any(toward.values()),
        # Landed exactly on the milestone: the schedule copied rather than approached. The
        # shipped clause's "do not jump to it" exists to prevent this, so an arm that moves
        # the ledger by jumping has not done what the schedule wanted.
        "jumped": all(
            drawn.get(f) == milestone.get(f) for f in MUTABLE if f in milestone
        ),
        "overshot": any(overshot.values()),
        # A ceiling raised, or a field altered that the sheet does not schedule. The
        # fabrication check: `_milestones` refuses a schedule that invents a statistic, and a
        # scene that invents one is the same defect arriving from the other side.
        "invented": any(
            drawn.get(f) != current.get(f) for f in ("hp_max", "mp_max") if f in drawn
        ),
    }


# --- stages --------------------------------------------------------------------------------


def run_cli(db: Path, args: list[str], *, model: str, extra: list[str] | None = None) -> str:
    argv = [
        str(REPO / ".venv/Scripts/python.exe"),
        "-m",
        "litharness",
        "--database",
        str(db),
        "--model",
        model,
        "--prefer",
        "ollama",
        "--no-billing",
        *(extra or []),
        *args,
    ]
    env = dict(os.environ)
    env.pop("LITHARNESS_ENV", None)
    done = subprocess.run(argv, capture_output=True, text=True, cwd=str(REPO), env=env)
    if done.returncode not in (0, 2):
        raise SystemExit(f"{' '.join(args)} failed ({done.returncode}):\n{done.stderr}")
    return done.stdout


def stage_prefix(out: Path, *, model: str, upto: int, target_words: int) -> None:
    """Draft a real book prefix once, so every arm draws from the same real checkpoint."""
    db = out / "book.db"
    out.mkdir(parents=True, exist_ok=True)
    book_id = "11111111-1111-5111-8111-111111111111"
    branch_id = "22222222-2222-5222-8222-222222222222"

    # Resumable on the book rather than on the file. A tick loop that dies at scene 7 should
    # be restartable without redrafting six scenes, and the book's own existence is the thing
    # that says whether creation already happened.
    exists = False
    if db.exists():
        store = SqliteStore.open(db)
        try:
            exists = store.head(book_id, branch_id) is not None
        finally:
            store.close()

    if not exists:
        run_cli(db, ["init"], model=model)
        seed = out / "seed.json"
        seed.write_text(
            json.dumps(seed_snapshot(book_id, branch_id), indent=2), encoding="utf-8"
        )
        print(
            run_cli(
                db,
                [
                    "new",
                    TITLE,
                    "--premise",
                    PREMISE,
                    "--scenes",
                    str(SCENES),
                    "--state",
                    str(seed),
                    "--book",
                    book_id,
                    "--branch",
                    branch_id,
                ],
                model=model,
            )
        )

    started = time.monotonic()
    for tick in range(400):
        store = SqliteStore.open(db)
        try:
            head = store.head(book_id, branch_id)
            drafted = (
                sum(
                    1
                    for beat in beats_for(head, arc_template(SCENES))
                    if not is_draftable(head, beat.logical_id, policy=DraftPolicy())
                )
                if head is not None
                else 0
            )
        finally:
            store.close()
        if drafted >= upto:
            print(f"prefix reached {drafted} scenes in {time.monotonic() - started:.0f}s")
            return
        run_cli(
            db, ["tick"], model=model, extra=["--target-words", str(target_words)]
        )
        if tick % 5 == 0:
            print(f"  tick {tick}: {drafted}/{upto} scenes", flush=True)
    raise SystemExit(f"prefix did not reach {upto} scenes in 400 ticks")


def make_provider(name: str, model: str) -> tuple[Any, bool]:
    """The generator for one arm, and whether the sampler can be held.

    **The frontier arm cannot hold the sampler, and that is a limit on the comparison rather
    than a detail.** `claude -p` exposes no temperature, top-p or seed, so its draws vary by
    the service's own sampling while the Ollama arms vary by a seed this script sets. Two
    consequences, both stated rather than papered over: the frontier draws are not paired with
    the local ones draw-for-draw, and its within-arm spread is not this experiment's to
    control. What survives is the between-arm comparison of *rates*, which is what the
    question needs.
    """
    if name == "ollama":
        return OllamaProvider(model=model), True
    if name == "claude_code":
        from litharness.providers.cli import ClaudeCodeProvider

        return ClaudeCodeProvider(model=model), False
    raise SystemExit(f"unknown provider {name!r}")


def stage_ablate(
    out: Path,
    *,
    model: str,
    draws: int,
    target_words: int,
    at: int | None,
    provider_name: str = "ollama",
    only: tuple[str, ...] | None = None,
    label: str = "",
) -> None:
    db = out / "book.db"
    book_id = "11111111-1111-5111-8111-111111111111"
    branch_id = "22222222-2222-5222-8222-222222222222"

    store = SqliteStore.open(db)
    try:
        head = store.head(book_id, branch_id)
        if head is None:
            raise SystemExit("no prefix; run --stage prefix first")
        beats = beats_for(head, arc_template(SCENES))
        target = next(
            (
                beat
                for beat in beats
                if is_draftable(head, beat.logical_id, policy=DraftPolicy())
                and (at is None or beat.ordinal == at)
            ),
            None,
        )
        if target is None:
            raise SystemExit("no draftable beat at that position")

        records = store.state_records(book_id, branch_id)
        packet = packet_for(store, head, target)
        status_example = system_voice_example(records, at=target.story_order_key)
        progression = progression_target(records, at=target.story_order_key)
        plan_item = scene_plan_for(store.plan_items(book_id, branch_id), target.logical_id)
        scene_plan = plan_item.text if plan_item is not None else None

        canon = [
            r
            for r in records
            if r.predicate == STATUS_PREDICATE and state_mod.is_canon(r)
        ]
        canon.sort(key=lambda r: state_mod.order_key_of(r) or "")
        current = {
            k: int(v)
            for k, v in dict(canon[-1].value).items()  # type: ignore[arg-type]
            if isinstance(v, (int, float))
        }
        milestones = {
            state_mod.order_key_of(r): {
                k: int(v) for k, v in dict(r.value).items() if isinstance(v, (int, float))  # type: ignore[arg-type]
            }
            for r in records
            if r.predicate == STATUS_PREDICATE
            and not state_mod.is_canon(r)
            and state_mod.order_key_of(r) is not None
        }
        milestone = (
            milestones[min(k for k in milestones if k and k >= (target.story_order_key or ""))]
            if progression
            else {}
        )
    finally:
        store.close()

    if not progression:
        raise SystemExit(
            "the prefix carries no milestone at or after this beat; the ablation has "
            "nothing to vary. Check that the outline call produced a schedule."
        )

    arms = tuple(arm for arm in ARMS if only is None or arm.key in only)
    if not arms:
        raise SystemExit(f"no arms match {only!r}")

    print(f"drawing scene {target.ordinal} ({target.story_order_key})")
    print(f"  provider {provider_name} / {model}")
    print(f"  current  {current}")
    print(f"  milestone{milestone}")
    print(f"  target line: {progression}")
    print(f"  {len(arms)} arms x {draws} draws = {len(arms) * draws} calls\n", flush=True)

    prose_dir = out / "prose"
    prose_dir.mkdir(exist_ok=True)
    profile = PROFILES["default"]
    rows: list[dict[str, Any]] = []
    tag = label or provider_name

    # Seeds held common across arms, which is what makes this paired: draw i of every arm
    # samples the same path through a different instruction. §51.1 held them the same way.
    seeds = [1000 + index for index in range(draws)]

    for arm in arms:
        system, prompt = render_arm(
            arm,
            target,
            book_title=None,
            packet=packet,
            status_example=status_example,
            target_words=target_words,
            scene_plan=scene_plan,
            progression=progression,
        )
        (out / f"system-{arm.key}.txt").write_text(system, encoding="utf-8")
        for index, seed in enumerate(seeds):
            provider, holds_sampler = make_provider(provider_name, model)
            started = time.monotonic()
            try:
                text = provider.complete(
                    CompletionRequest(
                        prompt=prompt,
                        system=system,
                        profile="default",
                        sampler=(
                            Sampler(
                                temperature=profile.temperature,
                                top_p=profile.top_p,
                                seed=seed,
                                repeat_penalty=profile.repeat_penalty,
                            )
                            if holds_sampler
                            else None
                        ),
                        timeout_seconds=600.0,
                    )
                ).text
            except Exception as error:  # noqa: BLE001 - a dead draw is data, not a crash
                rows.append(
                    {"arm": arm.key, "seed": seed, "tag": tag, "error": str(error)[:200]}
                )
                print(f"  {arm.key} #{index}: ERROR {error}", flush=True)
                continue
            (prose_dir / f"{tag}-{arm.key}-{seed}.txt").write_text(text, encoding="utf-8")
            row = {
                "arm": arm.key,
                "tag": tag,
                "seed": seed,
                "words": len(text.split()),
                "wall_s": round(time.monotonic() - started, 1),
                **score(parse_status(text), current, milestone),
            }
            rows.append(row)
            print(
                f"  {arm.key} #{index}: {row['words']}w "
                f"moved={row.get('moved')} fields={row.get('fields_moved')} "
                f"toward={row.get('toward')} jumped={row.get('jumped')} "
                f"({row['wall_s']}s)",
                flush=True,
            )

    result = {
        "provider": provider_name,
        "model": model,
        "sampler_held": provider_name == "ollama",
        "scene_ordinal": target.ordinal,
        "story_order_key": target.story_order_key,
        "current": current,
        "milestone": milestone,
        "target_line": progression,
        "target_words": target_words,
        "sampler": {
            "temperature": profile.temperature,
            "top_p": profile.top_p,
            "repeat_penalty": profile.repeat_penalty,
            "seeds": seeds,
        },
        "arms": {arm.key: arm.why for arm in arms},
        "draws": rows,
    }
    destination = out / f"results-{tag}.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nwrote {destination}")
    summarise(rows)


def summarise(rows: list[dict[str, Any]]) -> None:
    """One line per (arm, provider). Failed draws stay in `n` — a provider that could not
    write a readable line is a result about that provider, not a row to drop."""
    live = [r for r in rows if "error" not in r]
    print(
        f"\n{'arm':<14} {'where':<12} {'n':>3} {'extract':>8} {'moved':>7} {'toward':>7} "
        f"{'fields':>7} {'jumped':>7} {'invent':>7} {'words':>7}"
    )
    tags = sorted({str(r.get("tag", "")) for r in rows})
    for tag in tags:
        for arm in ARMS:
            group = [r for r in rows if r["arm"] == arm.key and r.get("tag") == tag]
            if not group:
                continue
            ok = [r for r in live if r["arm"] == arm.key and r.get("tag") == tag
                  and r.get("extractable")]
            written = [r for r in live if r["arm"] == arm.key and r.get("tag") == tag]
            n = len(group)
            print(
                f"{arm.key:<14} {tag:<12} {n:>3} {len(ok):>8} "
                f"{sum(1 for r in ok if r.get('moved')):>7} "
                f"{sum(1 for r in ok if r.get('toward')):>7} "
                f"{(sum(r.get('fields_moved', 0) for r in ok) / max(len(ok), 1)):>7.2f} "
                f"{sum(1 for r in ok if r.get('jumped')):>7} "
                f"{sum(1 for r in ok if r.get('invented')):>7} "
                f"{(sum(r['words'] for r in written) / max(len(written), 1)):>7.0f}"
            )
    print(
        "\nmoved/toward are counts of draws; fields is the mean number of the four mutable "
        "fields that changed.\njumped and invented are the Goodhart counters — an arm that "
        "wins on 'moved' while winning on those\nhas not done what the schedule asked. "
        "Read the prose in prose/ before believing any of it."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["prefix", "ablate", "both"], default="both")
    parser.add_argument("--model", default="phi4:latest")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--upto", type=int, default=10, help="scenes to draft as the prefix")
    parser.add_argument("--at", type=int, default=None, help="scene ordinal to draw")
    parser.add_argument("--draws", type=int, default=8)
    parser.add_argument("--target-words", type=int, default=900)
    parser.add_argument(
        "--provider",
        default="ollama",
        choices=["ollama", "claude_code"],
        help="who writes the draws. claude_code inherits the local CLI's auth and so spends "
        "subscription quota; the prefix is always drafted on ollama.",
    )
    parser.add_argument(
        "--arms",
        default=None,
        help="comma-separated arm keys to draw, for a second pass that need not repeat all "
        "five (e.g. A_current,D_purpose)",
    )
    parser.add_argument("--label", default="", help="tag for this pass in the results file")
    args = parser.parse_args()

    if args.stage in ("prefix", "both"):
        stage_prefix(
            args.out, model=args.model, upto=args.upto, target_words=args.target_words
        )
    if args.stage in ("ablate", "both"):
        stage_ablate(
            args.out,
            model=args.model,
            draws=args.draws,
            target_words=args.target_words,
            at=args.at,
            provider_name=args.provider,
            only=tuple(args.arms.split(",")) if args.arms else None,
            label=args.label,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
