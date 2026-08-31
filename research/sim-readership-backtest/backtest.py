"""The staged driver: dry run, pilot, full — PID-locked, cost-ledgered, probe-before-arm.

PREREG.md §8 and §10 are the contract. This module is thin on method — every methodological
choice lives in the six siblings — and thick on refusals: no session runs before its book is
probe-classified, no book counts as probed on a probe that returned nothing, no cell enters a
plan whose two stimuli are empty or byte-identical, no stage runs twice concurrently, no spend
passes the registered ceiling, and the full stage refuses without a pilot whose ledger held
and whose VOIDs stayed silent. Every refusal is counted where the result file can see it:
`under_run` carries planned sessions beside returned votes beside the transport's own failure
count, because the one failure mode this driver had no words for was an arm that bought a
twentieth of its plan and reported as a finished arm.

**Vote spaces, and the one remap this module owns.** `arms` produces choices in slot space
("A"/"B" as shown), which is what the positional control must read. The registered aggregate
(PREREG §6) is over pair *members*, so before aggregation the driver remaps each decided vote
via `high_was`: member-space "A" means the higher-outcome member, whatever slot it sat in.
`analysis.aggregate_by_pair` then reads member space, and `predicted == "A"` is the correct
prediction. Slot-space votes feed `analysis.positional_rate` and `analysis.sham_floor`
untouched. The remap lives in exactly one function (`to_member_space`) for the same reason
`arms.ordered` is the only place order is applied.

**Two verdicts since 2026-08-31.** PREREG's appended post-hoc amendment changed two things
about the control corners, and this module is where both land: control arms carry a stage salt
in their sample index so they draw fresh at the stage that has to certify them
(`control_stage_salt`), and every paid run writes `verdict_registered` beside `verdict_amended`
over one set of votes (`dual_verdict`). Neither verdict is called `verdict`, and the primary
arms are deliberately unsalted — their pilot pairs replay, which `amendment.disclosure` states
on the face of the result file.

The fictions input is the excerpt pass's artifact (rows with text for paired books only,
regenerated per RUNBOOK.md under the MirrorBench venv); this module never touches parquet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
_QUALITY = HERE.parent / "quality-measurement"
if str(_QUALITY) not in sys.path:
    sys.path.insert(0, str(_QUALITY))

import ablate  # noqa: E402
import analysis  # noqa: E402
import arms  # noqa: E402
import blinding  # noqa: E402
import corpus  # noqa: E402
import population  # noqa: E402
import recognition  # noqa: E402

STAGES = ("dry", "pilot", "full")

#: PREREG §8 stage (b): the pilot runs this fraction of the confirmatory target.
PILOT_FRACTION = 0.10

#: PREREG §8: the ceiling is a refusal, not a note.
#: **Raised 180 -> 900 on 2026-08-31 by the operator, verbatim: "yeah it's fine raise the
#: ceiling, we are using subscription quota anyways, just might be rate limited earlier in
#: the week before the reset." The number seen (K1a): the corrected basis prices the
#: registered full stage at ~$663 beside a ~$132 cumulative pilot; 900 covers both with
#: margin. The dollars are subscription-equivalent; the practical constraint the operator
#: names is the weekly rate-limit reset, not cash.**
COST_CEILING_USD = 900.0

#: PREREG §8: decided confirmatory pairs the full stage aims for.
N_TARGET = 200

#: Control-arm sizes. Shams per PREREG §7 (n = 12); damage and surface sized to clear
#: analysis' ten-outcome floor with margin at pilot cost.
SHAM_BOOKS = 12
DAMAGE_BOOKS = 15
SURFACE_PAIRS = 15

#: Surface arm selection: outcome-matched (conversion ratio at most this) ...
MATCHED_RATIO_MAX = 1.5
#: ... and formatting-divergent (mean-paragraph-length ratio at least this).
SURFACE_SPREAD_MIN = 2.0

#: The arms whose sample indices carry the stage salt (PREREG's post-hoc amendment of
#: 2026-08-31, part 2: **controls are sampled at the stage they certify**). The primary C and
#: P arms are deliberately absent — their pilot pairs are registered pairs of the confirmatory
#: set and replay by design, which the amendment discloses rather than hides.
CONTROL_ARMS = ("sham", "damage", "surface")

#: Per-stage salt for `arms._sample_index`. The pilot's controls were drawn under the empty
#: salt and its committed record must keep replaying free (RUNBOOK's guarantee), so stage (b)
#: keeps the empty string; stage (c) salts with its own name, which changes the cache key of a
#: byte-identical request and buys a fresh draw. The map is the whole mechanism: no salt, no
#: re-draw; wrong salt, wrong stage.
STAGE_SALT: dict[str, str] = {"dry": "", "pilot": "", "full": "full"}

#: PREREG's amendment section title, its date, and the operator's words that ordered it. The
#: constants live here because the result file must carry the amendment's provenance beside
#: the two verdicts it produces; `amendment_provenance` assembles them.
AMENDMENT_SECTION = "## Post-hoc amendment (2026-08-31)"
AMENDMENT_DATE = "2026-08-31"
AMENDMENT_DIRECTIVE = "draft the amendment, run the full after reset"
AMENDMENT_COMMIT_SUBJECT = (
    "Amend the two control corners for their mechanical reasons, and report both verdicts"
)

#: The declared per-session cost basis of the §8 ceiling arithmetic; the pilot's measured
#: ledger x10 must land within 2x of the estimate built from this, or the full stage refuses.
#: **Corrected 2026-08-31 under the K1a precedent (an edit forced by an error names the
#: number it had seen): the registered 0.012 was wrong by 6.2x — the 2026-08-30 pilot
#: measured $41.2066 over 1,104 records (510 two-call sessions + 84 probe calls), i.e.
#: $0.0747/session — and the correction was made after that number, under the operator's
#: standing go (plan/serial-pilot-18.md §8). At this basis the registered full stage prices
#: at ~$660 against the $180 ceiling; the ceiling is untouched and will refuse it, which is
#: the fork the operator decides.**
EST_USD_PER_SESSION = 0.075

#: Words of true continuation kept for the recognition probe's (c) leg.
TRUTH_WORDS = 80

_PROBE_MAX_TOKENS = 80


class _SentinelElicitor:
    """Stands where `elicit.Elicitor` would; constructing it is itself the failure."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("sentinel elicitor constructed; the dry stage tried to buy a call")


