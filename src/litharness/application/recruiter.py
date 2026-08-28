"""The Recruiter: an agent that drafts one writer for one shelf, and can put nobody on a roster.

**Why the roster needed a way to grow, in the operator's words (2026-08-28):** *"Can there be
some internal recruiter system, which will generate more varied and useful writers? i aknowledge
i never asked for Light Fantasy, but having diverse writers would be an asset to our project."*

**And why the roster is where the variety has to come from.** The premise lock is in the dossier
text itself. Each of the four cast dossiers names an inciting beat as well as an appetite, and
its writer draws that beat in every listing it has ever produced — ferreira's dossier says *"the
first message nobody asked for"* and its listings open on a message reaching every screen at
once. The counts are `plan/reader-read-5.md` §4.3's and stay there. The previous fix made the
dossier's variable *appetite* rather than *profession*, and the leak reproduced one level up:
the day job stopped leaking and the opening beat started. So variety is a roster property before
it is a prompt property, and growing a roster is generative work, which is the kind the Architect
pattern already contains.

**The containment is the tool surface, and here it is enumerated rather than wildcarded.**
When this shipped, `world_agent.ALLOWED_TOOLS` was the single glob `Bash(litharness world:*)`,
and `world accept` is itself a `litharness world ...` command — so on that point the
Architect's containment rested on the last line of its tool essay rather than on its allowance.
§146.9 measured that discrepancy real on 2026-08-28 (`claude` 2.1.236 ran `world accept` under
the glob) and the Architect's allowance is enumerated now too. `plan/director-role.md` calls a
property carried by who happens to hold the pen the laundering path. Four strings rather than
one is the whole cost of not repeating it here, and `cmd_roster` refuses acceptance outright
while a recruit run is in flight, which is a second lock that does not depend on how a
`Bash(prefix:*)` rule is matched.

**This role wears no dossier of its own and carries no house rules, and both absences are
decisions.** A cast writer drafting a colleague's dossier is the premise lock at one remove, so
`writers.system_for` is never called and `writer=None` — the anonymous control — is what every
call made before a cast existed. The house floor is absent for R1's reason rather than by
oversight: `tests/test_architecture.py` gives the criterion for that list, a role producing
reader-facing prose belongs on it, and this role's output is a bio nobody reads that is rendered
into the system message of every scene call. `house.CLARITY` and `house.READER` are craft
doctrine; `legal_dossier` refuses a dossier that names what good prose is; and §138 measured a
rule's affirmative half coming back as a verbal formula in the output. A Recruiter told *"every
sentence can be followed the first time it is read"* is one paraphrase away from writing that
into a dossier, where `prose_axes_named` cannot see it and it rides every scene call for a whole
book. The floor reaches the drafting call once, through `system_for`, where the prose is.

**Nothing here ranks, and the boundary is precise rather than absolute.** The agent is told the
roster exists and is told to read it — `roster show` is in the allowance and `_TOOLS` points at
it — because a recruit that lands on an occupied shelf by accident helps nobody. What it is
never told is *who to be like or unlike*: asking a model to differ from four named writers is a
model preferring among writers, which §61(5) and §105.1 have no containment for. And what
`roster show` returns is names, shelves and subjects — **not dossier prose, and not operator
notes**. Four one-paragraph exemplars in one form, shown to a model asked to write a fifth, is
that form arriving a fifth time; across a twelve-shelf run it would be one arm of the registered
contrast leaking into the other. The withholding is in the view, where it is mechanical, rather
than in the prompt, where it would be a request.
"""

from __future__ import annotations

from collections.abc import Mapping

from litharness.application import roster
from litharness.domain import writers as writers_domain
from litharness.domain.generation import CompletionRequest

#: Frozen profiles, one per shape, so the arms are separable on the decision rows without
#: anybody having to join back to the roster table to find out which cell a call was in.
SINGLE_IMAGE_PROFILE = "recruiter.single-image.v0"
SEVERAL_WITH_BEAT_PROFILE = "recruiter.several-with-beat.v0"
SEVERAL_NO_BEAT_PROFILE = "recruiter.several-no-beat.v0"

