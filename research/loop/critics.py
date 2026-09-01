"""The rejection-optimized critic roster: agents paid in verified kills, and the code that
decides which of their claims were verified.

The direction's amendment asked for competent adversarial agents whose only success metric is
rejection. The danger in that instruction is the obvious one — an agent told to find fault
finds fault, every time, at any length — and this repository already has the rule that answers
it: **agent prose is not evidence.** So the roster is built so that a critic's prose can do
nothing on its own. A claim arrives in a fixed schema, anchored to a span the critic must
quote exactly, and then:

* a claim with no verbatim span **evaporates in the parser** — structurally uncashable, gone
  before anything reads it;
* a claim that says a counter will find the thing it names has that counter run over that span,
  and **an empty counter refutes the claim and is recorded against the critic**;
* a claim that quotes furniture to make a claim about prose is refuted as mis-cited;
* what is left is either a citation established in code (the span is real, the family is on the
  operator's recorded taxonomy) or a line for the coordinator's gate to read.

The asymmetry between those last two is stated rather than smoothed over. A mechanical
verification demonstrates the defect. A taxonomy verification demonstrates only that the critic
quoted the real chapter and named a real family — **it is a citation, not a finding** — and the
coordinator's gate read is what turns it into a rejection. `BLOCKING_STATUSES` names what the
binding rule treats as a kill, and it is the coordinator who applies that rule: this module
reports, and writes nowhere except its own roster file.

Containment, restated in code rather than only in a comment:

* no critic prose reaches generation — the runner returns a record and its only write is the
  roster tally file, which no writer, planner or reviser reads;
* no field here is named score or verdict, and a critic has no way to express approval;
* nothing in this module is importable from `src/litharness`, and no corpus is read;
* the transport is the caller's `elicit.Elicitor`, which already carries the §109 CLI hardening
  flags — this module never constructs one and never spends by itself.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

HERE = Path(__file__).resolve().parent
_QM = HERE.parent / "quality-measurement"
for _path in (str(_QM), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import critic_prompts as prompts  # noqa: E402  # sibling research module, imported by path
import measures_adapter as ma  # noqa: E402  # sibling research module, imported by path
import number_context  # noqa: E402  # sibling research module, imported by path
import progression_cadence  # noqa: E402  # sibling research module, imported by path
import register_census  # noqa: E402  # sibling research module, imported by path


@dataclass(frozen=True, slots=True)
class Critic:
    """One lens. `families` is the menu this critic may claim from and nothing wider."""

    critic_id: str
    lens: str
    lens_note: str
    families: tuple[str, ...]


#: The roster: five lenses drawn from the read-recurrence map's family groups, each given the
#: families of one group and no others. The partition is the point — a critic that may claim
#: anything produces a scattergun whose hit rate says nothing about the lens — and the lens
#: notes are ours, written from the map's own gloss, never from anything an operator said.
ROSTER: tuple[Critic, ...] = (
    Critic(
        critic_id="sentence-fabric",
        lens="the sentence",
        lens_note=(
            "you read for how clauses are built and joined, and for punctuation that fails the "
            "sentence it is in. You do not care what happens in the chapter."
        ),
        families=("D1", "D2", "D4", "E1", "E2", "E3"),
    ),
    Critic(
        critic_id="spoonfeed-implication",
        lens="what the prose refuses to leave implied",
        lens_note=(
            "you read for the moment the text stops trusting the reader: an inference narrated "
            "out, a manner supplied by a generic gloss, a thing defined by what it is not."
        ),
        families=("G1", "G2", "G3", "C3", "C5"),
    ),
    Critic(
        critic_id="diegesis-integrity",
        lens="whether the game system belongs to the world",
        lens_note=(
            "you read for a system the characters live inside rather than one printed beside "
            "them, and for numbers that count something that matters."
        ),
        families=("A1", "A2", "A3", "A4", "L1", "M1"),
    ),
    Critic(
        critic_id="premise-freshness",
        lens="whether this premise is anyone's but the genre's",
        lens_note=(
            "you read the opening for a hook that belongs to this book and a protagonist with "
            "an exception of their own, against everything the genre already ships."
        ),
        families=("B1", "B2", "B3", "B4", "B5", "B6"),
    ),
    Critic(
        critic_id="popcorn-momentum",
        lens="the reader's attention, minute by minute",
        lens_note=(
            "you read for where a reader would put the chapter down: detail that pays nothing, "
            "a page where nothing advances, a cast too large to hold, an offer skimped."
        ),
        families=("C1", "C2", "C4", "H1", "J1", "J2", "K1", "F1", "I1"),
    ),
)

#: Words below which a span cannot carry a claim. A two-word span matches half the chapter and
#: proves nothing; the prompt asks for a clause or a sentence and this is where that is enforced.
MIN_SPAN_WORDS = 4

#: Families for which a span lying entirely on furniture lines is a MIS-CITATION: they are
#: claims about prose, and a status block is not prose. The system and presentation families
#: (A4, L1, M1) are deliberately absent — quoting furniture is exactly how those are shown.
PROSE_FAMILIES: frozenset[str] = frozenset(
    {"D1", "D2", "D4", "E1", "E2", "E3", "F1", "G1", "G2", "C1", "C3", "C5", "I1"}
)

_WS = re.compile(r"\s+")
_AND_CHAIN = re.compile(r",?\s+and\s+", re.IGNORECASE)


def _flat(text: str) -> str:
    """Whitespace collapsed, nothing else touched.

    Deliberately NOT a character fold. `normalise` in the instrument modules folds the em dash
    to a hyphen, and folding it here would erase the evidence for the one family whose whole
    subject is the em dash. Line wrapping is the only difference a quoting model reliably
    introduces, so it is the only difference forgiven.
    """
    return _WS.sub(" ", text).strip()


# ------------------------------------------------------------------------------ span counters


def _and_chains(span: str) -> int:
    return len(_AND_CHAIN.findall(span))


def _em_dashes(span: str) -> int:
    return span.count("—")


def _gloss(span: str) -> int:
    counts = register_census.gloss_counts(span)
    return int(counts.get("tier_a", 0)) + int(counts.get("tier_b", 0))


def _system_mentions(span: str) -> int:
    return number_context.measure(span, version=ma.MEASURE_VERSION).system_any


def _furniture_lines(span: str) -> int:
    return sum(progression_cadence.furniture_mask(span, version=ma.MEASURE_VERSION))


def _proper_nouns(span: str) -> int:
    return len(register_census.proper_nouns(span))


#: Family -> the counter a "mechanical" claim on that family is checked against. A family that
#: is not here has no counter, and a mechanical claim on it comes back `unverified:no-counter`
#: rather than being waved through: an unbacked mechanical claim must not be cheaper than a
#: backed one.
SPAN_COUNTERS: dict[str, Any] = {
    "D1": _and_chains,
    "D4": _em_dashes,
    "G1": _gloss,
    "A1": _system_mentions,
    "A3": _system_mentions,
    "A4": _furniture_lines,
    "M1": _furniture_lines,
    "C4": _proper_nouns,
}

#: Every status a claim can end in. Two are assigned in the parser, the rest in verification.
STATUSES: tuple[str, ...] = (
    "dropped:no-verbatim-span",
    "dropped:span-too-short",
    "refuted:off-map",
    "refuted:miscited-furniture",
    "refuted:counter-empty",
    "unverified:no-counter",
    "verified:mechanical",
    "verified:taxonomy",
    "gate-read",
)

#: What the direction note's binding rule treats as a verified kill. **The two are not equal
#: evidence and the report keeps them apart.** `verified:mechanical` is a demonstration: a
#: counter found the named thing in the quoted span. `verified:taxonomy` is a citation: the
#: span is really in the chapter and the family is really on the operator's recorded taxonomy,
#: which is what the amendment allows a claim to cash out as — it establishes that the critic
#: is talking about this chapter, and not that the defect is present. Blocking is applied by
#: the coordinator, never here.
BLOCKING_STATUSES: tuple[str, ...] = ("verified:mechanical", "verified:taxonomy")


@dataclass(frozen=True, slots=True)
class Claim:
    """One parsed claim, before verification."""

    family: str
    span_text: str
    location: str
    claim: str
    cashable_as: str


@dataclass(frozen=True, slots=True)
class Judged:
    """One claim with what the code could establish about it, and the number behind it."""

    critic_id: str
    chapter_id: str
    family: str
    span_text: str
    location: str
    claim: str
    cashable_as: str
    status: str
    counter: str = ""
    counter_value: int | None = None
    note: str = ""

    @property
    def blocking(self) -> bool:
        return self.status in BLOCKING_STATUSES


# ------------------------------------------------------------------------------------ parsing


def parse_claims(raw: str, critic: Critic) -> tuple[list[Claim], list[dict[str, Any]]]:
    """Claims out of one critic's raw answer, plus a record of everything discarded.

    Malformed JSON, a non-object, a missing `claims` list: all yield no claims and one
    discard record. Individual entries are dropped for a missing field, a family outside this
    critic's own menu, or a `cashable_as` outside the closed set. Nothing is repaired and
    nothing defaults — a claim missing its span is exactly the claim this design is built to
    let evaporate, and a helpful default would resurrect it.
    """
    drops: list[dict[str, Any]] = []
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [], [{"reason": "unparseable-json", "critic_id": critic.critic_id}]
    if not isinstance(parsed, dict) or not isinstance(parsed.get("claims"), list):
        return [], [{"reason": "no-claims-list", "critic_id": critic.critic_id}]

    claims: list[Claim] = []
    for index, entry in enumerate(parsed["claims"][: prompts.MAX_CLAIMS]):
        if not isinstance(entry, dict):
            drops.append({"reason": "claim-not-an-object", "index": index})
            continue
        span = entry.get("quote_span")
        family = entry.get("family")
        claim_text = entry.get("claim")
        cashable = entry.get("cashable_as")
        if not isinstance(span, dict) or not isinstance(span.get("text"), str):
            drops.append({"reason": "no-span", "index": index, "family": family})
            continue
        if family not in critic.families:
            drops.append({"reason": "family-outside-lens", "index": index, "family": family})
            continue
        if cashable not in prompts.CASHABLE:
            drops.append({"reason": "cashable-outside-set", "index": index, "family": family})
            continue
        if not isinstance(claim_text, str) or not claim_text.strip():
            drops.append({"reason": "no-claim-sentence", "index": index, "family": family})
            continue
        claims.append(
            Claim(
                family=family,
                span_text=span["text"],
                location=str(span.get("location", "")),
                claim=claim_text.strip(),
                cashable_as=cashable,
            )
        )
    return claims, drops


# ------------------------------------------------------------------------------- verification


def verify(claim: Claim, chapter: str, *, critic_id: str, chapter_id: str) -> Judged:
    """What the code can establish about one claim. Never an opinion about the claim.

    Order matters and is the design: the span must be in the chapter before anything else is
    asked, because every later question is about the span. A span that is not there does not
    get a family check or a counter — it is gone.
    """
    def judged(status: str, **extra: Any) -> Judged:
        return Judged(
            critic_id=critic_id, chapter_id=chapter_id, family=claim.family,
            span_text=claim.span_text, location=claim.location, claim=claim.claim,
            cashable_as=claim.cashable_as, status=status, **extra,
        )

    span = claim.span_text
    if _flat(span) not in _flat(chapter):
        return judged("dropped:no-verbatim-span", note="span is not in the chapter")
    if len(span.split()) < MIN_SPAN_WORDS:
        return judged(
            "dropped:span-too-short",
            note=f"span is {len(span.split())} words, under MIN_SPAN_WORDS={MIN_SPAN_WORDS}",
        )
    if claim.family not in prompts.FAMILIES:
        return judged("refuted:off-map", note="family is not on the recurrence map")
    if claim.family in PROSE_FAMILIES and span.strip() and _furniture_lines(span) == len(
        [line for line in span.splitlines() if line.strip()]
    ):
        return judged(
            "refuted:miscited-furniture",
            note="a claim about prose, quoting only furniture lines",
        )

    if claim.cashable_as == "mechanical":
        counter = SPAN_COUNTERS.get(claim.family)
        if counter is None:
            return judged(
                "unverified:no-counter",
                note=f"no span counter exists for family {claim.family}",
            )
        value = int(counter(span))
        status = "verified:mechanical" if value > 0 else "refuted:counter-empty"
        return judged(status, counter=counter.__name__, counter_value=value)
    if claim.cashable_as == "taxonomy-item":
        return judged(
            "verified:taxonomy",
            note="span is verbatim and the family is on the map; the defect itself is not shown",
        )
    return judged("gate-read", note="a line citation for the coordinator's gate to read")


# ---------------------------------------------------------------------------------- the runner


class Asker(Protocol):
    """`elicit.Elicitor.ask_raw`'s seam. The runner never constructs a transport."""

    def ask_raw(
        self, system: str, turns: list[dict[str, Any]], *, schema: dict[str, object] | None,
        max_tokens: int, tag: dict[str, Any], sample: int = 0, model: str | None = None,
    ) -> dict[str, Any]: ...


