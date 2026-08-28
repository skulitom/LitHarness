"""Revoicing: a writer draws a passage as itself, and its dossier is rewritten to read like it.

**The operator's question, and the answer this module makes buildable** — `plan/dossier-voice-
direction.md` carries both verbatim: *"I'm thinking we might need to give them instructions in
that writers voice. Do you not think they will use the same voice as used in their prompt?"* and
*"yet i'm sure we have plenty examples of text in other voices. Why don't we just ask a model to
rewrite X instruction in Y voice example?"* The answer to the first is yes and it is measured
three ways; the second names the mechanism, and everything then turns on where voice Y's example
comes from.

**Two acts, and they are deliberately two calls rather than one.**

1. **The draw.** The writer drafts a short original passage as itself, aimed by a derived style
   descriptor. A generative act with nothing judged, which is what keeps it inside R3 — the
   writer produces text and says nothing about whether any text is good.
2. **The rewrite.** An anonymous rewriter is shown that passage and the writer's dossier, and
   returns the dossier saying the same things in the passage's register.

Splitting them is what makes the descriptor's containment statable. The descriptor is a
prose-craft statement by construction — sentence length and connective density are what
`directors._PROSE_STYLE` refuses in a brief — and it reaches **exactly one call**, the draw. It
never reaches the rewrite, so it is two steps from the dossier rather than one; the passage
carries whatever survived, and the passage is the thing a rewriter is allowed to be shown. That
is the note's own *"the corpus aims; the pretrained prior executes"*, made into a call graph.

**Neither call carries a tool allowance at all**, which is stronger than the enumeration
`recruiter.ALLOWED_TOOLS` needed. A recruiter has to write a record it cannot otherwise reach, so
it holds four commands; these two calls return text a caller writes down, so they pass nothing
and `CompletionRequest.allowed_tools` stays empty — the default that spells "a single-shot
completion".

**Neither call carries the house floor, and the second is the reason for the first.** `recruiter`
made this exact call and recorded it: what it writes is a bio nobody reads, *but that bio rides in
the system message of every scene call the writer it describes ever makes*, which is the reason
the floor may not reach it rather than a reason it may. A passage nobody reads that becomes the
dossier is the same object one step earlier. And the specific harm is §138's, at its worst
leverage: the floor is constant across every writer, so it contributes nothing to the
differentiation an exhibited voice exists to create, while a floor demonstrated *into* the dossier
would arrive at every scene call twice — once as its rules and once as register. `overview` took
the floor off the listing call for a neighbouring reason and recorded it; this is that decision
made again with a different argument.

**What the prior art already settles, and what it leaves open.** §85 measured the
demonstrated-voice channel **open** — an exemplar-conditioned retell moves the register — and
`research/quality-measurement/voice_binding.py` measured its dose and its persistence. So
"exhibition moves register" is not this design's question. Two things make the remaining question
real: that work showed a model **market passages**, which
`plan/dossier-voice-direction.md` forbids on the generation side for measurement independence,
and it moved *scene prose* rather than the containment surface. Whether a **model-drafted**
exemplar moves a **dossier** is the open half, and it is smaller and sharper than the note's own
framing of it.

**And the control that work says this cannot go without is a borrowing control.** A model shown
somebody's prose can move toward it by picking up the features the register is made of or by
lifting its phrases, and a distance measure cannot tell those apart. `voice.SHARED_RUN_LIMIT` is
the cheap one-passage equivalent, and it is a refusal rather than a note: a rewrite that lifts a
clause is a copy wearing a register.
"""

from __future__ import annotations

from litharness.domain import voice as voice_domain
from litharness.domain import writers as writers_domain
from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import IllegalDossier, Writer

#: Frozen profiles, one per act, so the two are separable on the decision rows without anybody
#: having to join back to find out which call a row paid for. Dotted, lowercase and
#: version-suffixed, the convention `architect.seed.v0` and `recruiter.several-with-beat.v0`
#: already keep.
EXEMPLAR_PROFILE = "revoice.exemplar.v0"
REWRITE_PROFILE = "revoice.rewrite.v0"

#: Binds nothing on the `claude -p` transport, which never reads it; recorded rather than left to
#: read as a cap being enforced. `recruiter.MAX_OUTPUT_TOKENS` says the same thing for the same
#: reason.
MAX_OUTPUT_TOKENS = 2000

#: About how long a drawn passage should be. Long enough for a register to be visible in more than
#: one sentence, short enough that the draw is cheap and that a rewriter is shown a voice rather
#: than a story.
EXEMPLAR_WORDS = 150

