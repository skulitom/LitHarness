"""How much of a forged world is ever named on the page, and who named it first.

Serial Pilot 2 ran a book on a **329-record world**: 7 rules, 21 consequences across eight
domains of life, 27 entities with roles, 2 criteria with their ladders, 42 declared
manifestations, 28 claims of which 20 are hidden at scene one. All of it reached the writer —
a flat 229-231 established facts per drafting prompt, `context_omitted = 0` for the whole book.
What the prose did with it was read rather than counted: *the ladder appears as two spoken
dates, the doctrine is never explained, the bestiary shows up as one clause about moths*
(`plan/serial-pilot-2.md` §6.1). That is an observation. This is the counter.

**Naming-uptake is the only thing this reads, and every number is labelled so.** A coined noun
on the page is not the fact being *used* — pilot 2's S2 lesson, and the reason
`tools/serial_pilot_check.py`'s disclosure block is a note and never a check. Absence of a name
is not absence of honouring: the hidden section is *supposed* to go unnamed, so hidden claims
are reported in their own row and their silence is never a defect. Nothing here may be read as
"the world should be named more"; a counter that becomes the target is the
shallow-because-easy failure the project refuses.

**Two controls, and they were built before the census was read.**

*Control A, the wrong-world sham.* The same name sets, counted against twenty-one books that
never saw this world (`exports/fitness/`, no forged world, same genre). Expected near zero. It
will not be near zero on the wide leg, and that is known in advance rather than discovered:
*First In Time* coined `call`, `date`, `year`, `time`, `first`, `gate`, `table`, `river`,
`flat` and `draw`, and one of its manifestations is literally "a column headed NEVER". So two
name-set legs are registered **before the first count**, not one and then a repair:

- `wide` — the plan's rule, and `domain/worlds.py::key_nouns`' rule applied per subject: the
  subject's own id parts plus the inner-capital words of its own name-bearing records.
- `coined` — `wide` minus every token the genre shelf already owns, where "owns" is document
  frequency in the cached RoyalRoad corpus at a declared floor. The reference corpus is
  **not** the sham corpus, so the sham can still fail after narrowing; a narrowing defined by
  the control it is meant to survive would be a control that cannot fire.

Registering both legs is the §107.9.1 defect-6 discipline taken one step further. Fixing a
counter after seeing its answer is the failure `platform_priors.py` freezes its matchers to
avoid; declaring both answers first means there is nothing to fix and both stay on the record.

*Control B, the premise baseline.* The planner and the writer both saw the premise, and the
premise is derived from the world and carries its proper nouns. So the reading that matters is
**world-beyond-premise uptake**: what the 329 records put on the page that the premise's
paragraph did not already carry. Without this, "the world reached the page" and "the premise
reached the page" are the same number wearing two names.

**No bar.** Distributions, per run, with the sham beside them. The only outcome here that can
fail is the sham itself: a counter whose sham fires above its declared floor on the `coined`
leg is dead as built, and nothing else from it is reported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import statistics
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RESULTS = HERE / "results"

#: The gitignored derived-text root `corpus_leak_audit.DERIVED_TEXT_ROOTS` exists for, and the
#: same argument `world_lexicon.py` makes: a document-frequency table over 1.6M third-party
#: chapters is derived text and is not committed. What *is* committed is
#: `world-uptake-lexicon.json` — the frequencies of **our own worlds' name tokens only**, which
#: is a report about our worlds rather than a reproduction of anyone's prose.
DERIVED = HERE / "derived"
LEXICON_JSON = HERE / "world-uptake-lexicon.json"

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

if TYPE_CHECKING:  # pragma: no cover
    import litharness_contracts as lc

#: **Two venvs, and the import is guarded rather than assumed** — the pattern
#: `world_lexicon.py` established and had to state twice. One venv has `pyarrow` and can read
#: the RoyalRoad shelf; the other is this repository and can build a world. Neither has both,
#: so `--build-lexicon` runs under the first with `litharness` absent and every other leg runs
#: under `uv run` with it present. Anything that touches a world checks `require_worlds()`
#: first, so the failure is a sentence rather than a traceback at import time.
try:
    import litharness_contracts as lc

    from litharness.application import architect
    from litharness.domain import worlds

    _WORLDS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - exercised only under the pyarrow venv
    _WORLDS_AVAILABLE = False


def require_worlds() -> None:
    """Refuse, in one sentence, rather than fail at import time under the wrong venv."""
    if not _WORLDS_AVAILABLE:
        raise SystemExit(
            "this leg needs `litharness` and `litharness_contracts` importable; run it under "
            "`uv run` from the repository rather than under the venv that has pyarrow"
        )

# ============================================================================ the instrument
#
# Everything between this banner and the next is **byte-frozen before the first census** and
# covered by `registration_digest()`, which `--selftest` compares against `FROZEN_DIGEST`.
# A reworded matcher is a different instrument with no evidence behind it.

#: Connective and structural words inside a snake_case id that name nothing. **Restated from
#: `domain/worlds.py` rather than imported**, because that constant is private to the shipped
#: counter and this is research code that must be free to disagree with it — the argument
#: `corpus_io.era_cohort` makes for duplicating itself. `--selftest` asserts the two agree on
#: the pilot world, so a disagreement is a finding rather than a silent drift.
_ID_NOISE = frozenset({"the", "and", "for", "of", "house", "a", "an", "to", "in", "on"})

#: A capitalised word that is not the first word of a sentence. Byte-identical to
#: `domain/worlds.py::_INNER_CAPITAL`; see `_ID_NOISE` for why it is restated.
_INNER_CAPITAL = re.compile(r"(?<![.!?]\s)(?<!^)(?<![.!?]\s\s)\b([A-Z][A-Za-z'-]{2,})\b")

#: Predicates whose value is prose a world coined names inside. **Restated as literals rather
#: than read off `domain/worlds.py`**, for the reason `_ID_NOISE` gives and one more: the
#: lexicon leg runs under a venv where `litharness` is not importable, and a frozen constant
#: that cannot be evaluated there is a freeze that only holds on one machine. `--selftest`
#: asserts these are still the shipped module's three.
_NAME_BEARING = frozenset({"world_rule", "is_a", "manifests_as"})

#: Id suffixes `application/architect.py` mints itself when it reifies a world's JSON —
#: `f"{subject}_secret"`, `f"{system_id}_nature"`, `f"{subject}_belief"`, `f"{system_id}_view"`,
#: `f"{claim_id}_reveal"`, `f"{bond_id}_joint"`. **They are the record pattern's vocabulary and
#: not the world's**, and leaving them in would make every one of the ten `*_secret` claims
#: "named" by the word *secret* appearing anywhere in 7,812 words. Dropped from the id side of
#: a name set only, and only when trailing.
_MINTED_SUFFIXES = frozenset({"secret", "nature", "belief", "view", "reveal", "joint"})

#: One word of running text, for the premise baseline, the reference corpus and every naming
#: test. Letters only, so an apostrophe or a hyphen is a boundary — *watermaster's* yields
#: `watermaster` and *gate-moth* yields `gate` and `moth`. That is what "whole word" has to
#: mean for a counter whose name sets are snake_case id parts, and it is the difference between
#: a hyphenated coinage being found and being invisible.
_TOKEN = re.compile(r"[^\W\d_]+")

#: The kinds a declared feature comes in. Closed, and each one is a row in the census.
FEATURE_KINDS: tuple[str, ...] = (
    "entity",
    "rule",
    "consequence",
    "criterion",
    "rank",
    "manifestation",
    "claim",
)

#: How many distinct RoyalRoad fictions a token must appear in before the shelf owns it and the
#: `coined` leg drops it. **Five, restated from `world_lexicon.py::DEFAULT_FLOOR` with its
#: reason**: at a floor of one a single author's invented noun joins the lexicon and every later
#: world that coined the same word reads as derivative; at a high floor the lexicon collapses to
#: English. It is a placed number, stated as placed, and the census reports the same figures at
#: floors 1, 5, 25 and 100 so the choice is visible rather than load-bearing.
ORDINARY_FLOOR = 5

#: Floors the sensitivity table reports beside the headline.
SENSITIVITY_FLOORS: tuple[int, ...] = (1, 5, 25, 100)

#: The sham's own floor, and the only pass/fail quantity in this module. **A share, in
#: [0, 1], and it must be read as "the share of a world's declared features that a book which
#: never saw that world names anyway".** Direction: lower is a live counter. The number is
#: placed rather than measured — nothing has ever measured this quantity — so it is declared
#: with its arithmetic rather than with a citation: at 0.05 a 135-feature world may collide
#: with an unrelated book on at most six features before the counter is reporting the English
#: language instead of the world. The wide leg is *expected* to fail it; the `coined` leg is
#: the one whose failure would kill the instrument.
SHAM_CEILING = 0.05

PRE_REGISTRATION: dict[str, Any] = {
    "written": (
        "2026-08-22, before the first census was read and before any world-aware planner "
        "call existed, and byte-frozen with the matchers, the feature kinds, the id-noise "
        "and minted-suffix sets, the ordinary-word floor and the sham ceiling under "
        "FROZEN_DIGEST"
    ),
    "question": (
        "Of everything a forged world declares, how much is ever named in the prose of the "
        "book written on it; and of what is named, how much the scene plan named first and "
        "how much the writer improvised against a plan that had never been told the world."
    ),
    "what_is_measured": (
        "Naming uptake and nothing else. A feature is named in a text when a member of its "
        "name set appears there as a whole word, case-folded. This is not use, not honouring, "
        "not quality, and not reader effect. A world can be honoured everywhere and named "
        "nowhere -- the hidden section is required to be exactly that -- so a low number is "
        "not a defect and this module never says it is."
    ),
    "unit_of_analysis": (
        "One declared feature of one world, crossed with one scene of one run. Features are "
        "enumerated from the records: every subject carrying an entity_role, every world_rule "
        "subject, every consequence record, every criterion, every rank endpoint of a "
        "precedes edge, every manifests_as record, and every claim.content subject."
    ),
    "counting_rule": (
        "Whole-word, case-folded, no stemming and no inflection. 'gate' does not match "
        "'gates'. The error is in the safe direction for the census (it lowers uptake, which "
        "makes the finding harder to obtain rather than easier) and it moves the sham the same "
        "way, so the comparison between them is unaffected."
    ),
    "name_set_legs": {
        "wide": (
            "The handoff's rule and domain/worlds.py::key_nouns' rule applied per subject: the "
            "feature subject's own id parts (split on underscore, longer than three "
            "characters, minus _ID_NOISE, minus a trailing suffix architect.records_for "
            "minted) union the inner-capital words of that feature's own name-bearing records."
        ),
        "coined": (
            "wide minus every token the RoyalRoad shelf already owns at ORDINARY_FLOOR "
            "distinct fictions. Declared before the first count, not adopted after the sham "
            "fired: both legs are reported for every figure in this module, always."
        ),
    },
    "controls": {
        "A_wrong_world_sham": (
            "The same name sets counted against the twenty-one fitness books in "
            "exports/fitness/, which were written with no forged world in the same genre. "
            "Reported per book and pooled. The coined leg's pooled share is the one quantity "
            "here that can fail: above SHAM_CEILING the counter is reading the language rather "
            "than the world and nothing else from it is reported."
        ),
        "B_premise_baseline": (
            "Every whole word of the book's premise, case-folded, is the premise token set. A "
            "feature is named-beyond-premise when a token in (name set minus premise tokens) "
            "appears. Both the raw and the beyond-premise figures are reported; the "
            "beyond-premise one is the reading that means 'the 329 records reached the page'."
        ),
    },
    "declared_quantities": {
        "ever_named": (
            "Share of declared features named in the prose of any scene. Range [0, 1], unit "
            "share of features, no direction and no bar -- it is the ruler."
        ),
        "first_named_scene": (
            "The lowest scene ordinal whose prose names a feature, or null. Range [1, scenes]."
        ),
        "plan_first": (
            "Of the features named in prose, the share also named in the plan statement of "
            "some scene at or before their first prose scene. Range [0, 1]. This is the number "
            "the whole direction turns on and it has no bar either: it separates 'the plan "
            "carried the world' from 'the writer improvised against a blind plan', and which "
            "of those is better is not a question this module may answer."
        ),
        "packet_facts_never_named": (
            "Share of the established-fact lines in the frozen scene-one drafting prompt whose "
            "own words never appear in the book. Range [0, 1]. A different denominator from "
            "ever_named and reported as such."
        ),
        "sham_share": (
            "Pooled share of features named across the twenty-one wrong-world books. Range "
            "[0, 1], direction lower-is-live, ceiling SHAM_CEILING on the coined leg only."
        ),
    },
    "hidden_claims": (
        "Reported in their own row and never pooled with the rest. A hidden claim going "
        "unnamed is the design working. A hidden claim being named is not evidence of a leak "
        "either -- pilot 2 settled that a coined name on the page is not the secret being "
        "told -- so that row is a note in both directions."
    ),
    "run_a_is_a_different_condition": (
        "Run A had five of six answers handed over as established fact from scene one "
        "(stage-0 107.9.1 defect 10). It is reported separately and labelled, never pooled "
        "with run B."
    ),
    "attainability": (
        "Every quantity is a share of a non-empty finite set computed from records that exist "
        "on disk: the pilot world has 135 declared features, the books have eight scenes each, "
        "the sham corpus has twenty-one books. Nothing here can be empty by construction, and "
        "the one declared ceiling is on a quantity whose wide leg is expected to breach it."
    ),
    "no_bar_for_admission": (
        "None. Nothing here enters an axis, a counter registry, a prompt, a directive or a "
        "writer dossier. This is a distribution report and the sham is its own falsifier."
    ),
    "corrections": [
        {
            "when": "2026-08-22, after the first census of run B and before anything was read "
            "from it",
            "digest_before": "69ffc6a2b0917f1bec68",
            "what_was_wrong": (
                "This block declared the sham quantity twice and the two disagreed. "
                "SHAM_CEILING's own prose named a per-book share -- 'the share of a world's "
                "declared features that A BOOK which never saw that world names anyway' -- "
                "and declared_quantities.sham_share named the pooled union across all "
                "twenty-one books. The first implementation computed the union and compared "
                "it to the ceiling."
            ),
            "why_the_union_is_not_a_quantity_a_ceiling_can_sit_on": (
                "The union is not scale-free: it rises monotonically with the number of "
                "control books and reaches 1.0 for any non-zero per-book rate given enough "
                "of them. A ceiling on it is therefore a ceiling on the size of the control "
                "corpus rather than on the counter, which is the range-and-unit failure this "
                "project has recorded seven times. The per-book distribution is scale-free "
                "and is what the ceiling now reads."
            ),
            "what_changed": (
                "`sham` now reports median, maximum and pooled shares with a verdict against "
                "SHAM_CEILING for each, plus the share of control books naming nothing, and "
                "names the tokens that collided. SHAM_CEILING itself is unchanged at 0.05 and "
                "no figure was dropped: every number computed under the pre-correction digest "
                "is reported in research/quality-measurement/world-uptake.md beside its "
                "post-correction twin."
            ),
            "figures_computed_under_the_old_digest": (
                "run B, pooled union: wide 0.6667, coined 0.1837. Both are reported and "
                "neither is withdrawn."
            ),
        }
    ],
}


def digest(payload: object) -> str:
    """Stable digest of a payload. Sorted keys so dict order is never in the key."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def registration_digest() -> str:
    """Content address of everything inside the freeze banner.

    Printed on every artifact. A result file whose digest differs from the module's came from a
    different instrument, and the check is one comparison rather than a diff of prose.
    """
    return digest(
        {
            "pre_registration": PRE_REGISTRATION,
            "id_noise": sorted(_ID_NOISE),
            "inner_capital": _INNER_CAPITAL.pattern,
            "name_bearing": sorted(_NAME_BEARING),
            "minted_suffixes": sorted(_MINTED_SUFFIXES),
            "token": _TOKEN.pattern,
            "feature_kinds": list(FEATURE_KINDS),
            "ordinary_floor": ORDINARY_FLOOR,
            "sensitivity_floors": list(SENSITIVITY_FLOORS),
            "sham_ceiling": SHAM_CEILING,
        }
    )