# ---------------------------------------------------------------------------------- the lock


class PidLock:
    """One instance per stage, `force_remote.SingleRun`'s discipline in miniature.

    O_CREAT | O_EXCL is the atomicity; the file carries the holder's pid so the refusal can
    name it. Released on exit; a crash leaves the file and the refusal message says how to
    clear it, because silently stealing a lock is how two paid runs end up interleaved.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> PidLock:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = self.path.read_text(encoding="utf-8").strip() or "unknown"
            raise RuntimeError(
                f"another backtest instance holds {self.path.name} (pid {holder}); if that "
                "process is dead, delete the lock file and re-run"
            ) from None
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        return self

    def __exit__(self, *exc: object) -> None:
        self.path.unlink(missing_ok=True)


# -------------------------------------------------------------------------------- the inputs


def load_pairs(path: Path) -> list[corpus.Pair]:
    """The committed pair artifact (`pairs-v0.json`) back as `corpus.Pair` records."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        corpus.Pair(
            pair_id=entry["pair_id"],
            high=entry["high"],
            low=entry["low"],
            cell=tuple(entry["cell"]),
            ratio=float(entry["ratio"]),
        )
        for entry in payload["pairs"]
    ]


def load_fictions(path: Path) -> dict[str, corpus.Fiction]:
    """The excerpt pass's artifact: `{fiction_id: [row, ...]}` with chapter text carried."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        fiction_id: corpus.fiction_from_rows(rows) for fiction_id, rows in payload.items()
    }


def confirmatory(pairs: Sequence[corpus.Pair]) -> list[corpus.Pair]:
    """PREREG §3 as amended: the confirmatory pool is the `undeclared_2025` cells."""
    return [pair for pair in pairs if pair.cell[0] == "undeclared_2025"]


# --------------------------------------------------------------------------- probe machinery


def probe_material(fiction: corpus.Fiction) -> tuple[str, str] | None:
    """(blinded excerpt, raw continuation truth) for the probes, or None without chapters.

    The excerpt is the same blinded C-arm stimulus a main-arm session would show (PREREG §3);
    the truth is the raw text immediately after the cap, for the verbatim-continuation leg. A
    book whose excerpt exhausts its text has an empty truth: probe (c) then cannot hit, and
    (a)/(b) carry the screen alone.
    """
    chapters = corpus.chapters_1_to_3(fiction)
    if chapters is None:
        return None
    joined = "\n\n".join(chapter.text for chapter in chapters)
    capped = arms._cap_paragraph(joined)
    excerpt = blinding.blind(capped, title=fiction.title, author=fiction.author).text
    rest = joined[len(capped):].split()
    return excerpt, " ".join(rest[:TRUTH_WORDS])


def probe_book(elicitor: Any, fiction: corpus.Fiction, *, model: str) -> dict[str, Any]:
    """Run the three probes for one book and classify. Precedes every main-arm session.

    **A probe that was never answered is not a probe that came back negative.** PREREG §3 says
    every candidate book is probed before any main-arm call; a transport that returns no text
    has not probed it, and scoring that silence as a miss turns an unasked question into
    evidence of no recognition. Such a book is classified `unprobed` — outside `clean`, so it
    enters no arm — and the names of the unanswered probes travel with the record.

    The rule was written after the 2026-08-30 pilot, where 12 of 40 books had all three probes
    fail on the transport and all 12 were classified `clean`; the screen that carries the
    entire memorisation defense had, for those books, screened nothing.
    """
    material = probe_material(fiction)
    if material is None:
        return {"fiction_id": fiction.fiction_id, "classification": "recognised",
                "why": "no identifiable opening to probe; excluded rather than unprobed"}
    excerpt, truth = material
    results = []
    unanswered: list[str] = []
    for index, (probe_name, template) in enumerate(recognition.PROBES):
        record = elicitor.ask_raw(
            "", [{"role": "user", "content": template.format(excerpt=excerpt)}],
            schema=None, max_tokens=_PROBE_MAX_TOKENS,
            tag={"stage": "probe", "probe": probe_name, "fiction": fiction.fiction_id},
            sample=_probe_sample(fiction.fiction_id, index), model=model,
        )
        answer = record.get("text") or ""
        if not answer.strip():
            unanswered.append(probe_name)
        results.append(
            recognition.score_probe(
                probe_name, answer, title=fiction.title,
                author=fiction.author, truth_continuation=truth,
            )
        )
    classification = recognition.classify(results)
    out = {
        "fiction_id": fiction.fiction_id,
        "classification": classification,
        "probes": [asdict(result) for result in results],
    }
    if unanswered and classification == "clean":
        out["classification"] = "unprobed"
        out["why"] = f"no answer from probe(s) {', '.join(unanswered)}; a silence is not a miss"
        out["unanswered"] = unanswered
    return out


def _probe_sample(fiction_id: str, probe_index: int) -> int:
    payload = f"probe\x00{fiction_id}\x00{probe_index}"
    return int(hashlib.sha256(payload.encode()).hexdigest()[:16], 16)


# ------------------------------------------------------------------------- session construction


@dataclass(frozen=True, slots=True)
class PlannedSession:
    spec: arms.SessionSpec
    system: str
    text_a: str
    text_b: str


class DegenerateStimuli(ValueError):
    """A planned cell whose two stimuli cannot pose the question the cell exists to pose."""


def _sessions_for_pair(
    pair_id: str, arm: str, high_text: str, low_text: str,
    personas: Sequence[population.Persona],
) -> list[PlannedSession]:
    """Ten personas x two orders for one cell, or a named refusal if the cell is degenerate.

    Two byte-identical stimuli are not a comparison — both orders ask the same question and
    any answer is a coin the arm would count as a preference — and an empty stimulus is not a
    stimulus. Either raises `DegenerateStimuli`; `build_sessions` catches, counts and reports
    it, so a cell can leave the plan but never leave it quietly.

    The rail is here because of what the 2026-08-30 pilot cost, even though its own loss came
    later in the pipeline: 380 of 400 planned C-arm cells returned no vote — 360 of them left
    no record at all — and the result file said only that 20 votes existed, so the under-run
    had to be reconstructed from the raw cache. Every way a planned cell can fail to be one
    gets a count from now on: this is the build-time half, and `run_paid`'s planned-versus-
    returned census is the run-time half.
    """
    if not high_text.strip() or not low_text.strip():
        raise DegenerateStimuli(
            f"{arm}/{pair_id}: an empty stimulus is not a stimulus "
            f"(lengths {len(high_text)}, {len(low_text)})"
        )
    if high_text == low_text:
        raise DegenerateStimuli(
            f"{arm}/{pair_id}: byte-identical stimuli are not a comparison "
            f"(digest {corpus.excerpt_digest(high_text)[:16]})"
        )
    out = []
    for persona in personas:
        for order in (0, 1):
            text_a, text_b = arms.ordered(high_text, low_text, order)
            spec = arms.SessionSpec(
                pair_id=pair_id, arm=arm, persona_id=persona.persona_id, order=order,
                excerpt_a_digest=corpus.excerpt_digest(text_a),
                excerpt_b_digest=corpus.excerpt_digest(text_b),
            )
            out.append(
                PlannedSession(spec, population.system_prompt(persona), text_a, text_b)
            )
    return out


def build_sessions(
    pairs: Sequence[corpus.Pair],
    fictions: Mapping[str, corpus.Fiction],
    classifications: Mapping[str, str],
    personas: Sequence[population.Persona],
) -> dict[str, list[PlannedSession]]:
    """Every planned session for the given pairs, probe-before-arm enforced structurally.

    A book without a stored `clean` classification cannot enter any builder: its pairs are
    skipped and counted, never silently run (the PREREG §3 rule in code). Returns sessions by
    arm: primary C and P over recognition-clean pairs; C1 shams and the same-book C2 damage
    arm over the first clean high-side books; the C4 surface arm over outcome-matched,
    formatting-divergent clean book pairs.

    Two counts ride out with the sessions and neither may be dropped by a caller:
    `skipped_pairs` (no clean classification) and `degenerate_stimuli` (the named refusals
    `_sessions_for_pair` raised). A plan is only as trustworthy as its own account of what
    left it.
    """
    def clean(fiction_id: str) -> bool:
        return classifications.get(fiction_id) == "clean"

    sessions: dict[str, list[PlannedSession]] = {"C": [], "P": [], "sham": [], "damage": [],
                                                 "surface": []}
    degenerate: list[str] = []

    def cell(arm: str, pair_id: str, high_text: str, low_text: str) -> list[PlannedSession]:
        """One cell's sessions, or none plus a recorded refusal. Never a silent none."""
        try:
            return _sessions_for_pair(pair_id, arm, high_text, low_text, personas)
        except DegenerateStimuli as refusal:
            degenerate.append(str(refusal))
            return []

    skipped_pairs = 0
    clean_pairs = []
    for pair in pairs:
        if not (clean(pair.high) and clean(pair.low)):
            skipped_pairs += 1
            continue
        clean_pairs.append(pair)
        high_c, low_c = arms.c_arm_texts(pair, fictions, blinding.blind)
        sessions["C"].extend(cell("C", pair.pair_id, high_c, low_c))
        high_p, low_p = arms.p_arm_texts(pair, fictions, blinding.blind)
        sessions["P"].extend(cell("P", pair.pair_id, high_p, low_p))

    clean_high_books = [fictions[p.high] for p in clean_pairs]
    for fiction in clean_high_books[:SHAM_BOOKS]:
        windows = arms.sham_windows(fiction, blinding.blind)
        if windows is None:
            continue
        sessions["sham"].extend(cell("sham", f"sham-{fiction.fiction_id}", *windows))
    for fiction in clean_high_books[:DAMAGE_BOOKS]:
        chapters = corpus.chapters_1_to_3(fiction)
        if chapters is None:
            continue
        capped = arms._cap_paragraph("\n\n".join(c.text for c in chapters))
        intact = blinding.blind(capped, title=fiction.title, author=fiction.author).text
        shuffled = blinding.blind(
            ablate.paragraph_shuffle(capped, 1.0), title=fiction.title, author=fiction.author
        ).text
        if shuffled == intact:
            continue  # too few paragraphs to displace; an unmoved sham is no damage arm
        sessions["damage"].extend(
            cell("damage", f"damage-{fiction.fiction_id}", intact, shuffled)
        )
    sessions["surface"].extend(_surface_sessions(clean_pairs, fictions, personas, cell))
    sessions["skipped_pairs"] = skipped_pairs  # type: ignore[assignment]
    sessions["degenerate_stimuli"] = degenerate  # type: ignore[assignment]
    return sessions


