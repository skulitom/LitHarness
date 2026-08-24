"""The Architect: K worlds in one structured call, gated deterministically, chosen by nobody here.

Design: [`plan/world-architect.md`](../../../plan/world-architect.md). Ontology:
[`plan/state-model-abilities.md`](../../../plan/state-model-abilities.md) and
[`research/progression-generalization.md`](../../../research/progression-generalization.md).

**What this is upstream of.** The Director says what a book is about, the Writer drafts it, the
Reader/Judge reads it. None of them says what the world *is*, and measured against the live
serial (`plan/world-architect.md` §0) the consequence is exact: 23 canon records for a nine-scene
book — 15 typed by the operator, 8 readings of one status line — while the prose carries a
system, a cast, an institution and a bestiary that canon has never heard of.

**Three rails, and the middle one is the whole design.**

1. *Proposal, with exactly one exit.* Every record this module builds is `PROPOSED` and stamped
   `architect:<id>`, and `domain/worlds.world_record` defaults to `PROPOSED` so the rail is the
   default rather than something each call site remembers. The one exit is `forge --pick`, where a
   person has chosen among K and the choice is recorded as its own policy decision; only there is
   `records_for(..., authority=ACCEPTED_CANON)` called, and that is the same authority
   `cmd_import` writes an operator's snapshot under.
2. *No model picks the world.* K candidates are generated, gated, and **stopped**. There is no
   ranking, no score, no judge, and no import of one — `plan_search`'s tournament is not reused
   and is not reachable from here. If a world is chosen among K, a person chose it and `--pick`
   records that as its own decision. §61(5) then divides the confidence level by the candidate
   count, which is why the count is on the decision row.
3. *A palette, never a checklist.* Nothing below requires a world to declare a system, a
   criterion, a rank, a number or a creature. The counters report coverage **of what was
   declared**; `Coverage.share` returns 1.0 for a world that declared nothing, because "declared
   nothing" and "declared everything and showed none of it" must not be the same number.

**Distinctness is checked on axes that survive a lie.** The repository's prior is that instructed
distinctness is not distinctness — §89.1 measured one byte-identical answer vector across four
personas, §77 measured persona-to-passage ratios of 0.0028, 0.0071 and 0.0342. So the collapse
gate does not ask whether the K worlds *feel* different: it requires the declared real domain and
the declared geometry to be pairwise distinct, which is checkable, and reports
`directors.distinctness` over the rendered candidates beside it, which is comparable to every
other distinctness number in this project.

**Two prompt shapes, because one would be a preference.** `DIRECT` asks for the world.
`DOMAIN_FIRST` asks for the real domain and its real constraints and derives the system from them
inside the same call. Which one measures better is reported with its numbers rather than assumed;
if neither separates, that is the finding and it is recorded as one.
"""

from __future__ import annotations

import itertools
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import litharness_contracts as lc

from litharness.domain import directors, house
from litharness.domain import worlds as worlds_mod
from litharness.domain.directives import DirectiveKind
from litharness.domain.generation import CompletionRequest

#: Frozen generation profile, recorded in provenance like every other model call here.
PROFILE = "architect.world.v0"

#: Mechanical rather than prose: this call returns a structured world, and conformance is the
#: point. The pinned provider drops samplers entirely, so this is a provenance record — which is
#: exactly what `plan_search.tournament_sampler`'s docstring says about its own.
CALL_CLASS = "generation"

#: Three, for `PlanSearchPolicy`'s reason: a search over one alternative is not a search. Kept
#: low because the whole world is returned per candidate and the output is the binding cost.
DEFAULT_K = 3

#: How many scenes are being written now, when nobody says. `SIX_BEAT`'s count, restated rather
#: than imported so `domain.beats` does not become a dependency of the world vocabulary; the CLI
#: passes the real number and this is only the shape of the default.
DEFAULT_SCENES = 6

#: The axes a candidate must differ from its siblings on. Declared rather than inferred, and
#: checkable after the fact — which is the difference between a distinctness rail and an
#: instruction to be different.
GEOMETRIES: tuple[str, ...] = ("chain", "graph", "cycle", "threshold", "estimate", "set")


class ArchitectInputError(Exception):
    """A forge request that cannot be built."""


class ArchitectOutputError(Exception):
    """A world set the gates refuse. Refused before a single scene is paid for."""


# --- the schema ------------------------------------------------------------------------------

_ID = {"type": "string"}
_TEXT = {"type": "string"}

#: A string the answer is not allowed to leave empty. **Measured, not defensive.** The
#: 2026-08-22 forge returned a world with an empty `premise` that conformed to this schema and
#: then failed `worlds_from`'s shape check — $1.48 for three worlds, one of them unusable. The
#: older fields keep `_TEXT` because tightening them would change the schema every existing
#: world was forged under; the fields added since carry the floor.
_SAID = {"type": "string", "minLength": 1}

#: The shape of a declared id, and the sentence that says so. **Both are measured corrections.**
#: The first live forge under the protagonist rule returned three worlds out of three that named a
#: real declared id in an id field and then glossed it in the same field — `one_cooling_history —
#: the shape that gives a body one cooling history…` — because the ask described *which* thing to
#: select and the model wrote the description into the slot (stage-0 §112.5). Every id field added
#: since carries both.
_ID_PATTERN = "^[a-z0-9_]+$"
_ID_ONLY = (
    "AN ID AND NOTHING ELSE — one snake_case id declared in this world. Write `cap_read_a_seam`, "
    "never `cap_read_a_seam - the knack of seeing where two things were joined`. No dash, no "
    "gloss, no sentence: what the thing is belongs in its own fields."
)

_CONSEQUENCE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["domain", "consequence"],
    "properties": {
        "domain": {"type": "string", "enum": list(worlds_mod.CONSEQUENCE_DOMAINS)},
        "consequence": _TEXT,
    },
}

_RULE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "rule", "consequences", "manifests_as"],
    "properties": {
        "id": _ID,
        "rule": _TEXT,
        "consequences": {"type": "array", "items": _CONSEQUENCE},
        "manifests_as": _TEXT,
    },
}

#: **`grants` is the slot §114 measured as missing and did not add.** That entry counted 135 of
#: 156 rungs across 24 worlds as an *insignia* — a mark other people read — and permission
#: outnumbering capability 104 to 46, "because `_RANK` has a slot for what a rung LOOKS like
#: and one for what it COSTS and none for what it lets you do". Its answer was to build the
#: capability inventory *beside* the ladder, which left the ladder itself a chain of standings.
#:
#: The operator read a premise forged on that ladder and named the gap directly: *"readers want
#: something the character gets (numbers go up) and gets to keep forever — for example healing
#: touch ability gained, strong healing touch, revival. Readers want constant growth in
#: tangible abilities. Readers are rarely interested in more conceptual growth, at least in
#: this genre."* A chain of insignia is conceptual growth wearing a badge; a chain of
#: healing-touch-then-revival is the genre.
_RANK = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "visible_form", "cost_to_reach", "grants"],
    "properties": {
        "id": _ID,
        "visible_form": _TEXT,
        "cost_to_reach": _TEXT,
        "grants": {
            **_SAID,
            "description": (
                "What reaching this rung lets a person DO that the rung below could not — a "
                "power, in plain words, that they keep. Not a permission, not a title, not a "
                "room they may now enter. The SHAPE is that each rung does more of one "
                "tangible thing than the rung under it, and the thing is this world's own: "
                "one chain might run from mending a cut by touch, to closing a wound that "
                "would have killed, to bringing somebody back the same hour — and another "
                "from being heard across a room, to across a valley, to by somebody who has "
                "never met you. Those are two instances of the structure and neither is a "
                "template to copy. If the honest answer is that this rung grants nothing a "
                "body can do, the chain is a set of badges."
            ),
        },
    },
}

_CAPABILITY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "is_a", "manifests_as", "costs"],
    "properties": {
        "id": {**_SAID, "pattern": _ID_PATTERN, "description": _ID_ONLY},
        "is_a": {
            **_SAID,
            "description": (
                "What this lets a person DO, in one line, as a capability rather than a "
                "permission: what they can do that somebody without it cannot. Never 'is "
                "allowed to' and never 'has the rank of' — a rank is where somebody stands and "
                "this is what they can do."
            ),
        },
        "manifests_as": {
            **_SAID,
            "description": (
                "How it shows on the page when it is used: what is seen, heard or paid. Never "
                "an explanation and never a lecture, exactly as every other `manifests_as`."
            ),
        },
        "requires": {
            "type": "array",
            "description": (
                "Ids of other capabilities, or of a rank, that a person must already have "
                "before this one is reachable. Ids only, no sentences. Omit for a capability "
                "that needs nothing first; most worlds will have a few of those and they are "
                "where an inventory starts."
            ),
            "items": {**_SAID, "pattern": _ID_PATTERN},
        },
        "costs": {
            **_SAID,
            "description": (
                "What having it costs, payable on the page — time, a body, a debt, a foreclosed "
                "option. Every gain in this world carries a price and this is that rule applied "
                "to a thing a person can do."
            ),
        },
        "taught_by": {
            **_SAID,
            "pattern": _ID_PATTERN,
            "description": (
                "The declared id of whoever teaches or allows this, when somebody does. Omit it "
                "when nothing gates the capability but the work."
            ),
        },
    },
}

_CRITERION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "comparator", "evaluates"],
    "properties": {
        "id": _ID,
        "comparator": {"type": "string", "enum": list(worlds_mod.COMPARATORS)},
        "evaluates": _TEXT,
        "ranks": {"type": "array", "items": _RANK},
    },
}

_SYSTEM = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "name", "logic", "rules", "manifests_as"],
    "properties": {
        "id": _ID,
        "name": _TEXT,
        "logic": _TEXT,
        "rules": {"type": "array", "items": _RULE},
        "criterion": _CRITERION,
        "manifests_as": _TEXT,
        "collides_with": _TEXT,
        "interface": _TEXT,
        "hidden_personality": _TEXT,
        "view_withholds": _TEXT,
    },
}

_ENTITY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "is_a"],
    "properties": {
        "id": _ID,
        "is_a": _TEXT,
        "wants": _TEXT,
        "reach": _TEXT,
        "false_belief": _TEXT,
        "secret": _TEXT,
        "voice_tag": _TEXT,
        "manifests_as": _TEXT,
        "recognises": _TEXT,
        "grants": _TEXT,
        "prices_the_present": _TEXT,
        "relationships": {
            "type": "array",
            "description": (
                "Who this subject stands in what relation to. `predicate` is a snake_case "
                "relation (owes, employs, married_to, blames, outranks), `target` is another "
                "declared id, and `note` is the one thing about it a scene could use."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["predicate", "target"],
                "properties": {"predicate": _TEXT, "target": _TEXT, "note": _TEXT},
            },
        },
    },
}

_CREATURE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "is_a", "mechanism", "ecology", "human_use", "behaviour", "manifests_as"],
    "properties": {
        "id": _ID,
        "is_a": _TEXT,
        "mechanism": _TEXT,
        "ecology": _TEXT,
        "rank": _TEXT,
        "human_use": _TEXT,
        "behaviour": _TEXT,
        "bond_potential": _TEXT,
        "manifests_as": _TEXT,
    },
}

_BOND = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "members", "joint_ability"],
    "properties": {
        "id": _ID,
        "members": {"type": "array", "items": _ID},
        "joint_ability": _TEXT,
        "trait_link": _TEXT,
    },
}

_MYSTERY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "question", "answer", "disclosed_at_scene"],
    "properties": {
        "id": _ID,
        "question": _TEXT,
        "answer": _TEXT,
        "disclosed_at_scene": {"type": "integer"},
        "kind": {"type": "string", "enum": ["mystery", "plot", "progression", "character"]},
        "believed_instead_by": _TEXT,
    },
}

_CARDINALITY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "predicate", "group_key", "maximum"],
    "properties": {
        "id": _ID,
        "predicate": _TEXT,
        "scope": {"type": "string", "enum": [*worlds_mod.ENTITY_ROLES, worlds_mod.ANY_SCOPE]},
        "group_key": {"type": "string", "enum": list(worlds_mod.GROUP_KEYS)},
        "maximum": {"type": "integer"},
        # **The declared exceptions, and the reason they are not a `scope`.** `worlds.in_scope`
        # keeps a scope an `entity_role` because a shape is a rule about a *kind* of thing; an
        # exception is a declared fact about *one* subject. Omitted by almost every world, and a
        # shape that omits it is byte-identical to one forged before this key existed.
        "except": {
            "type": "array",
            "description": (
                "Declared ids this maximum does not govern. Almost always empty. A world that "
                "names a protagonist whose exception IS this shape lists them here."
            ),
            "items": _ID,
        },
    },
}

#: Where the protagonist starts on one declared ordinal ladder: the criterion's id and the
#: rung's id, both declared elsewhere in the same world. **Two ids and nothing else** — the
#: rung's visible form and its price already live on the rank, and repeating either here would
#: be a second copy of a fact the world states once (`plan/handoff-numbers-go-up.md`
#: boundary 10).
#:
#: **Both carry `pattern` and a description saying AN ID AND NOTHING ELSE, and that is
#: `_PROTAGONIST["exception"]`'s measured correction applied before it is paid for a second
#: time.** The first forge under the protagonist rule returned three worlds, every one of which
#: put a real declared id in `exception` and an em-dash gloss after it, and all three were
#: refused. These two fields are the same shape of ask — "name the criterion by its id" — so
#: they get the same answer without waiting for the same bill.
_STANDING = {
    "type": "object",
    "additionalProperties": False,
    "required": ["criterion", "rung"],
    "properties": {
        "criterion": {
            **_SAID,
            "pattern": "^[a-z0-9_]+$",
            "description": (
                "AN ID AND NOTHING ELSE — the snake_case id of a criterion declared in this "
                "world, whose comparator is `ordinal` and whose `ranks` are a chain of at "
                "least three. Write `crit_priority`, never `crit_priority - the order in "
                "which gates are shut`. What the criterion judges is already written where "
                "the criterion is declared."
            ),
        },
        "rung": {
            **_SAID,
            "pattern": "^[a-z0-9_]+$",
            "description": (
                "AN ID AND NOTHING ELSE — the snake_case id of one of that criterion's own "
                "`ranks`, and NOT the top one. Write `morning_right`, never `morning_right - "
                "two seasons of proving use`. What the rung looks like and what it costs are "
                "already written on the rank itself."
            ),
        },
    },
}

