"""The reviser: one drafted scene in, one rewritten scene out, and no choice made anywhere.

**The operator's directive, read 12** (`plan/serial-pilot-18.md` §4): after the finished draft,
a stronger model rewrites the chapter for sentence and paragraph structure. The families it is
aimed at were named across reads 10, 11 and 12 and are recorded there and in
`plan/serial-pilot-16.md` §7 — not restated here, and no sentence of any of them is in the text
below (§97.1).

**One draft in, one revision out, and that is the whole shape.** No second candidate is drawn,
nothing is scored, and no model is asked which of two texts is better. §61(5) and §105.1 are the
rails, and §105's own measurement is the prior: the one collaboration-shaped loop this project
built and measured returned the same commits for 2.25x the calls and shipped off. What is being
added here is not a tournament with one entrant; it is a **transformation**, the mechanism family
`blurb_rewrite` and `revoice` already occupy, where the return is checked against its input by
code rather than ranked against an alternative by a model.

**It never judges, and the containment is why that is a property rather than a promise.** The
returned text is measured against the draft by `domain/reviser.contain` — the machine lines
character for character, no name or number the draft did not have, a bounded length — and a
return that fails is discarded with the draft standing. Then the revision goes down the **same
gate ladder the draft would have**: shape, integrity, and §184's beat comparison, all of them on
the revised prose. `application/handlers.py` is where that ordering lives and why.

**What it stands on.** `house.CLARITY` and nothing else of the floor (§129's tier order read
literally). Every demand `CLARITY` makes is a sentence-or-paragraph surface — a term the reader
has not met, a sentence with two readings, an object acting, a comparison, a pronoun inside a
paragraph, a fourth thing happening after three — which is exactly this role's object. `READER`
and `ACCUMULATION` are demands about **what the story contains and what its reader collects**,
and a reviser acting on either would change the story, which containment refuses mechanically. A
demand whose only compliant response is refused by a check one function later is a demand landing
with its sign multiplied by zero (§154), so it is not sent.

**The model is a lever and not a claim.** `REVISION_MODEL` is `None`, which means the pinned
provider's own model — the strongest this installation has configured (`providers/cli.py`). The
directive's word is *smarter*, and this repository pins one frontier generator for every call
class on §1a's grounds, so what ships is the **seam**: a role whose model is nameable and
recorded separately from the writer's, ready for the day the installation configures a stronger
one. Naming a model here that the registry does not have would be a claim the code could not keep.
"""

from __future__ import annotations

from litharness.domain import house
from litharness.domain.generation import CompletionRequest

#: Frozen profile, so the reviser's decision rows are separable from the writer's without
#: anybody joining back to find out which call a row paid for. Dotted, lowercase and
#: version-suffixed, the convention `revoice.rewrite.v0` and `architect.seed.v0` already keep.
#:
#: It resolves to no sampler of its own: `generation.PROFILES` does not carry it, so
#: `PROFILES.get` falls to the prose default, and the `claude -p` transport reads no sampler at
#: all. It is provenance, and `repair`'s own profile string has been exactly that since it was
#: written.
REVISION_PROFILE = "reviser.scene.v0"

#: Which model the reviser asks for. **`None` means the pinned provider's own**, which is the
#: strongest model this installation has configured, and it is the default for the reason the
#: module docstring gives. An operator naming a different one here changes the reviser's model
#: and nothing else: it rides `CompletionRequest.model`, reaches only this call, and lands on
#: this call's own decision row.
REVISION_MODEL: str | None = None

#: Binds nothing on the `claude -p` transport, which never reads it. Recorded rather than left to
#: read as a cap being enforced, and set where the drafting call's own default sits, because the
#: thing being returned is a scene of the same length.
MAX_OUTPUT_TOKENS = 4096

#: Longer than a drafting call's, because this call's input is a scene plus the material the
#: scene was written from and the transport charges wall time, not tokens, for a timeout.
TIMEOUT_SECONDS = 600.0