def _mean_paragraph_words(fiction: corpus.Fiction) -> float | None:
    chapters = corpus.chapters_1_to_3(fiction)
    if chapters is None:
        return None
    blocks = [b for b in "\n\n".join(c.text for c in chapters).split("\n\n") if b.strip()]
    if not blocks:
        return None
    return sum(len(b.split()) for b in blocks) / len(blocks)


def _surface_sessions(
    clean_pairs: Sequence[corpus.Pair],
    fictions: Mapping[str, corpus.Fiction],
    personas: Sequence[population.Persona],
    cell: Callable[[str, str, str, str], list[PlannedSession]],
) -> list[PlannedSession]:
    """C4: same-cell book pairs matched on outcome, divergent on paragraph formatting.

    Candidates are the clean pairs' high-side books (their conversions are on record).
    Deterministic scan in fiction-id order; each book used at most once.
    """
    books = []
    for pair in clean_pairs:
        fiction = fictions[pair.high]
        outcome = corpus.conversion(fiction)
        spread = _mean_paragraph_words(fiction)
        if outcome and spread:
            books.append((fiction, outcome, spread, corpus.cell_key(fiction)))
    books.sort(key=lambda item: item[0].fiction_id)
    out: list[PlannedSession] = []
    used: set[str] = set()
    for i, (fa, oa, sa, cell_a) in enumerate(books):
        if len(out) // (len(personas) * 2) >= SURFACE_PAIRS:
            break
        if fa.fiction_id in used:
            continue
        for fb, ob, sb, cell_b in books[i + 1:]:
            if fb.fiction_id in used:
                continue
            ratio = max(oa, ob) / max(min(oa, ob), 1e-12)
            spread = max(sa, sb) / max(min(sa, sb), 1e-12)
            if cell_a == cell_b and ratio <= MATCHED_RATIO_MAX and spread >= SURFACE_SPREAD_MIN:
                pair_id = f"surface-{fa.fiction_id}-{fb.fiction_id}"
                high, low = (fa, fb) if oa >= ob else (fb, fa)
                high_text = arms._c_arm_text(high, blinding.blind)
                low_text = arms._c_arm_text(low, blinding.blind)
                out.extend(cell("surface", pair_id, high_text, low_text))
                used.update((fa.fiction_id, fb.fiction_id))
                break
    return out