def sample_index(critic_id: str, chapter_id: str) -> int:
    """A stable per-cell integer, folded the way `arms._sample_index` folds its cell.

    In the replay cache key beside the request digest, so two critics reading the same chapter
    cannot collapse into one cached answer.
    """
    payload = "\x00".join((prompts.ROSTER_VERSION, critic_id, chapter_id))
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


@dataclass(frozen=True, slots=True)
class CriticReport:
    """One run of the roster over one variant's chapters."""

    variant: str
    roster_version: str
    judged: tuple[Judged, ...]
    drops: tuple[dict[str, Any], ...]
    transport_failures: int = 0

    @property
    def blocking(self) -> tuple[Judged, ...]:
        return tuple(item for item in self.judged if item.blocking)

    def split(self) -> dict[str, int]:
        """How many claims ended in each status. Every status appears, including the zeros."""
        counts = dict.fromkeys(STATUSES, 0)
        for item in self.judged:
            counts[item.status] = counts.get(item.status, 0) + 1
        return counts

    def per_critic(self) -> dict[str, dict[str, int]]:
        """Per critic: claims made, and how many ended in each status."""
        out: dict[str, dict[str, int]] = {}
        for critic in ROSTER:
            mine = [item for item in self.judged if item.critic_id == critic.critic_id]
            counts = dict.fromkeys(STATUSES, 0)
            for item in mine:
                counts[item.status] = counts.get(item.status, 0) + 1
            out[critic.critic_id] = {"claims": len(mine), **counts}
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "roster_version": self.roster_version,
            "transport_failures": self.transport_failures,
            "split": self.split(),
            "per_critic": self.per_critic(),
            "blocking_statuses": list(BLOCKING_STATUSES),
            "claims": [asdict(item) for item in self.judged],
            "drops": list(self.drops),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def table(self) -> str:
        """One line per critic: claims made and where they ended."""
        rows = self.per_critic()
        width = max(len(name) for name in rows)
        lines = [f"{'critic'.ljust(width)}  claims  mech  taxon  refuted  dropped  gate"]
        for name, counts in rows.items():
            refuted = sum(v for k, v in counts.items() if k.startswith("refuted:"))
            dropped = sum(v for k, v in counts.items() if k.startswith("dropped:"))
            lines.append(
                f"{name.ljust(width)}  {counts['claims']:>6}  "
                f"{counts['verified:mechanical']:>4}  {counts['verified:taxonomy']:>5}  "
                f"{refuted:>7}  {dropped:>7}  {counts['gate-read']:>4}"
            )
        return "\n".join(lines)


