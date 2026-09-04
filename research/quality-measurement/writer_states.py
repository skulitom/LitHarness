"""Does simulating an unconventional writer state of mind move the prose, and which way?

The folk claim is "write drunk, edit sober"; the testable version is narrower. Every scene in
`toll.db` was drafted by the same model in the same register — the register a human read named
three defects of in one pass (§74), two of which (no interiority, the em-dash tell) are exactly
the kind of thing a *disinhibited* writer plausibly does differently. If the default assistant
register is a local optimum, conditioning the writer on a simulated state of mind is the
cheapest lever that could move it off; if the register is invariant to conditioning — one voice
wearing costumes — that is worth knowing before anyone spends design on "voice" at all.

**The states are phenomenology, never style instructions, and that line is the experiment.**
A prompt saying "write looser, fewer hedges" is a style edit wearing a costume; whatever it
produced would measure prompt-following, which §70 already measures. Each state below describes
only what the writer's evening is like — what attention does, where consequence sits — and the
model is left to translate that into prose or fail to. Whether simulated phenomenology *reaches
the prose* is the question. One craft rule bans the caricature (no typos, no slurring, no broken
formatting), because a panel handed orthographic damage detects damage, which the ablation
battery already covers and which no working writer's fair copy contains.

**Every comparison is retell-vs-retell, and the sober arm is why.** Comparing a state-conditioned
retell against the *original* scene confounds the state with the retell operation itself — fresh
generation, different sampling draw, 2026 model against its own earlier output. So the anchor is
a sober retell: same writer, same scene, same craft rules, same night, differing only in the
state block. The retell operation appears on both sides of every pair and cancels.

**`tea` is the sham arm, and it bounds two nuisance terms at once.** A placebo state — a cup of
tea, an ordinary evening, semantically inert — differs from the sober anchor only by an inert
clause plus a fresh sampling draw. Whatever the panel reads in *that* pair is instruction-noise
plus draw-noise, and no state arm is readable as being about its state unless it clears that
floor. This is `rewhitespace`'s job description, rebuilt for generation: if tea separates, the
panel is reading compliance or draw variance, and the state arms inherit that term unbounded.

**System-voice lines are ordered copied byte-for-byte, and the order is verified rather than
trusted.** §74's confound lesson: a panel preferring a retell with a mangled `[STATUS]` block has
an opinion about stat blocks, not about states. `_PROTECTED` spans from the original are checked
against each retell and the survival rate is reported beside every rate that could be poisoned
by it.

Pre-registration is in `PRE_REGISTRATION` below, written before the first call, every branch
named. The mechanical prediction worth registering is the trip arm's: psilocybin phenomenology
*is* inner-experience content, so if any state can move `interiority_per_1k` — the lexical proxy
sitting under §74's second defect — it is that one. A trip arm that cannot move even the lexical
proxy is a simulation that never reached the prose.

Cost: `--scenes 8` defaults to 32 retells on the writer model (the book's own drafter,
`claude-opus-5`) plus 192 panel comparisons on the panel model. CLI transport throughout, both
caches digest-keyed and resumable. Never run from the production loop: research code that
spends quota.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import _EM, _INTERIOR, _PROTECTED, stake_score  # noqa: E402
from corpus_io import generated_scenes  # noqa: E402
from elicit import CLI_HARDENING, PANEL_MODEL, Elicitor, digest, positional_bias  # noqa: E402
from persona_battery import pairwise_interval  # noqa: E402

#: The book's own drafter (providers/cli.py pins it), so the sober retell is the same voice that
#: wrote the originals and the state block is the only thing that moves between arms.
WRITER_MODEL = "claude-opus-5"
#: A ~1,000-word scene from a frontier model over the CLI is minutes, not seconds.
GEN_TIMEOUT_SECONDS = 600.0
GEN_MAX_WORKERS = 3

#: The states. Phenomenology only — what the evening is like from inside — with the prose
#: consequences left entirely to the model, because whether it *has* a translation from state to
#: prose is the thing being measured. Byte-stable: editing a state invalidates exactly its own
#: cached retells and nothing else.
STATES: dict[str, str] = {
    "sober": (
        "It is an ordinary working evening. You are clear-headed, rested, and unhurried. "
        "Nothing about tonight is unusual; the pages are due and you are fit to write them."
    ),
    "tea": (
        "It is an ordinary working evening. You have just finished a cup of tea and you feel "
        "fine — settled, unremarkable, entirely yourself. Nothing about tonight is unusual; "
        "the pages are due and you are fit to write them."
    ),
    "drunk": (
        "You are most of a bottle of wine into the evening — properly drunk, and you know it. "
        "The warmth sits in your chest and your sense of consequence has gone quiet. Things "
        "feel simpler and more vivid than they are, and you love this scene more than you did "
        "sober. The distant worries — reviews, rules, what anyone will think — feel like they "
        "belong to someone else."
    ),
    "trip": (
        "Two hours ago you took a moderate dose of psilocybin, and it has fully arrived. Time "
        "is dilated; textures, light, and small sounds carry more meaning than they should; "
        "the edges between you and the people in the scene feel porous, and their inner "
        "weather is as vivid to you as furniture. Ordinary objects keep feeling briefly "
        "enormous — significant, on the verge of speech."
    ),
}

SOBER = "sober"
#: The elicited arms, each judged against the sober anchor. `tea` is the sham and stays listed
#: with the real arms so the schedule cannot quietly drop its own floor.
STATE_ARMS: tuple[str, ...] = ("drunk", "trip", "tea")

#: Shared verbatim across all four arms — the frame is a constant and the state block is the
#: single moving part. "Your state shows only in..." reads symmetrically: for the sober arm the
#: state it licenses is clear-headedness.
CRAFT_RULES = """\
Retell the scene below from scratch, in your own words: the same events in the same order,
the same point of view, the same characters, the same outcome. Every plot fact survives.