# ----------------------------------------------------------------------------- the paid loop


def run_sessions(
    elicitor: Any, planned: Sequence[PlannedSession], *, model: str,
    ledger: dict[str, float], stage_salt: str = "",
) -> tuple[list[analysis.Vote], bool]:
    """Two-stage sessions in order; returns (votes, aborted_at_ceiling).

    After every session the elicitor's own spend is read into the ledger; crossing
    `COST_CEILING_USD` finishes nothing further — the current session completes, the abort
    flag raises to the caller, and the partial result says so.

    `stage_salt` is passed straight to `arms.build_session` and reaches nothing else: it
    changes the cache key, never the stimulus, the system prompt, the schema or the parse.
    `run_paid` is the only caller that sets it, and only for `CONTROL_ARMS`.
    """
    votes: list[analysis.Vote] = []
    for planned_session in planned:
        request = arms.build_session(
            planned_session.spec, planned_session.system,
            planned_session.text_a, planned_session.text_b,
            stage_salt=stage_salt,
        )
        stage1 = elicitor.ask_raw(
            request["system"], request["plan"][0]["turns"], schema=None,
            max_tokens=request["plan"][0]["max_tokens"], tag=request["tag"],
            sample=request["sample"], model=model,
        )
        turns = [
            *request["plan"][0]["turns"],
            {"role": "assistant", "content": stage1.get("text") or ""},
            *request["plan"][1]["turns"],
        ]
        stage2 = elicitor.ask_raw(
            request["system"], turns, schema=request["plan"][1]["schema"],
            max_tokens=request["plan"][1]["max_tokens"], tag=request["tag"],
            sample=request["sample"], model=model,
        )
        parsed = arms.parse_stage2(stage2.get("text") or "")
        if parsed is not None:
            choice, reason = parsed
            votes.append(
                analysis.Vote(
                    pair_id=planned_session.spec.pair_id, arm=planned_session.spec.arm,
                    persona_id=planned_session.spec.persona_id,
                    order=planned_session.spec.order, choice=choice, reason=reason,
                    high_was="A" if planned_session.spec.order == 0 else "B",
                )
            )
        spend = elicitor.spend() if hasattr(elicitor, "spend") else {}
        ledger["equivalent_usd"] = float(spend.get("equivalent_usd", 0.0))
        if ledger["equivalent_usd"] >= COST_CEILING_USD:
            return votes, True
    return votes, False