_PROTAGONIST = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "exception", "edge", "wants", "price", "standing"],
    "properties": {
        "id": {**_SAID, "description": "The declared id of a member of this world's cast."},
        # **A bare id, and the `pattern` is a measured correction rather than a precaution.**
        # The first live forge under this schema returned three worlds, every one of which put
        # a real declared id here and then an em-dash gloss after it — `one_cooling_history —
        # the shape that gives a body one cooling history and one fringe order does not hold
        # for him. He carries two…`. All three were refused by the gate for naming something
        # that is neither a declared rule nor a declared shape, which is what a whole sentence
        # normalises to. The field was asked for as "the id of the rule that does not hold for
        # them", and the model supplied the id *and* the clause describing it; the description
        # and the pattern now say which of the two this field is.
        "exception": {
            **_SAID,
            "pattern": "^[a-z0-9_]+$",
            "description": (
                "AN ID AND NOTHING ELSE — one snake_case id, declared elsewhere in this world, "
                "of the rule or cardinality shape that does not hold for this person. Write "
                "`rule_seed_never_true`, never `rule_seed_never_true - the rule that ...`. No "
                "dash, no gloss, no sentence: what the rule says is already written where the "
                "rule is declared, and what the exception lets them do belongs in `edge`."
            ),
        },
        "edge": {
            **_SAID,
            "description": (
                "What that exception lets them do that nobody else can, written the way "
                "`manifests_as` is written: how it shows on the page, never an explanation."
            ),
        },
        "wants": {**_SAID, "description": "What this person is after."},
        "price": {
            **_SAID,
            "description": "What the exception costs them, payable on the page.",
        },
        "capabilities": {
            "type": "array",
            "description": (
                "Ids of the declared capabilities this person already has, drawn from the "
                "world's own `capabilities` list. Ids only. This is the inventory a reader "
                "watches grow, so give them what they START the book with rather than "
                "everything the world has."
            ),
            "items": {**_SAID, "pattern": _ID_PATTERN},
        },
        "standing": _STANDING,
    },
}

_GRAPH_LINE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "edges"],
    "properties": {
        "label": {
            "type": "string",
            "description": (
                "A short bracket tag printed at the head of the line, like SYSTEM or REGISTER. "
                "One or two words, never a sentence."
            ),
        },
        "edges": {
            "type": "array",
            "description": (
                "Printed forms this world announces a change in. The line reads "
                "[LABEL] <who> <phrase> <what>, so a phrase is a short verb phrase of at most "
                "six words that joins a name to a thing, and the predicate is the snake_case "
                "relation it means. Omit the whole graph_line if this world does not announce "
                "itself in print; most do not, and absence costs nothing."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["phrase", "predicate"],
                "properties": {"phrase": _TEXT, "predicate": _TEXT},
            },
        },
    },
}

_DIRECTIVE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "text"],
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["constraint", "tone_note", "arc_note", "chapter_note"],
        },
        "text": _TEXT,
    },
}

_WORLD = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "title",
        "domain",
        "geometry",
        "progression_means",
        "inversion",
        "premise",
        "protagonist",
        "systems",
        "cast",
        "creatures",
        "mysteries",
    ],
    "properties": {
        "title": _TEXT,
        "domain": _TEXT,
        "geometry": {"type": "string", "enum": list(GEOMETRIES)},
        "progression_means": _TEXT,
        "inversion": _TEXT,
        "premise": _TEXT,
        # **Required of the forge, tolerated as absent everywhere downstream.** A world the
        # Architect proposes must say whose book it is; a book whose canon predates the field —
        # every world forged before 2026-08-22, `plan/serial-pilot-2-world.json` among them —
        # goes through `records_for` unchanged and renders the same packet it always did.
        "protagonist": _PROTAGONIST,
        "systems": {"type": "array", "items": _SYSTEM},
        "agencies": {"type": "array", "items": _ENTITY},
        "carriers": {"type": "array", "items": _ENTITY},
        "bonds": {"type": "array", "items": _BOND},
        "cast": {"type": "array", "items": _ENTITY},
        # **Optional, and the word is load-bearing.** A world with no capabilities is a
        # world about standing, or about a place, or about a debt — most of what this
        # forge has produced — and a required inventory would make every one of them
        # invent one. Absent means absent: `records_for` emits nothing, the gate says
        # nothing, and the packet is the packet it always was.
        "capabilities": {"type": "array", "items": _CAPABILITY},
        "creatures": {"type": "array", "items": _CREATURE},
        "places": {"type": "array", "items": _ENTITY},
        "institutions": {"type": "array", "items": _ENTITY},
        "history": {"type": "array", "items": _ENTITY},
        "mysteries": {"type": "array", "items": _MYSTERY},
        "cardinality": {"type": "array", "items": _CARDINALITY},
        "graph_line": _GRAPH_LINE,
        "directives": {"type": "array", "items": _DIRECTIVE},
    },
}

WORLDS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["worlds"],
    "properties": {"worlds": {"type": "array", "items": _WORLD}},
}

# --- the prompt --------------------------------------------------------------------------------

DIRECT = "direct"
DOMAIN_FIRST = "domain_first"
PROMPT_SHAPES: tuple[str, ...] = (DIRECT, DOMAIN_FIRST)

_SYSTEM_MESSAGE = house.with_house_rules(
    "You are the Architect for an open-ended serial. You say what a world IS: its systems, its "
    "rules, the prices those rules charge, who lives under them, and what is true but not yet "
    "known. You never say what the book is about scene by scene, you never write prose, and you "
    "never judge anything. Return only the requested JSON."
)

#: The rules every candidate is written under. Ordered so the two that decide whether a world is
#: *usable* — consequences and manifestations — come before the ones that decide whether it is
#: interesting, because the gates refuse on the first two and only report on the rest.
    # **Four rules the operator's worked example diagnosed on 2026-08-23, after six worlds.** The
    # example was a pitch: a biology graduate in a dead-end coffee job in a near-future with a
    # neural implant dies, wakes as a child in a magic world with the AI merged into him, finds
    # that magic here runs on cell biology, masters water magic with what he already knows, and
    # joins an academy. Slow burn.
    #
    # Read against the six worlds this forge had just produced, it named four things at once, and
    # each is fixed where it was caused rather than in a brief:
    #
    #   1. *"'wet cinder', 'because his body rings', 'with a stranger going pale' are not things
    #      anybody says in any context"* — the premise rule asked for a person's situation and got
    #      literary flash fiction. It now asks for a pitch, in the order things happen.
    #   2. *"Why do each of these options mention climbs and ladders — it sounds like we are stuck
    #      on these words for no reason"* — §113's ladder rule made the chain the world's identity.
    #      It is furniture now, met the way bronze-to-gold is met.
    #   3. The example keeps every genre comfort — isekai, academy, a system, slow burn — and is
    #      fresh underneath. `_DISTINCTNESS_RULE` and the originality rule had been read as a
    #      demand for strangeness, so a rule now says where originality belongs.
    #   4. Every world was inverting a default (nothing heals; no move-lists; nothing is hidden),
    #      which is what made each one alien. Inversion is optional from here.
    #
    # And the question under all four, which is answered honestly rather than engineered around:
    # *"do LLMs have access to the whole context? surely they would notice the insanity"*. The
    # forge sees the brief, the schema and these rules. It never sees its own premise as a reader
    # meets it, and nothing anywhere in this pipeline asks whether a reader would want the world.
    # No critic was added here — §61(5) and §105.1 are why — so the only lever is what is asked
    # for, which is what these four rules change.
    # **`standing` was the third schema word to reach the page, and it was measured there.**
    # `comprehension_battery` on *Wake the Jar*: three of eight unfollowable terms were the word
    # `standing` — *"hotter than a girl at her standing should be able to manage"* — after the
    # clause above had already taken `ladder` and `rung` off the page. The family is this
    # module's own vocabulary for its machinery and a reader has never been told any of it.
    # **The fourth amendment, and the first one a measurement rather than a read produced.**
    # `comprehension_battery` asked four readers of the target genres to quote anything in a
    # premise they could not follow. Over the two premises forged under the amendment above —
    # which was supposed to have fixed exactly this — nine and ten terms came back, and **every
    # one of them first appears in the last third of its premise** (65%, 69%, 73%, 74%, 70%, and
    # `frost rooms` at 96%, in the second-to-last clause). The openings were clean.
    #
    # So the rule was not being ignored; it was being obeyed while the premise established itself
    # and dropped once it accelerated. The clause names where it fails rather than repeating the
    # instruction louder, which is what the first version of it already tried.
    # **A standing correction about how the operator's examples are meant to be read**, made on
    # 2026-08-23 after this module had twice taken one for a specification: *"not every book has
    # to have bronze and gold. When I mentioned those ranks I was giving examples and was hoping
    # you would generalize the concept structure. Like Animal object in C++ if I mentioned cats
    # and bunnies."*
    #
    # `handoff-numbers-go-up` quoted *"say bronze is 1 and gold is 3"* and the rules that came out
    # of it printed bronze and gold; the operator's worked isekai example produced six worlds
    # fitted to its surface. The instance is never the interface. Where a rule below carries an
    # example it says so and gives two, because one example reads as the answer and two read as a
    # range.
    # **The readership, stated by the operator on 2026-08-23**: *"most readership is 20-30 male
    # for this genre, we should keep main characters relatable"*. RoyalRoad's audience is the
    # market this project writes for, and this is a targeting decision the operator owns.
    #
    # **What is written here is the declarative half only, and the split is §112 boundary 1's.**
    # That boundary forbids this module a default instruction about how to *handle* a
    # protagonist — open on the hero, make them likeable — and
    # `test_the_protagonist_rule_asks_for_a_declaration_and_never_an_outcome` enforces it with a
    # forbidden-verb list that has `likeable` on it. "Make the reader relate to them" is that
    # class of instruction and is not written. What is written is a fact about the world's
    # declaration: *who this person was before*. A world may still declare somebody unlikeable,
    # old, or hard to sit with; what it may not do by default is reach for a career veteran when
    # the reader is twenty-four.
    #
    # **It also has a craft reason that is not about demographics.** The competence-transfer
    # fantasy needs knowledge the reader can imagine owning. A biology degree and an internet
    # habit are transferable to a reader; twenty-two years of grinding lenses is somebody else's
    # life, and the reader watches it rather than wearing it.
    # **Three amendments from one operator read of six premises, 2026-08-23.** The six were
    # forged under §116, §118 and §119 and drew six complaints that turned out to be three:
    #
    #   1. *"There just doesn't seem to be a good reason for this limitation other than to show
    #      how our main character is special."* Said of a world where nobody can hear their own
    #      singing voice so that one person can, and again of a school where nobody may learn
    #      both halves of the art. **This rule caused it**: §112 asks for the one declared rule
    #      that does not hold for the protagonist, so the forge invents a limitation for everyone
    #      and exempts one person. The operator's own worked example runs the other way — a
    #      biology graduate is exceptional because of what he *brought*, and that world's rules
    #      are untouched by him.
    #   2. *"'every wonder is alive, small and kept in a crock' — makes no sense. What is alive?
    #      What is a crock? What counts as a wonder?"* and *"'a cracked man in a warm room who
    #      doesn't know her name' — do you know what this means? I think nobody does."* §119's
    #      pitch clause banned mood and invented compounds and never said *define your nouns*.
    #   3. *"Cuttings — that is inherently a bad thing to have. Nobody wants more cuts on their
    #      bodies, they want cool powers."* §118 put the daydream at the top of the ladder and
    #      said nothing about the method, so a world can pair a summit worth wanting with a
    #      mechanism a reader recoils from.
    #
    # Measured against them the same day: `research/quality-measurement/comprehension_battery.py`,
    # which asks four readers to restate a premise and scores how much they agree. Complaint 2 is
    # a comprehension failure by construction and had no instrument until then.