#: The digest of the frozen block. `--selftest` fails on divergence, which is the whole
#: mechanism: every number in `world-uptake.md` is attributable to this exact string or it is
#: attributable to nothing.
#:
#: **It has moved once**, from `69ffc6a2b0917f1bec68` to this, and the move is recorded inside
#: the block it addresses rather than only here — `PRE_REGISTRATION["corrections"]` says what
#: was wrong, why, and which figures were computed under the old one. Nothing was withdrawn.
FROZEN_DIGEST = "cd79c3f56e21a1354e27"

# =========================================================================== end of the freeze


@dataclass(frozen=True, slots=True)
class Feature:
    """One thing a world declared, and the words that would put it on a page."""

    feature_id: str
    kind: str
    subject: str
    role: str | None
    hidden_at_start: bool
    wide: frozenset[str]

    def names(self, ordinary: frozenset[str], *, leg: str) -> frozenset[str]:
        return self.wide if leg == "wide" else frozenset(self.wide - ordinary)


def _id_tokens(subject: str) -> set[str]:
    """`key_nouns`' id rule, applied to one subject, minus the suffixes `records_for` mints."""
    parts = subject.split("_")
    while parts and parts[-1] in _MINTED_SUFFIXES:
        parts = parts[:-1]
    return {part.casefold() for part in parts if len(part) > 3 and part not in _ID_NOISE}