def run_critics(
    variant: str,
    chapters: Sequence[tuple[str, str]],
    asker: Asker,
    *,
    roster: Sequence[Critic] = ROSTER,
    max_claims: int = prompts.MAX_CLAIMS,
) -> CriticReport:
    """Every critic against every chapter, parsed and verified. One call per cell.

    `chapters` is (chapter_id, text) pairs — the ids are the caller's, and they travel onto
    every claim so a blocking finding can be pointed at a line without consulting run state.

    A cell whose transport returned nothing is counted, not guessed at: `transport_failures`
    rides out on the report exactly as it does on the `Elicitor`, because a roster that reports
    no kills beside a non-zero failure count is reporting on the cells that answered.
    """
    judged: list[Judged] = []
    drops: list[dict[str, Any]] = []
    failures = 0
    for critic in roster:
        system = prompts.system_for(critic.lens, critic.lens_note, critic.families)
        for chapter_id, text in chapters:
            record = asker.ask_raw(
                system,
                [{"role": "user", "content": prompts.task_for(chapter_id, text, max_claims)}],
                schema=prompts.CLAIM_SCHEMA,
                max_tokens=prompts.MAX_TOKENS,
                tag={
                    "roster_version": prompts.ROSTER_VERSION,
                    "critic_id": critic.critic_id,
                    "chapter_id": chapter_id,
                    "variant": variant,
                },
                sample=sample_index(critic.critic_id, chapter_id),
            )
            raw = str(record.get("text") or "")
            if not raw or record.get("refused"):
                failures += 1
                drops.append({
                    "reason": "no-answer", "critic_id": critic.critic_id,
                    "chapter_id": chapter_id,
                })
                continue
            claims, parse_drops = parse_claims(raw, critic)
            for drop in parse_drops:
                drops.append({**drop, "critic_id": critic.critic_id, "chapter_id": chapter_id})
            judged.extend(
                verify(claim, text, critic_id=critic.critic_id, chapter_id=chapter_id)
                for claim in claims
            )
    return CriticReport(
        variant=variant, roster_version=prompts.ROSTER_VERSION,
        judged=tuple(judged), drops=tuple(drops), transport_failures=failures,
    )