_RULES: tuple[str, ...] = (
    "Every rule names at least three second-order consequences, each in a DIFFERENT domain of "
    "life from the allowed list. A rule whose consequences all land in one domain is one "
    "consequence with three faces. The consequences are where a world stops being a name.",
    "Every system, every rule, every rank and every creature carries `manifests_as`: one line "
    "of how it shows on the page — a printed line, a price paid, a mark worn, a sound, a change "
    "in how a stranger treats you. Never an explanation and never a lecture.",
    "Every rank has a form a reader can SEE, and every gain has a cost payable on the page in "
    "the same scene or earlier. A cost is paid in a body, in time, in risk, in something the "
    "person can no longer do, or in somebody who is now against them — never in money, never "
    "in a debt, and never in a piece of paper somebody files.",
    # **The ladder the reader counts, and it is one rule about what a world declares.**
    # `plan/handoff-numbers-go-up.md`: the operator's direction is that a rank ladder *is* the
    # genre's number — "bronze to gold rank advance is the same as the number going up; say
    # bronze is 1 and gold is 3" — so the quantity is the rung's place in the chain, counted
    # from the bottom, and the chain has to run in that direction to be counted.
    #
    # **Measured, and the ordering clause is the measurement's.** Of the four worlds forged
    # before this rule existed (pilots 2 and 3), two declared an ordinal criterion with a chain
    # of three or more and two did not; of those two, *Senior Water* declared its chain
    # highest-first (`first_water` at the bottom, `wash_right` at the top), so a reader counting
    # up that ladder counts a person getting weaker. And **no cast member of any of the four
    # stands anywhere on any chain**: a ladder with nobody on it is a costume with nobody in it.
    #
    # Nothing here says who rises, how fast, or how a rise should read. The opening standing is
    # a fact about where a book starts, in the register of every declared shape beside it; the
    # book is what happens next. `tests/test_architect.py` checks the rule text for the verbs an
    # outcome instruction would have to use.
    "At least one criterion has the comparator `ordinal` and carries `ranks`: a chain of AT "
    "LEAST THREE, listed LOWEST FIRST, each with a `visible_form` a reader can see, a "
    "`cost_to_reach` payable on the page, and a `grants` naming what that rung lets a person "
    "DO that the one below could not. **The chain is a chain of abilities and not of "
    "badges**: each rung is a bigger version of a tangible thing the person can do, they keep "
    "it, and nothing takes it back by default. Knowing more, being trusted more, or being "
    "allowed into a better room is not a rung. The protagonist's `standing` names that "
    "criterion by "
    "id and one of its rungs by id, and the rung is NOT the top one. The number a reader counts "
    "in this world is the rung's position from the bottom of that chain. The ladder is the "
    "world's FURNITURE and not its concept: a reader meets it as whatever THIS world calls "
    "its ordered standings, and the premise is about the person rather than about the "
    "chain. The surface form is the world's own and there is no house style for it — belts, "
    "grades, years, seals, colours, degrees, titles, thresholds and metals are all the same "
    "structure wearing different clothes, and a world that reaches for the nearest familiar "
    "set has skipped the part that was its own. **The words `ladder` and `rung` are this "
    "schema's and never the book's** — and so is `standing`, and so is any other word this "
    "schema uses for the machinery. None of them appear in the premise, in a rank's name, "
    "or anywhere a reader would see. A premise that says somebody wants to get high enough "
    "up the ladder has printed the scaffolding instead of the building, and one that says a "
    "girl runs hotter than her standing should allow has done it again in a different word. "
    "Name the rung this world names, in this world's own language.",
    # **The domain rule built five worlds set inside a trade, and the operator named it.**
    # Assaying, grafting, surveying, bell-founding, dyeing — the rule asked for a real domain of
    # human *work*, and the forge answered with the workshop, the yard, and the trade's own
    # vocabulary as the world's. Read on 2026-08-23: *"it just reads as too unnecessarily esoteric
    # and the concept isn't inspirational ... the words used are adding unnecessary complexity eg
    # mordant"*. Measured beside it: 32 worlds, 27 distinct domains, every one a trade, a science
    # or a body of law (§118.1).
    #
    # The physics was never the problem and every original clause is kept: a system whose costs
    # are a real craft's real constraints is what makes a world argue back. What is added is where
    # that craft belongs — under the hood rather than on the page — because the register rule
    # below already asks for "fast, plain, popcorn reading" and this rule was handing that prose a
    # glossary to write it in.
    "Literalise one real domain of human work or knowledge and take the system's logic and its "
    "costs from that domain's real constraints. Name the domain. The book should run on real "
    "ideas rather than invented ones. **The domain is the engine, not the setting.** The book "
    "is not set inside that trade, the trade is not the world's institution, and the domain's "
    "technical vocabulary never reaches the page — a reader learns none of its words and "
    "needs none. What somebody can do is said in plain words a reader could repeat after one "
    "read: the physics of a real craft, wearing none of its jargon.",
    # **The rule this module did not have, and sixteen rules went out without it.** Every rule
    # here asked what a world *declares* — consequences, manifestations, visible rungs, costs, a
    # ladder, an inventory, a protagonist, an inversion, mysteries with answers — and exactly one
    # contained the word *want*, where it means what one character wants. None asked whether
    # anybody would want any of it. §113 made the rungs countable and §114 made the abilities
    # distinct, and between them they produced a countable, distinct inventory of chores; the
    # operator's phrase for what was missing is *"Readers want to feel cool and progress in
    # meaningful ways"* (§118).
    #
    # **The examples are the operator's own, in two lists, kept in their order.** First: inventing
    # something useful, gaining popularity, control over things or the world, immortality,
    # becoming something greater, superhuman skills, and being unusually good at a craft more
    # easily than anyone else. Then: healing powers, control over the body, control over
    # mutations, creating a new sort of life, developing advanced technology, superhuman
    # augmentation — and earning money. An example list is what a model actually steers by, so
    # they are written into the rule rather than summarised.
    #
    # **Two of those items settle questions the rules beside this one would otherwise leave
    # open.** *Being effortlessly the best at something* is why neither this rule nor the domain
    # rule above bans crafts: the daydream is the ease and the standing, and learning what a
    # mordant is is homework. And *earning money* is not what the administration rule forbids —
    # a fortune somebody wins, spends and is envied for is a prize; a debt, a register and a filed
    # piece of paper are the chore. The rule says so in its own last sentence rather than leaving
    # two rules looking as though they disagree.
    #
    # It asks for a declaration and stops there, in the register of the declared-shape rules
    # beside it: nothing here says the wish should be a good one, that a reader should like it, or
    # that anybody achieves it. A ladder is a fact about the world; who climbs it is the book's.
    "Say what a person would want to be able to do here, and put that at the TOP of the "
    "ladder. The upper rungs are the daydream: moving faster than anyone can react; striking "
    "harder than a body should; seeing what nobody else sees; healing what nobody heals, "
    "including yourself; commanding your own body down to what it is made of, or changing "
    "what it is made of; surviving what should not be survivable, or not dying at all; "
    "commanding something dangerous; making a living thing that never existed; building the "
    "machine nobody has built; inventing the thing everybody ends up using; being known by "
    "people who have never met you; holding real control over things or over other people; "
    "getting rich; becoming something greater than you were; or being extraordinary at "
    "something that costs everybody else a lifetime. The lowest rungs are the beginner's "
    "version of that same thing, so a reader sees the whole climb from the bottom rung. A "
    "ladder whose top rung is a better version of a chore is a job. **The way it WORKS has "
    "to be wanted too, and not only where it ends.** A rung bought with something a reader "
    "would recoil from — another cut opened on your body, another piece of yourself handed "
    "over — is a rung nobody wants to stand on, whatever waits at the top; and a power "
    "whose method is unpleasant has to buy something worth having in the same breath, or a "
    "reader declines the whole ladder. Getting rich is a PRIZE "
    "and never an administration: a fortune somebody makes, spends and is envied for is a "
    "daydream, while a debt, a register, a tariff and a filed piece of paper are the chore "
    "the rule above forbids, and they are not the same thing.",
    "Give the world two systems whose logics are incompatible, and say what happens at the "
    "interface between them: which one wins where they disagree, what it does to a person "
    "caught between them, who is forced to choose, and what somebody can do under one and "
    "never under the other. The interface is the content, and it is physical or personal — a "
    "proving ground, a refusal to teach, a body that cannot hold both, a technique that "
    "unmakes another technique. It is NOT an exchange rate, a market, a court, a licence or "
    "a tariff.",
    # **Measured before it was written, over every world this project had forged.** Thirty
    # candidates, four briefs, both prompt shapes: every one carries administrative vocabulary,
    # at a median of 7.21 words per 1,000 of declared text and a minimum of 2.69, and **18 of
    # the 30 name a register, a debt, a court, a deed or a clerk in the PREMISE** — the one
    # sentence a reader meets first. The operator read three such premises on 2026-08-23 and
    # refused all three: *"All these sounds depressing and incredibly boring. Anything related
    # to debt or ledgers is a no no in a story"*.
    #
    # **The bias was this module's own text and not the model's.** The rule above described an
    # interface as an exchange rate and what the law says; the capability rule offered *a debt*
    # as a legitimate subject for a world; the mystery rule called an unpaid secret *a debt the
    # book can never pay*; and no rule anywhere said what a cost is paid IN. Four lines of
    # instruction, thirty worlds, one genre.
    #
    # It fences the *subject* and nothing else. A world may still charge brutally, may still
    # have institutions, and may still put somebody under an obligation they hate — what it may
    # not do is make the paperwork the point.
    "This world is a place people live in, not an administration. Its institutions are ones a "
    "reader would want to walk into — a school, a crew, a proving ground, a border post, a "
    "workshop, a rival house — and the pressure on people comes from rivals, teachers, "
    "distance, weather, wounds, hunger, time and each other. Do NOT organise a world, a "
    "system, a premise or the protagonist's problem around a debt, a ledger, a register, a "
    "licence, a deed, a tariff, a court, a wage or a filed piece of paper.",
    # **The one default that is not on the table, and the amendment is measured.**
    # `plan/handoff-numbers-go-up.md` Task 0.3: on the brief "progression fantasy", all three
    # forged worlds inverted a piece of this exact rule — *Senior Water* removed "portable
    # personal power", *What Takes* removed "a gain can be created", *The Closing Error* removed
    # "monotonic growth" — and the picked one then wrote two chapters in which nothing anybody
    # carried ever went up. An inversion rule with no floor deletes the genre's one
    # non-negotiable default three times out of three.
    #
    # It fences the *declaration* and nothing else: a world may still price a rise brutally, make
    # it revocable later by directive, or hand it to somebody who does not want it.
    "You MAY remove or invert ONE default of the genre — at most one, and never this one, "
    "which is not invertible here: the protagonist's standing on a declared ordinal ladder "
    "can rise, and the reader can count it. If you do, say what fills the hole. **A world "
    "that keeps every default and takes its distinctness from its engine and from the "
    "person it happens to is legitimate**, and is often the better book; `inversion` may say "
    "exactly that, and one of two worlds saying it is a healthy answer rather than a lazy "
    "one.",
    # **An inventory, beside the ladder rather than instead of it.** Measured over the 24 worlds
    # forged before 2026-08-22: 135 of 156 criterion rungs are an insignia — a mark other people
    # read — and permission outnumbers capability 104 to 46, because `_RANK` has a slot for what a
    # rung LOOKS like and one for what it COSTS and none for what it lets you do. The operator
    # read the book that came out of that and called its progression "boring accounting instead of
    # nine unique abilities" (`plan/reader-read-4.md` §1a).
    #
    # The rule asks for a set and says nothing about its size: *nine* is the operator's word for
    # an inventory, not a threshold, and `plan/handoff-ability-inventory.md` boundary 3 forbids a
    # floor. Nothing here says the protagonist should be good at them, should win with them, or
    # should have more of them than anybody else — an inventory declared is a fact about the
    # world, and who wins is the book's.
    "If people in this world can DO things — distinct, nameable things somebody either can or "
    "cannot do — list them in `capabilities`, and give the protagonist the ones they START "
    "with. A capability is what somebody can do; a rank is where somebody stands; they are "
    "different, and a world may declare either, both, or neither. Each capability carries what "
    "it lets a person do, how it shows on the page when it is used, what having it costs, "
    "whatever it needs first by id, and whoever teaches it if anyone does. A world about "
    "standing, or about one place, or about a single relationship may leave this out "
    "entirely, and many should.",
    # **The rule above inverts a default for everyone; this one declares an exception for one.**
    # `plan/reader-read-3.md` note 1: the operator read two chapters of a book forged on this
    # schema and named the premise as the defect — "readers desire … something that doesn't
    # happen to anyone else" — and measured against the module the gap was exact. The words
    # protagonist, main character and hero did not occur here, the outline invented whoever
    # acted, and none of the five forged cast members reached the page.
    #
    # It is written as a rule about what a world DECLARES, in the register of the declared-shape
    # rules beside it, and it stops there. Nothing in it says how to write the person, whether
    # the reader should like them, or that they win: an exception declared is a fact about the
    # world, and who wins is the book's. `tests/test_architect.py` checks the rule text for the
    # verbs an outcome instruction would have to use.
    "Name one member of the cast as this world's `protagonist`. Choose the one rule or "
    "cardinality shape this world declares that does not hold for them, or holds "
    "differently. **Prefer an exception they BROUGHT over one the world was bent to give "
    "them.** The cleanest version is that this person arrived carrying something nobody "
    "here has — a training, a habit of mind, an object from where they came from — and the "
    "world's rules are untouched by their presence. The version to avoid is a limitation "
    "invented for everybody else whose only job is to leave one person outside it: if a "
    "declared rule would not exist in this world were it not for this one character, it is "
    "a contrivance, and a reader can feel the shape of it. Nobody here being able to hear "
    "their own voice, so that one person can, is that shape. **If this person came from "
    "somewhere like our own world, the life they came from is one a reader in their "
    "twenties has lived**: an age near the reader's own, a degree they are not using, a job "
    "that covers the rent, a thing they know far too much about for no professional reason. "
    "What they bring is an education, a hobby or an obsession rather than thirty years at a "
    "trade — a reader owns the first three and cannot picture the fourth. "
    "and put **its id alone** in `exception` — one snake_case word such as "
    "`rule_seed_never_true`, with no dash and no clause after it. What that rule says is "
    "already written where the rule is declared, and a sentence there is not an id. Then give "
    "the `edge` that exception grants them, written the way `manifests_as` is written — how it "
    "shows on the page, never an explanation; what they want; and the price the exception "
    "charges them, payable on the page. If the exception is a cardinality shape, that shape "
    "lists their id in its `except`. Write the `premise` as that person's situation — who they "
    "are, what is singular about them, what is in the way — rather than as a description of "
    "the world, and name them in it. **Write it as a PITCH and not as prose**: plain modern "
    "English, in the order things happen, the way one person tells a friend what a book is "
    "about. Who they were before, what happened to them, what they can do here that nobody "
    "else can, and what they are heading toward. No mood, no imagery, no invented compound "
    "phrases, and no sentence that would only ever appear in a novel. Somebody who has read "
    "nothing but the premise should be able to repeat it accurately, in their own words, "
    "after one read. **Every noun a reader has not met before is explained in the same "
    "breath or it is not used.** A premise saying that every wonder here is alive and small "
    "and kept in a crock has spent three words the reader cannot cash — what is alive, what "
    "is a crock, what counts as a wonder — and a person named as a cracked man in a warm "
    "room is a person nobody can picture. Name the thing in words a reader already owns, or "
    "say what it is the first time it appears. **This holds hardest in the last third**, "
    "which is where it is always dropped: the school, the rival, the complication and the "
    "clock all arrive together at the end and each one drags in a name. Measured over the "
    "premises forged before this clause, EVERY term readers could not follow first appeared "
    "between 65% and 96% of the way through — `the cold hill`, `nine deep`, `frost rooms`, "
    "`keeper`, `the lists`. A noun in the last sentence owes the same half-clause as a noun "
    "in the first: not `measured against the frost rooms`, but `measured against the frost "
    "rooms, where they test how cold a pair of hands runs`. **Around 200 words, and 300 is "
    "too many.** Measured over the premises forged today: at 172 words a reader could not "
    "follow one thing, at 337 five, at 407 eight. Past that length a premise has stopped "
    "pitching a person and started explaining a world, and every extra sentence brings in "
    "another name that owes a gloss.",
    "Mysteries: each carries its ANSWER written down and the scene number where the reader "
    "learns it. A secret with no recorded answer is a promise the book can never keep. This "
    "world is an open-ended serial, so most answers land far out — but **at least one must be "
    "answered inside the {scenes} scenes being written now**, because an opening that asks "
    "four things and settles none teaches a reader that nothing here gets settled.",
    # The last clause is the operator's direction and not a softening of the rest of the rule:
    # the ladder's rungs ARE the numbers this world counts, so a world that wanted a stat block
    # to satisfy "numbers go up" has already been answered by the ladder rule above.
    # **`what a person can do` is added to this list, and the addition is measured.** The four
    # words this rule offered were crafting, standing, understanding and access — and *standing*
    # and *access* are permission systems, which are administered, which is what a register, a
    # board and a ward are for. Two of the three worlds picked for a pilot took exactly those two
    # words: pilot 2's `progression_means` opens with the single word "Standing.", pilot 4's is
    # tolerance and "what door it may stand in". The forge took the rule at its word and the
    # operator read the result as accounting (`plan/reader-read-4.md` §1a).
    "A world may have one system, several, or none; progression may be crafting, standing, "
    "understanding, access, what a person can do, or something else. Do not assume combat. Do "
    "not use levels, hit "
    "points, mana, experience points, currency, or any single number that means power, unless "
    "this particular world genuinely needs one and you say why in the system's logic. The "
    "ladder's rungs are the numbers this world counts; hit points, mana, experience and "
    "currency are still not assumed.",
    "Every name, place, creature and mechanic is original to this world. Never name, quote, "
    "imitate, or compare to any real person, brand, game, or published work.",
    "The prose this world will be written in is fast, plain, popcorn reading. The world shows "
    "on the page as interactions, prices paid and visible ranks. It is never explained.",
    "This is genre fiction and the genre's own furniture is WELCOME rather than avoided: an "
    "academy, a tournament, a master worth impressing, a party who travel together, a rival "
    "house, a first test, a system that speaks up. A reader came for those. Originality "
    "belongs in the engine underneath and in the person it happens to, never in refusing "
    "what the genre is for. A world nobody recognises is not a fresh world, it is a "
    "different book than the one somebody picked up.",
    "Ids are lowercase snake_case and unique within the world. Every id referenced anywhere "
    "must be declared somewhere.",
    "Cast, agencies and institutions carry `relationships`: who owes whom, who employs whom, "
    "who blames whom, who outranks whom. Each is a snake_case predicate, another declared id, "
    "and the one thing about the tie a scene could use. A cast with no ties between its "
    "members is a list of people rather than a place.",
    # **A world with a ladder declares the line the ladder is read off, and the predicate is
    # named from `domain/worlds.py` rather than typed here.** The chain this handoff exists to
    # close is *declare → ask → print → read*, and it was broken at the first link in a way no
    # count showed: all four worlds forged before this rule declared a `graph_line`, none of
    # their phrases meant "stands at", so `extract_graph_facts` had nothing to read a standing
    # out of even where it ran on every accepted scene.
    #
    # "Most worlds should leave it out" becomes "a world with no ladder may": the shape bounds
    # (`LABEL_WORDS`, `PHRASE_WORDS`) already refuse a paragraph, and a world that announces
    # nothing still owes nothing.
    "`graph_line` is a PARSER, not a summary: a bracket tag of one or two words, and short verb "
    "phrases of at most six words, so that `[TAG] Sella now holds the second seal` reads as a "
    "line a scene would actually print. A world that declares a ladder DECLARES a `graph_line`, "
    "and at least one of its phrases carries the predicate "
    f"`{worlds_mod.STANDS_AT_PREDICATE}` — the printed form this world says a change of "
    "standing in, so that a scene prints the line and it can be read back. Only a world with no "
    "ladder may leave `graph_line` out.",
)

