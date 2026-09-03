"""The Architect as an agent with tools, rather than a schema filled in once before chapter one.

**The operator, 2026-08-24:** *"in what world would a one-shot structured call be a good idea
for writing a book... The world would obviously evolve and grow with every chapter"*, and
*"Architect Writers and readers should work together to make the world as interesting as
possible"*, and *"also to make sure everything stays coherent and present in the world"*.

What this replaces is the retired Forge: one 32,000-token structured call, K
worlds at a time, a person picking one, and then a world that never changed again for the rest
of the book. What it is instead is the same cast writer, holding `litharness world`, building
the world of the book they are about to write and coming back to it as the book grows.

**The containment is the tool surface and not a promise.** The allowance is the world suite
and nothing else — no file access, no other command — and everything `world declare` writes is
`PROPOSED`, because `worlds.world_record` mints it that way. So this agent can propose a world
and cannot install one; `world accept` is a separate act with a decision row behind it. That is
§5's "no subsystem mutates canon directly" kept through a named command rather than by refusing
the model a shell.

**The allowance enumerates every world command except `accept`, because the single glob did
not hold that line.** This shipped as `Bash(litharness world:*)`, and `world accept` is itself
a `litharness world ...` command — measured 2026-08-28 on `claude` 2.1.236 (§146.9): under the
glob, `litharness world accept` ran, so the Architect's inability to self-accept rested on the
prompt's last line and nothing else. The same probes measured that an enumerated allowance is
enforced — the omitted command is refused and the refusal lands in the envelope's
`permission_denials` — and that a bare command matches its own `:*` entry, which is why the
enumeration below can be glob-only. The live probe is
`test_live_the_shipped_allowances_enforce_their_own_boundaries`; re-run it after any `claude`
upgrade, §109's rule.

**Nothing here judges.** The agent reads `world check` and `world presence`, both of which are
arithmetic over records, and it never sees a reader's verdict because there is no verdict to
see: the readership speaks in behaviour and in what it hopes for, and it speaks to the writer
through the overview loop, not to this.

**The seed ask names an issuer, and until §163 it did not.** `plan/reader-read-4.md` recorded
three standing instructions suppressing the genre's substance, the first of them the
Architect's rule against power numbers — and that rule is **gone**, swept for and not found:
no file under `src/` carries it or a paraphrase, it was cut in `530f40e` rather than with the
Forge two days later, and its affirmative tail (*"the ladder's rungs are the numbers this
world counts"*) survives re-signed in `house.py` as a clause about where an exact number
belongs. So there was nothing here to re-aim. What was here was an **absence**: the ask named
a ladder and named nothing that hands out its rungs, which is the condition
`plan/first-principles-litrpg-core.md` §2 measured — *"a world asked for ladders with no game
system builds institutions"*, and pilot 14's scheduled progression beats duly landed in guild
paperwork ranks. `_SYSTEM` is the occupant, and the reason this is an addition rather than a
subtraction is §156.1: the institutional lean is not in our text, so there is nothing to take
out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer, system_for

if TYPE_CHECKING:
    from litharness.application.concept import Concept

#: Frozen profiles, one per job, so seeding a world and growing one are separable on the rows.
SEED_PROFILE = "architect.seed.v0"
GROW_PROFILE = "architect.grow.v0"

#: The whole allowance: every world command except `accept`, one entry per subcommand, and the
#: omission is the containment (§146.9 measured that the matcher enforces it; the module
#: docstring says why the earlier `Bash(litharness world:*)` could not). Narrow enough to read:
#: this agent can run the world suite and nothing else, which is why `cli.DATABASE_ENV` exists —
#: a `--database` flag between the binary and the subcommand would force every entry here to
#: widen to `Bash(litharness:*)` and hand over every command. No entry contains a comma, because
#: the CLI transport joins the allowance with one; `tests/test_cli.py` derives this list from
#: the real parser so a new world subcommand cannot silently arrive pre-allowed or be forgotten.
ALLOWED_TOOLS: tuple[str, ...] = (
    "Bash(litharness world summary:*)",
    "Bash(litharness world show:*)",
    "Bash(litharness world rules:*)",
    "Bash(litharness world ladders:*)",
    "Bash(litharness world abilities:*)",
    "Bash(litharness world cast:*)",
    "Bash(litharness world threads:*)",
    "Bash(litharness world vocabulary:*)",
    "Bash(litharness world presence:*)",
    "Bash(litharness world check:*)",
    "Bash(litharness world declare:*)",
)

MAX_OUTPUT_TOKENS = 16000

#: The seed's wall-clock ceiling. Pilot 22's first arm (§197.1) measured a two-system seed
#: running past 1,800 seconds and being cut off mid-declaration.
SEED_TIMEOUT_SECONDS = 3600.0

_TOOLS = (
    "You build this world by running `litharness world` at a shell. It is the only command you "
    "have.\n"
    "Start with `litharness world vocabulary`, which tells you every predicate and role the "
    "world's language admits, and `litharness world summary`, which tells you what is already "
    "there. Then `litharness world declare <subject> <predicate>` with `--value` or `--object`.\n"
    "`litharness world check` reports what contradicts itself; run it as you go and fix what it "
    "names. `litharness world ladders`, `abilities`, `cast`, `threads` and `presence` read back "
    "what you have built.\n"
    "Everything you declare is a proposal. Accepting it into the book is somebody else's act, so "
    "declare what the book needs and keep it coherent."
)

#: **The occupant of the issuer position, and the whole of §163's addition to this prompt.**
#: A ladder needs something to hand its rungs out, and until this paragraph existed the ask
#: named a ladder and named no issuer — so the model supplied the nearest one it knows, which
#: is an office. `plan/first-principles-litrpg-core.md` §2 is the measurement: guild paperwork
#: ranks absorbed pilot 14's scheduled progression beats, and licences, wards and excise keep
#: returning, *"partly because a world asked for ladders with no game system builds
#: institutions"*. Subtraction was tried on the register side and did not move it; this is the
#: occupant instead.
#:
#: **Institutions are kept and given their job rather than forbidden**, and the paragraph
#: reaches that by naming none of them. They are the operator's own "agencies above the
#: protagonist", so a clause banning them would subtract from the wrong place — §156.1 measured
#: that the institutional lean is not in our text. What moves is *which* of the two owns the
#: ladder, and that is sayable without an institutional noun.
#:
#: **The first draft of this paragraph said it the other way and
#: `test_the_architect_task_text_names_no_institution` refused it**, correctly. It read
#: *"Guilds, wards, houses and licences may recognise where somebody stands … the book is
#: better with them in it"* — an explicit permission, written to keep institutions available.
#: §138's measurement is that a permission overproduces what it names, so that sentence would
#: have taught the Architect the exact vocabulary pilot 14's guild paperwork ranks came out of,
#: while believing it was protecting the story. The guard is §156.1's finding turned into a
#: rail: the lean is not in our text, *and that only stays true if nobody adds one*. The
#: institution here is therefore an unnamed whatever-else, which permits every institution and
#: primes none.
#:
#: **Every sentence names something declarable.** §154's second axis: a demand whose object is
#: a reader's state or an author's intention names nothing the addressee can emit. This
#: addressee's only act is a `world declare`, so each sentence here names a record — an entity
#: role, a chain, a capability, a prerequisite — and none of them asks for an effect. The
#: shapes are deliberately absent: `world vocabulary` is where a slot is written down, and a
#: copy here would be a second one to disagree with it (§152's defect, pre-made).
#: **Three sentences, and the compression is the budget's doing rather than taste.** The first
#: draft was six and put the role five over its ceiling; `test_prompt_budget` is explicit that
#: the choice is to take something out or to raise the number on purpose, so both were done —
#: this is as small as the ask gets while still carrying an issuer, a ladder that belongs to
#: it, an inventory that is countable, and the one edge that makes it a graph.
#: **The fourth sentence is §173's, and it names the moment the system offers.** Read 10, on the
#: draw the coordinator's gate passed: a rendered status line arriving at a number-move reads as
#: noise, and what a reader wants is to deliberate over what to take next. `SystemDef` had a
#: graph, a ladder and a scale and no fork, and `plan/house-genre-constraint.md` had queued the
#: gap since the night before. **A schema nothing seeds is §160's own history repeating** — that
#: entry shipped a system object with no declaring path, and it took §163 to document one and
#: §165.2 to mint what the documentation could not reach — so the ask carries the fork rather
#: than leaving it to `world vocabulary` alone.
#:
#: It is held to the three constraints the sentences above are held to. **It names records**
#: (§154): a fork, its ways, what each opens, and the rung it opens at are all `world declare`s,
#: and nothing in it asks for an effect on a reader. **It names no institution**, which
#: `test_the_architect_task_text_names_no_institution` enforces and §156.1's finding is the
#: reason for. And **it names no shape**: the slots are `world vocabulary`'s to state once, and a
#: copy here would be a second one to disagree with it (§152's defect, pre-made).
_SYSTEM = (
    "Something in this world grants what people can do, and a ladder belongs to whatever hands "
    "out its rungs: name that thing, declare it as this world's system, and give it the "
    "ladder; the line the book prints has that ladder's word and the system's grants for its "
    "columns and nothing else, because a sheet that prints other numbers is a position in no "
    "system and leaves the one you declared unfinished. The line the book prints when a "
    "standing changes may carry a second phrase, in the system's words, for a grant gained.\n"
    "Whatever else is in the world may recognise where somebody has got to, price it or "
    "withhold it, and the book is better when something does — but it reads the ladder rather "
    "than owning it, and the one this book is about climbs the system's.\n"
    "Declare what the system grants, in what order and at what cost, each grant countable and "
    "named in short plain words with no digits in them; at least one of them needs another one "
    "first, or what you have declared is a list rather than a graph; and no fewer than five "
    "grants and no more than eight, because a printed line holds that many columns and a "
    "system with more is refused at acceptance.\n"
    "Somewhere up that ladder the system puts a fork nobody takes twice: declare it, the two or "
    "three ways of taking it, which of the grants each way opens and which rung it opens at, "
    "and leave what any of them costs to the world. A way may say what it looks like "
    "(manifests_as) and what a person must already hold to be offered it (requires a "
    "grant, at a depth), so the fork a person meets is the one their own record earned.\n"
    "Where the system hands out something to be spent on its grants, declare it as a grant "
    "of its own that says per_rung how much every rung gives, and say on each grant it "
    "buys what that grant costs in it; a grant the rungs hand out is never gained or "
    "deepened, and a grant that costs it is not offered until it can be paid."
)

_SEED = (
    "You are building the world of the book you are about to write. The listing below is what a "
    "reader has already been promised, so the world has to be able to keep it.\n\n"
    f"{_TOOLS}\n\n"
    f"{_SYSTEM}\n\n"
    "Build enough world for the first chapters to stand on besides that: who is in it, how it "
    "works, and what is true that nobody has been told yet. Stop when the book could be "
    "written from what you have declared. Then say, in two or three sentences, what you built "
    "and what you deliberately left open."
)

#: **The second system, asked for only where the concept names one** (§197). The operator's
#: example puts the person under a competing system after a turn with some of the first's
#: grants kept. `_SYSTEM` declares one system; this sentence rides beside it only for a book
#: whose concept has two, so every one-system seed renders byte-identically. It names records
#: (a system, a ladder, grants, one sheet) and no shape, institution or effect, like the rest.
_SECOND_SYSTEM = (
    "Where the book's concept puts the person under a second system after its turn, declare "
    "that one too as a system of its own with its own ladder and grants, declare the sheet of "
    "the one system the book opens under and of no other, and declare what the concept says "
    "carries over as a grant of the second system with a name of its own, because a grant "
    "governed by two systems is a contradiction the check refuses. A person may stand on "
    "both ladders, so a shape that admits one stands_at per person is grouped by "
    "subject,value,order_key, one rung per ladder, and never by subject,order_key alone."
)

_GROW = (
    "You keep the world of a book that is being written. A chapter has just been drafted; your "
    "job is that the world still holds — that what the chapter established is in it, that "
    "nothing in it now contradicts anything else, and that what was declared is being spent "
    "rather than sitting unsaid.\n\n"
    f"{_TOOLS}\n\n"
    "`litharness world presence` shows which of this world's own names have reached the page and "
    "which never have; a name that stays unsaid for long is either a thing the book owes the "
    "reader or a thing the world does not need. Declare what the chapter made true, and what it "
    "now needs next. A grant the system hands out that the seed did not declare is declared "
    "the way the seed declared its grants, governed_by the system, and the line follows it. "
    "Then say, in two or three sentences, what changed and what you are watching."
)


def render_seed_request(
    overview: str, writer: Writer | None = None, *, concept: Concept | None = None
) -> CompletionRequest:
    """Build a world under a listing a reader has already been shown.

    `concept` is the book as its writer conceived it before the listing (stage-0 §197): what
    the world has to be able to hold rides under the listing as material, and the seed's task
    gains `_SECOND_SYSTEM` only for a concept that names one. `None` renders the request as
    it was, byte for byte: the listing and nothing above it.
    """
    prompt = f"The listing this book was sold on:\n\n{overview.strip()}"
    seed = _SEED
    if concept is not None:
        prompt = f"{prompt}\n\n{concept.render_for_seed()}"
        if concept.second_system is not None:
            seed = f"{_SEED}\n{_SECOND_SYSTEM}"
    return CompletionRequest(
        prompt=prompt,
        system=system_for(seed, writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=SEED_PROFILE,
        call_class="generation",
        # **3,600 rather than 1,800, measured** (§197.1): a two-system seed under a concept ran
        # the whole of the old ceiling and was cut off still declaring, its own check pass
        # never reached. A ceiling is what a runaway hits, not what a seed aims at.
        timeout_seconds=SEED_TIMEOUT_SECONDS,
        allowed_tools=ALLOWED_TOOLS,
    )


def render_grow_request(
    chapter: str, *, logical_id: str, writer: Writer | None = None
) -> CompletionRequest:
    """Keep the world after one chapter: what it established, and what it now owes."""
    return CompletionRequest(
        prompt=f"The chapter just drafted ({logical_id}):\n\n{chapter.strip()}",
        system=system_for(_GROW, writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=GROW_PROFILE,
        call_class="generation",
        timeout_seconds=1800.0,
        allowed_tools=ALLOWED_TOOLS,
    )


__all__ = [
    "ALLOWED_TOOLS",
    "GROW_PROFILE",
    "MAX_OUTPUT_TOKENS",
    "SEED_PROFILE",
    "render_grow_request",
    "render_seed_request",
]