#: The reviser's task. **Every craft clause is prohibition-signed** — §138 measured the
#: permission-only form of one clause returning more than six times what the prohibition-only
#: form did, and worse than saying nothing at all, so the flow this role exists to produce
#: enters as a prohibition on the shape standing in its way and never as an adjective. There is
#: no sentence here about what good prose is, no instruction to write beautifully, and no list of
#: instances: `house`'s standing constraint is that a rule may say what fails and may not
#: enumerate what succeeds, and three clauses have been cut from that module for being recited
#: back.
#:
#: **The conjunction is named as a part of speech rather than as a word.** A prohibition against
#: chaining that cannot say what the chaining is made of is unaddressable (§154), and quoting the
#: function words an operator used to describe the defect would be the read becoming prompt text
#: (§97.1). *A conjunction* is a thing a writer can see on the page and belongs to nobody's read.
#:
#: **Two of these are containment stated as instruction rather than as craft**, and they are here
#: as well as in `domain/reviser.py` on purpose: the check is what makes the property true, and
#: the sentence is what stops the model spending a call discovering it. The check is the
#: authority; the sentence says so.
#:
#: Carries no word of `house.MACHINERY_WORDS` — this text reaches the book's own prose, and
#: `tests/test_prompt_budget.py`'s leak rail is what says so rather than this comment.
_TASK = (
    "You are given one scene of a novel that is already written, and before it the material it "
    "was written from. Return that same scene rewritten, changing only how its sentences and "
    "its paragraphs are built.\n"
    "Nothing that happens changes: the same events in the same order with the same outcome, "
    "done and said by the same people in the same place. Nothing is added and nothing is cut. "
    "No name, no number and no fact that is not already in the scene you were given.\n"
    "A line beginning with a bracketed word in capitals is printed by the book as a machine "
    "rather than as prose. Reproduce each one character for character, where it already sits "
    "and as many times as it already appears; a check on the returned text compares them, and "
    "what fails it is discarded unread.\n"
    "What fails is a sentence hanging one happening on the next with no more between them than "
    "a conjunction or a comma, where one of them is the reason, the moment or the condition of "
    "another and the sentence never says which.\n"
    "What fails is a phrase punctuated as a sentence with no verb of its own, and a phrase "
    "opening a sentence whose actor is not the subject of the clause it opens.\n"
    "What fails is a run of sentences beginning the same way.\n"
    "What fails is a perception belonging to somebody in the scene and reported about them "
    "where they are present to say it or to think it; one nobody there is placed to have is "
    "not that.\n"
    "What fails is a paragraph whose last sentence is about something its first sentence was "
    "not.\n"
    "What fails is a phrase folding a fact the reader has not been given into a modifier, so "
    "that the sentence reads as though they had it.\n"
    "Return the rewritten scene and nothing else: no heading, no preamble, no commentary, and "
    "nothing about what you changed."
)


def revision_system() -> str:
    """The reviser's whole system message: `house.CLARITY` and then the task.

    Extracted as a function for `tests/test_prompt_budget.py`'s reason, which is the reason
    `overview.title_system` was extracted — a role assembled only inside its own call site is a
    role nobody can measure the size of.
    """
    return house.with_clarity_floor(_TASK)


def render_revision_request(
    scene: str, *, material: str | None = None, model: str | None = REVISION_MODEL
) -> CompletionRequest:
    """(request) for one rewrite of one drafted scene.

    **The scene goes last**, which is `writers.system_for`'s order argument at a third address:
    the last thing in a prompt is the thing a model acts on, and what it acts on is the scene.
    The material is what it acts *with*.

    **`material` is the packet the scene was drafted from, and it arrives without the drafting
    call's own closing instruction.** The payload's prompt ends on *Now write ...*, an imperative
    to produce a scene that does not yet exist; handing that to a call whose whole containment
    rests on producing the scene that does is the one sentence in the input most likely to be
    obeyed. So the planner records the packet as its own payload slot and this reads that,
    rather than slicing the assembled prompt at a boundary that would go stale (§184's rule
    about re-deriving an ask instead of reading it).

    `None` is accepted and renders nothing: a job enqueued before the packet had a slot still
    revises, on the scene alone, and containment is unchanged by which of the two it saw.
    """
    body = scene.strip()
    if not body:
        raise ValueError("there is no scene here to revise")
    prompt = (
        f"THE MATERIAL THIS SCENE WAS WRITTEN FROM\n\n{material.strip()}\n\nTHE SCENE\n\n{body}"
        if material and material.strip()
        else f"THE SCENE\n\n{body}"
    )
    return CompletionRequest(
        prompt=prompt,
        system=revision_system(),
        model=model,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=REVISION_PROFILE,
        call_class="generation",
        timeout_seconds=TIMEOUT_SECONDS,
    )


__all__ = [
    "MAX_OUTPUT_TOKENS",
    "REVISION_MODEL",
    "REVISION_PROFILE",
    "TIMEOUT_SECONDS",
    "render_revision_request",
    "revision_system",
]