_DISTINCTNESS_RULE = (
    "The {k} worlds must be structurally different, not one world re-dressed. Each must "
    "literalise a DIFFERENT real domain, use a DIFFERENT geometry from the allowed list, and "
    "mean something DIFFERENT by the word progression. Two worlds that differ only in their "
    "names are one world and will be refused."
)

_DOMAIN_FIRST_RULE = (
    "Work in this order inside your answer, and let the order show: first fix the real domain "
    "and write down the constraints that are actually true of it — what it costs, what it "
    "cannot do, what goes wrong, who gets hurt, and what it takes out of the person doing it. "
    "Then derive the system from those "
    "constraints so that every rule is a real constraint of the domain wearing the world's "
    "clothes. Do not invent a system and then decorate it with a domain's vocabulary."
)


def render_world_request(
    brief: str, *, k: int = DEFAULT_K, shape: str = DIRECT, scenes: int = DEFAULT_SCENES
) -> CompletionRequest:
    """One structured request for K worlds.

    `brief` is an operator directive or a Director brief — a genre, a real domain, a mood, or
    nothing. Empty is legitimate and is the interesting case: a world built from no direction at
    all is the control against which a directed one is read.

    **`scenes` is here because the first live forge did not have it and the omission showed.**
    Asked for reveal positions with no idea how long the book was, the model scheduled all four
    of a world's answers at scenes 17, 25, 33 and 41 — perfectly reasonable for an open-ended
    serial and useless for the two chapters actually being written, which would have opened four
    debts and settled none. That is the "40 opened, 0 paid" defect reproduced by a fix for it.
    """
    if k < 2:
        raise ArchitectInputError(
            f"a forge over {k} candidate(s) is not a search; K must be at least 2"
        )
    if scenes < 1:
        raise ArchitectInputError(f"a book of {scenes} scene(s) has nowhere to put a reveal")
    if shape not in PROMPT_SHAPES:
        raise ArchitectInputError(
            f"unknown prompt shape {shape!r}; the shapes are {', '.join(PROMPT_SHAPES)}"
        )
    rules = [
        _DISTINCTNESS_RULE.format(k=k),
        *(rule.format(scenes=scenes) if "{scenes}" in rule else rule for rule in _RULES),
    ]
    if shape == DOMAIN_FIRST:
        rules.insert(1, _DOMAIN_FIRST_RULE)
    prompt = json.dumps(
        {
            "brief": brief.strip() or "(none: build whatever world you would most want to read)",
            "return": f"exactly {k} worlds",
            "scenes_being_written_now": scenes,
            "allowed_geometries": list(GEOMETRIES),
            "allowed_consequence_domains": list(worlds_mod.CONSEQUENCE_DOMAINS),
            "allowed_comparators": list(worlds_mod.COMPARATORS),
            "rules": rules,
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return CompletionRequest(
        prompt=prompt,
        system=_SYSTEM_MESSAGE,
        schema=WORLDS_SCHEMA,
        max_output_tokens=32000,
        profile=PROFILE,
        call_class=CALL_CLASS,
        # **Measured, not chosen.** The first live forge — K=3, this schema, the pinned provider
        # — hit `CompletionRequest`'s 300-second default and raised `RetryableProviderError`
        # before a single world came back. Three complete worlds is the largest structured
        # answer anything in this repository asks for, and the default was set for a scene.
        timeout_seconds=1800.0,
    )


# --- the gates ----------------------------------------------------------------------------------

#: Comparison-to-an-external-work syntax. **A structural guard that names nothing**, which is
#: deliberate: a deny-list of titles inside a generation-side module would put named works into
#: the generation path, which is the boundary §97.3 draws and the one this project has already
#: walked to the edge of once. It catches the shapes a model reaches for when it borrows; it does
#: not catch a borrowed idea in original words, and no pattern would. **A vocabulary guard is not
#: comprehension** — the prompt carries the rule as well, and the two together are the whole of
#: what is claimed.
#:
#: **Narrowed 2026-08-21 after a measured false positive, which is this repository's third
#: instance of one failure.** The first version carried a bare `\bfranchise\b`. On the first live
#: `domain_first` forge it refused **two of three** worlds — a port whose *franchise* is the right
#: to vote, a ward surrendering its *franchise* — that is, ordinary legal English, in worlds
#: literalising salvage law and civic charter. `directors._CRAFT_INSTRUCTION` records the same
#: shape (a recall-tuned list run as a refusal gate has inverted error economics) and
#: `writer-roster.md` R1's em-dash refusal records it again. A media reference is a *named* thing,
#: so the surviving alternative requires capitals; `franchise`, `series` and `saga` are only
#: borrowed when a title precedes them.
_BORROWED = re.compile(
    r"(?i:\b(?:inspired by|reminiscent of|similar to|as seen in|as in the"
    r"|based on the|in the style of|homage to|riff on|a la|fan[- ]?fic)\b)|[®™]"
    # Case-sensitive on purpose: a media reference is a *named* thing, so the title-shaped
    # alternative requires capitals. `(?i:…)` scopes the phrase list's insensitivity above.
    r"|\bthe [A-Z][\w'-]*(?: [A-Z][\w'-]*){0,3} (?:series|franchise|saga)\b"
    # **The same narrowing a second time, and this one is measured over every world forged.**
    # `like in` sat in the case-insensitive list above until 2026-08-23, when it refused a
    # world over “reciting what a field looked like in a year before the listeners were
    # born”. Run over the 30 candidates forged before that date the whole guard fires
    # **once**, and that once is this false positive: no other phrase in the list has ever
    # fired on a forged world. So the phrase gets the capitals requirement the title-shaped
    # alternative already carries — a media reference is a named thing — rather than being
    # deleted, which would leave the guard one fewer way to catch what it exists for.
    r"|\blike in (?:the )?[A-Z]"
)


#: The administrative vocabulary a world may not be *about*, and why it is a word list.
#:
#: **Measured over the 30 worlds forged before 2026-08-23** — four briefs, both prompt shapes,
#: every pilot this project has run. Administrative words appear in **every one of them**, at a
#: median of 7.21 per 1,000 words of declared text (minimum 2.69, maximum 17.92), and **18 of the
#: 30 name one in the premise**, which is the sentence a reader meets first. The operator read
#: three such premises on 2026-08-23 and refused all three. `_RULES` is where that bias came from
#: and where it is fixed; this list is how the fix is checked.
#:
#: **`price`, `cost`, `pay` and `bond` are deliberately absent.** The schema asks every rule for a
#: price and every cast for its bonds, so counting those would count this module's own
#: instructions rather than the world. What is counted is the paperwork around them.
#:
#: **`court` came out on the first forge run under the amended rules, and the arithmetic is
#: recorded rather than argued.** A world of bell-founders held its duels on the *Bell Court*,
#: which is an arena, and the premise check refused it. Over the 30 worlds forged before this
#: list existed the premise check fires on 18 with `court` in the family and on **17 without**,
#: so the whole word buys one world in thirty and costs every yard, tennis and courtyard in the
#: language. `courtroom` stays, and so do `bailiff`, `docket`, `writ`, `magistrate`, `tribunal`
#: and `plaintiff`, which mean only the one thing. This module has now narrowed a word guard
#: from a measured false positive three times — `franchise`, `like in`, and this — and the
#: economics are the same each time: a recall-tuned list run as a refusal has them inverted.
_ADMINISTRATION: frozenset[str] = frozenset(
    """
    debt debts debtor debtors creditor creditors ledger ledgers register registers registry
    registries tariff tariffs licence licences license licenses courtroom docket dockets
    deed deeds lien liens wage wages tax taxes taxed levy levies fee fees rent rents invoice
    invoices contract contracts clerk clerks bailiff bailiffs arbitrate arbitrates arbitration
    litigation lawsuit mortgage mortgages toll tolls warrant warrants statute statutes
    magistrate magistrates notary audit audits auditor bookkeeping receipt receipts writ writs
    tribunal plaintiff broker brokers brokerage owed owes owing forfeiture forfeit assessor
    assessors filing filings claimant compensation indemnity arrears surety collateral
    """.split()  # noqa: SIM905 — a word list is prose, and reads as prose
)

_WORDS = re.compile(r"[a-z]+")


def _administration_in(text: str) -> tuple[str, ...]:
    """The administrative words in one piece of text, first-seen order, each named once."""
    seen: dict[str, None] = {}
    for word in _WORDS.findall(text.lower()):
        if word in _ADMINISTRATION:
            seen.setdefault(word, None)
    return tuple(seen)


def _declared_prose(value: Any) -> str:
    """Every string a world declares, key names excluded — what it says, not how it is filed."""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return " ".join(_declared_prose(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_declared_prose(item) for item in value)
    return ""


def _administration_rate(candidate: Candidate) -> float:
    """Administrative words per 1,000 words of declared text. A distribution, never a bar."""
    words = _WORDS.findall(_declared_prose(candidate.raw).lower())
    if not words:
        return 0.0
    return round(1000 * sum(1 for word in words if word in _ADMINISTRATION) / len(words), 2)

#: How many second-order consequences, in distinct domains, a declared rule owes. Three, and it
#: is the operator's figure taken as given rather than a measured threshold — recorded as chosen
#: so nobody later quotes it as measured. What makes it safe is that it gates a *candidate*, so
#: the cost of it being wrong is one of K rather than a serial.
CONSEQUENCE_FLOOR = 3


@dataclass(frozen=True, slots=True)
class Candidate:
    """One world as the model returned it, plus where it sat in the answer."""

    index: int
    raw: Mapping[str, Any]

    @property
    def title(self) -> str:
        return str(self.raw.get("title") or "").strip()

    @property
    def domain(self) -> str:
        return str(self.raw.get("domain") or "").strip()

    @property
    def geometry(self) -> str:
        return str(self.raw.get("geometry") or "").strip()

    @property
    def protagonist(self) -> Mapping[str, Any] | None:
        """The world's declared protagonist, or `None` for a world that declares none.

        `None` rather than an empty mapping: "this world says nothing about whose book it is"
        and "this world says its protagonist is nobody" are different, and every world forged
        before 2026-08-22 is the first.
        """
        raw = self.raw.get("protagonist")
        return raw if isinstance(raw, Mapping) else None

    def rendered(self) -> str:
        """The candidate as one canonical string, for a distance measure to run over."""
        return json.dumps(self.raw, ensure_ascii=False, sort_keys=True, indent=1)


def _fold(text: str) -> str:
    return " ".join(text.lower().split())


def worlds_from(payload: Mapping[str, Any], k: int) -> tuple[Candidate, ...]:
    """The model's K worlds, or a refusal naming what was wrong.

    **The collapse gate is here rather than hoped for**, and it is stricter than
    `plan_search._alternatives`' — which is exact string equality after casefolding and therefore
    cannot catch a re-worded collapse, a limitation that module's own docstring claims to prevent
    and does not. Here the axes are *declared*, so the check is on the declaration: two worlds
    that name the same real domain, or the same geometry, are one world in two hats, and they are
    refused before a single scene is paid for.

    It is still not a semantic check and does not claim to be. A model that writes "coopering"
    and "barrel-making" defeats it.
    """
    raw = payload.get("worlds")
    if not isinstance(raw, list):
        raise ArchitectOutputError("the answer must carry a list of worlds")
    if len(raw) != k:
        raise ArchitectOutputError(
            f"{len(raw)} world(s) returned; the forge asked for exactly {k}"
        )
    candidates: list[Candidate] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise ArchitectOutputError(f"world {index} is not an object")
        candidate = Candidate(index, entry)
        for field_name, value in (
            ("title", candidate.title),
            ("domain", candidate.domain),
            ("geometry", candidate.geometry),
            ("premise", str(entry.get("premise") or "").strip()),
        ):
            if not value:
                raise ArchitectOutputError(f"world {index} has no {field_name}")
        if candidate.geometry not in GEOMETRIES:
            raise ArchitectOutputError(
                f"world {index} declares the geometry {candidate.geometry!r}; the allowed "
                f"geometries are {', '.join(GEOMETRIES)}"
            )
        # **Refused here and nowhere downstream.** The forge must say whose book this is;
        # `records_for` must not, because `plan/serial-pilot-2-world.json` predates the field and
        # regenerating it byte-for-byte is what "reproducible" means here
        # (`test_the_pilot_package_regenerates_the_world_it_was_run_on`).
        #
        # Each field is checked for emptiness rather than for presence, because the schema's
        # `minLength` is a request and not a guarantee: the 2026-08-22 forge returned a world
        # whose `premise` was the empty string under a schema that asked for a string.
        protagonist = candidate.protagonist
        if protagonist is None:
            raise ArchitectOutputError(
                f"world {index} names no protagonist; a world says whose book it is, and the "
                "one it does not is a world an outline will invent a person for"
            )
        for field_name in ("id", "exception", "edge", "wants", "price"):
            if not str(protagonist.get(field_name) or "").strip():
                raise ArchitectOutputError(
                    f"world {index}'s protagonist has no {field_name}"
                )
        # **The standing is refused here for the same reason and on the same rail.** A forged
        # world says where its protagonist starts on the ladder it declared; `records_for` still
        # tolerates absence, so every world forged before 2026-08-22 regenerates unchanged.
        # Checked for emptiness rather than presence — `minLength` is a request, and the
        # 2026-08-22 forge returned an empty conforming `premise` for $1.48.
        standing = protagonist.get("standing")
        if not isinstance(standing, Mapping):
            raise ArchitectOutputError(
                f"world {index}'s protagonist names no standing; a world whose protagonist "
                "stands nowhere on its own ladder has declared a ladder with nobody on it"
            )
        for field_name in ("criterion", "rung"):
            if not str(standing.get(field_name) or "").strip():
                raise ArchitectOutputError(
                    f"world {index}'s protagonist standing has no {field_name}"
                )
        candidates.append(candidate)

    for axis, values in (
        ("domain", [_fold(c.domain) for c in candidates]),
        ("geometry", [_fold(c.geometry) for c in candidates]),
        ("premise", [_fold(str(c.raw.get("premise") or "")) for c in candidates]),
    ):
        repeated = sorted({value for value in values if values.count(value) > 1})
        if repeated:
            raise ArchitectOutputError(
                f"{len(repeated)} {axis} value(s) appear more than once across the {k} worlds "
                f"({', '.join(repeated)}); a collapsed forge is one world drafted K times, and "
                "the distinctness gate refuses it before any scene is paid for"
            )
    return tuple(candidates)


def _items(candidate: Candidate, key: str) -> tuple[Mapping[str, Any], ...]:
    raw = candidate.raw.get(key)
    if not isinstance(raw, list):
        return ()
    return tuple(entry for entry in raw if isinstance(entry, Mapping))


def _declared_rule_ids(candidate: Candidate) -> frozenset[str]:
    """Every rule id declared inside a system of this world."""
    found: set[str] = set()
    for system in _items(candidate, "systems"):
        rules = system.get("rules")
        for rule in rules if isinstance(rules, list) else ():
            if isinstance(rule, Mapping) and _identifier(rule):
                found.add(_identifier(rule))
    return frozenset(found)


def premise_names_protagonist(candidate: Candidate) -> bool:
    """Whether this world's premise says its protagonist's name. `False` when it declares none.

    Word-boundary rather than bare substring, so a two- or three-letter id part cannot be
    satisfied by the middle of an unrelated word — the failure class `worlds.key_nouns` records
    for its own first live run, where `mour` and `ise` arrived out of the middle of longer ids.

    **It checks the name and nothing else.** Whether the premise is *written as* that person's
    situation is a judgment and there is no instrument for it in this project; whether it says
    their name is arithmetic, and the arithmetic is what gets reported.
    """
    protagonist = candidate.protagonist
    if protagonist is None:
        return False
    premise = str(candidate.raw.get("premise") or "").casefold()
    tokens = [part for part in _identifier(protagonist).split("_") if part]
    return any(re.search(rf"\b{re.escape(part)}\b", premise) for part in tokens)


def _declared_subjects(candidate: Candidate) -> frozenset[str]:
    """Every id this world declares as a thing: people, places, capabilities, rungs and the rest.

    What a prerequisite or a teacher is allowed to point at. Built from the answer rather than
    from a list of array names kept in step by hand — a new array added later and forgotten here
    would silently make every reference into it a complaint.
    """
    found: set[str] = set()
    for value in candidate.raw.values():
        if not isinstance(value, list):
            continue
        for entry in value:
            if isinstance(entry, Mapping) and _identifier(entry):
                found.add(_identifier(entry))
    for system in _items(candidate, "systems"):
        criterion = system.get("criterion")
        if not isinstance(criterion, Mapping):
            continue
        ranks = criterion.get("ranks")
        for rank in ranks if isinstance(ranks, list) else ():
            if isinstance(rank, Mapping) and _identifier(rank):
                found.add(_identifier(rank))
    return frozenset(found - {""})


def _capability_complaints(candidate: Candidate) -> tuple[str, ...]:
    """Whether a declared inventory *refers*. Empty for a world that declares none.

    **Three membership checks and no count.** Whether nine is the right number of abilities,
    whether these are interesting ones, and whether the protagonist has enough of them are not
    asked here and have no instrument in this project: `plan/handoff-ability-inventory.md`
    boundary 3 forbids a floor, and `report()` carries the counters instead so that a
    distribution can exist before anybody declares a bar over it (§81, §85, §87, §89).

    What is checkable is that a prerequisite names something this world built, that a teacher
    exists, and that the protagonist's starting inventory is drawn from the world's own list.
    """
    declared = {_identifier(entry) for entry in _items(candidate, "capabilities")} - {""}
    if not declared:
        return ()
    complaints: list[str] = []
    subjects = _declared_subjects(candidate)

    for entry in _items(candidate, "capabilities"):
        subject = _identifier(entry)
        needs = entry.get("requires")
        for target in needs if isinstance(needs, list) else ():
            wanted = worlds_mod.normalise_id(str(target))
            if wanted and wanted not in subjects:
                complaints.append(
                    f"capability {subject} requires {wanted!r}, which this world never "
                    "declares; a prerequisite naming nothing is a sentence about difficulty"
                )
        teacher = worlds_mod.normalise_id(_text(entry, "taught_by"))
        if teacher and teacher not in subjects:
            complaints.append(
                f"capability {subject} is taught by {teacher!r}, whom this world never declares"
            )

    protagonist = candidate.protagonist or {}
    held = protagonist.get("capabilities")
    for target in held if isinstance(held, list) else ():
        wanted = worlds_mod.normalise_id(str(target))
        if wanted and wanted not in declared:
            complaints.append(
                f"the protagonist starts with {wanted!r}, which is not one of the declared "
                f"capabilities ({', '.join(sorted(declared))})"
            )
    return tuple(complaints)


def _protagonist_complaints(candidate: Candidate) -> tuple[str, ...]:
    """Deterministic complaints about a world's declared protagonist. Empty when it declares none.

    **Three membership checks and a substring, and deliberately nothing else.** No model is
    asked whether the hook is good, whether the edge is interesting, or whether this person is
    the right one to write about — that question has no instrument in this project and inventing
    one here would be the verdict channel `plan/world-architect.md` §2 keeps shut. What is
    checkable is whether the declaration *refers*: whether the person is somebody this world
    declared, whether the exception names a rule or shape this world declared, and whether the
    premise is about them.

    Silent for a world with no protagonist, which is every world forged before 2026-08-22 and
    the reason `test_the_pilot_package_regenerates_the_world_it_was_run_on` still gates clean.
    """
    protagonist = candidate.protagonist
    if protagonist is None:
        return ()
    complaints: list[str] = []
    subject = _identifier(protagonist)
    cast_ids = {_identifier(entry) for entry in _items(candidate, "cast")} - {""}
    if subject not in cast_ids:
        complaints.append(
            f"the protagonist is {subject or '(unnamed)'!r}, which is not one of the declared "
            f"cast ({', '.join(sorted(cast_ids)) or 'none'}); a book is about somebody this "
            "world has heard of"
        )
    exception = worlds_mod.normalise_id(_text(protagonist, "exception"))
    shape_ids = {_identifier(entry) for entry in _items(candidate, "cardinality")} - {""}
    declarable = _declared_rule_ids(candidate) | shape_ids
    if exception not in declarable:
        complaints.append(
            f"the protagonist's exception names {exception or '(nothing)'!r}, which is neither "
            "a declared rule nor a declared cardinality shape; an exception to nothing in "
            "particular is a description"
        )
    stated = {
        _identifier(entry): _text(entry, "wants")
        for entry in _items(candidate, "cast")
        if _text(entry, "wants")
    }
    wants = _text(protagonist, "wants")
    if subject in stated and wants and _fold(stated[subject]) != _fold(wants):
        complaints.append(
            f"{subject} wants {stated[subject]!r} as a cast member and {wants!r} as the "
            "protagonist; one person wants one thing at a time, and the cast entry is the one "
            "that reaches canon"
        )
    if subject and not premise_names_protagonist(candidate):
        complaints.append(
            f"the premise never names {subject!r}; a premise that describes the world rather "
            "than this person's situation is the shape `plan/reader-read-3.md` note 1 named"
        )
    return tuple(complaints)


#: The shortest chain a rung's position can be a number on. Two rungs is a switch — you are
#: either the one thing or the other — and a reader counting 1 then 2 has counted a state change
#: rather than a ladder. Three is the floor the operator's own example sets: bronze is 1 and gold
#: is 3. Stated here so nobody later quotes it as measured; it is a choice, like
#: `CONSEQUENCE_FLOOR`, and it gates a candidate rather than a serial.
LADDER_FLOOR = 3


def _ladders_of(candidate: Candidate) -> dict[str, tuple[str, ...]]:
    """Each declared criterion's id → its rank ids in declaration order, off the raw answer.

    Read from the answer rather than from `records_for` because the gate runs on the answer and
    a rank whose id normalises to nothing never becomes a record — which would make it invisible
    to a check whose whole job is to notice that the chain is too short.
    """
    found: dict[str, tuple[str, ...]] = {}
    for system in _items(candidate, "systems"):
        criterion = system.get("criterion")
        if not isinstance(criterion, Mapping):
            continue
        criterion_id = _identifier(criterion)
        if not criterion_id:
            continue
        ranks = criterion.get("ranks")
        found[criterion_id] = tuple(
            _identifier(rank)
            for rank in (ranks if isinstance(ranks, list) else ())
            if isinstance(rank, Mapping) and _identifier(rank)
        )
    return found


def _ladder_complaints(candidate: Candidate) -> tuple[str, ...]:
    """Deterministic complaints about the ladder and the standing on it. Membership and counting.

    Five checks, none of them an opinion: is there an ordinal chain long enough to count on, does
    the protagonist's standing refer to a declared criterion and a declared rung of *that*
    criterion, is the rung below the top, and does a world with a ladder declare the printed form
    a change of standing is announced in.

    **Silent for a world that declares no standing**, which is every world forged before
    2026-08-22 — the same rail `_protagonist_complaints` runs on, and the reason
    `test_the_pilot_package_regenerates_the_world_it_was_run_on` still gates clean.

    Nothing here asks whether the ladder is a good ladder or the rung the right rung. Those are
    judgments and `plan/world-architect.md` §2 keeps the channel that would answer them shut.
    """
    protagonist = candidate.protagonist
    standing = protagonist.get("standing") if protagonist is not None else None
    if not isinstance(standing, Mapping):
        return ()

    complaints: list[str] = []
    comparators = {
        _identifier(criterion): _text(criterion, "comparator")
        for system in _items(candidate, "systems")
        for criterion in (system.get("criterion"),)
        if isinstance(criterion, Mapping) and _identifier(criterion)
    }
    ladders = _ladders_of(candidate)
    countable = {
        criterion
        for criterion, ranks in ladders.items()
        if comparators.get(criterion) == "ordinal" and len(ranks) >= LADDER_FLOOR
    }
    if not countable:
        complaints.append(
            f"no criterion has the comparator 'ordinal' and a chain of at least {LADDER_FLOOR} "
            "ranks; the number a reader of this genre counts is a rung's place in such a chain, "
            "and a world with none has nothing to count"
        )

    criterion = worlds_mod.normalise_id(_text(standing, "criterion"))
    rung = worlds_mod.normalise_id(_text(standing, "rung"))
    if criterion not in ladders:
        complaints.append(
            f"the protagonist stands on {criterion or '(nothing)'!r}, which is not a criterion "
            f"this world declares ({', '.join(sorted(ladders)) or 'none'})"
        )
    elif criterion not in countable:
        complaints.append(
            f"the protagonist stands on {criterion}, whose comparator is "
            f"{comparators.get(criterion) or '(none)'!r} over {len(ladders[criterion])} rank(s); "
            f"a standing counts only on an 'ordinal' chain of at least {LADDER_FLOOR}"
        )
    chain = ladders.get(criterion, ())
    if criterion in ladders and rung not in chain:
        complaints.append(
            f"the protagonist stands at {rung or '(nothing)'!r}, which is not a rank of "
            f"{criterion} ({', '.join(chain) or 'none'})"
        )
    elif chain and rung == chain[-1]:
        complaints.append(
            f"the protagonist starts at {rung}, the top of {criterion}; a book that opens at the "
            "top of the only ladder it declared has nowhere on it to go"
        )

    # The declaration, not the prose: whether this world says what a change of standing is
    # printed as. `parse_graph_line`'s bounds are checked at `graph_line_for`; what is checked
    # here is that the line exists and that one of its phrases means "stands at".
    if ladders:
        graph_line = candidate.raw.get("graph_line")
        if not isinstance(graph_line, Mapping) or not str(graph_line.get("label") or "").strip():
            complaints.append(
                "this world declares a ladder and no graph_line; a standing nothing prints is a "
                "standing no scene can announce and no parser can read back"
            )
        else:
            edges = graph_line.get("edges")
            printed = {
                worlds_mod.normalise_id(_text(edge, "predicate"))
                for edge in (edges if isinstance(edges, list) else ())
                if isinstance(edge, Mapping)
            }
            if worlds_mod.STANDS_AT_PREDICATE not in printed:
                complaints.append(
                    "the graph_line carries no phrase whose predicate is "
                    f"{worlds_mod.STANDS_AT_PREDICATE!r} "
                    f"({', '.join(sorted(printed)) or 'no phrases at all'}); the line the ladder "
                    "is read off is the one form this world does not announce"
                )
    return tuple(complaints)


def _administration_complaints(candidate: Candidate) -> tuple[str, ...]:
    """The premise, and only the premise. The rate is reported beside it and carries no bar.

    **Where the line is drawn and why it is drawn there.** A world may have institutions, may
    charge for everything, and may put somebody under an obligation they hate; what it may not
    do is make the paperwork the thing the book is about. The premise is where that shows and
    it is the sentence a reader meets first, so it is the one place this is a refusal.

    **Attainable, checked the way §81, §85, §87 and §89 each were not.** Over the 30 worlds
    forged before this check existed, **12 pass it and 18 fail it** — both subgroups non-empty,
    the quantity is a membership test with no scale to mis-declare, and the unit is one world.
    No bar is declared over `administration_per_1k`: that is a distribution nobody has ranged
    against an outcome, and a threshold over it would be exactly the mistake those four entries
    record.
    """
    named = _administration_in(str(candidate.raw.get("premise") or ""))
    if not named:
        return ()
    return (
        f"the premise is written in administration ({', '.join(named)}); it is the sentence a "
        "reader meets first, and a world whose hook is paperwork is what the operator refused "
        "three times out of three on 2026-08-23",
    )


def gate_candidate(
    candidate: Candidate, *, scenes: int = DEFAULT_SCENES, include_subject: bool = True
) -> tuple[str, ...]:
    """Deterministic complaints about one world. Empty means it passed.

    Six checks, each arithmetic or membership over the structured answer and none of them an
    opinion about whether the world is any good:

    1. every declared rule reaches `CONSEQUENCE_FLOOR` distinct domains of life;
    2. every declared feature says how it shows on the page;
    3. every mystery records an answer and a disclosure scene;
    4. **at least one answer lands inside the scenes being written now**;
    5. the declared protagonist refers — to a cast member, to a rule or shape, and by name in
       the premise (`_protagonist_complaints`; silent for a world that declares none);
    6. the ladder is countable and the standing sits on it below the top, and a world with a
       ladder says what a change of standing is printed as (`_ladder_complaints`; silent for a
       world that declares no standing);
    7. the premise is not written in administration (`_administration_complaints`);
    8. nothing in the answer compares itself to something outside it (RS1 / C3).

    **`include_subject=False` is for a world somebody has already chosen**, and §115.3 is
    the precedent: a check added after the fact must not park an artefact over a fault it
    could not have been forged clear of. Check 7 arrived on 2026-08-23, after all 30
    worlds in this repository had been forged and two had been written, and 18 of the 30
    fail it. `tools/rematerialise_forge_bundle.py` and the pilot-package regeneration pass
    it False so that rebuilding a chosen world stays possible; **nothing at forge time
    does**, which is the only place the check is meant to act.
    """
    complaints: list[str] = []

    for system in _items(candidate, "systems"):
        system_id = str(system.get("id") or "?")
        if not str(system.get("manifests_as") or "").strip():
            complaints.append(f"system {system_id} never says how it shows on the page")
        rules = system.get("rules")
        for rule in rules if isinstance(rules, list) else ():
            if not isinstance(rule, Mapping):
                continue
            rule_id = str(rule.get("id") or "?")
            consequences = rule.get("consequences")
            domains = {
                str(item.get("domain") or "")
                for item in (consequences if isinstance(consequences, list) else ())
                if isinstance(item, Mapping)
            } & set(worlds_mod.CONSEQUENCE_DOMAINS)
            if len(domains) < CONSEQUENCE_FLOOR:
                complaints.append(
                    f"rule {rule_id} reaches {len(domains)} domain(s) of life "
                    f"({', '.join(sorted(domains)) or 'none'}); the floor is "
                    f"{CONSEQUENCE_FLOOR} and a rule that reaches fewer is a name rather than "
                    "a world"
                )
            if not str(rule.get("manifests_as") or "").strip():
                complaints.append(f"rule {rule_id} never says how it shows on the page")
        criterion = system.get("criterion")
        if isinstance(criterion, Mapping):
            ranks = criterion.get("ranks")
            for rank in ranks if isinstance(ranks, list) else ():
                if not isinstance(rank, Mapping):
                    continue
                if not str(rank.get("visible_form") or "").strip():
                    complaints.append(
                        f"rank {rank.get('id')!r} has no form a reader can see; a rank you are "
                        "told rather than shown is a number with a costume"
                    )
                if not str(rank.get("cost_to_reach") or "").strip():
                    complaints.append(
                        f"rank {rank.get('id')!r} costs nothing to reach"
                    )

    for creature in _items(candidate, "creatures"):
        creature_id = str(creature.get("id") or "?")
        for field_name in ("mechanism", "ecology", "human_use", "behaviour", "manifests_as"):
            if not str(creature.get(field_name) or "").strip():
                complaints.append(f"creature {creature_id} declares no {field_name}")

    mysteries = _items(candidate, "mysteries")
    if not mysteries:
        complaints.append(
            "no mystery with a recorded answer; the promise ledger would have nothing to pay "
            "with, which is the defect measured at 40 opened and 0 paid on the live serial"
        )
    landed: list[int] = []
    for mystery in mysteries:
        mystery_id = str(mystery.get("id") or "?")
        if not str(mystery.get("answer") or "").strip():
            complaints.append(f"mystery {mystery_id} records no answer")
        scene = mystery.get("disclosed_at_scene")
        if not isinstance(scene, int) or isinstance(scene, bool) or scene < 1:
            complaints.append(
                f"mystery {mystery_id} names no scene at which the reader learns it"
            )
        else:
            landed.append(scene)
    if mysteries and not [scene for scene in landed if scene <= scenes]:
        # **Measured on the first live forge.** With no scene count in the prompt, one world
        # scheduled its four answers at scenes 17, 25, 33 and 41 — sensible for an open-ended
        # serial and useless for the eight scenes actually being written, which would have
        # opened four debts and paid none. That is the 40-opened-0-paid defect reproduced by
        # the machinery built to fix it.
        complaints.append(
            f"every answer lands after scene {scenes}, the last one being written "
            f"(earliest is {min(landed)}); an opening that asks and never settles teaches a "
            "reader that nothing here gets settled"
        )

    complaints.extend(_protagonist_complaints(candidate))
    complaints.extend(_capability_complaints(candidate))
    complaints.extend(_ladder_complaints(candidate))
    if include_subject:
        complaints.extend(_administration_complaints(candidate))

    borrowed = sorted(set(_BORROWED.findall(candidate.rendered())))
    if borrowed:
        complaints.append(
            f"the answer compares itself to something outside it ({', '.join(borrowed)}); RS1 "
            "and C3 forbid naming, quoting or imitating any real work, author, brand or system"
        )
    return tuple(complaints)


# --- the world as records --------------------------------------------------------------------


def _text(entry: Mapping[str, Any], key: str) -> str:
    return str(entry.get(key) or "").strip()


def _identifier(entry: Mapping[str, Any], key: str = "id") -> str:
    return worlds_mod.normalise_id(_text(entry, key))


def records_for(
    candidate: Candidate,
    *,
    authority: lc.StateAuthority = lc.StateAuthority.PROPOSED,
    scenes: int = DEFAULT_SCENES,
) -> tuple[lc.StateRecord, ...]:
    """One world as record patterns over `lc.StateRecord`. No migration, no new record kind.

    Everything here is `domain/worlds.py`'s vocabulary, which is
    `research/progression-generalization.md` §6.2 and §8 spelled as they spell it.

    **`authority` is the rail, and it is a parameter because the rail has exactly one exit.** The
    default is `PROPOSED`: a forged world is a candidate, it reaches no context packet, and
    `context.assemble` filters it out by `is_canon` before anything else happens. `ACCEPTED_CANON`
    is passed at exactly one call site — `cmd_forge --pick`, where a person has chosen among K and
    the choice is recorded as its own policy decision. That is the same authority `cmd_import`
    writes an operator's snapshot under, and its comment is the precedent: *accepted on the
    director's authority, not extracted from prose this system generated*.

    **Without this the whole role would be inert**, and quietly: every record would stay a
    proposal, `assemble` would drop the lot, and a serial forged with a system, a cast and a
    bestiary would draft against a premise and nothing else — looking, at every layer, exactly
    like the book this role exists to stop producing.
    """
    out: list[lc.StateRecord] = []
    seen: set[str] = set()

    def add(record: lc.StateRecord) -> None:
        if record.record_id in seen:
            return
        seen.add(record.record_id)
        out.append(
            record
            if authority is lc.StateAuthority.PROPOSED
            else replace(record, authority=authority)
        )

    def entity(entry: Mapping[str, Any], role: str) -> str:
        subject = _identifier(entry)
        if not subject:
            return ""
        add(worlds_mod.world_record(subject, worlds_mod.ENTITY_ROLE_PREDICATE, value=role))
        if _text(entry, "is_a"):
            add(worlds_mod.world_record(subject, "is_a", value=_text(entry, "is_a")))
        for key, predicate in (
            ("wants", "wants"),
            ("reach", "can_reach"),
            ("voice_tag", "voice_tag"),
            ("recognises", "recognises"),
            ("grants", "grants"),
            ("prices_the_present", "prices_the_present"),
        ):
            if _text(entry, key):
                add(worlds_mod.world_record(subject, predicate, value=_text(entry, key)))
        if _text(entry, "manifests_as"):
            add(
                worlds_mod.world_record(
                    subject, worlds_mod.MANIFESTS_PREDICATE, value=_text(entry, "manifests_as")
                )
            )
        # **Relationships are edges, which is the capability nothing in this repository used to
        # write.** `object_ref` has been on every record since the contract shipped and no code
        # constructed one; a cast whose ties live in prose is a cast the store cannot check, and
        # `state.cardinality.v0` has nothing to count.
        relationships = entry.get("relationships")
        for tie in relationships if isinstance(relationships, list) else ():
            if not isinstance(tie, Mapping):
                continue
            predicate = worlds_mod.normalise_id(_text(tie, "predicate"))
            target = worlds_mod.normalise_id(_text(tie, "target"))
            if not predicate or not target:
                continue
            add(
                worlds_mod.world_record(
                    subject, predicate, object_ref=target, value=_text(tie, "note") or None
                )
            )
        return subject

    for system in _items(candidate, "systems"):
        system_id = _identifier(system)
        if not system_id:
            continue
        add(
            worlds_mod.world_record(
                system_id, worlds_mod.ENTITY_ROLE_PREDICATE, value="system"
            )
        )
        add(worlds_mod.world_record(system_id, "is_a", value=_text(system, "logic")))
        add(
            worlds_mod.world_record(
                system_id, worlds_mod.MANIFESTS_PREDICATE, value=_text(system, "manifests_as")
            )
        )
        # The interface between two incompatible logics is the content, so it is a fact about
        # the world rather than a note about the system.
        if _text(system, "collides_with") and _text(system, "interface"):
            add(
                worlds_mod.world_record(
                    system_id,
                    "collides_with",
                    object_ref=worlds_mod.normalise_id(_text(system, "collides_with")),
                    value=_text(system, "interface"),
                )
            )
        # A hidden personality is a claim about the system that has not been disclosed — §3.5's
        # reduction, and the reason it is a claim rather than a field.
        if _text(system, "hidden_personality"):
            claim_id = f"{system_id}_nature"
            add(
                worlds_mod.world_record(
                    claim_id,
                    worlds_mod.CLAIM_CONTENT,
                    value=_text(system, "hidden_personality"),
                )
            )
        if _text(system, "view_withholds"):
            view_id = f"{system_id}_view"
            add(worlds_mod.world_record(view_id, worlds_mod.TYPE_PREDICATE, value=worlds_mod.VIEW))
            add(
                worlds_mod.world_record(
                    view_id, worlds_mod.VIEW_SUBSTRATE, object_ref=system_id
                )
            )
            add(
                worlds_mod.world_record(
                    view_id, worlds_mod.VIEW_MAPPING, value=_text(system, "manifests_as")
                )
            )
            add(
                worlds_mod.world_record(
                    view_id, worlds_mod.VIEW_WITHHOLDS, value=_text(system, "view_withholds")
                )
            )

        rules = system.get("rules")
        for rule in rules if isinstance(rules, list) else ():
            if not isinstance(rule, Mapping):
                continue
            rule_id = _identifier(rule)
            if not rule_id:
                continue
            add(
                worlds_mod.world_record(
                    rule_id, worlds_mod.WORLD_RULE_PREDICATE, value=_text(rule, "rule")
                )
            )
            add(
                worlds_mod.world_record(
                    rule_id, worlds_mod.MANIFESTS_PREDICATE, value=_text(rule, "manifests_as")
                )
            )
            add(
                worlds_mod.world_record(
                    rule_id, worlds_mod.BUNDLE_MEMBER, object_ref=system_id
                )
            )
            consequences = rule.get("consequences")
            for item in consequences if isinstance(consequences, list) else ():
                if not isinstance(item, Mapping):
                    continue
                domain = _text(item, "domain")
                if domain in worlds_mod.CONSEQUENCE_DOMAINS:
                    add(
                        worlds_mod.world_record(
                            rule_id,
                            worlds_mod.CONSEQUENCE_PREDICATE,
                            object_ref=domain,
                            value=_text(item, "consequence"),
                        )
                    )

        criterion = system.get("criterion")
        if isinstance(criterion, Mapping):
            criterion_id = _identifier(criterion)
            if criterion_id:
                add(
                    worlds_mod.world_record(
                        criterion_id, worlds_mod.TYPE_PREDICATE, value=worlds_mod.CRITERION
                    )
                )
                add(
                    worlds_mod.world_record(
                        criterion_id,
                        worlds_mod.COMPARATOR_PREDICATE,
                        value=_text(criterion, "comparator"),
                    )
                )
                add(
                    worlds_mod.world_record(
                        criterion_id,
                        worlds_mod.EVALUATES_PREDICATE,
                        object_ref=worlds_mod.normalise_id(_text(criterion, "evaluates")),
                    )
                )
                ranks = criterion.get("ranks")
                rank_ids: list[str] = []
                for rank in ranks if isinstance(ranks, list) else ():
                    if not isinstance(rank, Mapping):
                        continue
                    rank_id = _identifier(rank)
                    if not rank_id:
                        continue
                    rank_ids.append(rank_id)
                    add(
                        worlds_mod.world_record(
                            rank_id,
                            worlds_mod.MANIFESTS_PREDICATE,
                            value=_text(rank, "visible_form"),
                        )
                    )
                    add(
                        worlds_mod.world_record(
                            rank_id, "costs", value=_text(rank, "cost_to_reach")
                        )
                    )
                    # **`grants` reaches canon on the same predicate a capability uses.** §114's
                    # chain is declare -> ask -> print -> read, and a slot that stops at the forge
                    # is declared and nothing else. `is_a` is what `_CAPABILITY` writes for "what
                    # this lets a person do", so a rung's grant is legible to the packet as the
                    # same kind of fact rather than as a fifth vocabulary.
                    if _text(rank, "grants"):
                        add(
                            worlds_mod.world_record(
                                rank_id, "is_a", value=_text(rank, "grants")
                            )
                        )
                # The ordinal domain as edges, with the criterion on the edge so a world running
                # two ladders at once cannot have them spliced into one order nobody declared.
                for lower, higher in itertools.pairwise(rank_ids):
                    add(
                        worlds_mod.world_record(
                            lower,
                            worlds_mod.PRECEDES_PREDICATE,
                            object_ref=higher,
                            value=criterion_id,
                        )
                    )

    for key, role in (
        ("agencies", "agency"),
        ("carriers", "carrier"),
        ("cast", "cast"),
        ("places", "place"),
        ("institutions", "institution"),
        ("history", "institution"),
    ):
        for entry in _items(candidate, key):
            subject = entity(entry, role)
            if not subject:
                continue
            # A cast member's false belief and secret are claims, never fields: the gap between
            # what is true, what a character holds and what the reader has been told is what
            # §3.4 makes expressible, and a field would collapse all three.
            if _text(entry, "false_belief"):
                claim_id = f"{subject}_belief"
                add(
                    worlds_mod.world_record(
                        claim_id, worlds_mod.CLAIM_CONTENT, value=_text(entry, "false_belief")
                    )
                )
                # Marked wrong, and the marker is what keeps it out of the packet's hidden
                # section — which says *true*. Without it a character's error would be handed
                # to the writer as something to honour.
                add(worlds_mod.world_record(claim_id, worlds_mod.CLAIM_FALSE, value=True))
                add(
                    worlds_mod.world_record(
                        subject, worlds_mod.BELIEVES, object_ref=claim_id
                    )
                )
            if _text(entry, "secret"):
                claim_id = f"{subject}_secret"
                add(
                    worlds_mod.world_record(
                        claim_id, worlds_mod.CLAIM_CONTENT, value=_text(entry, "secret")
                    )
                )
                add(
                    worlds_mod.world_record(
                        subject, "keeps_secret", object_ref=claim_id
                    )
                )

    for creature in _items(candidate, "creatures"):
        subject = _identifier(creature)
        if not subject:
            continue
        add(worlds_mod.world_record(subject, worlds_mod.ENTITY_ROLE_PREDICATE, value="creature"))
        add(worlds_mod.world_record(subject, "is_a", value=_text(creature, "is_a")))
        add(
            worlds_mod.world_record(
                subject, worlds_mod.MANIFESTS_PREDICATE, value=_text(creature, "manifests_as")
            )
        )
        for key, predicate in (
            ("mechanism", "works_by"),
            ("ecology", "lives_by"),
            ("rank", "ranks_at"),
            ("human_use", "used_by_people_for"),
            ("behaviour", "does"),
            ("bond_potential", "bonds_by"),
        ):
            if _text(creature, key):
                add(worlds_mod.world_record(subject, predicate, value=_text(creature, key)))

    for bond in _items(candidate, "bonds"):
        bond_id = _identifier(bond)
        if not bond_id:
            continue
        members = bond.get("members")
        for member in members if isinstance(members, list) else ():
            member_id = worlds_mod.normalise_id(str(member))
            if member_id:
                add(
                    worlds_mod.world_record(
                        bond_id, worlds_mod.MEMBER, object_ref=member_id
                    )
                )
        if _text(bond, "joint_ability"):
            add(
                worlds_mod.world_record(
                    bond_id,
                    worlds_mod.PERMITS,
                    object_ref=f"{bond_id}_joint",
                    value=_text(bond, "joint_ability"),
                )
            )
        if _text(bond, "trait_link"):
            add(worlds_mod.world_record(bond_id, "trait_link", value=_text(bond, "trait_link")))

    for mystery in _items(candidate, "mysteries"):
        claim_id = _identifier(mystery)
        if not claim_id:
            continue
        add(
            worlds_mod.world_record(
                claim_id, worlds_mod.CLAIM_CONTENT, value=_text(mystery, "answer")
            )
        )
        add(
            worlds_mod.world_record(
                claim_id, worlds_mod.QUESTION_PREDICATE, value=_text(mystery, "question")
            )
        )
        scene = mystery.get("disclosed_at_scene")
        if isinstance(scene, int) and not isinstance(scene, bool) and scene >= 1:
            # The ordinal always; a *position* only for a scene this book has. See `story_key`.
            add(worlds_mod.world_record(claim_id, worlds_mod.REVEAL_SCENE, value=scene))
            position = story_key(scene, scenes=scenes)
            if position is not None:
                add(
                    worlds_mod.world_record(
                        f"{claim_id}_reveal",
                        worlds_mod.DISCLOSED_TO,
                        value=worlds_mod.READER,
                        object_ref=claim_id,
                        order_key=position,
                    )
                )
        if _text(mystery, "believed_instead_by"):
            add(
                worlds_mod.world_record(
                    worlds_mod.normalise_id(_text(mystery, "believed_instead_by")),
                    worlds_mod.BELIEVES,
                    object_ref=f"{claim_id}_belief",
                )
            )

    shape_ids: set[str] = set()
    for shape in _items(candidate, "cardinality"):
        shape_id = _identifier(shape)
        maximum = shape.get("maximum")
        group_key = _text(shape, "group_key")
        predicate = _text(shape, "predicate")
        if not shape_id or not predicate or group_key not in worlds_mod.GROUP_KEYS:
            continue
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            continue
        add(
            worlds_mod.world_record(
                shape_id, worlds_mod.TYPE_PREDICATE, value=worlds_mod.CARDINALITY_CONSTRAINT
            )
        )
        add(
            worlds_mod.world_record(
                shape_id, worlds_mod.PREDICATE_PREDICATE, value=predicate
            )
        )
        add(
            worlds_mod.world_record(
                shape_id,
                worlds_mod.SCOPE_PREDICATE,
                value=_text(shape, "scope") or worlds_mod.ANY_SCOPE,
            )
        )
        add(worlds_mod.world_record(shape_id, worlds_mod.GROUP_KEY_PREDICATE, value=group_key))
        add(worlds_mod.world_record(shape_id, worlds_mod.MAXIMUM_PREDICATE, value=maximum))
        shape_ids.add(shape_id)
        excepted = shape.get("except")
        for entry in excepted if isinstance(excepted, list) else ():
            subject = worlds_mod.normalise_id(str(entry))
            if subject:
                add(
                    worlds_mod.world_record(
                        shape_id, worlds_mod.EXCEPTS_PREDICATE, object_ref=subject
                    )
                )

    # **The protagonist, as records rather than as a field.** Everything a world declares is a
    # record here and this is not the exception — the packet, the gate and the second extractor
    # family all read records, and a field would be a fact only this module could see.
    #
    # The role is a *second* one on a cast member, so the cast loop above has already written
    # `entity_role cast` and this adds `entity_role protagonist` beside it. Nothing is emitted
    # at all for a world that declares no protagonist, which is what keeps
    # `plan/serial-pilot-2-world.json` regenerating byte-for-byte.
    protagonist = candidate.protagonist
    if protagonist is not None:
        subject = _identifier(protagonist)
        exception = worlds_mod.normalise_id(_text(protagonist, "exception"))
        if subject:
            add(
                worlds_mod.world_record(
                    subject, worlds_mod.ENTITY_ROLE_PREDICATE, value="protagonist"
                )
            )
            # **`wants` is the cast entry's, and the protagonist's copy is a restatement.**
            # `_ENTITY` already carries `wants` and the cast loop above has already written it,
            # so emitting the protagonist's too puts two values in a single slot — which
            # `state.contradiction.v1` reports as MAJOR and blocking, correctly, because a
            # person wanting two different things at one position is a defect and not a set.
            #
            # Measured on the first book drafted on a world that declares one: the model wrote
            # *"Fourth-grade material before Orin's throat-mark lapses in nine days."* on the
            # protagonist and *"Fourth-grade material, in nine days, by any route."* on the cast
            # entry — the same want in two wordings — and the book poisoned a scene over it.
            # The cast entry wins because it is where the schema puts a want for everybody;
            # `gate_candidate` complains when the two are both declared and differ, so the
            # divergence is seen at forge time rather than at scene four.
            declares_want = {
                _identifier(entry)
                for entry in _items(candidate, "cast")
                if _text(entry, "wants")
            }
            for key, predicate in (
                ("edge", worlds_mod.EDGE_PREDICATE),
                ("wants", "wants"),
                ("price", worlds_mod.PRICE_PREDICATE),
            ):
                if key == "wants" and subject in declares_want:
                    continue
                if _text(protagonist, key):
                    add(
                        worlds_mod.world_record(
                            subject, predicate, value=_text(protagonist, key)
                        )
                    )
            if exception:
                add(
                    worlds_mod.world_record(
                        subject, worlds_mod.EXCEPTION_PREDICATE, object_ref=exception
                    )
                )
                # **The one derivation, and it is a definition rather than an inference.** "X is
                # the exception to shape S" and "S does not govern X" are the same fact said from
                # the two ends of one edge, and `worlds.in_scope` reads only the second. A world
                # that declared the first and forgot the second would hand the writer an
                # exception the gate still refuses — decoration, which is what
                # `plan/handoff-protagonist.md` Task 1 exists to prevent. Only for a shape this
                # world actually declared: an `exception` naming a *rule* has no maximum to
                # except and gets the edge above and nothing more.
                if exception in shape_ids:
                    add(
                        worlds_mod.world_record(
                            exception, worlds_mod.EXCEPTS_PREDICATE, object_ref=subject
                        )
                    )
            # **Where they start, as one flat edge with the criterion riding on it.** The shape
            # mirrors `precedes` exactly (`value = criterion_id`) so that two ladders in one
            # world cannot be spliced, and it is flat rather than the reified `EVALUATION_*`
            # triple because the *page* can only print a flat edge — `[TAG] Kell now stands at
            # two wood` — and the forge's copy of the fact has to be readable by the same
            # function that reads the page's (`plan/handoff-numbers-go-up.md` boundary 9).
            #
            # **Placed at the opening rather than left unplaced, and the placement is load-
            # bearing.** A standing is a fact that changes, so a `progression_target`-class
            # lookup has to be able to ask "which standing is in force at this scene" and
            # "which milestone is still ahead" — both of which compare order keys. An unplaced
            # record asserts no position, and `records_before` keeps it in every window, so an
            # unplaced standing could never be *before* a milestone and the schedule would aim
            # at a target the book had already passed. Standing world rules are unplaced for
            # exactly the opposite reason: they never change.
            #
            # Absent for a world that declares no standing, which is every world forged before
            # 2026-08-22 — the condition that keeps
            # `test_the_pilot_package_regenerates_the_world_it_was_run_on` green.
            standing = protagonist.get("standing")
            if isinstance(standing, Mapping):
                criterion = worlds_mod.normalise_id(_text(standing, "criterion"))
                rung = worlds_mod.normalise_id(_text(standing, "rung"))
                if criterion and rung:
                    add(
                        worlds_mod.world_record(
                            subject,
                            worlds_mod.STANDS_AT_PREDICATE,
                            object_ref=rung,
                            value=criterion,
                            order_key=story_key(1, scenes=scenes),
                        )
                    )

    # **The inventory: a countable set of things a person can do.** An ordinary subject with a
    # role, not a reified node — a `change` is *one occurrence with many roles* and renders
    # "X happened", which is the right aspect for the morning somebody learned a thing and the
    # wrong one for the thing itself. The two coexist: this declares the capability, and a world
    # that wants to schedule an acquisition still has `change` for it.
    #
    # Nothing is emitted for a world that declares none, which is every world forged before
    # 2026-08-22 and most of the ones after.
    for capability in _items(candidate, "capabilities"):
        subject = _identifier(capability)
        if not subject:
            continue
        add(
            worlds_mod.world_record(
                subject, worlds_mod.ENTITY_ROLE_PREDICATE, value="capability"
            )
        )
        for key, predicate in (
            ("is_a", "is_a"),
            ("manifests_as", worlds_mod.MANIFESTS_PREDICATE),
            ("costs", worlds_mod.COSTS),
        ):
            if _text(capability, key):
                add(
                    worlds_mod.world_record(
                        subject, predicate, value=_text(capability, key)
                    )
                )
        teacher = worlds_mod.normalise_id(_text(capability, "taught_by"))
        if teacher:
            add(worlds_mod.world_record(subject, worlds_mod.TAUGHT_BY, object_ref=teacher))
        needs = capability.get("requires")
        for entry in needs if isinstance(needs, list) else ():
            target = worlds_mod.normalise_id(str(entry))
            if target:
                add(worlds_mod.world_record(subject, worlds_mod.REQUIRES, object_ref=target))

    # **Who holds what, and the protagonist is the only subject the forge says it of.** A world
    # declares its people and its capabilities separately; the one edge between them written here
    # is the protagonist's, because `plan/handoff-ability-inventory.md` boundary 6 keeps this from
    # becoming a second standing and because the protagonist's id is the one subject the whole
    # pipeline already threads (§112). Only ids the world actually declared: an inventory that
    # names something the world never built is the `exception_to` defect one field over.
    declares = candidate.protagonist
    held = declares.get("capabilities") if declares is not None else None
    if declares is not None and held:
        holder = _identifier(declares)
        declared = {_identifier(entry) for entry in _items(candidate, "capabilities")} - {""}
        for entry in held if isinstance(held, list) else ():
            target = worlds_mod.normalise_id(str(entry))
            if holder and target in declared:
                add(worlds_mod.world_record(holder, worlds_mod.CAN_DO, object_ref=target))

    graph_line = candidate.raw.get("graph_line")
    if isinstance(graph_line, Mapping) and graph_line.get("label"):
        add(
            worlds_mod.world_record(
                "book", worlds_mod.GRAPH_LINE_PREDICATE, value=dict(graph_line)
            )
        )
    return tuple(out)


def story_key(scene: int, *, scenes: int) -> str | None:
    """A story-order key in `beats_for`'s own vocabulary, or `None` for a scene this book lacks.

    **The width is the book's, and getting that wrong was a measured leak.** `domain/beats.py`
    mints `f"s{index:0{width}d}"` with `width = len(str(len(scenes)))`, so an eight-scene book's
    keys are `s1…s8` — width one. A fixed two-digit form put `s04` and `s41` into the same
    namespace, and `order_key` comparison is lexicographic: `"s1" > "s04"`, so on Serial Pilot 2
    **the two answers the opening existed to keep were the two the packet handed the writer as
    established fact**, while an arc answer six chapters out drifted between sections scene by
    scene. Nothing raised; the strings compared fine.

    **A reveal outside this book gets no position at all**, which is the honest encoding rather
    than a clamp: the reader is not told inside these scenes, so the claim has no disclosure here
    and `undisclosed_claims` keeps it hidden throughout. The world's intent is not lost — the
    ordinal is stored under `worlds.REVEAL_SCENE` either way.
    """
    if scene < 1 or scene > scenes:
        return None
    return f"s{scene:0{len(str(scenes))}d}"


def directives_for(candidate: Candidate) -> tuple[dict[str, str], ...]:
    """The directive set a forged world needs the loop to carry.

    Kinds are restricted to what a role may write: the four interpretive kinds plus `constraint`.
    A `veto` is a refusal and refusal is the operator's; `control` is pause/resume/kill and is
    not narrative at all. This is `directors.DIRECTOR_KINDS`' argument with `constraint` added,
    because a *world fact* stated as a standing rule is exactly what the verbatim lane is for —
    and unlike a prose-craft rule, it is not doctrine about how to write.
    """
    allowed = {
        DirectiveKind.CONSTRAINT.value,
        DirectiveKind.TONE_NOTE.value,
        DirectiveKind.ARC_NOTE.value,
        DirectiveKind.CHAPTER_NOTE.value,
    }
    out: list[dict[str, str]] = []
    for entry in _items(candidate, "directives"):
        kind = _text(entry, "kind")
        text = _text(entry, "text")
        if kind in allowed and text:
            out.append({"kind": kind, "text": text, "label": f"forged {kind}"})
    return tuple(out)


def promises_for(candidate: Candidate) -> tuple[dict[str, Any], ...]:
    """One promise per recorded reveal, so the ledger has something to pay with.

    The measured defect this answers is the oldest in the project: **40 promises opened and 0
    paid** on the live serial, 32 and 0 before it. Every one of those was opened by the summary
    handler out of a scene that had just been written, and nothing anywhere held the answer. A
    reveal forged with its answer and its scene is a debt with a settlement date attached.

    `subject` is deliberately the mystery's own id: `pay_promise` is reachable only through
    `promise_id_for(book_id, normalise_subject(<what the summariser wrote>))`, so a seeded debt
    whose subject the summariser would never echo can never be settled by the loop.
    """
    out: list[dict[str, Any]] = []
    for mystery in _items(candidate, "mysteries"):
        subject = _identifier(mystery)
        scene = mystery.get("disclosed_at_scene")
        if not subject or not isinstance(scene, int) or isinstance(scene, bool) or scene < 1:
            continue
        kind = _text(mystery, "kind") or "mystery"
        out.append(
            {
                "subject": subject,
                "description": _text(mystery, "question"),
                "kind": kind,
                "due_scene": scene,
            }
        )
    return tuple(out)


# --- the counters a report is made of -----------------------------------------------------------


def spread(candidates: Sequence[Candidate]) -> float | None:
    """Mean pairwise distance among the K worlds of one forge. `None` below two candidates.

    **Named a spread rather than a distinctness, because it is not one.**
    `directors.distinctness` compares two *sources* by asking whether the gap between them
    clears each one's own noise floor. K worlds from one call share a source, so there is no
    floor to clear and the number here can only say how far apart this call's answers landed.
    The comparison that *is* a distinctness reading is between the two prompt shapes, and it
    lives on the measurement side where the second forge can be paid for
    (`plan/world-architect.md` §6, M1).
    """
    texts = [candidate.rendered() for candidate in candidates]
    pairs = [
        directors.distance(texts[i], texts[j])
        for i in range(len(texts))
        for j in range(i + 1, len(texts))
    ]
    return sum(pairs) / len(pairs) if pairs else None


def _countable_ladders(
    records: Sequence[lc.StateRecord],
) -> dict[str, tuple[str, ...]]:
    """Ordinal criteria whose results form a chain, as criterion id → chain. Read off records.

    Off the records rather than off the raw answer, unlike `_ladders_of`, because this feeds a
    *report* about the world the store will hold: a rank whose id normalises away is not on the
    chain the writer or the extractor will ever see, and counting it here would report a ladder
    nothing downstream has.
    """
    comparators = worlds_mod.criteria(records)
    found = {
        criterion: worlds_mod.ladder_of(records, criterion)
        for criterion, comparator in comparators.items()
        if comparator == "ordinal"
    }
    return {criterion: chain for criterion, chain in found.items() if chain}


def _opening_rung_index(records: Sequence[lc.StateRecord]) -> int | None:
    """The protagonist's 1-based rung at the opening, or `None` when there is no one number.

    **Reads the edges directly rather than calling `worlds.standing_of`, and the difference is
    the rail.** `standing_of` filters to canon, which is right for every caller downstream of a
    pick — a proposal must not read as where the book's protagonist stands. A candidate's records
    are `PROPOSED` by construction, so this report would be `None` for every world if it went
    through that function, and a counter that is always empty reads as a world with no ladder.

    `None` when the world declares no protagonist, no standing, or more than one standing whose
    chain gives a number — one report field cannot answer for two ladders, and choosing between
    them is the guess `rung_index` refuses.
    """
    subjects = worlds_mod.entities_with_role(records, "protagonist")
    if not subjects:
        return None
    indices = [
        found
        for record in records
        if record.predicate == worlds_mod.STANDS_AT_PREDICATE
        and record.subject == subjects[0]
        and record.object_ref
        and (
            found := worlds_mod.rung_index(
                records, str(record.value or "").strip(), record.object_ref
            )
        )
        is not None
    ]
    return indices[0] if len(indices) == 1 else None


def report(candidate: Candidate, *, scenes: int = DEFAULT_SCENES) -> dict[str, Any]:
    """Every deterministic number this candidate has, computed over its own records.

    Counters, never a verdict. Nothing here orders one world above another and nothing may be
    read as doing so; `plan/world-architect.md` §6 records which of these have bars (M3, M4) and
    which are reported distributions with no bar (M2, M5, M6) and why.
    """
    records = records_for(candidate, scenes=scenes)
    coverage = worlds_mod.manifestation_coverage(records)
    domains = worlds_mod.consequence_domains(records)
    return {
        "index": candidate.index,
        "title": candidate.title,
        "domain": candidate.domain,
        "geometry": candidate.geometry,
        "records": len(records),
        "edges": sum(1 for record in records if record.object_ref),
        "rules": len(domains),
        "consequence_domains_per_rule": {
            rule: len(found) for rule, found in sorted(domains.items())
        },
        "min_consequence_domains": min((len(v) for v in domains.values()), default=0),
        "features": len(coverage.features),
        "manifestation_coverage": round(coverage.share, 4),
        "manifestation_missing": list(coverage.missing),
        "criteria": worlds_mod.criteria(records),
        "cardinality_shapes": len(worlds_mod.cardinality_shapes(records)),
        # **Three facts about the declaration, and not one about the hook.** Whether this world
        # says whose book it is, whether it says what rule does not hold for them, and whether
        # its premise says their name — each computed off the records this candidate produced.
        # Nothing here orders one world above another and nothing may be read as doing so; the
        # forge still stops and a person picks (`plan/world-architect.md` §2).
        # **Five counters about the ladder, and not one verdict about it.** How many ordinal
        # criteria carry a chain, how long each chain is, where the protagonist opens on theirs,
        # whether the printed form exists, and the inversion verbatim so the run record can be
        # read beside `plan/handoff-numbers-go-up.md` Task 0.3's four worlds without a
        # classifier standing between them. `opening_rung_index` is `None` for a world that
        # declares no standing and for one whose chain is not a chain — empty rather than a
        # guess, `rung_index`'s own rule.
        # **Two counters about vocabulary, one of which the gate refuses on.** The share of
        # this world's declared text that is paperwork, and the administrative words its
        # premise names. The rate is a distribution with no bar over it (the 30 worlds forged
        # before 2026-08-23 ranged 2.69 to 17.92, median 7.21); the premise list is what
        # `_administration_complaints` refuses on, and it is printed here so the operator sees
        # the number rather than only the complaint.
        "administration_per_1k": _administration_rate(candidate),
        "administration_in_premise": list(
            _administration_in(str(candidate.raw.get("premise") or ""))
        ),
        "ladders": len(_countable_ladders(records)),
        "rungs_per_ladder": {
            criterion: len(chain)
            for criterion, chain in sorted(_countable_ladders(records).items())
        },
        "opening_rung_index": _opening_rung_index(records),
        "graph_line_declared": bool(candidate.raw.get("graph_line")),
        "inversion_text": str(candidate.raw.get("inversion") or ""),
        "protagonist_declared": bool(worlds_mod.entities_with_role(records, "protagonist")),
        "exception_declared": any(
            record.predicate == worlds_mod.EXCEPTION_PREDICATE for record in records
        ),
        "premise_names_protagonist": premise_names_protagonist(candidate),
        # **Three counts and no verdict.** How many distinct things this world says a person can
        # do, how many the protagonist starts with, and how deep its own prerequisite structure
        # runs. Nothing orders one world above another and **none of the three is a floor** — the
        # operator's "nine unique abilities" is a word for an inventory, not a threshold, and
        # §81, §85, §87 and §89 are four separate records of what happens when a count is read as
        # a bar. A distribution has to exist before anyone declares one over it.
        "capabilities_declared": len(worlds_mod.capabilities(records)),
        "protagonist_capabilities": len(
            worlds_mod.capabilities_of(records, _identifier(candidate.protagonist))
            if candidate.protagonist is not None
            else ()
        ),
        "requirement_depth": worlds_mod.requirement_depth(records),
        "claims_with_answers": len(worlds_mod.claims(records)),
        "reveals_scheduled": len(worlds_mod.disclosures(records)),
        "hidden_at_start": len(
            worlds_mod.undisclosed_claims(records, at=story_key(1, scenes=scenes))
        ),
        "key_nouns": list(worlds_mod.key_nouns(records)),
        "validator_complaints": list(worlds_mod.validate(records)),
        "gate_complaints": list(gate_candidate(candidate, scenes=scenes)),
    }


def snapshot_for(
    candidate: Candidate,
    *,
    book_id: str,
    branch_id: str,
    revision_id: str,
    architect_id: str,
    created_at: str,
    authority: lc.StateAuthority = lc.StateAuthority.PROPOSED,
    scenes: int = DEFAULT_SCENES,
) -> lc.StateSnapshot:
    """The world as a `StateSnapshot` that `litharness new --state` consumes unchanged.

    `actor` carries the machine authorship, which is the provenance rail made durable: a snapshot
    an Architect proposed is distinguishable from one an operator typed, in the artifact itself
    and not only in a decision row.
    """
    return lc.StateSnapshot(
        meta=lc.ArtifactMeta(
            schema_version="1.2.0",
            artifact_id=f"{architect_id}-{candidate.index}",
            artifact_kind="state_snapshot",
            created_at=created_at,
            actor=worlds_mod.machine_author(architect_id),
            tool=lc.ToolIdentity(name="litharness-architect", version="0.1.0"),
        ),
        book_id=book_id,
        branch_id=branch_id,
        revision_id=revision_id,
        records=list(records_for(candidate, authority=authority, scenes=scenes)),
    )


def bundle_for(
    candidate: Candidate,
    *,
    book_id: str,
    branch_id: str,
    revision_id: str,
    architect_id: str,
    created_at: str,
    brief: str,
    shape: str,
    scenes: int = DEFAULT_SCENES,
) -> dict[str, Any]:
    """Everything `new --state … --premise …` and the directive lane need, in one object."""
    return {
        "architect_id": architect_id,
        "brief": brief,
        "prompt_shape": shape,
        "index": candidate.index,
        "title": candidate.title,
        "premise": str(candidate.raw.get("premise") or "").strip(),
        "seed": lc.to_jsonable(
            snapshot_for(
                candidate,
                book_id=book_id,
                branch_id=branch_id,
                revision_id=revision_id,
                architect_id=architect_id,
                created_at=created_at,
                scenes=scenes,
            )
        ),
        "directives": list(directives_for(candidate)),
        "promises": list(promises_for(candidate)),
        "report": report(candidate, scenes=scenes),
        "world": dict(candidate.raw),
    }


__all__ = [
    "CALL_CLASS",
    "CONSEQUENCE_FLOOR",
    "DEFAULT_K",
    "DEFAULT_SCENES",
    "DIRECT",
    "DOMAIN_FIRST",
    "GEOMETRIES",
    "PROFILE",
    "PROMPT_SHAPES",
    "WORLDS_SCHEMA",
    "ArchitectInputError",
    "ArchitectOutputError",
    "Candidate",
    "bundle_for",
    "directives_for",
    "gate_candidate",
    "premise_names_protagonist",
    "promises_for",
    "records_for",
    "render_world_request",
    "report",
    "snapshot_for",
    "spread",
    "story_key",
    "worlds_from",
]
