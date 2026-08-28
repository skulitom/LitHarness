"""The roster, as an agent asks it questions rather than as four dossiers compiled into a file.

`application/world.py`'s shape and `application/world.py`'s rule: **every view here is a thin
wrapper and no new rule is written in a presentation layer.** Where a check needs a fact the
domain does not already state, the fact belongs in `domain/writers.py`.

**The one place this module is deliberately louder than `world.py` is the vocabulary.** That
docstring records the lesson — an agent got a predicate wrong because nothing in `--help` said
which of two words it wanted — and the payload it produced still names each field with a hint
*string*. A hint string is not a shape: it cannot say whether a flag repeats, whether it is
required, or what a whole assembled command looks like, and an agent that has to compose a
command out of five hints composes it wrong and then learns the interface by writing records.
`plan/handoff-writer-recruiter.md` says the write-only-interface lesson has now been paid for
three times, so here each field is an object with a type, a repeat flag, its constraints and an
example, and the whole command line is shown once, assembled.

**Nothing here ranks, compares, or prefers.** There is no view that orders writers by anything
but their names, no "best dossier", and no output line that names two writer ids together;
`plan/handoff-writer-recruiter.md`'s rail 4 and §61(5)/§105.1 are why. What the census below
reports about a dossier is arithmetic over its own text and is never a verdict about it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from litharness.domain import house
from litharness.domain import voice as voice_domain
from litharness.domain import writers as writers_domain
from litharness.domain.directors import prose_axes_named

#: Every view addressable by name, so the CLI's subcommand table and this module cannot drift.
#: `declare` and `accept` are not views — they write — and are handled in `cmd_roster`.
VIEWS: tuple[str, ...] = ("vocabulary", "show", "check")

#: The twelve shelves, verbatim from the operator, 2026-08-28, keyed by the slug the CLI and the
#: store use. **The label is character-for-character theirs**, including "LitRPG Comedy" and the
#: parenthetical in "Chinese Cultivation (in English)": the model receives the label and never
#: the slug, and normalising either would be an edit to the operator's words.
#:
#: This is the canonical home for the list and nothing else restates it. It is a recruitment
#: brief rather than a quota — the operator's word beside "varied" was "useful", and both halves
#: are theirs — so a shelf with nobody on it is a fact `show` reports, never a gate.
SPECIALIZATIONS: Mapping[str, str] = {
    "light-fantasy": "Light Fantasy",
    "cozy-fantasy": "Cozy Fantasy",
    "litrpg-comedy": "LitRPG Comedy",
    "sci-fi": "Sci-Fi",
    "dark-fantasy": "Dark Fantasy",
    "supernatural": "Supernatural",
    "cultivation": "Cultivation",
    "chinese-cultivation": "Chinese Cultivation (in English)",
    "historical": "Historical",
    "progression-fantasy": "Progression Fantasy",
    "isekai": "Isekai",
    "portal-fantasy": "Portal Fantasy",
}

#: What each of `writers.DOSSIER_SHAPES` means, for the vocabulary payload. The membership is
#: the domain's and this only maps it; adding a key here without adding it there is caught by
#: `test_the_shape_vocabulary_has_one_home`.
#:
#: **No line here says which shape is better and none says what a good dossier is.** The pair
#: `several-with-beat` / `several-no-beat` is the contrast and `single-image` is the on-disk
#: control; a description that hinted would settle by assertion the question the registered arm
#: exists to measure.
SHAPES: Mapping[str, str] = {
    "single-image": (
        "one love, and it is an opening image: the moment on this shelf the writer would "
        "write again and again. The form all four shipped dossiers use, and the control"
    ),
    "several-with-beat": (
        "three or four separate loves at category level, one of them phrased as a moment a "
        "story opens on"
    ),
    "several-no-beat": (
        "three or four separate loves at category level, none of them phrased as a scene: "
        "what this writer values in a story rather than one they like to start on"
    ),
}

#: The three markers that separate the appetite pool from the career pool, **measured over the
#: two pools this repository already ships rather than chosen**: all four of `writers.CAST` open
#: on "You write", say "you love", and close on a clause about what they want a reader to do,
#: and none of the ten in `writers.BUILTIN` does any of the three. `BUILTIN` is exactly the
#: failure being screened for — ten dossiers about what somebody did for a living.
_APPETITE_MARKERS: Mapping[str, str] = {
    "writes": r"^\s*you write\b",
    "loves": r"\byou love\b",
    "wants_a_reader": r"\byou want (?:a|the) reader\b",
}


def appetite_markers(text: str) -> tuple[str, ...]:
    """Which of the three appetite markers this dossier carries. **A census, never a gate.**

    Its absence is suggestive: a dossier that never says what this person writes is probably a
    dossier about what they did for a living, which is the G3 failure that produced four worlds
    with no magic in them. Its presence proves nothing — *"You write cozy fantasy. You ran an
    inn for nine years..."* carries all three and is the exact failure — and
    `recruiter._RECRUIT` teaches this shape, so a model that complies produces the markers
    whether or not it produced an appetite. A passing count therefore measures compliance.

    **And gating on it would damage the one measurement this build exists to enable.** The three
    are calibrated on four dossiers that are all the `single-image` control, so refusing a
    dossier that lacks them would push the `several-*` arms toward the control's form, which is
    the arm's variable being quietly removed by its own guard.

    `test_the_appetite_markers_separate_the_cast_from_the_career_pool` is that arithmetic. If a
    later edit breaks it, this census has lost its licence rather than found a defect.
    """
    lowered = text.strip().casefold()
    return tuple(
        marker
        for marker, pattern in _APPETITE_MARKERS.items()
        if re.search(pattern, lowered, re.MULTILINE)
    )


def machinery_words(text: str) -> tuple[str, ...]:
    """This system's own vocabulary, found in a dossier. Reported, and never a complaint.

    `house.MACHINERY_WORDS` exists because `standing` reached a drafted chapter (§120), and a
    dossier rides in the system message of every scene call, so the concern is live here. It is
    still a census: `writers.BUILTIN["volcanology"]` contains *"the standing argument with
    people whose town it was"*, which is ordinary English and would be refused by a gate. A
    counter that refuses a shipped fixture is a counter measuring the wrong thing.
    """
    lowered = text.casefold()
    return tuple(sorted(word for word in house.MACHINERY_WORDS if word in lowered))


def reserved_name(name: str) -> str:
    """The reason `name` is unavailable to a stored writer, or `""` when it is free.

    A non-raising wrapper over `writers.refuse_reserved_name`, because the CLI's contract for
    this class of refusal is print-and-return-`EXIT_FAULT` rather than a traceback.
    """
    try:
        writers_domain.refuse_reserved_name(name)
    except writers_domain.IllegalDossier as error:
        return f"litharness: {error}"
    return ""


def _field(
    flag: str,
    type_: str,
    *,
    repeats: bool,
    required: bool,
    constraints: Sequence[str],
    example: str,
) -> dict[str, Any]:
    return {
        "flag": flag,
        "type": type_,
        "repeats": repeats,
        "required": required,
        "constraints": list(constraints),
        "example": example,
    }


#: One assembled, legal `declare` line. **Shown whole rather than left to be composed**, and
#: pinned by a test that parses it with the real parser and runs the real guard over its
#: dossier, so it cannot rot into an example the interface would refuse.
EXAMPLE_DECLARE = (
    "litharness roster declare okafor "
    '--interest "cozy fantasy" --interest "small towns and shopfronts" '
    '--dossier "You write the kind of fantasy where the stakes are a bakery, a bad harvest '
    "and somebody's estranged aunt, and the magic is small enough to live with. What you love "
    "is competence at low volume: a person who is good at one narrow thing, a town that needs "
    "exactly that thing, and a season of work that adds up. You have no patience for a villain "
    'who wants the world. You want a reader to close a chapter feeling like they could stay." '
    '--note "recruit: cozy fantasy"'
)


def vocabulary() -> dict[str, Any]:
    """Every field a declaration takes and **the shape each one has**, not just its name.

    `world.vocabulary` was written because an agent could not have learned from `--help` that a
    capability needs `entity_role capability` rather than `type capability`. Its fix was a
    sentence per predicate, and a sentence is still not a shape: as of 2026-08-28 that payload
    does not say `precedes` needs its criterion in `--value`, which is Serial Pilot 7's measured
    defect, and it omits the comparator predicate `worlds.validate` requires outright. Both
    survive *because* a hint string has nowhere to put "required" or "repeats".

    So every field below is an object, the whole command line is shown once assembled, and the
    example is executed by a test. `refused` is illustrative and says so — `directors`'
    craft-instruction vocabulary is the only authority and restating its patterns here would
    give them a second home, which the house rule about counts forbids for the same reason.
    """
    return {
        "declare_command": (
            'litharness roster declare NAME --dossier "ONE PARAGRAPH" '
            "--interest SUBJECT [--interest SUBJECT ...] [--note TEXT]"
        ),
        "example": EXAMPLE_DECLARE,
        "fields": {
            "name": _field(
                "positional, first",
                "string",
                repeats=False,
                required=True,
                constraints=[
                    "one lowercase surname and nothing else",
                    "not a name the compiled cast or the probe pool already holds",
                    "addressed material: it is part of this writer's content address",
                ],
                example="okafor",
            ),
            "dossier": _field(
                "--dossier",
                "string, one quoted argument",
                repeats=False,
                required=True,
                constraints=[
                    "one paragraph, about eighty words; no line breaks are needed and none "
                    "of the four shipped dossiers has one",
                    "what this person reads the shelf for and loves to write, never a job "
                    "they held",
                    "nothing about how to write: sentences, punctuation, rhythm, how much of "
                    "somebody's thinking belongs on a page. That is refused, not discouraged",
                    "addressed material",
                ],
                example='"You write the kind of fantasy where the stakes are a bakery..."',
            ),
            "interest": _field(
                "--interest",
                "string",
                repeats=True,
                required=False,
                constraints=[
                    "once per subject, two or three in all",
                    "order is addressed material: reordering mints a different writer",
                    "no subject twice",
                ],
                example='--interest "cozy fantasy" --interest "small towns and shopfronts"',
            ),
            "specialization": _field(
                "--specialization",
                "one of `specializations`",
                repeats=False,
                required=True,
                constraints=[
                    "already set for this run; you do not pass it",
                    "not addressed material: it says why this writer was drafted, not who "
                    "they are",
                ],
                example="cozy-fantasy",
            ),
            "shape": _field(
                "--shape",
                "one of `shapes`",
                repeats=False,
                required=True,
                constraints=[
                    "already set for this run; you do not pass it",
                    "not addressed material",
                ],
                example="several-no-beat",
            ),
            "note": _field(
                "--note",
                "string",
                repeats=False,
                required=False,
                constraints=[
                    "an annotation for a person: it never reaches a drafting prompt, and no "
                    "roster view returns it",
                    "not addressed material, so adding one does not mint a new writer",
                ],
                example='"recruit: cozy fantasy"',
            ),
        },
        "specializations": dict(SPECIALIZATIONS),
        "shapes": dict(SHAPES),
        "refused": {
            "authority": (
                'litharness roster check --dossier "..." is the only authority, it costs '
                "nothing, it writes no record, and it exits zero whatever it finds. Rehearse "
                "before you declare"
            ),
            "hard": [
                "the character — (em dash, U+2014) anywhere in the dossier. It refused "
                "four of the ten dossiers on the first slate, and not because any of them "
                "said anything about punctuation: a dossier rides in the system message of "
                "every scene call, so a dossier written with the mark demonstrates the mark "
                "on every draft. Use a comma, a colon or a full stop"
            ],
            "examples_not_exhaustive": [
                "any word for how prose should read: sentence length, word choice, adverbs, "
                "prose style, writing style, purple prose",
                "any word for how much of a character's head reaches the page: interiority, "
                "inner monologue, show don't tell, free indirect",
                'the words "status line", "stat line", "stat block", "status block"',
                'the word "punctuation" in any form',
            ],
        },
        "how": [
            "Everything `declare` writes is proposed. Putting a writer on the roster is "
            "somebody else's act and you do not have that command.",
            "`declare` refuses an illegal dossier rather than warning, because a dossier is "
            "one whole artifact in one command and there is no half-built state for it to be "
            "in. `check --dossier` is where you find out for free.",
            "Read `roster show` before you write: it gives you every writer this database "
            "holds, what each one's shelf and subjects are, and which shelves have nobody on "
            "them. It does not give you their dossiers, deliberately, and reading somebody "
            "else's is not part of this job.",
            "A dossier is one paragraph and needs no line breaks, so one quoted argument "
            "carries it. You cannot write a file and you cannot pipe.",
            "Nothing you do here ranks one writer against another and nothing casts a writer "
            "on a book. You draft one dossier for the shelf you were given.",
        ],
    }


def _shelves(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, list[str]]]:
    shelves: dict[str, dict[str, list[str]]] = {
        slug: {"accepted": [], "proposed": []} for slug in SPECIALIZATIONS
    }
    for row in rows:
        shelf = shelves.setdefault(
            row["specialization"], {"accepted": [], "proposed": []}
        )
        shelf.setdefault(row["status"], []).append(row["name"])
    return shelves


def show(
    rows: Sequence[Mapping[str, Any]],
    all_rows: Sequence[Mapping[str, Any]],
    *,
    with_dossier: bool = False,
) -> dict[str, Any]:
    """Who this installation holds, which shelf each was drafted for, and which have nobody.

    **The dossier's prose is off by default, and that is a containment choice rather than a
    terseness one.** Showing four one-paragraph exemplars in the same form to a model asked to
    write a fifth produces that form a fifth time, which would be the `single-image` control
    smuggled into the arms that are supposed to differ from it. Names, shelves and interests are
    what duplicate-avoidance actually needs. `--dossier` adds the text and makes reading a
    colleague's dossier a deliberate act the transcript records, which is the same move
    `Writer.render` already makes by sending prose and never the interest list.

    `cast` lists the four compiled writers by **name and interests only, never a dossier**, so a
    recruit does not land on an occupied shelf by accident. `BUILTIN` is not listed at all: those
    ten are a probe fixture rather than writers on a shelf, and `--writer geology` has never
    drafted anything. Their names stay reserved all the same.

    **`note` is not in the payload, and its absence is the same rail one level over.** An
    operator annotation is where a preference gets written down — *"this one came out too grim,
    the next should go lighter"* is exactly the sentence somebody would put there — and a view a
    generative agent holds is where that preference would reach another generative agent, with
    no decision row and nothing measured behind it. That is the channel `recruiter`'s containment
    paragraph exists to refuse, and it is cheaper to have no field for it than to argue about
    what people should write in one. The cost, stated: a note is written and read back through
    the store, not through this view.
    """
    listed: list[dict[str, Any]] = []
    for row in rows:
        entry = {
            "writer_id": row["writer_id"],
            "name": row["name"],
            "status": row["status"],
            "specialization": row["specialization"],
            "shape": row["shape"],
            "interests": list(row["interests"]),
            "proposed_at": row["proposed_at"],
            "accepted_at": row["accepted_at"],
            # The moment, not the grounds. **The refusal's reason stays out of this payload for
            # the same rail that keeps `note` out**, one paragraph up: a reason is where a
            # preference gets written down — *"too grim, go lighter"* — and this is the view a
            # generative agent holds. The timestamp is a fact; the sentence is a channel. The
            # reason is written and read back through the store, never through here.
            "refused_at": row["refused_at"],
        }
        if with_dossier:
            entry["dossier"] = row["dossier"]
        listed.append(entry)
    shelves = _shelves(all_rows)
    return {
        "writers": listed,
        "cast": [
            {
                "name": writer.name,
                "writer_id": writer.writer_id,
                "interests": list(writer.interests),
            }
            for writer in writers_domain.CAST.values()
        ],
        "shelves": shelves,
        "unstaffed": [
            slug
            for slug in SPECIALIZATIONS
            if not shelves[slug]["accepted"] and not shelves[slug]["proposed"]
        ],
    }


def check(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """What is wrong with this roster by arithmetic, never by taste.

    `world.check`'s boundary, inherited word for word: every complaint below is arithmetic or
    membership over the stored rows, and none is a judgment about whether a dossier is any good.
    A view that could say one writer is better than another is the thing this whole subsystem is
    built not to have.

    **The census never produces a complaint** and the two halves are separated for a measured
    reason: `machinery_words` would refuse `writers.BUILTIN["volcanology"]` on *"the standing
    argument"*, and `appetite_markers` is calibrated on four dossiers that are all one shape.
    Both are numbers to look at; neither is a gate, and `appetite_markers`' docstring says why
    turning it into one would remove the arm's variable.
    """
    complaints: list[str] = []
    accepted_names: dict[str, str] = {}
    census: dict[str, dict[str, Any]] = {}
    for row in rows:
        # **A refused writer is nobody's problem, and this exit is what makes refusal terminal
        # rather than decorative** (stage-0 §149). An illegal dossier is the row an operator is
        # most likely to turn down, and it is also the row `legal_dossier` complains about; if
        # refusal did not silence the complaint, `roster check` would exit 2 forever over a
        # decision that has already been taken, and the only way to quiet it would be deleting
        # the row — which is the retraction this schema exists to refuse.
        if row["status"] == writers_domain.RosterStatus.REFUSED.value:
            continue
        writer_id = row["writer_id"]
        dossier = row["dossier"]
        try:
            writers_domain.legal_dossier(dossier)
        except writers_domain.IllegalDossier as error:
            complaints.append(f"{row['name']} ({writer_id}): {error}")
        try:
            writers_domain.refuse_reserved_name(row["name"])
        except writers_domain.IllegalDossier as error:
            complaints.append(f"{writer_id}: {error}")
        expected = writers_domain.writer_id_for(
            name=row["name"],
            dossier=dossier,
            interests=tuple(row["interests"]),
            exemplar_digest=row["exemplar_digest"],
        )
        if expected != writer_id:
            complaints.append(
                f"{row['name']} ({writer_id}) does not address its own content; something "
                f"edited a stored column in place and it should address to {expected}"
            )
        if len(set(row["interests"])) != len(row["interests"]):
            complaints.append(f"{row['name']} ({writer_id}) lists a subject twice")
        if row["specialization"] not in SPECIALIZATIONS:
            complaints.append(
                f"{row['name']} ({writer_id}) was drafted for {row['specialization']!r}, "
                "which is not one of the twelve shelves"
            )
        if row["shape"] not in writers_domain.DOSSIER_SHAPES:
            complaints.append(
                f"{row['name']} ({writer_id}) carries shape {row['shape']!r}, which is not a "
                "dossier shape, so it is in no arm of the registered contrast"
            )
        if row["status"] == writers_domain.RosterStatus.ACCEPTED.value:
            if row["name"] in accepted_names:
                complaints.append(
                    f"{row['name']} answers to two accepted writers, {accepted_names[row['name']]}"
                    f" and {writer_id}; `--writer {row['name']}` has no one answer"
                )
            accepted_names[row["name"]] = writer_id
        census[writer_id] = {
            "appetite_markers": list(appetite_markers(dossier)),
            "machinery_words": list(machinery_words(dossier)),
            # **`voice.exhibition_census` rather than a count of the character here.** This line
            # used to hold the mark as a literal, which made it a second home for the one thing
            # `voice.EXHIBITION_MARKERS` is now the home of — and a home that could only ever
            # report the axis somebody thought of in 2026-08. A newly registered axis with a mark
            # now appears in this payload without anybody editing it.
            "exhibited": voice_domain.exhibition_census(dossier),
            "dossier_words": len(dossier.split()),
        }
    shelves = _shelves(rows)
    return {
        "complaints": complaints,
        "ok": not complaints,
        "writers": len(rows),
        "proposed": sum(
            1
            for row in rows
            if row["status"] == writers_domain.RosterStatus.PROPOSED.value
        ),
        "accepted": len(accepted_names),
        "refused": sum(
            1
            for row in rows
            if row["status"] == writers_domain.RosterStatus.REFUSED.value
        ),
        "unstaffed": [
            slug
            for slug in SPECIALIZATIONS
            if not shelves[slug]["accepted"] and not shelves[slug]["proposed"]
        ],
        "census": census,
    }


def rehearse(dossier: str) -> dict[str, Any]:
    """Read a candidate dossier back and say what would refuse it. Writes nothing, costs nothing.

    **This is the command that removes the reason to probe.** Serial Pilot 7's finding was that
    an agent refused by a tool works around the tool rather than saying what it meant, and that
    the fix is a tool fix rather than a rule: `world declare` warns instead of refusing because a
    world is transiently incoherent by nature. A dossier is not — it arrives whole in one
    command, and no companion record can make a legal one look illegal — so `roster declare`
    refuses, and this is where an agent finds out for free first.

    The verdict is in the payload rather than in the exit code, and `cmd_roster` returns
    `EXIT_OK` even when `legal` is false. A rehearsal that exits nonzero is a rehearsal an agent
    stops running.
    """
    refusal: str | None = None
    try:
        writers_domain.legal_dossier(dossier)
    except writers_domain.IllegalDossier as error:
        refusal = str(error)
    return {
        "legal": refusal is None,
        "refusal": refusal,
        "axes_named": list(prose_axes_named(dossier)),
        # **`axes_carried` is new and `axes_named` changed meaning on 2026-08-28**, and an agent
        # reading this payload should be told the truth rather than a convenient one. Before the
        # split, an em-dashed dossier came back as `axes_named: ["em_dash"]` — it had named
        # nothing. `legal` and `refusal` are unchanged: the same dossiers are refused, for the
        # same reason, said correctly.
        "axes_carried": list(voice_domain.axes_exhibited(dossier)),
        "words": len(dossier.split()),
        "has_em_dash": "em_dash" in voice_domain.axes_exhibited(dossier),
        "has_line_break": "\n" in dossier.strip(),
        "appetite_markers": list(appetite_markers(dossier)),
        "machinery_words": list(machinery_words(dossier)),
    }


__all__ = [
    "EXAMPLE_DECLARE",
    "SHAPES",
    "SPECIALIZATIONS",
    "VIEWS",
    "appetite_markers",
    "check",
    "machinery_words",
    "rehearse",
    "reserved_name",
    "show",
    "vocabulary",
]
