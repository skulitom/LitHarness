"""The world, as an agent asks it questions rather than as a blob handed over.

**Why this exists, in the operator's words (2026-08-24):** *"in what world would a one-shot
structured call be a good idea for writing a book... The world would obviously evolve and grow
with every chapter"*, and *"all our agents should interact with each other through cli tools, as
it is native interface for them"*.

§132 named the gap and did not close it: raising the writer's packet from 6,000 tokens to 200,000
stops the eviction and does not make a writer that *understands* its world, because *"a
professional does not hold the two hundred pages, they consult them"*. This module is the
consulting surface. Every view below is a thin wrapper over a function `domain/worlds.py`
already had — `rules`, `criteria`, `rank_order`, `ladder_of`, `standing_of`, `capabilities_of`,
`questions`, `reveal_scenes`, `validate` — turned into something an agent can call and parse.
**No new world logic is written here**; if a view needs a rule the domain does not already
state, the rule belongs in `worlds.py` and not in a presentation layer.

**Why the writes are safe, and the rail is not this module's.** `worlds.world_record` mints at
`PROPOSED` and its own docstring says why: Architect output is a proposal and reaches canon only
through a recorded policy decision. So an agent holding these tools writes proposals, and canon
still costs a decision row — which is the substance of §5's "no subsystem mutates canon
directly", preserved *through* the tool surface rather than by denying one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import litharness_contracts as lc

from litharness.domain import genre, worlds
from litharness.domain import state as state_mod

#: Every view is addressable by name, so the CLI's subcommand table and this module cannot
#: drift apart, and an agent can be told the list of views without a second source for it.
VIEWS: tuple[str, ...] = (
    "rules",
    "ladders",
    "abilities",
    "cast",
    "threads",
    "presence",
    "check",
    "vocabulary",
)


def vocabulary() -> dict[str, Any]:
    """Every word this world's language admits, so an agent can find out rather than guess.

    **Written because the first agent to hold these tools got it wrong in a way the tools could
    not have taught it.** Declaring a capability needs `entity_role capability`, not `type
    capability` — `type` is for the five reified node kinds and `worlds.capabilities` reads the
    role — and nothing in `--help` said so. A CLI is an agent's native interface only if the
    interface is discoverable; a vocabulary a caller has to already know is a Python API with a
    shell in front of it.

    Values come from `domain/worlds.py`'s own constants, so this cannot drift from what
    `validate` will accept. **The prose beside them can and did**, which is the defect below.

    **Four of these lines named the wrong slot, and one of them cost a pilot six dead
    records.** Checked line by line against the function that reads each predicate on
    2026-08-29, after `consequence` was found documenting `--object` as the rule while
    `worlds.consequence_domains` has always read it as the domain. The other three were the
    same error unreported: `evaluates` and `edge` were written backwards, and `precedes`,
    `stands_at`, `disclosed_to` and `claim.false` each named the slot they take an edge in and
    stayed silent about the value slot their reader actually keys on — while `comparator`, the
    predicate without which `criteria` finds no criterion at all, was not listed. The shapes
    here are now each one a statement about a named reader in `domain/worlds.py`.

    **What stops it drifting again is a pair of tests and neither alone would do.**
    `test_every_documented_slot_is_the_slot_its_reader_reads` builds a record to each shape and
    hands it to the function that reads that predicate, which pins the shape but is still the
    author's reading of the prose written down twice;
    `test_the_documented_line_names_the_slots_its_own_record_fills` compares the line to that
    verified record, so a line naming a slot its record does not fill fails. The pair does not
    catch a line that names the right two slots and swaps which id goes where — the way
    `evaluates` was wrong — and saying so is the point: a check believed to cover more than it
    does is worse than one known to be narrow.

    **Three predicates were reachable, load-bearing and absent from this mapping entirely, and
    the genre floor's own repair path was one of them** (§163). `status_sheet`,
    `status_snapshot` and `graph_line` are all declarable through `world declare` — measured on
    the real CLI, on a listing-created book: two declarations and a `world accept` cleared
    `genre.genre_block` and rendered `[STATUS] sera — Attunement 1 | Threads 2/3`, the book's
    own columns, out of `extraction.system_voice_example`. Nothing refused them and nothing
    was missing; they were simply not written down, in the command `world_agent`'s prompt calls
    the list of *every* predicate the world's language admits. **`world vocabulary` is not a
    reference an Architect consults beside another one — it is the whole of what a fresh draw
    is told**, which is what makes an omission here indistinguishable from a prohibition.

    **What the omission cost is a default rather than a silence, and that is the sharper
    finding.** A book that declares no `status_sheet` does not go without one: it gets
    `extraction.DEFAULT_SHEET`, whose labels reach the *writer* through
    `system_voice_example` as the example line to imitate. So the operator's stated not-this
    was arriving as what a book gets for declaring nothing, and the only escape was the
    predicate nobody was told about. This is `worlds.py`'s "absence is free" — true of the
    world model, and not true one layer down, where absence has a default with content in it.

    **Four more lines landed with §160's vocabulary, and two of its predicates were
    deliberately left out.** `governed_by` and `is_a` are documented because the Architect meets
    them either way: `validate` complains about a system nobody declared, and `is_a` has carried
    every name in this vocabulary since Serial Pilot 1's operator-typed seed while appearing in
    no list. `can_do` and `requires` gained the value slots §160 put in them. But
    `magnitude_scale` and `system_digest` are **not** documented, because they are minted by
    `gamesystem.records_for` and never by hand — writing them down would invite a second
    declaration beside the drawn one, which is the two-writers hazard the `status_sheet` line
    already exists to warn about, manufactured on purpose. A predicate an agent cannot usefully
    declare does not belong in the list of what it may declare.

    **A fifth line was wrong, in the `how` list rather than among the predicates, and it was
    wrong in the reassuring direction.** It said a corrected declaration that changes the
    subject, the `--object` **or the `--order-key`** fills a different slot so both survive.
    `record_id_for` carries no position, so the third is false: a redeclaration that moves only
    the position is the same record, `record_state_records` is `INSERT OR IGNORE`, and the
    store keeps the **first** position. `declare` does say `already on record`, so it is not
    silent — but an Architect told it had just filled a second slot reads that as confirmation
    while the wrong position stands. The two shipped tests could not catch this one: they grade
    the predicate lines against their readers, and this was a sentence about identity.

    **The line for `status_sheet` names no example fields, deliberately.** §138 measured that a
    permission overproduces what it names, so a line illustrating the shape with the default's
    own columns would teach the thing it exists to let a world escape. It names the *slots* and
    says the fields are the book's own. For the same reason the hazard it does name is the one
    that fails silently: `extraction.sheet_for` abstains to the default when a book declares
    two sheets, so a second declaration is not an error, it is a quiet return to the line the
    world was trying to replace.
    """
    return {
        "entity_roles": list(worlds.ENTITY_ROLES),
        "node_types": sorted(worlds.NODE_TYPES),
        "comparators": list(worlds.COMPARATORS),
        "consequence_domains": list(worlds.CONSEQUENCE_DOMAINS),
        "group_keys": list(worlds.GROUP_KEYS),
        "predicates": {
            "entity_role": "what kind of thing this is; --value one of entity_roles",
            "type": "reifies a node; --value one of node_types, and only those",
            "world_rule": "a rule this world runs on; --value the rule in plain words",
            "consequence": (
                "a second-order effect of a rule; the rule is the subject, --object one of "
                "consequence_domains, --value the consequence in plain words"
            ),
            "manifests_as": "how it shows on the page; --value one line",
            "can_do": (
                "a person holds a capability; --object the capability's id, and --value how "
                "far they have taken it as a whole number. Leave the number off to say only "
                "that they hold it"
            ),
            "requires": (
                "a prerequisite; --object what must come first, and --value how far it has to "
                "have been taken as a whole number. Leave it off, or 1, for held at all"
            ),
            "governed_by": (
                "which system grants this; the criterion or the capability is the subject, "
                "--object the system, which has to be a subject carrying the system role. A "
                "ladder whose system nobody declared has no issuer, and that is the space "
                "something else fills"
            ),
            "is_a": (
                "what a thing is called, in this world's own words; --value the name. The "
                "printed labels live here — the word a book counts rungs in, and an ability's "
                "— so keep those short, letters only, and free of digits"
            ),
            "costs": "what it takes; --value or --object",
            "taught_by": "who teaches it; --object the teacher",
            "comparator": (
                "how a criterion judges; the criterion is the subject, --value one of "
                "comparators, and a criterion without one is not a criterion"
            ),
            "evaluates": (
                "what a criterion judges; the criterion is the subject, --object the kind of "
                "thing it judges"
            ),
            "precedes": (
                "rung ordering, lowest first; --object the rung above, --value the criterion "
                "whose ladder this is. Never --order-key: a ladder is not in story time"
            ),
            "stands_at": (
                "where somebody stands; --object the rung, --value the criterion whose ladder "
                "it is, and --order-key when the book has already moved them"
            ),
            "asks": "an open question; --value the question in plain words",
            "reveal_scene": "which scene answers it; --value the scene number",
            "claim.content": "something believed; --value the claim",
            "claim.false": "marks a claim untrue; --value true, and only a literal true",
            "believes": "who holds a claim; the believer is the subject, --object the claim",
            "disclosed_to": (
                "who has been told; --object the claim, --value reader when the one told is "
                "the reader, and --order-key where in the book they are told"
            ),
            "edge": (
                "what the one exceptional person can do that nobody else can; --value in "
                "plain words"
            ),
            "price": "what a thing charges; --value in plain words",
            "exception_to": "the rule that does not hold here; --object the rule",
            # **The three that were reachable, load-bearing and undocumented** (§163). Every
            # one is a JSON object in the value slot, which `cli._scalar` has kept whole since
            # §158; none takes an edge. They are last in this mapping because a world declares
            # at most one of each and the ones above are what it spends its declarations on.
            "status_sheet": (
                "the columns this book's own status line prints; --value an object "
                '{"fields": [{"name": <the key a snapshot fills>, "label": <what the line '
                'prints>, "paired": true|false}]}, and a paired field prints '
                "current/maximum and adds a <name>_max key. Declare exactly one or none: a "
                "book that declares none, and a book that declares two, both print a generic "
                "line written in nobody's vocabulary"
            ),
            "status_snapshot": (
                "where those columns stand, as numbers; --value an object mapping each field "
                "name to its number, and --order-key where in the book it becomes true — "
                "leave the key off for the state the book opens in, which is then the one "
                "found at every position. Until one of these is accepted the book is never "
                "asked for a status line at all"
            ),
            "graph_line": (
                "the line this book prints when somebody's standing changes; --value an "
                'object {"label": <a short bracket tag>, "edges": [{"predicate": '
                '"stands_at", "phrase": <the words this book uses for it>}]}. Declare one '
                "only if this world announces itself; a world whose systems are quiet "
                "declares none and prints none"
            ),
        },
        "how": [
            "Everything `declare` writes is PROPOSED. `world accept` is what makes it canon.",
            "`declare` and `check` refuse nothing; they report. Building a world one record at "
            "a time is transiently incoherent by nature, so `world accept` is the only gate, "
            "and it refuses on a contradiction unless you pass --force.",
            "A `--value` that is a bare number is stored as a number: `--value 34`, not "
            "`--value \"34\"`. `reveal_scene` is only read when it is a genuine integer.",
            "A question is two records and the pair is what makes it legal: `claim.content` "
            "with the answer, `asks` with the question, and `reveal_scene` with the scene the "
            "reader learns it. Declaring `asks` alone is reported until its answer lands.",
            "A capability is `entity_role capability`, then `manifests_as`, then somebody "
            "`can_do` it by --object.",
            "A ladder is `type criterion` and a `comparator ordinal`, its rungs joined "
            "lowest-first by `precedes` with the criterion in --value, and somebody at "
            "`stands_at` one of them. Every `precedes` on one ladder must carry the same "
            "--value, or the rungs belong to no ladder and the standings count nothing.",
            "--order-key is where in the *story* a record becomes true, and nothing else. It "
            "is not how a record is scoped, filed or grouped; a ladder, a criterion and a "
            "capability are all outside story time and take none.",
            "This house publishes one genre, and a book that cannot state anybody's standing "
            "as numbers is not in it. The whole of that question is whether canon holds a "
            "status_snapshot whose value is an object; `world check` reports the gap while "
            "you are still building, and says nothing about whether the sheet is any good.",
            "A drawn system brings its own status_sheet with it, so do not declare a second "
            "one beside it. Two of them do not collide loudly: the book falls back to a "
            "generic line written in nobody's vocabulary, which is the thing the declaration "
            "existed to escape.",
            "A record in the wrong slot cannot be taken back — there is no retraction, and a "
            "corrected declaration that changes the subject or the --object fills a different "
            "slot, so both survive. `declare` reports these separately from what is merely not "
            "coherent yet; read that list before writing the next record.",
            "A record's identity is blind to --order-key, so a redeclaration that changes only "
            "the position is the same record and does not land: `declare` answers `already on "
            "record` and the first position stands. Nothing can move a record in story time, "
            "and a fact that has not changed is not worth restating at a later position — the "
            "restatement is dropped either way.",
        ],
    }


def _canon_only(records: Sequence[lc.StateRecord]) -> tuple[lc.StateRecord, ...]:
    return tuple(record for record in records if state_mod.is_canon(record))


def declarations(
    records: Sequence[lc.StateRecord], *, subject: str | None = None
) -> list[dict[str, Any]]:
    """Every declaration, in story order, with provenance on each line.

    Proposals are included and labelled rather than filtered. An Architect that cannot see what
    it proposed last chapter would propose it again, and the authority field is what tells the
    two apart — which is the same reason `cmd_state` prints provenance.
    """
    rows: list[dict[str, Any]] = []
    for record in state_mod.in_story_order(records):
        if subject is not None and record.subject != subject:
            continue
        position = record.story_position
        rows.append(
            {
                "record_id": record.record_id,
                "subject": record.subject,
                "predicate": record.predicate,
                "value": record.value,
                "object": record.object_ref,
                "order_key": position.order_key if position is not None else None,
                "authority": record.authority.value,
                "canon": state_mod.is_canon(record),
                "says": state_mod.describe(record),
            }
        )
    return rows


def rules(records: Sequence[lc.StateRecord]) -> list[dict[str, Any]]:
    """The world's declared rules, each with the domains of life its consequences reach."""
    by_rule = worlds.consequence_domains(records)
    return [
        {"rule": rule, "consequence_domains": list(by_rule.get(rule, ()))}
        for rule in worlds.rules(records)
    ]