def to_member_space(votes: Sequence[analysis.Vote]) -> list[analysis.Vote]:
    """The one remap: slot-space choices become member-space ("A" = the higher-outcome member).

    "neither" survives untouched; `high_was` becomes "A" uniformly because in member space the
    higher member *is* side A. Positional and sham arithmetic must never receive these.
    """
    remapped = []
    for vote in votes:
        if vote.choice == "neither":
            choice = "neither"
        else:
            choice = "A" if vote.choice == vote.high_was else "B"
        remapped.append(
            analysis.Vote(
                pair_id=vote.pair_id, arm=vote.arm, persona_id=vote.persona_id,
                order=vote.order, choice=choice, reason=vote.reason, high_was="A",
            )
        )
    return remapped


def outcomes_from(aggregate: Mapping[str, Any]) -> list[int]:
    """Member-space aggregate to the primary outcome vector: 1 when the high member won."""
    return [
        1 if entry["predicted"] == "A" else 0
        for entry in aggregate["pairs"].values()
        if entry["decided"]
    ]


# ----------------------------------------------------------------------------------- the plan


def plan(stage: str, n_confirmatory: int) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; stages are {', '.join(STAGES)}")
    target = min(N_TARGET, n_confirmatory)
    pairs_this_stage = math.ceil(PILOT_FRACTION * target) if stage == "pilot" else target
    personas = len(population.POPULATION)
    primary_sessions = pairs_this_stage * personas * 2 * 2  # C and P arms, both orders
    control_sessions = (SHAM_BOOKS + DAMAGE_BOOKS + SURFACE_PAIRS) * personas * 2
    probes = 3 * (2 * pairs_this_stage + SHAM_BOOKS + DAMAGE_BOOKS + 2 * SURFACE_PAIRS)
    sessions = primary_sessions + control_sessions
    return {
        "stage": stage,
        "confirmatory_pool": n_confirmatory,
        "pairs_this_stage": pairs_this_stage,
        "sessions": sessions,
        "probe_calls": probes,
        "calls_worst_case": sessions * 2 + probes,
        "estimated_usd": round(sessions * EST_USD_PER_SESSION, 2),
        "ceiling_usd": COST_CEILING_USD,
    }


# ------------------------------------------------------------------------------------ result


def control_stage_salt(stage: str, arm: str) -> str:
    """The salt one arm carries at one stage: `STAGE_SALT[stage]` for a control, else empty.

    Two lookups, no branching cleverness, because this is the function that decides which
    cells re-draw and which replay — and a reader has to be able to check that decision
    against PREREG's amendment in one glance. An unknown stage raises rather than defaulting
    to the empty string: a silent no-salt would put stage (c)'s controls back on the pilot's
    cached answers, which is the exact defect the amendment exists to remove.
    """
    if stage not in STAGE_SALT:
        raise ValueError(f"unknown stage {stage!r}; stages are {', '.join(STAGES)}")
    return STAGE_SALT[stage] if arm in CONTROL_ARMS else ""