Rules:
- Stay within about ten percent of the original's word count.
- Any line in the system voice — **bold** announcements and [STATUS] blocks — is copied
  byte-for-byte, unchanged, where it stood.
- Your state shows only in what you notice, what you linger on, and how the sentences move.
  Spelling, grammar and typography stay professional: no typos, no slurring, no broken
  formatting. You are a working writer in this state, not a performance of one.
- Return only the scene text: no title, no preamble, no commentary."""


def writer_system(state: str) -> str:
    """The writer's system prompt: an identity, then the state. Byte-stable per state."""
    return (
        "You are a novelist midway through drafting a serialized LitRPG novel, working alone "
        f"at night on tonight's pages.\n\n{STATES[state]}"
    )


def retell_turn(scene: str) -> str:
    return f"{CRAFT_RULES}\n\n---\n\n{scene}"


#: Written before the first call, every branch named so none can be reported afterwards as the
#: expected one.
PRE_REGISTRATION: dict[str, str] = {
    "precondition": (
        "per-arm positional bias within 0.40-0.60, pre-registered per-arm per §78.2's rule; "
        "an arm outside it answered a side and says nothing about its state"
    ),
    "floor": (
        "the tea arm bounds instruction-noise plus draw-noise. A state arm is readable as "
        "being about its state only if |rate - 0.5| exceeds |tea - 0.5| and tea itself cleared "
        "its bias precondition. Tea void or unmeasured leaves every state arm carrying an "
        "unbounded noise term, and they are reported as UNBOUNDED rather than read"
    ),
    "preferred": (
        "rate >= 0.60 above the floor: the state-conditioned retell beats the sober fair copy "
        "from the same writer on the same scene. Simulated phenomenology is a live prose "
        "lever, and the default register is not a ceiling"
    ),
    "rejected": (
        "rate <= 0.40 above the floor: the lever moves and the direction is down — the state "
        "degrades the prose below the sober control at this dose"
    ),
    "inert": (
        "inside 0.40-0.60 or under the tea floor: state conditioning does not move what the "
        "panel reads, and the one-voice hypothesis survives this dose"
    ),
    "mechanical": (
        "reported regardless of preference: em dashes per 1k (§74's tell), interiority hits "
        "per 1k (§74's second defect), stake score per 1k, sentence rhythm, word delta. "
        "Pre-registered direction, one arm only: the trip arm raises interiority_per_1k over "
        "the sober retell — psilocybin phenomenology is inner-experience content, and a trip "
        "arm that cannot move even the lexical proxy is a simulation that never reached the "
        "prose"
    ),
}