def ladders(records: Sequence[lc.StateRecord]) -> list[dict[str, Any]]:
    """Every ordinal criterion, its rungs lowest-first, and who is standing on which.

    The rung's position from the bottom is the number this world counts (§113), so it is
    returned rather than left for a caller to derive and get off by one.
    """
    out: list[dict[str, Any]] = []
    people = sorted(worlds.entities_with_role(records, "cast"))
    for criterion, label in sorted(worlds.criteria(records).items()):
        chain = worlds.ladder_of(records, criterion)
        if not chain:
            continue
        grants = dict(worlds.rank_order(records, criterion=criterion))
        standing: list[dict[str, Any]] = []
        for subject in people:
            where = worlds.standing_of(records, subject)
            rung = where.get(criterion)
            if rung is None:
                continue
            standing.append(
                {
                    "subject": subject,
                    "rung": rung,
                    "position": worlds.rung_index(records, criterion, rung),
                }
            )
        out.append(
            {
                "criterion": criterion,
                "label": label,
                "rungs": [
                    {"rung": rung, "position": index + 1, "grants": grants.get(rung, "")}
                    for index, rung in enumerate(chain)
                ],
                "standing": standing,
            }
        )
    return out


def abilities(
    records: Sequence[lc.StateRecord], *, holder: str | None = None
) -> dict[str, Any]:
    """What this world says a person can do, and who holds what.

    `declared` minus what anybody holds is the headroom a book has left to give away, which is
    the quantity the ability-inventory work (§114) exists to make visible — measured at zero in
    three of ten retired Forge worlds, which is a protagonist who starts holding everything.
    """
    declared = list(worlds.capabilities(records))
    if holder is not None:
        return {
            "declared": declared,
            "holder": holder,
            "held": list(worlds.capabilities_of(records, holder)),
        }
    held: dict[str, list[str]] = {}
    for subject in sorted(worlds.entities_with_role(records, "cast")):
        owned = list(worlds.capabilities_of(records, subject))
        if owned:
            held[subject] = owned
    spoken_for = {name for owned in held.values() for name in owned}
    return {
        "declared": declared,
        "held": held,
        "unclaimed": [name for name in declared if name not in spoken_for],
    }