def amendment_provenance() -> dict[str, Any]:
    """The amendment's own record, read out of PREREG.md so the two cannot drift apart.

    The result file must be able to say, on its own face, that its `verdict_amended` came from
    a post-hoc change and which change: the date, the operator's words verbatim, the two
    mechanical parameters, and a content address for the registration text that argues them.
    `section_sha256` is taken over PREREG.md from the amendment heading to end of file, read
    through Python's universal-newline translation so the digest is the same on an LF or a
    CRLF checkout (`registration_digests`' whole-file digest is over raw bytes and is not).

    The amendment commit's hash cannot be in a file that commit contains, so the pointer is
    its subject line — `git log --grep` finds it — beside the content address, which pins the
    bytes that matter. If the section is absent the record says so and the run is still
    written: a missing registration text is a fact about the run, not a reason to lose it.
    """
    text = (HERE / "PREREG.md").read_text(encoding="utf-8")
    index = text.find(AMENDMENT_SECTION)
    if index < 0:
        return {
            "present": False,
            "why": f"PREREG.md carries no {AMENDMENT_SECTION!r} section; the code amended "
                   "what the registration did not — report the amended verdict as unregistered",
        }
    return {
        "present": True,
        "date": AMENDMENT_DATE,
        "kind": "post-hoc analysis amendment, drafted after the re-pilot's control numbers "
                "were seen and recorded as such",
        "operator_directive": AMENDMENT_DIRECTIVE,
        "prereg_section": AMENDMENT_SECTION.lstrip("# "),
        "section_sha256": hashlib.sha256(text[index:].encode("utf-8")).hexdigest(),
        "commit_subject": AMENDMENT_COMMIT_SUBJECT,
        "sham_min_decided": analysis.SHAM_MIN_DECIDED,
        "control_arms_stage_salted": list(CONTROL_ARMS),
        "primary_arms_stage_salted": [],
        "disclosure": (
            "The primary C and P arms are not salted: the pilot's 20 pairs are registered "
            "members of the confirmatory set, so this run's aggregate includes their replayed "
            "votes as its first 10%. Registered design, same rules, stated rather than silent."
        ),
    }


def _verdict_or_refusal(
    primary_outcomes: Sequence[int], **rule: Any
) -> dict[str, Any]:
    """`analysis.verdicts`, with its ten-outcome refusal caught and named rather than raised.

    The refusal is a result (a bound from a handful of pairs is §85's zero-width defect), so
    it lands in the record as `{"verdict": "refused", "why": ...}` exactly as the single-verdict
    path recorded it before the amendment. Both verdicts go through here, so neither can fail
    in a way the other hides.
    """
    try:
        return analysis.verdicts(primary_outcomes, **rule)
    except ValueError as refusal:
        return {"verdict": "refused", "why": str(refusal)}


def dual_verdict(
    primary_outcomes: Sequence[int], *,
    largest_true_effect: float,
    positional: Mapping[str, Any],
    votes_by_sham: Mapping[str, Sequence[analysis.Vote]],
    damage_outcomes: Sequence[int],
    shuffle: Mapping[str, Any],
) -> dict[str, Any]:
    """Both rules over one set of votes — PREREG's post-hoc amendment, part 3.

    Returns the five keys the result file carries for the decision: `sham` (the registered
    floor), `sham_amended` (the guarded floor), `verdict_registered`, `verdict_amended`, and
    `amendment` (the provenance). **There is no key named `verdict`**: the whole point is that
    a reader has to name the rule they are quoting.

    The two verdicts differ in exactly one input, the sham record. Same primary outcomes, same
    positional record, same damage outcomes, same shuffle, same `largest_true_effect` — so any
    difference between them is attributable to the sham corner and to nothing else. That is
    also why this is one function rather than two call sites that could drift apart.
    """
    sham = analysis.sham_floor(votes_by_sham)
    sham_amended = analysis.sham_floor(votes_by_sham, min_decided=analysis.SHAM_MIN_DECIDED)
    rule: dict[str, Any] = {
        "largest_true_effect": largest_true_effect,
        "positional": positional,
        "damage_outcomes": damage_outcomes,
        "shuffle": shuffle,
    }
    def _in_margin_band(floor: float) -> bool:
        return floor < largest_true_effect < floor + 0.05

    return {
        "sham": sham,
        "sham_amended": sham_amended,
        "verdict_registered": _verdict_or_refusal(primary_outcomes, sham=sham, **rule),
        "verdict_amended": _verdict_or_refusal(primary_outcomes, sham=sham_amended, **rule),
        # PREREG §7 registers a +0.05 clearance margin over the sham floor that
        # `analysis.verdicts` never implemented (it implements the void half only) — recorded
        # as an observation at amendment time, deliberately not closed post hoc. This flag
        # makes the divergence announce itself exactly when it matters: the outcome landed
        # where the registered TEXT and the registered CODE disagree, and a reader of either
        # verdict has to say which authority they are quoting.
        "unimplemented_margin_band": {
            "registered": _in_margin_band(sham["floor"]),
            "amended": _in_margin_band(sham_amended["floor"]),
            "band": "floor < effect < floor + 0.05 (PREREG §7's uncoded clearance)",
        },
        "amendment": amendment_provenance(),
    }


def _fresh_only(
    primary_agg: Mapping[str, Any], pool: Sequence[corpus.Pair], stage: str,
) -> dict[str, Any] | None:
    """Accuracy over the confirmatory pairs the pilot never saw; None below stage (c).

    The pilot's pairs are `pool[:20]` by construction (the pilot plan's own slice), so the
    fresh set is everything decided beyond them. Descriptive only — the registered primary
    stays the pooled aggregate, and PREREG §A.4(4) discloses the pooling.
    """
    if stage != "full":
        return None
    pilot_ids = {p.pair_id for p in pool[: plan("pilot", len(pool))["pairs_this_stage"]]}
    fresh = [
        1 if entry["predicted"] == "A" else 0
        for pair_id, entry in primary_agg["pairs"].items()
        if entry["decided"] and pair_id not in pilot_ids
    ]
    return {
        "n": len(fresh),
        "correct": sum(fresh),
        "accuracy": (sum(fresh) / len(fresh)) if fresh else None,
    }