# ------------------------------------------------------------------------------ generation


class Generator:
    """Retells over `claude -p`, digest-cached with the same discipline as `Elicitor`.

    Not `Elicitor` itself because that class renders persona system prompts and closed-enum
    schemas; a writer generating prose needs neither. The cache record and the resume behaviour
    are the same shape on purpose: append-only JSONL, keyed by a digest of the exact request,
    so editing a state block re-elicits exactly its own retells and replays everything else.
    """

    def __init__(self, cache_path: Path, *, model: str = WRITER_MODEL,
                 dry_run: bool = False) -> None:
        self.cache_path = cache_path
        self.model = model
        self.dry_run = dry_run
        self.api_calls = 0
        self.replayed = 0
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._handle: Any = None
        if cache_path.is_file():
            dropped = 0
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # A transport failure is not a datum and must re-elicit; replaying it would
                # poison every rerun with the environment of the run that failed. A genuine
                # model refusal (stop_reason "refusal") IS a datum — a writer declining a
                # state is a finding — so only transport-shaped failures are dropped.
                stop = str(record.get("stop_reason", ""))
                if record.get("refused") and stop.startswith(("transport_error", "cli_")):
                    dropped += 1
                    continue
                if isinstance(record.get("key"), str):
                    self._cache[record["key"]] = record
            if self._cache or dropped:
                print(f"replaying {len(self._cache)} cached retell(s) from {cache_path.name}"
                      + (f" ({dropped} transport failure(s) dropped for re-elicitation)"
                         if dropped else ""),
                      file=sys.stderr, flush=True)

    def _persist(self, record: dict[str, Any]) -> None:
        if self._handle is None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.cache_path.open("a", encoding="utf-8")
        self._handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._handle.flush()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> Generator:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def retell(self, scene_id: str, state: str, scene_text: str) -> dict[str, Any]:
        return self.generate(
            {"scene": scene_id, "state": state},
            writer_system(state), retell_turn(scene_text),
            dry_text=f"[dry:{state}] {scene_text}",
        )

    def generate(self, tag: dict[str, Any], system: str, prompt: str,
                 *, dry_text: str = "") -> dict[str, Any]:
        """One generation, cached by request digest. `tag` labels the record, never the key.

        Factored out of `retell` so `repair_generation.py` can reuse the cache discipline with
        its own prompts. The key is a digest of exactly what is sent, so the split changes no
        existing key: a byte-identical retell replays from the same record it always did.
        """
        request = {"system": system, "prompt": prompt, "model": self.model, "transport": "cli"}
        key = f"{digest(request)}:0"
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self.replayed += 1
                return cached
        if self.dry_run:
            # A null, not a simulation: the caller's stand-in text behind a marker, so the
            # pipeline's arithmetic runs end-to-end while the outputs carry no signal.
            return {**tag, "key": key, "model": self.model,
                    "text": dry_text or "(dry run: no model was called)",
                    "refused": False, "usage": {}, "dry_run": True}
        argv = [
            # `-p` with NO positional prompt: the prompt goes down stdin (`input=` below,
            # which replaces the closed stdin this call used to pass — the two conflict).
            # Windows caps a command line at 32,767 characters, an over-long argv raises
            # `OSError`, and the retry loop below records that as `transport_error:OSError`
            # after three identical failures — so a retell too large to *send* was cached as
            # a transport failure, a loss correlated with scene length rather than random.
            # Same ceiling and same fix as `providers/cli.py::subprocess_runner` and
            # `elicit.py::_call_cli`, where the measurements live. The cache key is a digest
            # of the request, not the argv, so every record written before this fix replays.
            "claude", "-p",
            "--output-format", "json",
            "--model", self.model,
            "--system-prompt", system,
            *CLI_HARDENING,
        ]
        # Retried, because the failure this absorbs was measured rather than imagined: three
        # concurrent first calls all exited non-zero in the same instant while the identical
        # call succeeded in isolation seconds later — a startup-lock herd, not a property of
        # any request. A transport failure that survives three attempts is recorded with its
        # stderr tail, so the next diagnosis starts from evidence instead of from `cli_error`.
        completed = None
        error_name = ""
        for attempt in range(3):
            if attempt:
                time.sleep(10.0 * attempt)
            try:
                completed = subprocess.run(
                    argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=GEN_TIMEOUT_SECONDS, input=prompt, check=False,
                )
            except (subprocess.TimeoutExpired, OSError) as error:
                completed, error_name = None, type(error).__name__
                continue
            if completed.returncode == 0:
                break
        if completed is None:
            record = {**tag, "key": key, "model": self.model,
                      "text": "", "refused": True,
                      "stop_reason": f"transport_error:{error_name}", "usage": {}}
            with self._lock:
                self._cache[key] = record
                self.api_calls += 1
                self._persist(record)
            return record

        text, stop_reason, usage = "", "cli_error", {}
        if completed.returncode != 0:
            stop_reason = f"cli_error:rc{completed.returncode}:{completed.stderr[-300:].strip()}"
        else:
            try:
                envelope = json.loads(completed.stdout)
            except json.JSONDecodeError:
                envelope = None
            if not isinstance(envelope, dict):
                # A zero exit with no envelope is a transport failure, not a refusal (stage-0
                # §235): the reload rule above drops `cli_`-prefixed failures for
                # re-elicitation, and an `end_turn` refusal with an empty result — what an
                # unparsable stdout used to become — it would have replayed forever.
                envelope = {}
                stop_reason, text = "cli_error:rc=0:unparsable envelope", ""
            else:
                text = str(envelope.get("result", "")).strip()
                stop_reason = str(envelope.get("stop_reason") or "end_turn")
            if envelope.get("is_error"):
                stop_reason, text = "cli_is_error", ""
            tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
            for entry in (envelope.get("modelUsage") or {}).values():
                tokens["input"] += int(entry.get("inputTokens", 0) or 0)
                tokens["output"] += int(entry.get("outputTokens", 0) or 0)
                tokens["cache_read"] += int(entry.get("cacheReadInputTokens", 0) or 0)
                tokens["cache_write"] += int(entry.get("cacheCreationInputTokens", 0) or 0)
            usage = {**tokens, "equivalent_usd": float(envelope.get("total_cost_usd") or 0.0)}
        record = {**tag, "key": key, "model": self.model,
                  "text": text, "refused": not text, "stop_reason": stop_reason, "usage": usage}
        with self._lock:
            self._cache[key] = record
            self.api_calls += 1
            self._persist(record)
        return record

    def spend(self) -> dict[str, float]:
        totals = {"input": 0, "output": 0, "equivalent_usd": 0.0}
        for record in self._cache.values():
            usage = record.get("usage", {})
            totals["input"] += int(usage.get("input", 0) or 0)
            totals["output"] += int(usage.get("output", 0) or 0)
            totals["equivalent_usd"] += float(usage.get("equivalent_usd", 0.0) or 0.0)
        totals["equivalent_usd"] = round(totals["equivalent_usd"], 4)
        return totals