def cast(records: Sequence[lc.StateRecord]) -> dict[str, Any]:
    """Who is in this world, by the role the world gave them, and who the protagonist is."""
    protagonist = worlds.protagonist_brief(records)
    return {
        "protagonist": (
            protagonist.to_jsonable() if protagonist is not None else None
        ),
        "roles": {
            subject: list(roles)
            for subject, roles in sorted(worlds.entity_roles(records).items())
        },
    }


def threads(records: Sequence[lc.StateRecord], *, at: str | None = None) -> dict[str, Any]:
    """Open questions, where each is answered, and what the reader has not been told yet.

    `at` is a story position: what is still open *as of* that point, which is the question a
    writer drafting scene seven has and a writer drafting scene one does not.
    """
    reveals = worlds.reveal_scenes(records)
    return {
        "questions": [
            {"question": question, "asks": text, "answered_at_scene": reveals.get(question)}
            for question, text in sorted(worlds.questions(records).items())
        ],
        "undisclosed": [
            {"subject": record.subject, "says": state_mod.describe(record)}
            for record in worlds.undisclosed_claims(records, at=at)
        ],
        "open": [
            {"subject": record.subject, "says": state_mod.describe(record)}
            for record in state_mod.open_threads(records)
        ],
    }


def presence(
    records: Sequence[lc.StateRecord], scenes: Mapping[str, str]
) -> dict[str, Any]:
    """Which of this world's coined names have reached the page, and which have not.

    `scenes` is `{logical_id: prose}` for the scenes that have been drafted; an empty mapping
    describes a book that has not started, where everything is absent and that is not a fault.

    **Absence is reported, never refused.** A world declares far more than any one chapter can
    show and a serial spends its names slowly on purpose, so a count here is a thing for the
    Architect to look at rather than a gate. `worlds.key_nouns` says the same of itself: it
    feeds a distribution report and not a bar, because `opening_proper_nouns` is the case where
    a counter nominated for a named defect put the complained-about chapter at the 68.5th
    percentile of published openings.
    """
    # **Filtered here rather than in `key_nouns`, and the split is deliberate.** That counter
    # builds names by splitting subject ids on `_`, so a world whose ids are `agency_the_drift`
    # and `creature_saltmilk_doe` contributes `agency` and `creature` — this schema's own type
    # vocabulary, which no reading of the counter ever wanted as one of the world's coined
    # names. That is the same class of implementation error its docstring already licenses
    # fixing (`not`, `mour`), but `key_nouns` feeds §107.6's reported figures and editing it
    # would move numbers that are on the record for a different question. So the vocabulary is
    # dropped in the view that cares, and the counter is left alone.
    _SCHEMA_WORDS = frozenset(
        word
        for term in (*worlds.ENTITY_ROLES, *worlds.NODE_TYPES)
        for word in term.casefold().split("_")
    )
    names = tuple(
        name for name in worlds.key_nouns(records) if name not in _SCHEMA_WORDS
    )
    drafted = {
        logical_id: text.casefold() for logical_id, text in scenes.items() if text.strip()
    }
    seen: dict[str, list[str]] = {}
    for name in names:
        where = [logical_id for logical_id, text in drafted.items() if name in text]
        if where:
            seen[name] = sorted(where)
    absent = [name for name in names if name not in seen]
    return {
        "declared_names": len(names),
        "drafted_scenes": len(drafted),
        "on_the_page": dict(sorted(seen.items())),
        "never_said": absent,
        "share_present": round(len(seen) / len(names), 4) if names else None,
    }