def registration_digests(pairs_path: Path) -> dict[str, str]:
    prereg = (HERE / "PREREG.md").read_bytes()
    return {
        "prereg_sha256": hashlib.sha256(prereg).hexdigest(),
        "population_digest": population.population_digest(),
        "pairs_digest": hashlib.sha256(pairs_path.read_bytes()).hexdigest()[:16],
    }


def write_result(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=STAGES)
    parser.add_argument("--pairs", default=str(HERE / "pairs-v0.json"))
    parser.add_argument("--fictions", default=str(HERE / "fictions-v0.json"))
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--cache", default=str(HERE / "backtest-raw.jsonl"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    pairs_path = Path(args.pairs)
    pool = confirmatory(load_pairs(pairs_path))
    stage_plan = plan(args.stage, len(pool))
    print(json.dumps(stage_plan, indent=2, sort_keys=True))

    if args.stage == "dry":
        fictions = load_fictions(Path(args.fictions))
        classifications = dict.fromkeys(fictions, "clean")  # dry: structure only, no probe
        sessions = build_sessions(
            pool[: stage_plan["pairs_this_stage"]], fictions, classifications,
            population.POPULATION,
        )
        for arm_name in ("C", "P", "sham", "damage", "surface"):
            print(f"  {arm_name}: {len(sessions[arm_name])} session(s)")
        for refusal in sessions["degenerate_stimuli"]:
            print(f"  refused: {refusal}")
        print("dry: no elicitor constructed, nothing spent", file=sys.stderr)
        return 0

    if not args.yes:
        print(f"pass --yes to spend (stage {args.stage}); --stage dry costs nothing",
              file=sys.stderr)
        return 1
    # The operator's go arrived 2026-08-30, verbatim: "Let's just do the sim-readership
    # maybe it will help" — recorded in plan/serial-pilot-18.md §8 (commit 930127e), five
    # days after §123's registration. This commit is the citation the refusal above asked
    # for; every ceiling and stage gate below it still holds.
    return run_paid(args)


