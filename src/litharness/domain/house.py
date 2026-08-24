"""The two things every role that writes for a reader is told, recorded once.

**Why this module exists, and it is an architecture finding rather than a style preference.**
On 2026-08-23 six forged worlds were refused by the operator and five rule changes went into
`application/architect._RULES` — a premise must be a pitch, its nouns must be explained where
they appear, its ladder must be abilities somebody keeps, its world may not be an administration.
Measured on premises, they worked: unexplained terms fell from twenty to two and the forge's
administrative vocabulary fell 25x.

Then the first book written on that world opened on 1,067 words of a call-centre shift rendered
step by step, and the operator's reading of chapter one was that *"it's like the clarity learnings
haven't been applied at all"*. They had not been. **Every one of those changes edited the
Architect, and the Writer, the outline and the planner never saw any of them** — the writer's
whole system prompt was three sentences about not writing headings. The lesson is the operator's:
*"we should definitely have the clarity feature in all subagents of our application, as it would
help put everything in the correct perspective, as well as our goal for fulfilling the readers."*

**Written once and referenced, never restated.** Nine modules in this package call a model. Text
copied into nine prompts is text that drifts in eight of them, and the repository's standing rule
about counts — one canonical home, pointers everywhere else — is the same rule for instructions.

**What this is NOT, and the boundary is `planner`'s own.** `point_of_view`'s docstring refuses to
carry an adjective because *how* to handle a protagonist is the director's to say, and "a default
here would be this system's own taste arriving in every prompt it ever renders" (§95's scope
axiom, §97.1). That boundary holds and this does not cross it: **neither rule below is a
judgment about a story.** They do not say what to write, who to like, how a scene should end, or
that anybody should win. One says a reader must be able to follow the words; the other says the
words should be spent on what the book is selling. Both are the operator's standing direction,
recorded here with their provenance so that a later reader can see they were *given* rather than
assumed — which is exactly what §95 leaves open.
"""

from __future__ import annotations

#: **Clarity, as measured rather than as an adjective.** `comprehension_battery` asked four
#: readers of the target genres to quote anything in a premise they could not follow, and the
#: terms they quoted were always the same shape: a word used as if the reader already knew it —
#: `frost rooms`, `keeper`, `the lists`, `nine deep`. The fix that worked on premises is the
#: sentence below, and it is what the prose never got.
CLARITY = (
    "Clarity is the floor. Every word a reader has not met before is explained where it is "
    "used, in plain language, or it is not used: a name, a rank, a place, a piece of the "
    "world's own vocabulary. Nothing needs reading twice to be followed, and nothing is left "
    "for the reader to work out later. A thing the reader cannot follow is a thing that did "
    "not happen."
)

#: **What the reader came for.** The measured failure this answers is one scene of eight spent
#: rendering a support call step by step — technically an opening in which somebody wants
#: something, and 1,067 words that bought the reader nothing. The simulated reader panel passed
#: that chapter with zero comprehension faults, which is why this is a second rule and not a
#: clause of the first.
READER = (
    "Spend the words on what the reader opened this book for. Detail that only establishes "
    "who somebody is — the steps of a job, the numbers on a card, the order of a routine — is "
    "worth a line rather than a scene, and if the events would be equally true with those "
    "specifics removed, remove them. Every scene moves the thing the book is about closer or "
    "further away."
)

#: The block as it reaches a prompt. One blank line between the two, so a role can append it to
#: its own instructions without reflowing them.
HOUSE_RULES = f"{CLARITY}\n\n{READER}"


def with_house_rules(system: str) -> str:
    """`system` with the house rules appended, or the rules alone for an empty system.

    A function rather than a constant at each call site, because every role that grew its own
    concatenation grew its own spacing, and a prompt that differs by whitespace between two roles
    is two prompts for the digest-keyed replay cache and one prompt for a reader.
    """
    body = system.strip()
    return f"{body}\n\n{HOUSE_RULES}" if body else HOUSE_RULES
