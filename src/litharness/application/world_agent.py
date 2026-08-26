"""The Architect as an agent with tools, rather than a schema filled in once before chapter one.

**The operator, 2026-08-24:** *"in what world would a one-shot structured call be a good idea
for writing a book... The world would obviously evolve and grow with every chapter"*, and
*"Architect Writers and readers should work together to make the world as interesting as
possible"*, and *"also to make sure everything stays coherent and present in the world"*.

What this replaces is the retired Forge: one 32,000-token structured call, K
worlds at a time, a person picking one, and then a world that never changed again for the rest
of the book. What it is instead is the same cast writer, holding `litharness world`, building
the world of the book they are about to write and coming back to it as the book grows.

**The containment is the tool surface and not a promise.** The allowance is
`Bash(litharness world:*)` and nothing else — no file access, no other command — and everything
`world declare` writes is `PROPOSED`, because `worlds.world_record` mints it that way. So this
agent can propose a world and cannot install one; `world accept` is a separate act with a
decision row behind it. That is §5's "no subsystem mutates canon directly" kept through a named
command rather than by refusing the model a shell.

**Nothing here judges.** The agent reads `world check` and `world presence`, both of which are
arithmetic over records, and it never sees a reader's verdict because there is no verdict to
see: the readership speaks in behaviour and in what it hopes for, and it speaks to the writer
through the overview loop, not to this.
"""

from __future__ import annotations

from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer, system_for

#: Frozen profiles, one per job, so seeding a world and growing one are separable on the rows.
SEED_PROFILE = "architect.seed.v0"
GROW_PROFILE = "architect.grow.v0"

#: The whole allowance. Narrow enough to read: this agent can run the world suite and nothing
#: else, which is why `cli.DATABASE_ENV` exists — a `--database` flag between the binary and the
#: subcommand would force this to widen to `Bash(litharness:*)` and hand over every command.
ALLOWED_TOOLS: tuple[str, ...] = ("Bash(litharness world:*)",)

MAX_OUTPUT_TOKENS = 16000

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

_SEED = (
    "You are building the world of the book you are about to write. The listing below is what a "
    "reader has already been promised, so the world has to be able to keep it.\n\n"
    f"{_TOOLS}\n\n"
    "Build enough world for the first chapters to stand on: who is in it, what they can do, what "
    "getting better means here and what it costs, and what is true that nobody has been told "
    "yet. Stop when the book could be written from what you have declared. Then say, in two or "
    "three sentences, what you built and what you deliberately left open."
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
    "now needs next. Then say, in two or three sentences, what changed and what you are watching."
)


def render_seed_request(overview: str, writer: Writer | None = None) -> CompletionRequest:
    """Build a world under a listing a reader has already been shown."""
    return CompletionRequest(
        prompt=f"The listing this book was sold on:\n\n{overview.strip()}",
        system=system_for(_SEED, writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=SEED_PROFILE,
        call_class="generation",
        timeout_seconds=1800.0,
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