def run_paid(args: argparse.Namespace) -> int:
    """Stages (b) and (c): probe-before-arm, all five arms, the registered analysis, one file.

    Thin on method by the module's own charter — every choice below names the sibling that
    owns it. The ledger is read after every session (`run_sessions`); the ceiling aborts
    mid-arm and the partial result says so. The pilot's own gate (PREREG §8: no VOID fired,
    ledger within 2x of estimate) is computed descriptively here because `verdicts`'s
    insufficient_n precedence deliberately silences VOIDs below target n.

    Since PREREG's post-hoc amendment of 2026-08-31 this function writes **two** verdicts over
    one set of votes: `verdict_registered` under the rule as registered, `verdict_amended`
    under the amended sham floor, with `amendment` carrying the provenance of the change.
    Control arms draw fresh at a salted stage (`control_stage_salt`); the primary arms do not,
    so a full run's aggregate contains the pilot pairs' replayed votes — which the amendment
    record states in `amendment.disclosure` rather than leaving to be inferred from a cache.
    """
    import elicit
    from force_remote import SingleRun

    fictions_path = Path(args.fictions)
    if not fictions_path.is_file():
        print(
            f"the excerpt-pass artifact is absent: {fictions_path}. Regenerate it per "
            "RUNBOOK.md free leg 3 (excerpt_pass.py, MirrorBench venv) before any paid "
            "stage; nothing was spent.",
            file=sys.stderr,
        )
        return 1
    pairs_path = Path(args.pairs)
    pool = confirmatory(load_pairs(pairs_path))
    stage_plan = plan(args.stage, len(pool))
    stage_pairs = pool[: stage_plan["pairs_this_stage"]]
    fictions = load_fictions(fictions_path)
    out_path = Path(args.out) if args.out else HERE / f"result-{args.stage}.json"

    with SingleRun(HERE / "backtest.pid", label=f"backtest {args.stage}"):
        elicitor = elicit.Elicitor(
            cache_path=Path(args.cache), model=args.model,
            spot_model=None,  # PREREG §7: no spot model — cutoff reasoning
            transport="cli",
        )
        ledger: dict[str, float] = {"equivalent_usd": 0.0}

        needed = sorted({p.high for p in stage_pairs} | {p.low for p in stage_pairs})
        probes: list[dict[str, Any]] = []
        classifications: dict[str, str] = {}
        for fiction_id in needed:
            record = probe_book(elicitor, fictions[fiction_id], model=args.model)
            classifications[fiction_id] = record["classification"]
            probes.append(record)
        recognised = sorted(f for f, c in classifications.items() if c == "recognised")
        unprobed = sorted(f for f, c in classifications.items() if c == "unprobed")

        sessions = build_sessions(stage_pairs, fictions, classifications,
                                  population.POPULATION)
        skipped_pairs = sessions.pop("skipped_pairs")
        degenerate_stimuli = sessions.pop("degenerate_stimuli")
        planned_sessions = {arm: len(cells) for arm, cells in sessions.items()}
        votes: dict[str, list[analysis.Vote]] = {}
        aborted = False
        for arm_name in ("C", "P", "sham", "damage", "surface"):
            if aborted:
                votes[arm_name] = []
                continue
            votes[arm_name], aborted = run_sessions(
                elicitor, sessions[arm_name], model=args.model, ledger=ledger,
                stage_salt=control_stage_salt(args.stage, arm_name),
            )

        reward_ids = [p.persona_id for p in population.reward_split()]
        primary_agg = analysis.aggregate_by_pair(to_member_space(votes["C"]), reward_ids)
        primary_outcomes = outcomes_from(primary_agg)
        largest_true = (
            abs(sum(primary_outcomes) / len(primary_outcomes) - 0.5)
            if primary_outcomes else 0.0
        )
        positional = analysis.positional_rate(votes["C"])
        by_sham: dict[str, list[analysis.Vote]] = {}
        for vote in votes["sham"]:
            by_sham.setdefault(vote.pair_id, []).append(vote)
        damage_agg = analysis.aggregate_by_pair(to_member_space(votes["damage"]), reward_ids)
        damage_outcomes = outcomes_from(damage_agg)
        try:
            shuffle = analysis.label_shuffle(
                primary_outcomes, seed_material="|".join(map(str, primary_outcomes)),
            )
        except ValueError as refusal:
            shuffle = {"clear_share": 0.0, "refused": str(refusal)}
        dual = dual_verdict(
            primary_outcomes, largest_true_effect=largest_true, positional=positional,
            votes_by_sham=by_sham, damage_outcomes=damage_outcomes, shuffle=shuffle,
        )

        positional_deviation = (
            abs(positional["rate"] - 0.5) if positional.get("rate") is not None else None
        )
        pilot_gate = {
            "ledger_usd": ledger["equivalent_usd"],
            "estimate_usd": stage_plan["estimated_usd"],
            "ledger_within_2x": ledger["equivalent_usd"] <= 2 * stage_plan["estimated_usd"],
            "void_positional": (
                positional_deviation is not None and positional_deviation >= largest_true
                and bool(primary_outcomes)
            ),
            "void_sham": dual["sham"]["floor"] >= largest_true and bool(primary_outcomes),
            "void_sham_amended": (
                dual["sham_amended"]["floor"] >= largest_true and bool(primary_outcomes)
            ),
            "shuffle_clear_share": shuffle.get("clear_share"),
            "aborted_at_ceiling": aborted,
        }

        surface_agg = analysis.aggregate_by_pair(to_member_space(votes["surface"]),
                                                 reward_ids)
        p_agg = analysis.aggregate_by_pair(to_member_space(votes["P"]), reward_ids)
        result = {
            "stage": args.stage,
            "plan": stage_plan,
            "registration": registration_digests(pairs_path),
            "probe": {"books": len(needed), "recognised": recognised,
                      "unprobed": unprobed, "skipped_pairs": skipped_pairs},
            "votes": {arm: len(v) for arm, v in votes.items()},
            # The under-run census: what the plan asked for, beside what came back, beside the
            # transport's own count of calls that never landed. The 2026-08-30 pilot reported
            # `votes` alone, so an arm that bought 20 of its 400 planned sessions read as a
            # completed arm and the shortfall had to be reconstructed from the raw cache. Any
            # gap between `planned` and `votes_returned` is a hole in the arm, whatever opened
            # it, and it is now on the face of the result file.
            "under_run": {
                "planned": planned_sessions,
                "votes_returned": {arm: len(v) for arm, v in votes.items()},
                "degenerate_stimuli": degenerate_stimuli,
                "transport_failures": getattr(elicitor, "transport_failures", None),
                "failure_reasons": dict(getattr(elicitor, "failure_reasons", {}) or {}),
            },
            "primary": {"aggregate": primary_agg, "outcomes": primary_outcomes,
                        "largest_true_effect": largest_true,
                        # The continuation check, descriptive: stage (c) was ordered after
                        # the pilot showed 15/19, which tilts the pooled estimate's null.
                        # The fresh-pairs-only accuracy stands beside the pooled figure so
                        # agreement kills the objection on contact and divergence is seen.
                        "fresh_only": _fresh_only(primary_agg, pool, args.stage)},
            "p_arm": {"aggregate": p_agg},
            "surface": {"aggregate": surface_agg},
            "positional": positional,
            "damage_outcomes": damage_outcomes,
            "shuffle": shuffle,
            # sham, sham_amended, verdict_registered, verdict_amended, amendment
            **dual,
            "control_stage_salt": {
                arm: control_stage_salt(args.stage, arm)
                for arm in ("C", "P", "sham", "damage", "surface")
            },
            "pilot_gate": pilot_gate,
            "ledger": ledger,
            "spend": elicitor.spend() if hasattr(elicitor, "spend") else {},
        }
        write_result(result, out_path)
        print(json.dumps({"stage": args.stage, "out": str(out_path),
                          "ledger_usd": ledger["equivalent_usd"],
                          "verdict_registered": dual["verdict_registered"].get("verdict"),
                          "verdict_amended": dual["verdict_amended"].get("verdict"),
                          "under_run": result["under_run"],
                          "pilot_gate": pilot_gate}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