#: The draw's task. **No clause says what good prose is and none names a prose axis**: the
#: descriptor arrives in the prompt half as numbers, and the writer's own dossier is the only
#: thing in the system half. §136's rule, inherited — per-draw material goes in the prompt, and a
#: standing system instruction would give one draw's aim authority over every draw.
_DRAW = (
    "You are drafting the opening of a chapter: prose from the middle of a working night, not "
    "a sample and not a demonstration.\n"
    "Nobody has given you a story. Write the one you would write.\n"
    f"About {EXEMPLAR_WORDS} words.\n"
    "Return only the prose: no title, no heading, no preamble, no commentary, and nothing "
    "about what you wrote or why."
)

#: The rewriter's whole system message. **No dossier and no floor**, for the module docstring's
#: two reasons, and no identity of any kind: a cast writer rewriting a colleague's dossier is the
#: premise lock at one remove, which is `recruiter`'s recorded reason for running with
#: `writer=None`, and a writer rewriting *its own* dossier is a role editing its own containment
#: surface.
#:
#: **The G3 shape is quoted as a result and never as a recipe**, which is `house`'s standing
#: constraint: a rule may say what fails and may not enumerate what succeeds. There is deliberately
#: no affirmative description of a good register anywhere in this text — the passage is the
#: instruction, which is `repair_generation.exemplar_system`'s own line, reused rather than
#: reinvented.
_REWRITE = (
    "You are given a passage and, after it, a paragraph by the same person.\n"
    "Return the paragraph rewritten so that it moves the way the passage moves.\n"
    "Everything the paragraph says survives: the same claims in the same order, the same "
    "subject, the same things loved, the same thing wanted of a reader. You are changing how it "
    "reads and nothing about what it reports.\n"
    "Take nothing else from the passage. Not its story, not its images, not its nouns, and no "
    "run of its words. A rewrite that borrows a phrase is refused by a check on the returned "
    "text, and the record is not written.\n"
    "Say nothing about how to write. Not a word on sentences, punctuation, rhythm, how much of "
    "somebody's thinking belongs on a page, or what makes prose good. That is refused rather "
    "than discouraged: this paragraph is sent again with every scene of every book its writer "
    "drafts, so one line of it about how to write would answer a question this project has "
    "open, in every prompt, with nothing to answer back.\n"
    "No dashes in it. The gate matches the mark itself and refuses the record whatever the "
    "sentence was doing.\n"
    "One paragraph, no line breaks. Return the paragraph and nothing else: no preamble, no "
    "commentary, and no quotation marks around it."
)


def render_descriptor(descriptor: voice_domain.StyleDescriptor) -> str:
    """A descriptor as a model receives it. **The one place these numbers reach a prompt.**

    Rendered from `StyleDescriptor.as_labels`, so the numbers a model was aimed with and the
    numbers written onto the decision row are formatted by one function. Two renderers is two
    values nobody can join back.

    The closing sentence is a prohibition rather than an instruction, and it is doing real work:
    without it the block reads as a standard to be met, and a model handed a standard reports
    meeting it. Nothing here is a claim about what good prose is, and saying so costs one line.
    """
    lines = "\n".join(f"{name} {value}" for name, value in descriptor.as_labels().items())
    return (
        "A voice, as numbers:\n\n"
        f"{lines}\n\n"
        "Write so that the same measurements over your passage would come back near these. "
        "None of it says what good prose is; these are the shape of a voice and not a judgment "
        "of one."
    )


def render_exemplar_request(
    writer: Writer, *, descriptor: voice_domain.StyleDescriptor
) -> CompletionRequest:
    """The draw: this writer, aimed by this descriptor, writing one passage as itself.

    **`descriptor` is required and has no default, which is a design rule made structural.** An
    unaimed draw is the circularity this whole path exists to escape: a passage drawn under a
    house-voiced dossier, with nothing else aiming it, is our own register coming back in a new
    costume, and a dossier rewritten against *that* reproduces the homogeneity rather than
    breaking it. `plan/dossier-voice-direction.md` lists our own books as source 2 and calls it
    *legal but circular*; an exemplar drawn with no descriptor is source 2 at one remove. So the
    signature refuses it rather than a comment discouraging it.
    """
    return CompletionRequest(
        prompt=render_descriptor(descriptor),
        system=f"{writer.render()}\n\n{_DRAW}",
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=EXEMPLAR_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
    )