_SHAPE_PROFILE: Mapping[str, str] = {
    "single-image": SINGLE_IMAGE_PROFILE,
    "several-with-beat": SEVERAL_WITH_BEAT_PROFILE,
    "several-no-beat": SEVERAL_NO_BEAT_PROFILE,
}

#: The whole allowance, **enumerated rather than wildcarded**, and the module docstring says
#: why. No string contains a comma, which matters because the CLI transport joins them with one.
#:
#: **`vocabulary` and `show` are named without a trailing argument pattern and the other two are
#: not**, and the asymmetry is deliberate rather than tidy. `check` needs `--dossier` to rehearse
#: and `declare` needs its flags; the two read views need no argument at all, and bare forms
#: return everything they have. What that buys, because an argument-free entry is matched exactly
#: rather than as a prefix, is that `roster show --dossier` — the flag that would hand one arm's
#: dossier prose to the other arm's recruit — is unreachable from inside a run. ~~We have not
#: verified which way that matcher goes~~ **Verified 2026-08-28 on `claude` 2.1.236 (§146.9):
#: under the allowance `Bash(litharness roster show)`, the command `litharness roster show
#: --dossier` was refused and the refusal recorded in the envelope's `permission_denials`. The
#: wall is a wall** — and the claim that held either way still holds: a narrower string can never
#: permit more than a wider one, and nothing in the prompt or the vocabulary invites the flag.
ALLOWED_TOOLS: tuple[str, ...] = (
    "Bash(litharness roster vocabulary)",
    "Bash(litharness roster show)",
    "Bash(litharness roster check:*)",
    "Bash(litharness roster declare:*)",
)

#: Binds nothing on the `claude -p` transport, which never reads it. It is here for a
#: Messages-API provider that does not currently serve this role, and it is recorded rather than
#: left to be read as a cap that is being enforced.
MAX_OUTPUT_TOKENS = 4000

_TOOLS = (
    "You draft this writer by running `litharness roster` at a shell. It is the only command "
    "you have.\n"
    "Start with `litharness roster vocabulary`, which names every field a writer declaration "
    "takes and the shape each one has, and `litharness roster show`, which lists who this "
    "installation already holds and which shelves have nobody on them.\n"
    'Then `litharness roster check --dossier "..."`, which reads a candidate back to you and '
    "says what would refuse it. It costs nothing and writes no record, so use it before you "
    "declare.\n"
    'Then `litharness roster declare NAME --dossier "..." --interest SUBJECT` once per '
    "subject, in order, and `--note`.\n"
    "Everything you declare is a proposal. Putting a writer on the roster is somebody else's "
    "act, so declare the writer this shelf needs and stop there."
)

#: The task, shape clause excluded. **The G3 failure is quoted as a result and never as a
#: rule**, which is `house`'s standing constraint learned three times on 2026-08-25: a rule may
#: say what fails, and it may not enumerate what succeeds. There is deliberately no affirmative
#: recipe for a good dossier anywhere in this text.
_RECRUIT = (
    "You are drafting one writer, for one shelf and no other: the shelf named below.\n\n"
    f"{_TOOLS}\n\n"
    "A writer is a name, two or three named subjects, and a dossier: a short paragraph saying "
    "what this person reads that shelf for and loves to write. It is an appetite and never a "
    "job they held. Four writers were once given careers instead, and each one set a book "
    "inside their own day job: collar grades in a restaurant, coat colours on a mountain, "
    "cords in a stabling yard, and four worlds with no magic in any of them. Somebody for cozy "
    "fantasy is a person who reads cozy fantasy, not an innkeeper.\n"
    "A dossier says nothing about how to write. Not a word on sentences, punctuation, rhythm, "
    "how much of somebody's thinking belongs on a page, or what makes prose good. That is "
    "refused rather than discouraged: the gate reads the dossier, names the axis it matched, "
    "and the writer never mints. The reason it is a refusal is that a dossier is sent again "
    "with every scene of every book that writer drafts, so one line of it about how to write "
    "would answer a question this project has open, in every prompt, with nothing to answer "
    "back.\n"
    "Write it to the writer, as you: You write, What you love is, You want a reader to. One "
    "paragraph, about eighty words.\n"
    "No dashes in it. The gate matches the mark itself and refuses the record whatever the "
    "sentence was doing, so a dossier with one in it never becomes a writer. Full stops, "
    "commas and colons.\n"
    "One lowercase surname for the name, and nothing else in that field."
)