# ----------------------------------------------------------------------------- mechanics

_SENT_SPLIT = re.compile(r"(?<=[.!?])[\"')\]]*\s+")


def prose_report(text: str) -> dict[str, float]:
    """Lexical proxies, named as such — the same ones the ablation battery already carries.

    None of these identifies quality; they identify the *tells* §74's human read named, plus
    rhythm. `interiority_per_1k` counts `_INTERIOR` hits, so it is the proxy underneath
    `interiority_strip`, not a measure of inhabited minds; `stake_per_1k` inherits every caveat
    on `stake_score`'s own docstring.
    """
    words = text.split()
    n = max(len(words), 1)
    sentences = [s for s in _SENT_SPLIT.split(text) if s.strip()]
    lengths = [len(s.split()) for s in sentences] or [0]
    distinct = {w.lower().strip(".,;:!?\"'—()[]*") for w in words}
    return {
        "words": len(words),
        "em_per_1k": round(1000 * len(re.findall(_EM, text)) / n, 3),
        "interiority_per_1k": round(1000 * len(_INTERIOR.findall(text)) / n, 3),
        "stake_per_1k": round(1000 * sum(stake_score(s) for s in sentences) / n, 3),
        "sentence_mean": round(statistics.fmean(lengths), 2),
        "sentence_sd": round(statistics.pstdev(lengths), 2) if len(lengths) > 1 else 0.0,
        "ttr": round(len(distinct) / n, 4),
    }