def _capitals(text: object) -> set[str]:
    """`key_nouns`' prose rule, applied to one value."""
    if not isinstance(text, str):
        return set()
    return {word.casefold() for word in _INNER_CAPITAL.findall(text)}


def _words(text: str) -> set[str]:
    """Every whole word of a text, case-folded. The one tokenisation this module uses."""
    return set(_TOKEN.findall(text.casefold()))


def features_of(records: Sequence[lc.StateRecord], *, scenes: int) -> tuple[Feature, ...]:
    """Every declared feature of a world, with its name set.

    The enumeration is the handoff's and it is deliberately wider than
    `domain/worlds.py::features`, which counts only what a reader must be able to *see* and
    excludes cast, places and institutions on purpose. This module is asking a different
    question — what of the world is ever named — and a cast member nobody names is exactly the
    kind of thing it exists to count.
    """
    require_worlds()
    by_subject: dict[str, list[lc.StateRecord]] = {}
    for record in records:
        by_subject.setdefault(record.subject, []).append(record)

    def subject_names(subject: str) -> frozenset[str]:
        names = _id_tokens(subject)
        for record in by_subject.get(subject, ()):
            if record.predicate in _NAME_BEARING:
                names |= _capitals(record.value)
        return frozenset(names)

    hidden = {
        record.subject
        for record in worlds.undisclosed_claims(
            records, at=architect.story_key(1, scenes=scenes)
        )
    }
    roles = worlds.entity_roles(records)
    found: list[Feature] = []

    def add(
        feature_id: str, kind: str, subject: str, names: frozenset[str], role: str | None
    ) -> None:
        found.append(
            Feature(
                feature_id=feature_id,
                kind=kind,
                subject=subject,
                role=role,
                hidden_at_start=subject in hidden,
                wide=names,
            )
        )

    for subject in sorted(roles):
        add(subject, "entity", subject, subject_names(subject), "|".join(roles[subject]))
    for subject in worlds.rules(records):
        add(subject, "rule", subject, subject_names(subject), None)
    for subject in sorted(worlds.criteria(records)):
        add(subject, "criterion", subject, subject_names(subject), None)
    ranks = {end for edge in worlds.rank_order(records) for end in edge}
    for subject in sorted(ranks):
        add(subject, "rank", subject, subject_names(subject), None)
    for subject in sorted(worlds.claims(records)):
        add(subject, "claim", subject, subject_names(subject), None)
    # Record-level features: a consequence and a manifestation have no id of their own, so the
    # name set is their subject's id parts plus whatever *this* record's prose coins. Two
    # consequences of one rule can therefore share a name set, and where they do the row is
    # saying no more than the rule's row does; that is a property of the world's vocabulary and
    # it is reported rather than repaired.
    for record in records:
        if record.predicate == worlds.CONSEQUENCE_PREDICATE and record.value:
            names = frozenset(_id_tokens(record.subject) | _capitals(record.value))
            add(record.record_id, "consequence", record.subject, names, record.object_ref)
        elif record.predicate == worlds.MANIFESTS_PREDICATE and record.value:
            names = frozenset(_id_tokens(record.subject) | _capitals(record.value))
            add(record.record_id, "manifestation", record.subject, names, None)
    return tuple(found)