#: The three deliberate forms. **No clause says which is better and none says what a good
#: dossier is**, because the point of the set is that nobody knows: a prompt that hinted would
#: settle by assertion the question a registered listing arm exists to measure.
#:
#: `several-with-beat` and `several-no-beat` are the contrast and differ in **one** thing,
#: whether a love is phrased as a scene a story opens on. `single-image` reproduces what the
#: four shipped dossiers do and differs from both in **two** things — one love, and a beat — so
#: it is the on-disk control and is not an arm.
#:
#: *"each of them a kind of story rather than a single scene"* is the clause doing the work in
#: `several-no-beat`: without it a model returns three vivid images instead of one, which is the
#: control's form three times over. *"none of them the centre"* blocks it from nominating one as
#: primary, which is the same form wearing a list.
_SHAPE_CLAUSE: Mapping[str, str] = {
    "single-image": (
        "Build the dossier on one image: the moment on this shelf that this writer would "
        "write again and again."
    ),
    "several-with-beat": (
        "Build the dossier on three or four separate loves rather than one, each of them a "
        "kind of story this writer reads this shelf for, and phrase one of them as a moment a "
        "story opens on."
    ),
    "several-no-beat": (
        "Build the dossier on three or four separate loves rather than one: different things "
        "this writer reads this shelf for, each of them a kind of story rather than a single "
        "scene, none of them a moment a story opens on, and none of them the centre."
    ),
}

#: The twelve shelves against the form each is drafted in, **fixed before any call was made**.
#: Four per cell. Assignment is a stated rule rather than a draw, and the rule exploits the
#: structure the operator's own slate happens to have:
#:
#: 1. the slate holds three near-duplicate pairs — (Light Fantasy, Cozy Fantasy),
#:    (Cultivation, Chinese Cultivation in English), (Isekai, Portal Fantasy) — and each is
#:    **split across the two contrast cells**, alternating direction by pair index so that
#:    which member goes first is not itself a factor. On those three pairs the shelf is
#:    approximately held while the shape varies, which is a partial within-shelf design at no
#:    extra recruits;
#: 2. **LitRPG Comedy takes the control**, because reproducing the shipped form on four more
#:    threat-forward shelves reproduces a result already on disk, and it is the one shelf left
#:    from the group the operator called light. That cell then asks the capability question:
#:    does the shipped form force a dark opening on a shelf that should not have one?
#: 3. the remaining five fill by slate position, the first two completing the contrast cells
#:    and the last three taking the control.
#:
#: **The limitation, stated with the design rather than after it**: shelf is held only on those
#: three pairs, the other six are confounded with cell, and the residual difference inside a
#: near pair is not zero. Breaking that needs a second dossier per shelf in the opposite cell,
#: which is twice the recruits.
SLATE: tuple[tuple[str, str], ...] = (
    ("light-fantasy", "several-with-beat"),
    ("cozy-fantasy", "several-no-beat"),
    ("litrpg-comedy", "single-image"),
    ("sci-fi", "several-with-beat"),
    ("dark-fantasy", "several-no-beat"),
    ("supernatural", "single-image"),
    ("cultivation", "several-no-beat"),
    ("chinese-cultivation", "several-with-beat"),
    ("historical", "single-image"),
    ("progression-fantasy", "single-image"),
    ("isekai", "several-with-beat"),
    ("portal-fantasy", "several-no-beat"),
)