def check(records: Sequence[lc.StateRecord]) -> dict[str, Any]:
    """What is wrong with this world by arithmetic, never by taste.

    `worlds.validate` is the whole of it, plus the manifestation count, and its own docstring
    states the boundary this inherits: every check is arithmetic or membership over the records
    and none is a judgment about whether the world is any good.

    **`will_not_resolve` is carried here as well as at `declare`, and it does not move `ok`.**
    Serial Pilot 12's first seed read fifteen complaints out of this view, every one of them a
    standing on a rung no chain declared, and wrote a diagnosis saying the records were stored
    correctly and the CLI was at fault — an argument for `--force`. The cause was nine
    `precedes` edges it had scoped by `--order-key`, which this view had no way to mention
    because the edges themselves are legal. What is added is the naming and not a verdict:
    `worlds.slot_warnings` is about which slot a record went in, `ok` stays what
    `validate` says, and nothing here refuses anything.

    **`gaps` is the third list and it is a different thing from either** (§163). A complaint is
    a world contradicting itself and a warning is a record in a slot nothing reads; a gap is
    something the house requires that this world has not declared *yet*, which on a half-built
    world is the ordinary state and never a fault. It is reported for the reason `presence`
    gives for reporting absence: an Architect that cannot see what is still missing has to
    remember it instead, and the one gap here is the one the pipeline used to observe out loud
    and proceed past anyway (`domain/genre.py`'s opening argument).

    **It does not move `ok`, and that is the same rail `will_not_resolve` is on.** `ok` is what
    `validate` says and `world accept` is the only gate; a world with no sheet yet is coherent,
    and refusing it here would refuse every world in the middle of being built. The genre floor
    already refuses at draft time, where the answer is final.

    Both questions are asked through `domain/genre.py` rather than restated, so this view and
    the floor cannot come to disagree — the mistake §158 is the correction for. `system_gap` is
    §160's and reports a world whose numbers have no system behind them, or one that declares
    two sheets and would therefore silently render a line it never chose.
    """
    coverage = worlds.manifestation_coverage(records)
    complaints = list(worlds.validate(records))
    gaps: list[str] = []
    if not genre.has_starting_sheet(records):
        gaps.append(
            "no accepted status_snapshot whose value is an object, so nothing in this book "
            "can state where anybody stands as a number and no scene will be asked to. "
            "`world vocabulary` has the shape; `world accept` is what makes it count"
        )
    # **Both, when both are true, because they are different facts.** The line above is the
    # genre floor's question — can this book speak system voice at all — and `system_gap` is
    # §160's: does the sheet it speaks with belong to a system the world declared. A book can
    # fail the first and not the second (a hand-seeded sheet under a declared system) or the
    # second and not the first (a sheet seeded by hand with no system behind it), and collapsing
    # them would report whichever was checked first as though it were the whole answer.
    from_system = genre.system_gap(records)
    if from_system is not None:
        gaps.append(from_system)
    return {
        "complaints": complaints,
        "ok": not complaints,
        "gaps": gaps,
        "will_not_resolve": [
            warning for record in records for warning in worlds.slot_warnings(record)
        ],
        "manifested": len(coverage.covered),
        "needing_manifestation": len(coverage.features),
        "unmanifested": list(coverage.missing),
    }


