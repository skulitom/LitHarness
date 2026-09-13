"""World creation and chapter reconciliation through a restricted proposal-only tool surface.

Concept-backed seeds separate world properties from pending story intentions. Those intentions
constrain starting state and future access; they are not declaration material. Reconciliation
receives established prose. Declarations remain proposals until world acceptance;
the agent's command allowance deliberately excludes that operation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from litharness.domain.beats import TemplateMismatch, beats_for, template_for
from litharness.domain.generation import CompletionRequest
from litharness.domain.revision import Revision
from litharness.domain.serials import SerialShape, arcs_of, beats_for_serial
from litharness.domain.writers import Writer, system_for

if TYPE_CHECKING:
    from litharness.application.concept import Concept

#: Frozen profiles, one per job, so seeding a world and growing one are separable on the rows.
SEED_PROFILE = "architect.seed.v7"
GROW_PROFILE = "architect.grow.v4"

# Explicit subcommands exclude acceptance. A broad world:* allowance would permit it.
# Transport joins entries with commas; tests compare this list with the real parser.
ALLOWED_TOOLS: tuple[str, ...] = (
    "Bash(litharness world summary:*)",
    "Bash(litharness world query:*)",
    "Bash(litharness world rules:*)",
    "Bash(litharness world ladders:*)",
    "Bash(litharness world abilities:*)",
    "Bash(litharness world cast:*)",
    "Bash(litharness world threads:*)",
    "Bash(litharness world vocabulary:*)",
    "Bash(litharness world presence:*)",
    "Bash(litharness world check:*)",
    "Bash(litharness world declare:*)",
    # The batch form (stage-0 §241): the same `declare`, several records per call, so a
    # seed is no longer one shell round-trip per record. Inline JSON only; it takes no
    # path, which is what keeps this list a prefix match on a command line (§146.9).
    "Bash(litharness world declare-batch:*)",
)

MAX_OUTPUT_TOKENS = 16000

#: The seed's wall-clock ceiling. Pilot 22's first arm (§197.1) measured a two-system seed
#: running past 1,800 seconds and being cut off mid-declaration.
SEED_TIMEOUT_SECONDS = 3600.0

_TOOLS = (
    "Start with `litharness world vocabulary`, which tells you every predicate and role the "
    "world's language admits, and `litharness world summary`, which tells you what is already "
    "there. Declare related facts together with `litharness world declare-batch --records "
    "'<JSON array>'`, about twenty-five records per batch, using the vocabulary's record "
    "fields and passing the JSON as one literal argument.\n"
    "Inspect relevant entities with `litharness world query --subjects <id> <id>`, "
    "optionally `--predicate <name>`; it returns at most fifty records per page, with "
    "next_offset for `--offset` and a selection hash to detect changes between pages. "
    "Run `litharness world check` as you go and fix what it names.\n"
    "Everything you declare is a proposal. Accepting it into the book is somebody else's act, so "
    "declare what the book needs and keep it coherent. "
    "World rules describe how the world works, and manifestations describe in-world forms. "
    "Use wants for current desires, voice_tag for speaking manner and disposition for ordinary "
    "temperament or habits; these are changeable character assertions. Beliefs use believes "
    "edges to claims. A character's actual magical constraints, physiology or curses remain "
    "world rules; separate these from personality even when supplied in the same passage. "
    "Future scene actions, explanations and endings belong in story plans, not world rules."
)

# System mechanics use the vocabulary returned by the world tool.
_SYSTEM = (
    "Something in this world grants what people can do, and a ladder belongs to whatever hands "
    "out its rungs: name that thing, declare it as this world's system, and give it the "
    "ladder; the line the book prints has that ladder's word and the system's grants for its "
    "columns and nothing else, because a sheet that prints other numbers is a position in no "
    "system and leaves the one you declared unfinished. The line the book prints when a "
    "standing changes may carry a second phrase, in the system's words, for a grant gained.\n"
    "Declare what the system grants, in what order and at what cost, each grant countable and "
    "named in short plain words with no digits in them; at least one of them needs another one "
    "first, or what you have declared is a list rather than a graph; the engine accepts "
    "five to eight grants per system.\n"
    "Let entry-level capabilities be useful without separately acquired perception or "
    "control grants; fundamental handling can be part of the capability. Use numerical "
    "prerequisite depths only when the source supplies them; ownership uses one and rank "
    "requirements refer to rank rungs.\n"
    "Use a system-following status sheet with show_unheld set to false unless the author's "
    "brief explicitly requests a complete skill tree on the page. "
    "Declaring a grant does not "
    "give it to the viewpoint character or require its introduction in chapter one.\n"
    "Declare a permanent fork only when the supplied story specifies mutually exclusive "
    "paths, with its ways, grants and opening rungs; spending one resource among upgrades "
    "does not permanently exclude those upgrades. A way may have manifests_as and requires "
    "edges for grants at a depth.\n"
    "Where the system hands out something to be spent on its grants, declare it as a grant "
    "of its own that says per_rung how much every rung gives, and say on each grant it "
    "buys what that grant costs in it; a grant the rungs hand out is never gained or "
    "deepened, and a grant that costs it is not offered until it can be paid."
)

_SEED = (
    "Build the supplied world, including its history, inhabitants' own pursuits, magical "
    "effects and usable capabilities, using only the detail needed to support it. "
    "Supplied motives and mechanics take precedence over defaults; leave unspecified "
    "advancement quotas and additional cast open. Declare observable forms, activity and "
    "historical traces through manifests_as, separately from undisclosed explanations in "
    "claim.content.\n\n"
    f"{_TOOLS}\n\n"
    f"{_SYSTEM}\n\n"
    "Establish which people the viewpoint character can understand and be understood by, "
    "including any translation mechanism or language barrier the supplied story relies on. "
    "Briefly report what you built and left open."
)

# Only concepts with a second system need this declaration contract.
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
    "job is to reconcile what the chapter established with the existing world.\n\n"
    f"{_TOOLS}\n\n"
    "Declare facts established by this chapter at its supplied story key. Undisclosed "
    "world material need not appear on the page. A grant the system hands out that the seed "
    "did not declare is declared "
    "the way the seed declared its grants, governed_by the system, and the line follows it. "
    "Then say, in two or three sentences, what changed."
)


def render_seed_request(
    overview: str, writer: Writer | None = None, *, concept: Concept | None = None
) -> CompletionRequest:
    """Give seeding the source boundary without treating planned events as completed facts."""
    prompt = (
        "Reader-facing listing (a promise to support, not completed events or scene "
        f"instructions):\n\n{overview.strip()}"
    )
    seed = _SEED
    if concept is not None:
        opening = concept.discovery.opening if concept.discovery else concept.first_arc.opens
        prompt += f"\n\n{concept.render_for_world()}"
        prompt += (
            "\n\nPending story intentions (constraints, not facts to declare):\n"
            "Initialize before the opening's actions, retaining capabilities already owned "
            "there; its acquisitions, completed tests, meetings and discoveries have not "
            "happened. Support the later possibilities without declaring their occurrence "
            "or adding access restrictions.\n"
            f"Opening:\n{opening}"
        )
        if concept.discovery is not None:
            prompt += f"\nLater possibilities:\n{concept.discovery.growth}"
        if concept.second_system is not None:
            seed = f"{_SEED}\n{_SECOND_SYSTEM}"
    prompt += _author_constraints(concept)
    return CompletionRequest(
        prompt=prompt,
        # The treatment owns story choices once supplied. The dossier remains part of
        # invention and prose writing, not another instruction to choose a different world.
        system=system_for(seed, None if concept is not None and concept.discovery else writer),
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
    chapter: str, *, logical_id: str, writer: Writer | None = None, concept: Concept | None = None,
    story_order_key: str | None = None,
) -> CompletionRequest:
    """Reconcile chapter-established facts without replaying the planned opening."""
    prompt = f"The chapter just drafted ({logical_id}):\n\n{chapter.strip()}"
    if story_order_key is not None:
        prompt += (
            f"\n\nThis chapter's exact story key: {story_order_key}. Use this order_key for "
            "facts and disclosures established here; leave only timeless world mechanics "
            "unkeyed."
        )
    prompt += _author_constraints(concept)
    return CompletionRequest(
        prompt=prompt,
        system=system_for(_GROW, None if concept is not None and concept.discovery else writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=GROW_PROFILE,
        call_class="generation",
        timeout_seconds=1800.0,
        allowed_tools=ALLOWED_TOOLS,
    )


def chapter_story_key(
    revision: Revision, logical_id: str, *, serial_shape: SerialShape,
) -> str | None:
    """Use the planner/summary coordinate space, including stable keys for serials."""
    try:
        arcs = arcs_of(revision, serial_shape)
        beats = (
            beats_for_serial(revision, serial_shape) if arcs and arcs[0].closed
            else beats_for(revision, template_for(revision))
        )
    except TemplateMismatch:
        return None
    return next((beat.story_order_key for beat in beats if beat.logical_id == logical_id), None)


def _author_constraints(concept: Concept | None) -> str:
    if concept is None or not concept.author_brief:
        return ""
    return (
        "\n\nAuthor's original brief (constrains world building; requested future scenes "
        f"remain intentions):\n{concept.author_brief}"
    )


__all__ = [
    "ALLOWED_TOOLS",
    "GROW_PROFILE",
    "MAX_OUTPUT_TOKENS",
    "SEED_PROFILE",
    "render_grow_request",
    "render_seed_request",
]