def render_rewrite_request(*, dossier: str, exemplar: str) -> CompletionRequest:
    """The rewrite: this paragraph, in that passage's register, saying what it already said.

    **The passage comes first and the paragraph last**, which is `writers.system_for`'s order
    argument applied one level down: the last thing in a prompt is the thing a model acts on, and
    what it acts on is the paragraph. The passage is what it acts *with*.
    """
    if not dossier.strip():
        raise IllegalDossier("there is no paragraph here to rewrite")
    if not exemplar.strip():
        raise IllegalDossier(
            "there is no passage here to rewrite against, and an unaimed rewrite is the house "
            "register asked to change into itself"
        )
    return CompletionRequest(
        prompt=(
            f"THE PASSAGE\n\n{exemplar.strip()}\n\n"
            f"THE PARAGRAPH\n\n{dossier.strip()}"
        ),
        system=_REWRITE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=REWRITE_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
    )


def accept_rewrite(*, original: str, exemplar: str, returned: str) -> str:
    """The rewritten dossier, or a refusal. **Four gates, and no redraw behind any of them.**

    **The composition lives here rather than in the domain**, and the boundary is
    `application/roster.py`'s: the *rules* are domain — `writers.legal_dossier` and
    `voice.axes_exhibited` are, and neither is restated — and which text gets which gates at
    which moment is a workflow. `cmd_roster` already composes `legal_dossier` with
    `refuse_reserved_name` the same way.

    The gates, in the order a failure is most likely:

    1. **A returned paragraph is one paragraph.** No line break, because none of the shipped
       dossiers has one and `roster vocabulary` says so. This is the cheap catch for a model that
       answered with a preamble, and it is honest about what it misses: a one-line preamble
       survives it. What backstops that is the same thing that backstops everything else here —
       the result lands `proposed` and a person reads it before `roster accept`.
    2. **R1 and the registered-axis census, both through `legal_dossier`.** A rewrite that
       started explaining its own register names an axis; one written with a mark demonstrates
       it. Both never mint.

       **This was two gates here and is one, and the collapse is worth recording rather than
       tidying.** The census had its own branch calling `voice.axes_exhibited`, written before
       the naming/carrying split moved the em dash out of `directors._CRAFT_INSTRUCTION` and put
       the census inside `legal_dossier` itself. The moment that landed, this branch became
       unreachable: every text it could catch had already raised one line earlier. An adversarial
       review found it, and found that the test naming it passed through the *other* gate's
       message, so "five gates" was four and one of them had a receipt for code that never ran.
       Two commits in one session made each other redundant, which is the argument for the
       review rather than an argument against either commit.
    3. **The borrowing control**, through `voice.longest_shared_run`. `voice_binding.py`'s design
       (§89.5) says a model shown prose moves toward it by feature or by phrase and that a
       distance cannot tell those apart; a lifted clause is a copy wearing a register.
    4. **A rewrite that changed nothing is refused.** It would mint a new writer — the exemplar
       digest is addressed material — whose dossier is byte-identical to its parent's, which is a
       second row that differs from the first in nothing that ever reaches a prompt.

    **There is no redraw.** A refusal is reported and no writer is written. Drawing again and
    keeping the one that passed is selection among candidates by preference, which is the rail
    §61(5) and §105.1 hold, and §146.8 refused exactly this move when a census hit could have
    been redrawn away. The operator may run it again; that is a recorded act rather than a quiet
    retry.
    """
    text = returned.strip()
    if not text:
        raise IllegalDossier("the rewrite returned nothing")
    if "\n" in text:
        raise IllegalDossier(
            "the rewrite returned more than one paragraph. A dossier is one paragraph and "
            "arrives in one quoted argument; a line break here is usually a preamble the model "
            "added, and nothing is written"
        )
    # R1 and the census in one call, and the docstring says why there is not a second one here.
    writers_domain.legal_dossier(text)
    run = voice_domain.longest_shared_run(exemplar, text)
    if run >= voice_domain.SHARED_RUN_LIMIT:
        raise IllegalDossier(
            f"the rewrite shares a run of {run} words with the passage it was shown, against a "
            f"limit of {voice_domain.SHARED_RUN_LIMIT}. That is borrowing rather than register, "
            "which is the distinction the exemplar-dose work (§89.5) was built around, and the "
            "two are not "
            "separable after the fact"
        )
    if text == original.strip():
        raise IllegalDossier(
            "the rewrite returned the paragraph unchanged. It would mint a new writer, because "
            "the exemplar digest is addressed material, whose dossier is byte-identical to its "
            "parent's — a second row differing in nothing that reaches a prompt"
        )
    return text


__all__ = [
    "EXEMPLAR_PROFILE",
    "EXEMPLAR_WORDS",
    "MAX_OUTPUT_TOKENS",
    "REWRITE_PROFILE",
    "accept_rewrite",
    "render_descriptor",
    "render_exemplar_request",
    "render_rewrite_request",
]