def summary(
    records: Sequence[lc.StateRecord],
    in_force: Sequence[lc.StateRecord] | None = None,
) -> dict[str, Any]:
    """One call an agent can open with: how big this world is and where the holes are.

    **Two sets, counted separately, because the difference is a thing to know.** `records`,
    `canon` and `proposed` describe the store — everything ever declared on this branch. The
    contents below them describe `in_force`: what the world actually says, which is canon plus
    the proposals nothing has replaced (`integrity.in_force`). `replaced` is the gap, and it is
    reported rather than netted away — a world carrying two dozen dead declarations is
    something the Architect should be able to see, and it was invisible while the two sets were
    the same list.

    `in_force` defaults to `records`, so a caller with no store behind it — every test that
    builds records by hand — gets exactly what it got before.
    """
    speaking = tuple(in_force) if in_force is not None else tuple(records)
    canon = _canon_only(records)
    return {
        "records": len(records),
        "canon": len(canon),
        "proposed": len(records) - len(canon),
        "replaced": len(records) - len(speaking),
        "rules": len(worlds.rules(speaking)),
        "criteria": len(worlds.criteria(speaking)),
        "capabilities": len(worlds.capabilities(speaking)),
        "cast": len(worlds.entities_with_role(speaking, "cast")),
        "open_questions": len(worlds.questions(speaking)),
        "check": check(speaking),
    }


__all__ = [
    "VIEWS",
    "abilities",
    "cast",
    "check",
    "declarations",
    "ladders",
    "presence",
    "rules",
    "summary",
    "threads",
    "vocabulary",
]
