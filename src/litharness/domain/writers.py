"""The Writer role: a named professional who drafts, and never says whether a draft is good.

Companion to `domain/directors.py`, and the divergences from it are the interesting part. A
Director acts *before* prose exists and emits directives; a Writer is the role that has been
acting all along — every scene in this system was drafted by somebody — and has never had an
identity. `application/planner.py`'s system message was the whole of the drafter's self: *"You
are drafting one scene of a novel"*, plus mechanics. Nothing named a person, a career, a taste or
a subject.

**The prior says this will probably be decorative, and it is stated here rather than discovered
later.** §89.1 measured `qwen3:14b` returning one distinct answer vector across four personas,
byte-identical. §83 found register invariant to simulated phenomenology. §77 measured
persona-to-passage sum-of-squares ratios of 0.0028, 0.0071 and 0.0342 while changing *the
question* by one word moved a rate ten points. A roster that has not been checked is §89.1 in a
fourth costume.

What makes this design not simply that experiment again: **those were personas held to make a
judgment, and a Writer makes none.** Inertness in a judging persona silently converts N opinions
into one and the panel still reports N. Inertness in a drafting persona is directly measurable
against the drafts themselves, at no model cost beyond prose that was going to be generated
anyway. So the prior does not veto the roster — it dictates the shape of the dossier
(`legal_dossier`, and *deep in domain, shallow in demography*) and the gate that must clear before
any writer comparison may be reported (`distinctness`, reused from `directors` rather than
reimplemented).

See `plan/writer-roster.md`. Nothing here casts, scores, or reads reception: R3 says a writer
never judges, and a writer that did would be a judge in a hat.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256

from litharness.domain import house
from litharness.domain.directors import (
    IllegalBrief,
    prose_axes_named,
)
from litharness.domain.text import canonicalize

#: Prefix for a writer's content address. `wtr-` rather than `dtor-`: the two are different roles
#: in different tables, and a shared prefix would invite a shared lookup.
WRITER_ID_PREFIX = "wtr-"

#: Separator inside the addressed material. `\x00` cannot occur in canonicalised text, so no
#: dossier can forge a field boundary by containing the separator.
_FIELD = "\x00"

#: Separator between interests inside their own field, distinct from `_FIELD` so that
#: `("a", "b")` and `("a\x00b",)` cannot address to the same writer.
_ITEM = "\x1f"


class RosterStatus(enum.StrEnum):
    """Where a stored writer stands, and the gap between the two members is a person.

    Lowercase values because every status column in this schema stores lowercase; `PROPOSED`
    and `ACCEPTED` in `plan/handoff-writer-recruiter.md` are member names rather than column
    values. The enum lives in the domain because the *rail* does — a Recruiter proposes and
    only an operator's decision row accepts — and an adapter that invented its own strings
    would be the place that rail could quietly lose a member.
    """

    PROPOSED = "proposed"
    ACCEPTED = "accepted"


#: The dossier's form, as a **variable rather than a fix**. All four `CAST` dossiers are built
#: the same way and each writer opens every empty-brief listing on the beat its own dossier
#: names; the counts are `plan/reader-read-5.md` §4.3's. Whether that is caused by the dossier
#: carrying *one* love or by its carrying an *opening beat* is the question a registered
#: listing arm exists to separate, so recruits are drafted in three deliberate forms and
#: nothing standardises on one by default.
#:
#: **The two that make the contrast are `several-with-beat` and `several-no-beat`**: the same
#: several loves at category level, differing only in whether one of them is phrased as a scene
#: the story opens on. `single-image` reproduces the shipped form and varies *two* factors
#: against the other two — one love and a beat — so it is the on-disk control and is not an arm
#: of the contrast. That labelling is the whole reason there are three rather than two: a
#: two-cell design that moved count and beat together could not say which one moved the result.
#:
#: Here rather than in a SQL `CHECK` because SQLite cannot alter one without rebuilding the
#: table, and a fourth form should cost a line of Python rather than migration 036.
DOSSIER_SHAPES: frozenset[str] = frozenset(
    {"single-image", "several-with-beat", "several-no-beat"}
)


class IllegalDossier(IllegalBrief):
    """A dossier a Writer is not licensed to carry.

    Subclasses `IllegalBrief` deliberately: R1 is *inherited* from the Director's rail rather
    than restated, so a caller that already refuses illegal briefs refuses illegal dossiers by
    the same `except`. The rule is one rule — a role may name what it knows, never what good
    prose is — and two exception types would let it drift into two rules.
    """


def legal_dossier(text: str) -> None:
    """Raise unless `text` says what a writer knows rather than what good prose is.

    **R1, and it matters more here than it does for a brief.** A brief reaches the narrative
    planner and the writer sees its consequences; a dossier rides in the system message of *every
    scene call*, beside `feedback` — which is the one channel `plan/reader-judge-loop.md` §2.1
    guards with a four-step admission path. One sentence in a dossier about sentence rhythm,
    punctuation, or how much interiority belongs on a page injects a prose axis into every prompt
    for a whole book, with no counter, no validation and no reader behind it.

    Not hypothetical: `em_dash`'s own pre-registered hypothesis is still VOID with the estimate
    leaning *toward* the mark (§78.3), so a dossier saying "she never could stand a dash" would
    assert as premise the thing the loop exists to test.

    The guard is `directors.prose_axes_named` unchanged — narrow, high-precision vocabulary, and
    a paraphrase gets through. No regex fixes that, and the trade is stated in `_CRAFT_INSTRUCTION`
    rather than hidden here. What it buys is that the axes the loop is **actively measuring**
    cannot be pre-empted by a dossier that says so plainly.
    """
    if not text.strip():
        raise IllegalDossier("a writer with no dossier is not a writer; it is the anonymous call")
    named = prose_axes_named(text)
    if named:
        raise IllegalDossier(
            f"this dossier names the registered prose axis/axes {', '.join(named)}. A dossier "
            "says what this writer knows the inside of; what good prose is comes from readers "
            "through the axis admission path (plan/reader-judge-loop.md §2.1), never from a "
            f"drafting prompt — {named[0]}'s own hypothesis is still under test"
        )


def writer_id_for(
    *,
    name: str,
    dossier: str,
    interests: Sequence[str],
    exemplar_digest: str | None = None,
) -> str:
    """Content address over the writer itself, so a roster cannot drift under the books it wrote.

    **`exemplar_digest` participates from the first mint, and that is the whole point of it being
    here before anything populates it** (`plan/writer-roster.md` §3.1). Two different id changes
    have to stay distinguishable:

    * populating an exemplar later *should* mint a new writer, because an exemplar changes what
      the writer drafts and that is identity rather than drift;
    * adding the *field* later would re-address every writer that already existed without changing
      what any of them does — a schema re-mint, which is pure loss.

    Including it now, canonically empty, buys the first and avoids the second. `None` addresses as
    the empty string; since the roster is empty as of 2026-08-20 there is nothing to re-mint.
    """
    # **The interest field is length-prefixed, because joining alone is forgeable.** Without the
    # count, `("a", "b")` and `("a\x1fb",)` join to the same bytes and address to the same
    # writer — two different rosters, one id. Measured, not reasoned about: the first version of
    # this function returned equal ids for that pair. A content address that can collide is the
    # one kind of defect this scheme exists to make impossible.
    subjects = tuple(canonicalize(subject) for subject in interests)
    material = _FIELD.join(
        (
            name,
            canonicalize(dossier),
            _ITEM.join((str(len(subjects)), *subjects)),
            exemplar_digest or "",
        )
    ).encode()
    return f"{WRITER_ID_PREFIX}{sha256(material).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class Writer:
    """One named professional: what they know the inside of, and nothing about good prose."""

    writer_id: str
    name: str
    #: The backstory: career, training, the work they did before this, how they came to it, which
    #: questions in the subject still bother them. **Deep in domain, shallow in demography** — no
    #: age, no hometown, no commute. `research/quality-measurement/personas.py` opens with why:
    #: a persona described demographically elicits *stereotype performance*, a model writing what
    #: it thinks that person sounds like, which is a different behaviour wearing the same words.
    dossier: str
    #: Named subjects this writer knows from the inside, ordered. The roster's actual variable:
    #: professional competence is held constant across every writer per the directive, so nobody
    #: is new, struggling, or bad at this. Craft is not what varies here.
    interests: tuple[str, ...] = ()
    #: **Socket, deliberately unpopulated.** Own-generated only if ever admitted — third-party
    #: prose here is leak-audit class, and this is the most-repeated text in the system. Admission
    #: sits on R1's boundary, because an exemplar demonstrates what good prose looks like, which
    #: is exactly what a dossier may not assert. An operator act, not a build decision.
    exemplar_digest: str | None = None
    #: Operator annotation. Never sent to a model, and therefore not addressed either — an
    #: annotation that minted a new writer would make note-keeping a versioning event.
    note: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        legal_dossier(self.dossier)
        if not self.name.strip():
            raise IllegalDossier("a writer needs a name; provenance is the whole point")
        if len(set(self.interests)) != len(self.interests):
            raise IllegalDossier(f"{self.name} lists a subject twice: {self.interests}")
        expected = writer_id_for(
            name=self.name,
            dossier=self.dossier,
            interests=self.interests,
            exemplar_digest=self.exemplar_digest,
        )
        if self.writer_id != expected:
            raise IllegalDossier(
                f"writer_id {self.writer_id} does not address this writer"
            )

    def render(self) -> str:
        """The dossier as it reaches a drafting call, and nothing else reaches one.

        `name` and `interests` are provenance and indexing; the model receives the dossier's
        prose. Sending the interest list as a bare enumeration would hand the model a checklist,
        and a checklist is what turns "knows the inside of tides" into "mentions tides" — which is
        G3's contamination failure arriving by invitation rather than by accident.
        """
        return self.dossier.strip()


def build(
    name: str,
    dossier: str,
    *,
    interests: Sequence[str] = (),
    exemplar_digest: str | None = None,
    note: str = "",
) -> Writer:
    """A writer from its own words, with the id derived rather than supplied."""
    return Writer(
        writer_id=writer_id_for(
            name=name,
            dossier=dossier,
            interests=tuple(interests),
            exemplar_digest=exemplar_digest,
        ),
        name=name,
        dossier=dossier,
        interests=tuple(interests),
        exemplar_digest=exemplar_digest,
        note=note,
    )


#: The first slate: **examples rather than recommendations**, the same status `directors.BUILTIN`
#: carries. Nothing here claims any of them is a good writer for any book; which roster is worth
#: running is an operator act, the way admitting a fixture family is (§84).
#:
#: **Two pairs are deliberately adjacent, and that is the load-bearing part of the slate.** Ten
#: far-apart subjects can only ask whether binding happens at all — a single bit — and a far-pair
#: pass has fooled this project before (§77's persona ratios looked like separation until one word
#: of question change moved a rate ten points). `volcanology` neighbours `geology`, and
#: `estuarine` neighbours `marine`: same tradition, same instruments, different hazard and
#: different timescale. The registered prediction is that far pairs separate more than near pairs
#: and near pairs still separate more than a writer against itself. Far and near reading alike
#: means the label bound and the subject did not.
BUILTIN: Mapping[str, Writer] = {
    writer.name: writer
    for writer in (
        build(
            "geology",
            "You spent eleven seasons mapping ground nobody had mapped, most of them above four "
            "thousand metres, before you wrote anything anyone read. You know what a slope does "
            "in the hour before it goes, and how long it takes to get a body down from one. You "
            "learned to read rock the way other people read weather: not as scenery but as a "
            "record of pressure and time, and you cannot look at a cut bank without reading it. "
            "What still bothers you is how much of what you were taught about a formation turned "
            "out to be somebody's guess repeated until it hardened.",
            interests=("field geology", "high-altitude survey"),
            note="example: earth science, far anchor; neighbour of volcanology",
        ),
        build(
            "volcanology",
            "You worked eruption response for nine years, running instruments on a flank "
            "that might clear in a month or might not, plus the standing argument with "
            "people whose town it "
            "was about what the numbers meant. You know the sound of a swarm on a seismometer "
            "before the count comes back, and you know what it costs to be the one who says "
            "evacuate and be wrong. Gas ratios, tilt, the specific dishonesty of an average. "
            "What still bothers you is that the ones that killed people were rarely the ones "
            "that looked dangerous.",
            interests=("volcanology", "eruption monitoring"),
            note="example: earth science, NEAR neighbour of geology, graded binding probe",
        ),
        build(
            "marine",
            "You did fourteen long-voyage seasons, most of them out of sight of anything, "
            "counting and tagging and losing gear to weather. You know how a ship smells on day "
            "forty and what happens to a watch schedule when the science goes wrong at three in "
            "the morning. You think about scale constantly: what a transect can and cannot see, "
            "and how much of an ocean is inferred from a line of dots. What still bothers you is "
            "how much of the record is where the ships happened to go.",
            interests=("marine biology", "long-voyage fieldwork"),
            note="example: marine, far anchor; neighbour of estuarine",
        ),
        build(
            "estuarine",
            "You worked coastal survey and fisheries assessment, which means you worked with "
            "people whose livelihood was the number you were about to publish. Tidal creeks, "
            "salinity wedges, a nursery ground that moves. You know how a stock assessment is "
            "actually assembled and where the uncertainty is buried, and you have sat in the "
            "room when the quota came down. What still bothers you is that the fishers were "
            "usually right about where the fish were and never right about why.",
            interests=("estuarine ecology", "fisheries survey"),
            note="example: marine, NEAR neighbour of marine, graded binding probe",
        ),
        build(
            "logistics",
            "You moved things for a living, which meant fuel, ammunition, food and people, "
            "across distances where the plan and the road disagreed. You know that an army "
            "is a queue and that the interesting failures are never at the front. Load "
            "plans, throughput, the difference between what a bridge is rated for and "
            "what crosses it. What still "
            "bothers you is how often the shortage was somewhere in the system all along and "
            "nobody could see it because nobody owned the whole picture.",
            interests=("military logistics", "supply"),
            note="example: far",
        ),
        build(
            "tenure",
            "You read manor rolls for a decade: who held what of whom, what was owed at "
            "Michaelmas, which fields went out of cultivation and in whose lifetime. You know "
            "that most of the past was agricultural and that most agricultural history is a "
            "dispute about boundaries. You think in seasons and in obligations that outlive the "
            "people who made them. What still bothers you is how much of the record was written "
            "by the party with an interest in it.",
            interests=("medieval agriculture", "land tenure"),
            note="example: far",
        ),
        build(
            "orbital",
            "You flew payload operations, which is to say you spent years in a room where "
            "everything that happens has already happened eight minutes ago. You know how a "
            "burn is planned and how a plan survives contact with a thruster that under-performs "
            "by two percent. Windows, margins, the tyranny of the ephemeris. What still bothers "
            "you is how many procedures exist because of one incident nobody involved will "
            "discuss.",
            interests=("orbital mechanics", "flight operations"),
            note="example: far",
        ),
        build(
            "forensic",
            "You traced money for a living, which is mostly reading things people wrote when "
            "they thought nobody would. You know what a ledger looks like when it has been "
            "tidied and what a legitimate business looks like when it is having a bad year, and "
            "you know that the difference is smaller than anyone comfortable would like. What "
            "still bothers you is how many of them were not clever, only patient, and how long "
            "patience works.",
            interests=("forensic accounting", "fraud"),
            note="example: far",
        ),
        build(
            "linguistics",
            "You worked on languages with few speakers and worse records, reconstructing what "
            "must have been said from what survived being written down by somebody who did not "
            "speak it. You know how a sound change propagates and how a translation decides "
            "things the original left open. What still bothers you is that the confident "
            "reconstructions and the shaky ones are printed in the same typeface.",
            interests=("historical linguistics", "translation"),
            note="example: far",
        ),
        build(
            "outbreak",
            "You did field epidemiology, the part that is interviews and shoe leather rather "
            "than models. You know what a case definition does to a curve and how quickly a "
            "number becomes a policy and then becomes a fact. You have been the person asking a "
            "family what they ate. What still bothers you is how much of the response was "
            "decided in the first week on the worst information anyone would have.",
            interests=("epidemiology", "outbreak fieldwork"),
            note="example: far",
        ),
    )
}



#: **The cast that writes books, as distinct from `BUILTIN`, which measures whether a dossier
#: binds at all.** Those ten are earth science, marine science, orbital operations and
#: epidemiology in near/far subject pairs, because the probe needed a graded distance. Not one of
#: them reads the genre this project publishes in, and none had ever reached a prompt. They stay
#: where they are: a fixture that moves when the product wants a writer has stopped being a
#: fixture.
#:
#: **What varies here is appetite — never craft, and no longer a profession.** The first
#: version of this cast named four real careers (a kitchen, a climbing wall, veterinary
#: surgery, competitive games) and each writer promptly set a book inside their own day
#: job: collar grades in a restaurant, coat colours on a mountain, cords in a stabling
#: yard. That is G3 contamination, which this module's own docstring names and warns
#: about — a writer who knows metallurgy from the inside is being asked to write *this*
#: book, not a book about metallurgy — and it produced four worlds with no magic in them.
#: A dossier's variable is what this person reads the genre for and loves to write, which
#: is a real writer's bio and not a setting the book can be dropped into.
#: `legal_dossier` enforces the second half, and the first half is the point: the retired
#: Forge's private rules were assertions about what the genre's reader wants, addressed to
#: nobody in particular. A professional who reads progression fantasy for training arcs does
#: not need to be
#: told that an academy is furniture the reader came for. That is the operator's standing note
#: about hardcoding what a professional already knows, applied where it is cheapest to apply.
#:
#: **The leak reproduced one level up, measured 2026-08-28** (`plan/reader-read-5.md` §4.3,
#: which owns the counts). Making the variable appetite rather than profession stopped the day
#: job leaking and started the opening beat leaking: every one of these four names an inciting
#: beat as well as an appetite, and each writer draws that beat in every listing it has drawn.
#: *"You want a reader to finish a chapter
#: wanting to try something"* is an appetite and locks nothing; *"the first message nobody asked
#: for"* is an image of how a story opens and locks everything. These four are left exactly as
#: they are — they are the controls the roster is read against — and `DOSSIER_SHAPES` is where
#: the alternative gets drafted instead.
CAST: Mapping[str, Writer] = {
    writer.name: writer
    for writer in (
        build(
            "ferreira",
            "You write the kind of serial where an ordinary world is pulled into something "
            "vastly larger and everybody finds out at the same moment. What you love is the "
            "hour the rules become visible: the first message nobody asked for, the first "
            "build that should not work and does. You "
            "think of power as something people discover and abuse rather than something they "
            "are handed. You want a reader to finish a chapter wanting to try something.",
            interests=("system apocalypse", "builds and broken skills"),
            note="cast: integration, the system, discovered exploits",
        ),
        build(
            "halloran",
            "You write people who wake up somewhere impossible and have to survive the "
            "afternoon. What you love is the first hour of a new world: the first monster, "
            "the first spell that goes wrong, the first thing somebody can do that they "
            "could not do yesterday, and the slow widening after it, where the map gets "
            "bigger every time "
            "the character does. You have no patience for a hero who arrives finished. You want "
            "the reader to want the next power before the character knows it exists.",
            interests=("portal fantasy", "dungeons and first delves"),
            note="cast: isekai, the first delve, the widening map",
        ),
        build(
            "vance",
            "You write reincarnation: somebody who died badly and woke up as something else, "
            "sometimes not even human. What you love is the bond: a beast that should have "
            "killed the main character and is theirs instead, a dragon that is nobody's mount, "
            "a familiar with opinions. You are interested in what a person will spend on another "
            "living thing and what it costs them. You want the reader to be frightened for "
            "somebody who is not the hero.",
            interests=("reincarnation", "beasts, dragons and bonds"),
            note="cast: reincarnation, monsters, companions",
        ),
        build(
            "okonjo",
            "You write cultivation and academy serials: sects, masters worth impressing, rivals "
            "who are genuinely better for a while, and breakthroughs that arrive at the worst "
            "possible moment. What you love is the shape of getting stronger in front of other "
            "people, the technique somebody is not supposed to have, the tournament that goes "
            "wrong, the teacher whose reasons are their own. You want a reader to feel the room "
            "change when the main character finally does the thing.",
            interests=("cultivation", "academies, sects and tournaments"),
            note="cast: cultivation, masters, breakthroughs",
        ),
    )
}


#: Names a stored writer may not take, because a stored row resolves **before** these do.
#: `CAST` are the four controls the roster is read against, and `BUILTIN` are the ten the
#: distinctness probe reads. **Not every book on disk was written by one of them** — §139.1
#: records that every scene this system drafted before 2026-08-25 was written by nobody, and
#: the anonymous no-writer arm is still what `--writer` unset returns. That is the point: a
#: store row wearing one of these names would not fail, it would quietly answer instead,
#: which is the worst outcome available to a run whose whole question is whether the arms
#: differ — `_selected_writer` already refuses an unknown name loudly for exactly that reason.
RESERVED_NAMES: frozenset[str] = frozenset(BUILTIN) | frozenset(CAST)


def refuse_reserved_name(name: str) -> None:
    """Raise unless `name` is free for a stored writer to take.

    `IllegalDossier` is a stretch for a name collision — it is documented as *a dossier a Writer
    is not licensed to carry* — and it is chosen for the reason that type subclasses
    `IllegalBrief` at all: one rule, one `except`. A caller that already refuses an illegal
    dossier refuses an illegal admission by the same clause, and two exception types would let
    "a writer this roster may not hold" drift into two rules.
    """
    if name.strip() in RESERVED_NAMES:
        raise IllegalDossier(
            f"{name!r} is a compiled writer's name. The four in CAST are the controls the "
            "roster is read against and the ten in BUILTIN are the distinctness probe; a "
            "stored row answering to one of them would shadow a control rather than fail"
        )


def system_for(task: str, writer: Writer | None = None) -> str:
    """One system message for any role that writes for a reader: who, then the floor, then the job.

    **The Architect and the drafter were two prompt stacks, and `domain/house.py` records what
    that cost.** Five rule changes went into the Architect, measured and working; the first book
    written on that world opened on a call-centre shift rendered step by step, because the writer
    had never seen any of them. `with_house_rules` fixed the floor and left the rest doubled —
    the Architect still had its own identity, its own rule essay, and no idea who was going to
    write the book. This is the other half: the same person, the same floor, a different job.

    **Order is who, then rules, then task**, which is `planner.render_prompt`'s order unchanged:
    the dossier first because it is who is writing, the task last because the last thing in a
    prompt is the thing a model acts on.

    `None` renders exactly what every call site rendered before a cast existed, so the no-writer
    control stays byte-identical and is what the roster is read against.
    """
    body = house.with_house_rules(task)
    return f"{writer.render()}\n\n{body}" if writer is not None else body


__all__ = [
    "BUILTIN",
    "CAST",
    "DOSSIER_SHAPES",
    "RESERVED_NAMES",
    "WRITER_ID_PREFIX",
    "IllegalDossier",
    "RosterStatus",
    "Writer",
    "build",
    "legal_dossier",
    "refuse_reserved_name",
    "system_for",
    "writer_id_for",
]