# ------------------------------------------------------------------------------- the tally file


def load_tally(path: Path) -> dict[str, Any]:
    """The roster file, or a fresh one. A file from another roster version is not pooled.

    Refusing to pool is the whole reason the version is in the file: a critic's record of
    verified kills is a record of a specific prompt's performance, and carrying it across a
    reworded prompt would credit one instrument with another's finds.
    """
    if not path.is_file():
        return {"roster_version": prompts.ROSTER_VERSION, "runs": 0, "critics": {}}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if loaded.get("roster_version") != prompts.ROSTER_VERSION:
        raise ValueError(
            f"roster file {path} was written under {loaded.get('roster_version')!r}, but this "
            f"roster is {prompts.ROSTER_VERSION!r}; tallies from two prompt versions are not "
            "one critic's record and are not pooled"
        )
    return loaded


def record_run(path: Path, report: CriticReport) -> dict[str, Any]:
    """Fold one report into the roster file and write it back. The only write this module makes.

    This is the "optimize for rejection" pressure the direction asked for, kept as bookkeeping:
    a per-critic running count of what its claims cashed out as. Nothing trains on it, nothing
    selects on it, and no prompt reads it — a critic whose kills dry up is a question for
    whoever next revises the roster, not an input to anything automatic.
    """
    tally = load_tally(path)
    tally["runs"] = int(tally.get("runs", 0)) + 1
    critics = tally.setdefault("critics", {})
    for critic_id, counts in report.per_critic().items():
        entry = critics.setdefault(
            critic_id, {"claims": 0, **dict.fromkeys(STATUSES, 0), "runs": 0}
        )
        entry["runs"] = int(entry.get("runs", 0)) + 1
        for key, value in counts.items():
            entry[key] = int(entry.get(key, 0)) + int(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tally, indent=2) + "\n", encoding="utf-8", newline="\n")
    return tally