def named(text: str, tokens: Iterable[str]) -> frozenset[str]:
    """Which of `tokens` appear in `text` as whole words, case-folded."""
    if not text:
        return frozenset()
    present = _words(text)
    return frozenset(token for token in tokens if token in present)


# --- substrate ------------------------------------------------------------------------------


def world_from_package(path: Path) -> tuple[architect.Candidate, tuple[lc.StateRecord, ...], str]:
    """The committed pilot world, rebuilt the way `tests/test_architect.py` rebuilds it."""
    require_worlds()
    package = json.loads(path.read_text(encoding="utf-8"))
    candidate = architect.Candidate(0, package["world"])
    return candidate, records_of(candidate), str(candidate.raw["premise"])


def world_from_forge(
    path: Path, index: int
) -> tuple[architect.Candidate, tuple[lc.StateRecord, ...], str]:
    """One candidate out of a forge bundle. `forge.json` keys its worlds under `candidates`."""
    require_worlds()
    forge = json.loads(path.read_text(encoding="utf-8"))
    entry = forge["candidates"][index]
    candidate = architect.Candidate(entry["index"], entry["world"])
    return candidate, records_of(candidate), str(candidate.raw["premise"])


def records_of(candidate: architect.Candidate, *, scenes: int = 8) -> tuple[lc.StateRecord, ...]:
    """`ACCEPTED_CANON` and the book's own scene count, both of which change the answer.

    At `PROPOSED` every canon-filtered reader in `domain/worlds.py` returns nothing; at the
    six-scene default the scene-seven reveal loses its position and the world says something
    else. Neither is a free parameter and neither has a safe default here.
    """
    return architect.records_for(
        candidate, authority=lc.StateAuthority.ACCEPTED_CANON, scenes=scenes
    )


#: The literal the packet's own renderer emits above the established facts, and the one below
#: them. `domain/context.py` writes both; matching on them rather than on a count is what keeps
#: this working when the fact count changes.
_FACTS_HEADER = "Established facts"
_HIDDEN_HEADER = "True, and the reader has not been told"


def packet_facts(prompt: str) -> tuple[str, ...]:
    """The established-fact lines of a frozen drafting prompt, in the order the writer saw them.

    Read off the stored prompt rather than reassembled from the records, because the prompt is
    what the writer was actually handed and the packet drops whatever the budget could not
    hold. On Serial Pilot 2 nothing was dropped -- `context_omitted` is 0 for the whole book --
    so on that substrate the two agree; on any book where they disagree the prompt is right.
    """
    start = prompt.find(_FACTS_HEADER)
    if start < 0:
        return ()
    end = prompt.find(_HIDDEN_HEADER, start)
    block = prompt[start : end if end > 0 else len(prompt)]
    return tuple(
        line[2:].strip()
        for line in block.splitlines()
        if line.startswith("- ") and line[2:].strip()
    )


def scenes_from_db(path: Path) -> list[dict[str, Any]]:
    """Per scene: the plan statement it was drafted against, its prose, and its frozen prompt.

    Three tables, because the three live in three places: the statement inside
    `plan_revisions.items_json` of the revision the job named, the prose in `node_versions` at
    the branch head, and the prompt in `jobs.payload`. Opened read-only -- a census must never
    be able to write to the run it is reading.
    """
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        jobs: dict[str, dict[str, Any]] = {}
        for row in connection.execute(
            "SELECT payload FROM jobs WHERE job_kind = 'scene_draft' AND payload IS NOT NULL"
        ):
            payload = json.loads(row["payload"])
            jobs[payload["logical_id"]] = payload
        cached: dict[str, list[dict[str, Any]]] = {}

        def plan_items(revision_id: str) -> list[dict[str, Any]]:
            if revision_id not in cached:
                found = connection.execute(
                    "SELECT items_json FROM plan_revisions WHERE plan_revision_id = ?",
                    (revision_id,),
                ).fetchone()
                cached[revision_id] = json.loads(found["items_json"]) if found else []
            return cached[revision_id]

        head = connection.execute("SELECT revision_id FROM branch_heads").fetchone()
        prose = {
            row["logical_id"]: row["content"]
            for row in connection.execute(
                "SELECT nv.logical_id, nv.content FROM revision_nodes rn "
                "JOIN node_versions nv ON nv.version_id = rn.version_id "
                "WHERE rn.revision_id = ? AND nv.kind = 'scene' AND nv.tombstoned = 0",
                (head["revision_id"],),
            )
        }
        out: list[dict[str, Any]] = []
        ordered = sorted(jobs.items(), key=lambda kv: kv[1]["selected_by"]["ordinal"])
        for logical_id, payload in ordered:
            items = plan_items(payload["plan_revision_id"])
            out.append(
                {
                    "logical_id": logical_id,
                    "ordinal": int(payload["selected_by"]["ordinal"]),
                    "scene_plan": statement_for(items, logical_id),
                    "prose": prose.get(logical_id) or "",
                    "prompt": payload.get("prompt") or "",
                }
            )
        return out
    finally:
        connection.close()


def statement_for(items: Sequence[Mapping[str, Any]], logical_id: str) -> str:
    """`domain/plans.py::scene_plan_for`'s rule against raw JSON: scope first, derived id second.

    Reimplemented rather than imported because the items are dicts out of a stored revision
    rather than `lc.PlanItem`s, and rehydrating a whole revision to read one string would make
    a read-only census depend on the contracts version the run was written under. The two runs
    already disagree about the id convention -- `scene-N-arithmetic` on run A,
    `scene-plan-N-<slug>` on run B, neither of them the derived `{logical_id}-plan` -- so the
    scope branch is the only one that works and the derived branch is the fallback it is in the
    shipped function.
    """
    for item in items:
        scope = item.get("scope")
        if (
            item.get("kind") == "scene_plan"
            and isinstance(scope, Mapping)
            and scope.get("logical_id") == logical_id
        ):
            return str(item.get("text") or "")
    derived = f"{logical_id}-plan"
    for item in items:
        if item.get("kind") == "scene_plan" and item.get("logical_id") == derived:
            return str(item.get("text") or "")
    return ""