#: The three near-duplicate pairs, named so the within-pair reading is a thing the code knows
#: about rather than something a later reader has to notice. Two of the three were produced by
#: accident under plain cycling; three of three are produced by the rule above, and the
#: difference is entirely whether it was written down first.
NEAR_PAIRS: tuple[tuple[str, str], ...] = (
    ("light-fantasy", "cozy-fantasy"),
    ("cultivation", "chinese-cultivation"),
    ("isekai", "portal-fantasy"),
)


#: Supplementary hires outside the registered arm. The operator, 2026-08-28, after reviewing
#: all twelve applications (seven signed, five refused): *"I was thinking we are lacking some
#: mystery, detective and historical specializations."* Mystery and detective are new shelves;
#: historical's gap is a refused recruit and takes a redraw on its existing shelf.
#:
#: **These are production hires, not cells.** §146's arm is the twelve above, 4/4/4, and its
#: readings exclude everything here. The shape is `several-no-beat` for all supplementary
#: hires, by a recorded production rule rather than a cell assignment: the structural audit
#: (reader-read-5 §4.3) identified the named opening beat as the premise-lock mechanism, and a
#: production hire wants the form the audit predicts locks least — a prediction §146 registers
#: and has not yet measured, which is why this is a default and not a finding.
SUPPLEMENTARY: tuple[tuple[str, str], ...] = (
    ("mystery", "several-no-beat"),
    ("detective", "several-no-beat"),
    ("historical-portal-fantasy", "several-no-beat"),
)


def shape_for(specialization: str) -> str:
    """The form this shelf is drafted in, from `SLATE` then `SUPPLEMENTARY`. Raises for an
    unknown shelf."""
    for slug, shape in (*SLATE, *SUPPLEMENTARY):
        if slug == specialization:
            return shape
    raise ValueError(
        f"{specialization!r} is not a shelf this roster admits; the shelves are "
        f"{', '.join(roster.SPECIALIZATIONS)}"
    )


def render_recruit_request(specialization: str, *, shape: str) -> CompletionRequest:
    """One recruit: one shelf, one form, holding the roster's read views and declare.

    **The shelf reaches the prompt half and never the system half**, and it arrives as *"The
    shelf this writer is for"* rather than as what a book is about. §136 measured the two words
    *progression fantasy* outweighing every rule in the prompt when a shelf label arrived under
    that heading; and a standing system instruction would give one shelf authority over every
    recruit this process makes.
    """
    if specialization not in roster.SPECIALIZATIONS:
        raise ValueError(
            f"{specialization!r} is not one of the twelve shelves; they are "
            f"{', '.join(roster.SPECIALIZATIONS)}"
        )
    if shape not in writers_domain.DOSSIER_SHAPES:
        raise ValueError(
            f"{shape!r} is not a dossier shape; the shapes are "
            f"{', '.join(sorted(writers_domain.DOSSIER_SHAPES))}"
        )
    return CompletionRequest(
        prompt=(
            "The shelf this writer is for:\n\n"
            f"{roster.SPECIALIZATIONS[specialization]}"
        ),
        system=f"{_RECRUIT}\n{_SHAPE_CLAUSE[shape]}",
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=_SHAPE_PROFILE[shape],
        call_class="generation",
        timeout_seconds=900.0,
        allowed_tools=ALLOWED_TOOLS,
    )


__all__ = [
    "ALLOWED_TOOLS",
    "MAX_OUTPUT_TOKENS",
    "NEAR_PAIRS",
    "SEVERAL_NO_BEAT_PROFILE",
    "SEVERAL_WITH_BEAT_PROFILE",
    "SINGLE_IMAGE_PROFILE",
    "SLATE",
    "render_recruit_request",
    "shape_for",
]