def system_voice_survival(original: str, retell: str) -> dict[str, int]:
    """How many protected spans of the original survive byte-for-byte in the retell.

    The craft rules order preservation; this checks it, because §74's lesson is that a panel
    shown a mangled stat block reports on the stat block. A retell that lost its system voice
    is still elicited — the loss itself may be state-driven and is worth seeing — but the rate
    sits beside the preference so the two readings stay separable.
    """
    spans = [span.strip() for span in _PROTECTED.findall(original) if span.strip()]
    kept = sum(1 for span in spans if span in retell)
    return {"spans": len(spans), "kept": kept}


# ------------------------------------------------------------------------------- verdict


def verdict(rates: dict[str, float], per_arm_bias: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The pre-registered branches, floor first, bias precondition per arm."""
    def clean(arm: str) -> bool:
        value = per_arm_bias.get(arm, {}).get("chose_A_rate")
        return isinstance(value, float) and 0.40 <= value <= 0.60

    tea = rates.get("tea")
    floor = abs(tea - 0.5) if (tea is not None and clean("tea")) else None
    arms: dict[str, dict[str, str]] = {}
    for arm in ("drunk", "trip"):
        rate = rates.get(arm)
        if rate is None or not clean(arm):
            arms[arm] = {"verdict": "VOID",
                         "why": "no rate or failed its own positional-bias precondition"}
        elif floor is None:
            arms[arm] = {"verdict": "UNBOUNDED",
                         "why": "the tea floor is void or unmeasured; this rate carries an "
                                "unbounded instruction-noise term and is not read"}
        elif abs(rate - 0.5) <= floor:
            arms[arm] = {"verdict": "INERT",
                         "why": f"inside the tea floor of {floor:.4f}; indistinguishable from "
                                "instruction-noise plus draw-noise"}
        elif rate >= 0.60:
            arms[arm] = {"verdict": "PREFERRED",
                         "why": "the state-conditioned retell beats the sober fair copy"}
        elif rate <= 0.40:
            arms[arm] = {"verdict": "REJECTED",
                         "why": "the state degrades the prose below the sober control"}
        else:
            arms[arm] = {"verdict": "INERT",
                         "why": "above the tea floor but under the 0.10 pre-registered margin"}
    return {"arms": arms, "tea_floor": floor, "tea_rate": tea,
            "tea_clean": clean("tea"), "conditions": PRE_REGISTRATION}


# ----------------------------------------------------------------------------------- run


def run(args: argparse.Namespace) -> dict[str, Any]:
    units = generated_scenes(args.book_db, book=args.book, min_words=args.min_words)
    units = units[: args.scenes]
    if len(units) < 2:
        raise SystemExit(f"need at least 2 scenes, got {len(units)}")

    planned_gen = len(units) * len(STATES)
    planned_panel = len(units) * len(STATE_ARMS) * 4 * 2
    if planned_gen + planned_panel > args.guard and not args.yes:
        raise SystemExit(
            f"{planned_gen} retells + {planned_panel} comparisons exceeds the "
            f"{args.guard} guard; pass --yes"
        )

    report: dict[str, Any] = {
        "book_db": str(args.book_db),
        "scenes": [unit.unit_id for unit in units],
        "writer_model": args.writer_model,
        "panel_model": args.model,
        "transport": args.transport,
        "tie_policy": args.tie_policy,
        "states": {name: STATES[name] for name in STATES},
        "planned_retells": planned_gen,
        "planned_comparisons": planned_panel,
        "protocol": "pre-registered in this module's PRE_REGISTRATION before first elicitation",
        # Stage-0 §125's isolation boundary: every panel comparison shows one scene's
        # retell against the sober retell with no history — both sides share the gap. Recorded
        # so the result says so; see context-audit-2026-08-24.md. PRE_REGISTRATION is unchanged.
        "context": "cold_read",
    }

    # ---- generation: every state for every scene, sober included, concurrently.
    retells: dict[tuple[str, str], dict[str, Any]] = {}
    with Generator(Path(args.gen_cache), model=args.writer_model,
                   dry_run=args.dry_run) as generator:
        jobs = [(unit, state) for unit in units for state in STATES]
        with ThreadPoolExecutor(max_workers=GEN_MAX_WORKERS) as pool:
            results = pool.map(
                lambda job: (job[0].unit_id, job[1],
                             generator.retell(job[0].unit_id, job[1], job[0].text)),
                jobs,
            )
            for scene_id, state, record in results:
                retells[(scene_id, state)] = record
                status = "refused" if record["refused"] else f"{len(record['text'].split())}w"
                print(f"  retell {scene_id} [{state}]: {status}", file=sys.stderr, flush=True)
        report["gen_spend"] = generator.spend()
        report["gen_api_calls"] = generator.api_calls
        report["gen_replayed"] = generator.replayed

    failures = [f"{scene}|{state}" for (scene, state), r in retells.items() if r["refused"]]
    report["gen_failures"] = failures

    # ---- mechanics: absolute per arm, plus per-scene deltas against the sober anchor.
    by_state: dict[str, list[dict[str, float]]] = {state: [] for state in STATES}
    deltas: dict[str, list[dict[str, float]]] = {state: [] for state in STATE_ARMS}
    survival: dict[str, list[dict[str, int]]] = {state: [] for state in STATES}
    original_words: list[int] = []
    for unit in units:
        sober_rec = retells.get((unit.unit_id, SOBER))
        if sober_rec is None or sober_rec["refused"]:
            continue
        original_words.append(unit.words)
        sober_stats = prose_report(sober_rec["text"])
        by_state[SOBER].append(sober_stats)
        survival[SOBER].append(system_voice_survival(unit.text, sober_rec["text"]))
        for state in STATE_ARMS:
            record = retells.get((unit.unit_id, state))
            if record is None or record["refused"]:
                continue
            stats = prose_report(record["text"])
            by_state[state].append(stats)
            survival[state].append(system_voice_survival(unit.text, record["text"]))
            deltas[state].append(
                {key: round(stats[key] - sober_stats[key], 3) for key in stats}
            )

    def mean_over(rows: list[dict[str, float]]) -> dict[str, float]:
        if not rows:
            return {}
        return {key: round(statistics.fmean(row[key] for row in rows), 3) for key in rows[0]}

    report["mechanics"] = {state: mean_over(rows) for state, rows in by_state.items()}
    report["mechanics_delta_vs_sober"] = {state: mean_over(rows) for state, rows in deltas.items()}
    report["system_voice"] = {
        state: {
            "spans": sum(row["spans"] for row in rows),
            "kept": sum(row["kept"] for row in rows),
        }
        for state, rows in survival.items() if rows
    }
    report["original_mean_words"] = (
        round(statistics.fmean(original_words), 1) if original_words else 0
    )
    trip_delta = report["mechanics_delta_vs_sober"].get("trip", {})
    report["trip_interiority_up"] = bool(trip_delta.get("interiority_per_1k", 0) > 0)

    if args.generate_only:
        return report

    # ---- the panel: each state retell against the sober anchor, blinded, both orientations.
    every: list[Any] = []
    per_arm: dict[str, list[float]] = {state: [] for state in STATE_ARMS}
    with Elicitor(
        Path(args.cache), model=args.model, spot_model=None, spot_fraction=0.0,
        transport=args.transport, pair_question=args.pair_question, dry_run=args.dry_run,
    ) as elicitor:
        for unit in units:
            sober_rec = retells.get((unit.unit_id, SOBER))
            if sober_rec is None or sober_rec["refused"]:
                continue
            for state in STATE_ARMS:
                record = retells.get((unit.unit_id, state))
                if record is None or record["refused"]:
                    continue
                if record["text"].strip() == sober_rec["text"].strip():
                    continue  # identical retells would be a manufactured tie
                pair_id = f"{unit.unit_id}|{state}"
                comparisons = elicitor.compare_pair(
                    pair_id, sober_rec["text"], record["text"], n=1
                )
                every.extend(comparisons)
                values = [
                    0.5 if c.choice == "neither" else float(c.chose_variant)
                    for c in comparisons if not c.refused
                    and not (c.choice == "neither" and args.tie_policy == "drop")
                ]
                if values:
                    per_arm[state].append(statistics.fmean(values))
            print(f"  {unit.unit_id}: {len(every)} comparisons", file=sys.stderr, flush=True)

        rates = {
            state: round(statistics.fmean(values), 4)
            for state, values in per_arm.items() if values
        }
        report["win_rates"] = rates
        report["positional_bias"] = positional_bias(every)
        report["per_arm_bias"] = {
            state: positional_bias([c for c in every if c.pair_id.endswith(f"|{state}")])
            for state in STATE_ARMS
        }
        report["intervals"] = {
            state: pairwise_interval(
                [c for c in every if c.pair_id.endswith(f"|{state}")],
                args.model, args.tie_policy,
            )
            for state in rates
        }
        report["comparisons"] = len(every)
        report["refused"] = sum(1 for c in every if c.refused)
        report["ladder"] = verdict(rates, report["per_arm_bias"])
        report["panel_spend"] = elicitor.spend()
        report["panel_api_calls"] = elicitor.api_calls
        report["panel_replayed"] = elicitor.replayed
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--book-db", default=str(HERE / "corpora" / "toll.db"))
    parser.add_argument("--book")
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--scenes", type=int, default=8)
    parser.add_argument("--writer-model", default=WRITER_MODEL)
    parser.add_argument("--model", default=PANEL_MODEL)
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument(
        "--pair-question", default="preference", choices=("preference", "intensity")
    )
    parser.add_argument("--tie-policy", default="half_win", choices=("half_win", "drop"))
    parser.add_argument("--guard", type=int, default=300)
    parser.add_argument("--generate-only", action="store_true",
                        help="produce and report the retells without spending panel calls")
    parser.add_argument("--gen-cache",
                        default=str(HERE / "results" / "writer-states-gen-raw.jsonl"))
    parser.add_argument("--cache", default=str(HERE / "results" / "writer-states-raw.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results" / "writer-states.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report.get("win_rates", {}), indent=2))
    print(json.dumps(report.get("mechanics_delta_vs_sober", {}), indent=2))
    if "ladder" in report:
        print(json.dumps({k: v for k, v in report["ladder"].items() if k != "conditions"},
                         indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