def fitness_books(root: Path) -> list[tuple[str, str]]:
    """The wrong-world control corpus: books with no forged world behind them, same genre."""
    return [
        (path.stem, path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("fitness-*.md"))
    ]


# --- the census -----------------------------------------------------------------------------


def share(hit: int, total: int) -> float | None:
    """`None` for an empty denominator, never 0.0 -- the two are different readings."""
    return None if not total else round(hit / total, 4)


def census(
    features: Sequence[Feature],
    scenes: Sequence[Mapping[str, Any]],
    *,
    premise: str,
    ordinary: frozenset[str],
    leg: str,
) -> dict[str, Any]:
    """One leg of the census over one run. Distributions only; nothing here is a verdict."""
    premise_tokens = _words(premise)
    rows: list[dict[str, Any]] = []
    for feature in features:
        names = feature.names(ordinary, leg=leg)
        beyond = frozenset(names - premise_tokens)
        plan_hits = [s["ordinal"] for s in scenes if named(s["scene_plan"], names)]
        prose_hits = [s["ordinal"] for s in scenes if named(s["prose"], names)]
        plan_beyond = [s["ordinal"] for s in scenes if named(s["scene_plan"], beyond)]
        prose_beyond = [s["ordinal"] for s in scenes if named(s["prose"], beyond)]
        rows.append(
            {
                "feature_id": feature.feature_id,
                "kind": feature.kind,
                "role": feature.role,
                "subject": feature.subject,
                "hidden_at_start": feature.hidden_at_start,
                "names": sorted(names),
                "names_beyond_premise": sorted(beyond),
                "plan_scenes": plan_hits,
                "prose_scenes": prose_hits,
                "plan_scenes_beyond_premise": plan_beyond,
                "prose_scenes_beyond_premise": prose_beyond,
                "first_named_scene": min(prose_hits) if prose_hits else None,
                "first_named_scene_beyond_premise": min(prose_beyond) if prose_beyond else None,
            }
        )

    def summarise(subset: Sequence[Mapping[str, Any]], *, beyond: bool) -> dict[str, Any]:
        tail = "_beyond_premise" if beyond else ""
        nameable = [row for row in subset if row["names" + tail]]
        in_prose = [row for row in nameable if row["prose_scenes" + tail]]
        in_plan = [row for row in nameable if row["plan_scenes" + tail]]
        # **"The plan named it first" is a scene-level reading and not a temporal one.** Every
        # statement in a book is written by one outline call before any prose exists, so
        # "earlier in time" is true of every plan mention and says nothing. What separates a
        # planned feature from an improvised one is whether the statement for the scene that
        # first named it, or any statement before that, had already named it.
        planned = [
            row
            for row in in_prose
            if any(o <= min(row["prose_scenes" + tail]) for o in row["plan_scenes" + tail])
        ]
        firsts = [row["first_named_scene" + tail] for row in in_prose]
        return {
            "declared": len(subset),
            "nameable": len(nameable),
            "ever_named_in_prose": len(in_prose),
            "ever_named_in_plan": len(in_plan),
            "share_named_in_prose": share(len(in_prose), len(nameable)),
            "share_named_in_plan": share(len(in_plan), len(nameable)),
            "plan_first": len(planned),
            "writer_improvised": len(in_prose) - len(planned),
            "share_plan_first_of_prose_named": share(len(planned), len(in_prose)),
            "first_named_scene_median": statistics.median(firsts) if firsts else None,
        }

    visible = [row for row in rows if not row["hidden_at_start"]]
    hidden = [row for row in rows if row["hidden_at_start"]]

    def both(subset: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return {
            "raw": summarise(subset, beyond=False),
            "beyond_premise": summarise(subset, beyond=True),
        }

    roles = sorted({str(row["role"]) for row in visible if row["kind"] == "entity"})
    return {
        "leg": leg,
        "scenes": len(scenes),
        "all_declared_features": both(visible),
        "by_kind": {
            kind: both([r for r in visible if r["kind"] == kind]) for kind in FEATURE_KINDS
        },
        "by_entity_role": {
            role: both([r for r in visible if r["kind"] == "entity" and r["role"] == role])
            for role in roles
        },
        # **Its own row, and never pooled.** A hidden claim is supposed to go unnamed; counting
        # its silence as a miss would make the design working look like the counter failing.
        "hidden_claims": both(hidden),
        "features": rows,
    }


def packet_fact_uptake(
    facts: Sequence[str], book: str, *, vocabulary: frozenset[str], premise: str
) -> dict[str, Any]:
    """Of the lines the writer read under "Established facts", how many are ever echoed.

    A different denominator from the feature census and reported as one: a fact line is a
    rendered record, and several lines can carry the same name. A line whose words include no
    world name at all cannot be counted either way and gets its own bucket rather than being
    quietly scored as a miss.
    """
    premise_tokens = _words(premise)
    page = _words(book)
    hit = 0
    beyond = 0
    unnameable = 0
    for fact in facts:
        tokens = _words(fact) & vocabulary
        if not tokens:
            unnameable += 1
            continue
        if tokens & page:
            hit += 1
        if (tokens - premise_tokens) & page:
            beyond += 1
    countable = len(facts) - unnameable
    return {
        "facts": len(facts),
        "carrying_no_world_name": unnameable,
        "countable": countable,
        "named_on_the_page": hit,
        "never_named": countable - hit,
        "share_never_named": share(countable - hit, countable),
        "named_beyond_premise": beyond,
        "share_named_beyond_premise": share(beyond, countable),
    }


def sham(
    features: Sequence[Feature],
    books: Sequence[tuple[str, str]],
    *,
    ordinary: frozenset[str],
    leg: str,
) -> dict[str, Any]:
    """Control A. The same name sets against prose that has never seen this world.

    Pooled *and* per book, because the two say different things: one book sharing one ordinary
    noun is noise, and every book sharing the same noun is the counter reading the language.
    """
    nameable = [f for f in features if f.names(ordinary, leg=leg)]
    per_book: list[dict[str, Any]] = []
    fired: Counter[str] = Counter()
    colliding: Counter[str] = Counter()
    for title, text in books:
        page = _words(text)
        hits = []
        for feature in nameable:
            struck = feature.names(ordinary, leg=leg) & page
            if not struck:
                continue
            hits.append(feature)
            fired[feature.feature_id] += 1
            for token in struck:
                colliding[token] += 1
        per_book.append(
            {
                "book": title,
                "features_named": len(hits),
                "share": share(len(hits), len(nameable)),
            }
        )
    shares = [row["share"] for row in per_book if row["share"] is not None]
    quiet = sum(1 for value in shares if value == 0.0)

    def verdict(value: float | None) -> str:
        if value is None:
            return "not computable"
        return "PASS" if value <= SHAM_CEILING else "FIRES ABOVE ITS CEILING"

    median = round(statistics.median(shares), 4) if shares else None
    worst = max(shares) if shares else None
    pooled = share(len(fired), len(nameable))
    return {
        "leg": leg,
        "books": len(books),
        "nameable_features": len(nameable),
        "ceiling": SHAM_CEILING,
        # **Three statistics and three verdicts, because one of them is not scale-free.** The
        # pooled union rises with the number of control books and would reach 1.0 on any
        # non-zero per-book rate given enough of them, so it is reported and is not the
        # reading. The per-book distribution is what a ceiling can sit on. See
        # PRE_REGISTRATION["corrections"].
        "median_share_per_book": median,
        "max_share_per_book": worst,
        "pooled_share_named_in_any_book": pooled,
        "books_naming_nothing": quiet,
        "share_of_books_naming_nothing": share(quiet, len(shares)),
        "verdicts": {
            "median_per_book": verdict(median),
            "max_per_book": verdict(worst),
            "pooled_union": verdict(pooled),
        },
        "per_book": per_book,
        "colliding_tokens": [
            {"token": token, "books": count} for token, count in colliding.most_common(20)
        ],
        "worst_offenders": [
            {"feature_id": key, "books": count} for key, count in fired.most_common(15)
        ],
    }


# --- the ordinary-word reference ------------------------------------------------------------


#: Every world this module has name sets for. The reference lexicon is built over the union of
#: their tokens and nothing else, which is what makes the committed artifact a report about our
#: own worlds rather than a word list distilled out of somebody else's fiction.
WORLD_SOURCES: tuple[tuple[str, str], ...] = (
    ("pilot", "plan/serial-pilot-2-world.json"),
    ("forge-0", "pilot2/direct2/forge.json#0"),
    ("forge-1", "pilot2/direct2/forge.json#1"),
    ("forge-2", "pilot2/direct2/forge.json#2"),
)


def load_world(
    spec: str, *, root: Path
) -> tuple[architect.Candidate, tuple[lc.StateRecord, ...], str]:
    """`<path>` for a committed package, `<path>#<index>` for one candidate of a forge bundle."""
    if "#" in spec:
        path, _, index = spec.partition("#")
        return world_from_forge(_resolve(path, root), int(index))
    return world_from_package(_resolve(spec, root))


def _resolve(path: str, root: Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / path


def vocabulary_of(features: Sequence[Feature]) -> frozenset[str]:
    """Every token any feature of a world would be named by, on the wide leg."""
    return frozenset().union(*(f.wide for f in features)) if features else frozenset()


def corpus_snapshot() -> str:
    """The pinned RoyalRoad snapshot the reference was read at, from `corpus_io` itself.

    Imported lazily and by name rather than restated: this one *is* a pin on somebody else's
    artifact, and a second copy of a pin is a second thing that can be stale.
    """
    from corpus_io import SNAPSHOT_REVISION

    return str(SNAPSHOT_REVISION)


def build_lexicon(
    tokens: frozenset[str], *, shards: tuple[int, ...], limit: int, min_words: int
) -> dict[str, Any]:
    """Document frequency of our worlds' name tokens across the cached RoyalRoad shelf.

    **The document is a fiction, not a chapter**, and the reason is the same one
    `state_coverage.py` had to learn: a per-chapter frequency answers "how often is this word
    used", and the question here is "how many separate authors already own it". A word one
    author uses four hundred times is one author's word.

    Runs under the venv that has `pyarrow`, not the repository's. Everything else in this
    module runs under `uv run`.
    """
    from corpus_io import royalroad_chapters

    fictions: dict[str, set[str]] = {token: set() for token in tokens}
    seen: set[str] = set()
    chapters = 0
    for unit in royalroad_chapters(shards=shards, min_words=min_words, limit=limit):
        chapters += 1
        seen.add(unit.work_id)
        page = _words(unit.text)
        for token in tokens & page:
            fictions[token].add(unit.work_id)
    return {
        "built": "royalroad",
        "snapshot": corpus_snapshot(),
        "shards": list(shards),
        "chapters": chapters,
        "fictions": len(seen),
        "min_words": min_words,
        "limit": limit,
        "tokens": len(tokens),
        "document_frequency": {token: len(stories) for token, stories in sorted(fictions.items())},
    }


def ordinary_tokens(lexicon: Mapping[str, Any], *, floor: int) -> frozenset[str]:
    """The tokens the shelf owns at `floor` distinct fictions."""
    frequency = lexicon.get("document_frequency") or {}
    return frozenset(token for token, count in frequency.items() if int(count) >= floor)


def load_lexicon(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(
            f"the ordinary-word reference is missing at {path}. Build it first with "
            "--build-lexicon under a venv that has pyarrow; the coined leg cannot be "
            "computed without it and reporting only the wide leg would be the pre-registered "
            "answer with half of it removed."
        )
    return json.loads(path.read_text(encoding="utf-8"))


# --- the selftest ---------------------------------------------------------------------------


def selftest() -> int:
    """The free leg: the matchers, the enumeration, the arithmetic, and the freeze.

    Run before anything that reads a run, and re-run after every edit. The last check is the
    byte-freeze and it is the one that makes every committed number attributable to a
    particular instrument rather than to a family of them.
    """
    require_worlds()
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    check("seven feature kinds, no duplicates", len(FEATURE_KINDS) == 7 == len(set(FEATURE_KINDS)))
    check("the sham ceiling is a share in (0, 1)", 0.0 < SHAM_CEILING < 1.0)
    check(
        "the declared floor is one of the sensitivity floors",
        ORDINARY_FLOOR in SENSITIVITY_FLOORS,
    )
    check(
        "the restated name-bearing predicates are still the shipped module's three",
        {worlds.WORLD_RULE_PREDICATE, "is_a", worlds.MANIFESTS_PREDICATE} == _NAME_BEARING,
    )
    check(
        "the restated inner-capital rule is byte-identical to the shipped one",
        _INNER_CAPITAL.pattern == worlds._INNER_CAPITAL.pattern,
    )
    check("the restated id-noise set is the shipped one", _ID_NOISE == worlds._ID_NOISE)

    # -- the tokeniser is what "whole word" means here
    check("an apostrophe is a boundary", _words("the watermaster's book") >= {"watermaster"})
    check("a hyphen is a boundary", _words("a gate-moth") >= {"gate", "moth"})
    check("case is folded", _words("NEVER") == {"never"})
    check("a plural is not the singular", "gate" not in _words("the gates stood open"))
    check("digits name nothing", _words("1449 and 1462") == {"and"})

    # -- the id rule, including the suffixes `records_for` mints
    check("a minted suffix is dropped", _id_tokens("c_wren_holt_secret") == {"wren", "holt"})
    check("a short part is dropped", _id_tokens("c_ada_serrell") == {"serrell"})
    check("id noise is dropped", _id_tokens("i_church_of_spending") == {"church", "spending"})
    check(
        "only a trailing suffix is dropped",
        _id_tokens("m_secret_valley") == {"secret", "valley"},
    )

    # -- the prose rule
    check(
        "a sentence-initial capital is not a name",
        _capitals("Never mind the Kettle Basin.") == {"kettle", "basin"},
    )

    # -- the enumeration, against the world the pilot ran on
    package = REPO / "plan" / "serial-pilot-2-world.json"
    if not package.is_file():
        failures.append(f"the committed pilot world is missing at {package}")
    else:
        candidate, records, premise = world_from_package(package)
        found = features_of(records, scenes=8)
        kinds = Counter(f.kind for f in found)
        check(f"27 entities enumerated (found {kinds['entity']})", kinds["entity"] == 27)
        check(f"7 rules enumerated (found {kinds['rule']})", kinds["rule"] == 7)
        check(
            f"21 consequences enumerated (found {kinds['consequence']})",
            kinds["consequence"] == 21,
        )
        check(f"2 criteria enumerated (found {kinds['criterion']})", kinds["criterion"] == 2)
        check(f"8 ranks enumerated (found {kinds['rank']})", kinds["rank"] == 8)
        check(
            f"42 manifestations enumerated (found {kinds['manifestation']})",
            kinds["manifestation"] == 42,
        )
        check(f"28 claims enumerated (found {kinds['claim']})", kinds["claim"] == 28)
        hidden = sum(1 for f in found if f.hidden_at_start and f.kind == "claim")
        check(f"20 claims hidden at scene one (found {hidden})", hidden == 20)
        check("every feature id is unique", len({f.feature_id for f in found}) == len(found))
        check("the premise is not empty", bool(premise.strip()))
        check("the candidate is the picked one", candidate.title == "First In Time")

        # **The restated rule must agree with the shipped one.** `key_nouns` builds its set from
        # the subjects that carry a role or a rule; the same subjects here, unioned, must give
        # the same answer apart from the minted suffixes this module drops on purpose and the
        # `_ID_NOISE` word `key_nouns` keeps because it never looks at a claim id.
        shipped = set(worlds.key_nouns(records))
        mine: set[str] = set()
        for feature in found:
            if feature.kind in {"entity", "rule"}:
                mine |= feature.wide
        check(
            f"the restated rule reproduces key_nouns on entities and rules "
            f"(missing {sorted(shipped - mine)[:6]}, extra {sorted(mine - shipped)[:6]})",
            mine == shipped,
        )

        # -- the arithmetic, on a text this module writes itself
        wren = next(f for f in found if f.feature_id == "c_wren_holt")
        check("a named feature is found", bool(named("Wren rode the ditch.", wren.wide)))
        check("an unnamed feature is not", not named("Nobody moved.", wren.wide))
        rows = census(
            found,
            [
                {"ordinal": 1, "scene_plan": "Wren opens a gate.", "prose": "Nothing happened."},
                {"ordinal": 2, "scene_plan": "Nothing.", "prose": "Wren Holt turned the wheel."},
            ],
            premise="A book about nothing at all.",
            ordinary=frozenset(),
            leg="wide",
        )
        row = next(r for r in rows["features"] if r["feature_id"] == "c_wren_holt")
        check("plan and prose scenes are read separately", row["plan_scenes"] == [1])
        check("the first named scene is the lowest", row["first_named_scene"] == 2)
        summary = rows["all_declared_features"]["raw"]
        check(
            "a feature named in an earlier plan counts as planned",
            summary["plan_first"] >= 1,
        )
        check("shares are in range", all(
            value is None or 0.0 <= value <= 1.0
            for key, value in summary.items()
            if key.startswith("share_")
        ))

        # -- the sham can fire, which is the whole point of having one
        loud = sham(found, [("stub", "Wren Holt stood at the headgate in the Kettle Basin.")],
                    ordinary=frozenset(), leg="wide")
        check(
            "the sham fires on prose that names the world",
            (loud["pooled_share_named_in_any_book"] or 0) > 0,
        )
        check(
            "a firing sham names the token that collided",
            "wren" in {row["token"] for row in loud["colliding_tokens"]},
        )
        check(
            "a firing sham has a verdict for each of its three statistics",
            set(loud["verdicts"]) == {"median_per_book", "max_per_book", "pooled_union"},
        )
        quiet = sham(
            found, [("stub", "The quick brown fox.")], ordinary=frozenset(), leg="wide"
        )
        check(
            "the sham is quiet on prose that does not",
            quiet["pooled_share_named_in_any_book"] == 0.0,
        )

        # -- packet facts
        prompt = (
            "Premise: x\n\nEstablished facts:\n- Rule -- the river answers a date.\n"
            "- Nothing at all.\n\nTrue, and the reader has not been told -- x:\n- a secret\n"
        )
        check("the fact block is read off the prompt", packet_facts(prompt) == (
            "Rule -- the river answers a date.", "Nothing at all."
        ))

    # -- the freeze
    computed = registration_digest()
    check(
        f"the frozen block still digests to {FROZEN_DIGEST} (computed {computed})",
        computed == FROZEN_DIGEST,
    )

    for message in failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(
        f"selftest: {'PASS' if not failures else str(len(failures)) + ' FAILURES'} "
        f"(registration digest {computed})",
        file=sys.stderr,
    )
    return 1 if failures else 0


# --- the runs -------------------------------------------------------------------------------


def envelope(extra: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "protocol": "plan/handoff-worldbuilding.md tasks 1 and 2",
        "registration_digest": registration_digest(),
        "pre_registration": PRE_REGISTRATION,
        **extra,
    }


def run_census(args: argparse.Namespace) -> dict[str, Any]:
    """The full census over one run, both legs, both controls."""
    root = Path(args.repo) if args.repo else REPO
    candidate, records, premise = load_world(args.world, root=root)
    features = features_of(records, scenes=args.scenes)
    lexicon = load_lexicon(Path(args.lexicon))
    books = fitness_books(Path(args.fitness))
    if not books:
        raise SystemExit(
            f"the wrong-world control corpus is empty at {args.fitness}. exports/ is "
            "gitignored and does not exist in a worktree, so --fitness must point at the "
            "checkout that holds it. A census without its sham is not a census."
        )
    scenes = (
        scenes_from_db(Path(args.database))
        if args.database
        else json.loads(Path(args.statements).read_text(encoding="utf-8"))["scenes"]
    )
    vocabulary = vocabulary_of(features)
    facts = next((packet_facts(s.get("prompt") or "") for s in scenes if s.get("prompt")), ())
    book = "\n\n".join(str(scene.get("prose") or "") for scene in scenes)

    legs: dict[str, Any] = {}
    for leg in ("wide", "coined"):
        ordinary = (
            frozenset()
            if leg == "wide"
            else ordinary_tokens(lexicon, floor=args.floor)
        )
        legs[leg] = {
            "census": census(
                features, scenes, premise=premise, ordinary=ordinary, leg=leg
            ),
            "sham": sham(features, books, ordinary=ordinary, leg=leg),
            "packet_facts": packet_fact_uptake(
                facts,
                book,
                vocabulary=frozenset(vocabulary - ordinary),
                premise=premise,
            ),
        }
    sensitivity = {
        str(floor): {
            "ordinary_tokens_in_this_world": len(
                vocabulary & ordinary_tokens(lexicon, floor=floor)
            ),
            "sham": {
                key: sham(
                    features,
                    books,
                    ordinary=ordinary_tokens(lexicon, floor=floor),
                    leg="coined",
                )[key]
                for key in (
                    "median_share_per_book",
                    "max_share_per_book",
                    "pooled_share_named_in_any_book",
                    "share_of_books_naming_nothing",
                )
            },
        }
        for floor in SENSITIVITY_FLOORS
    }
    return envelope(
        {
            "label": args.label,
            "world": {
                "source": args.world,
                "title": candidate.title,
                "records": len(records),
                "declared_features": len(features),
                "vocabulary": sorted(vocabulary),
                "premise_words": len(_words(premise)),
            },
            "substrate": {
                "database": args.database,
                "statements": args.statements,
                "scenes": len(scenes),
                "words": len(book.split()),
                "packet_facts_read": len(facts),
                "fitness_books": len(books),
            },
            "floor": args.floor,
            "legs": legs,
            "floor_sensitivity": sensitivity,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--emit-tokens", action="store_true")
    parser.add_argument("--build-lexicon", action="store_true")
    parser.add_argument("--tokens", default=None, help="a token file --emit-tokens wrote")
    parser.add_argument("--census", action="store_true")
    parser.add_argument("--label", default="unlabelled")
    parser.add_argument("--world", default="plan/serial-pilot-2-world.json")
    parser.add_argument("--repo", default=None, help="root the --world path is relative to")
    parser.add_argument("--database", default=None, help="a run to read, opened read-only")
    parser.add_argument("--statements", default=None, help="a JSON of scenes, for a plan-only arm")
    parser.add_argument("--scenes", type=int, default=8)
    parser.add_argument("--floor", type=int, default=ORDINARY_FLOOR)
    parser.add_argument("--lexicon", default=str(LEXICON_JSON))
    parser.add_argument(
        "--fitness",
        default=str(REPO / "exports" / "fitness"),
        help="the wrong-world control corpus; gitignored, so a worktree needs this passed",
    )
    parser.add_argument("--shards", default="30,3", help="RoyalRoad shards for --build-lexicon")
    parser.add_argument("--limit", type=int, default=6000)
    parser.add_argument("--min-words", type=int, default=300)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.emit_tokens:
        # **The two legs are split by venv and not by preference.** Building the token union
        # needs `litharness`; reading the shelf needs `pyarrow`; nothing on this machine has
        # both. So this leg writes the union and `--build-lexicon --tokens` reads it back under
        # the other venv, with the registration digest carried across so a token file emitted
        # by a different instrument cannot be silently consumed by this one.
        root = Path(args.repo) if args.repo else REPO
        tokens: set[str] = set()
        covered: list[str] = []
        for name, spec in WORLD_SOURCES:
            try:
                _, records, _ = load_world(spec, root=root)
            except (FileNotFoundError, KeyError, IndexError) as problem:
                print(f"  skipping {name}: {problem}", file=sys.stderr)
                continue
            tokens |= vocabulary_of(features_of(records, scenes=args.scenes))
            covered.append(name)
        emitted_path = Path(args.out) if args.out else DERIVED / "world-uptake-tokens.json"
        emitted_path.parent.mkdir(parents=True, exist_ok=True)
        emitted_path.write_text(
            json.dumps(
                {
                    "worlds": covered,
                    "registration_digest": registration_digest(),
                    "tokens": sorted(tokens),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        print(f"{len(tokens)} tokens over {len(covered)} world(s); wrote {emitted_path}")
        return 0

    if args.build_lexicon:
        if not args.tokens:
            parser.error("--build-lexicon needs the --tokens file --emit-tokens wrote")
        emitted = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
        if emitted.get("registration_digest") != registration_digest():
            parser.error(
                "the token file was emitted by a different instrument; re-run --emit-tokens"
            )
        tokens = set(emitted["tokens"])
        covered = list(emitted.get("worlds") or [])
        shards = tuple(int(part) for part in args.shards.split(",") if part.strip())
        lexicon = build_lexicon(
            frozenset(tokens), shards=shards, limit=args.limit, min_words=args.min_words
        )
        lexicon["worlds"] = covered
        lexicon["registration_digest"] = registration_digest()
        out = Path(args.out) if args.out else LEXICON_JSON
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(lexicon, indent=2, sort_keys=True), encoding="utf-8")
        owned = len(ordinary_tokens(lexicon, floor=ORDINARY_FLOOR))
        print(
            f"{len(tokens)} tokens over {len(covered)} world(s); {owned} owned by the shelf "
            f"at a floor of {ORDINARY_FLOOR} fiction(s); wrote {out}"
        )
        return 0

    if not args.census:
        parser.error("one of --selftest, --build-lexicon or --census is required")
    if not args.database and not args.statements:
        parser.error("--census needs a --database or a --statements file")
    if selftest():
        print("refusing to run: the selftest failed", file=sys.stderr)
        return 1

    report = run_census(args)
    out = Path(args.out) if args.out else RESULTS / f"world-uptake-{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    for leg, block in report["legs"].items():
        summary = block["census"]["all_declared_features"]
        print(
            f"{leg:7s} named-in-prose {summary['raw']['share_named_in_prose']} "
            f"(beyond premise {summary['beyond_premise']['share_named_in_prose']}) "
            f"plan-first {summary['raw']['share_plan_first_of_prose_named']} "
            f"| sham/book median {block['sham']['median_share_per_book']} "
            f"max {block['sham']['max_share_per_book']} "
            f"pooled {block['sham']['pooled_share_named_in_any_book']} "
            f"({block['sham']['books_naming_nothing']}/{block['sham']['books']} silent)"
        )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
