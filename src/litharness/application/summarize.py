"""The producer for `domain/context.py`'s evicted-context slot.

**Why this exists at all, and why it did not before.** The context packet drops the oldest
prose when the budget binds, records the omission, and hands the generator nothing about the
scenes it dropped. That was invisible for as long as this system wrote 172-word scenes:
`plan/stage-0-decisions.md` §47 measured the 6,000-token budget binding at scene 24 at that
length and recorded the eviction counter staying "at zero for every six-scene fixture, which
is exactly why this limit went unnoticed". At the lengths a capable generator writes it binds
around scene five, so a book of any real size was about to be written by a model that could
not see most of it.

**Fielded rather than free-form, and each field written fresh.** The fields are the four
things the packet's other sections cannot carry for an evicted scene — where it happened, who
was in it, what changed, what it left open — and asking for them by name is what stops the
answer being a paragraph of atmosphere. `OPEN` is the field with a ground truth: this project
records `open_threads` as state, so what a summary claims the book still owes can be checked
against what the book *records* it owes rather than taken on trust. `check_open_threads` is
that check.

**Per scene, never a rolling digest of the book.** A rolling summary has to be recomputed
whenever any covered scene is repaired, and it accumulates drift with nothing to compare
against. A per-scene summary is idempotent, addressed by that scene's own content hash, and a
repair invalidates exactly one.

**It is a mechanical call and routes to a local model** (§15): at ~1,000 invocations for a
draft, the CLI adapters' 15-24k-token per-invocation harness tax would dwarf the payload, and
this is the highest-count job class in the system.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import litharness_contracts as lc

from litharness.application.conductor import JobHandler
from litharness.application.ports import SummaryStore, TextGenerator
from litharness.application.repair import SCENE_SUMMARY
from litharness.domain import state as state_mod
from litharness.domain.beats import Beat, TemplateMismatch, beats_for, template_for
from litharness.domain.events import Event
from litharness.domain.extraction import normalise_subject
from litharness.domain.findings import Finding, Severity, Status, finding_id_for
from litharness.domain.generation import PROFILES, CompletionRequest
from litharness.domain.jobs import Job
from litharness.domain.nodes import NodeKind
from litharness.domain.promises import (
    PROMISE_KINDS,
    Promise,
    describe_owed,
    normalise_kind,
    parse_due_hint,
    promise_id_for,
)
from litharness.domain.text import content_hash

#: The call class, which is what routes this to a non-billing provider even in production.
CALL_CLASS = "mechanical"

#: Resolves to a greedy sampler: a summary of fixed prose is an extraction, and the same scene
#: should compress the same way twice.
PROFILE = "mechanical"

#: Words. Small on purpose — the whole value of the slot is that a scene costs a fraction of
#: its prose to keep, and a summary that ran long would evict the prose it was meant to spare.
TARGET_WORDS = 60

#: §61 Add 2 extends the four packet fields with three structural ones, folded into this
#: same call rather than a new one (§15: the per-invocation harness tax dwarfs the payload,
#: so asks fold into one invocation). `delta` is the dramatic value shift — not ledger
#: arithmetic, which is the distinction scene_change_profile died on: the confession scene
#: carried zero state records. `promises_opened`/`promises_paid` feed the promise ledger
#: (migration 023). Everything model-sourced here stays advisory.
#:
#: `delta`'s union type is written as `anyOf` on purpose: the shallow validator in
#: `providers/base.py` reads a single top-level `"type"` per property, so a `["object",
#: "null"]` list there would break it, while `anyOf` is simply not checked at that depth —
#: a null answer passes, and a real provider still sees the full constraint.
#:
#: **W1 (§94) adds `kind` to each opened promise and adds no call**, which is the same rule
#: applied a second time: the ask that already holds the scene is the ask that gains the
#: question. What a kind buys is the per-kind open-versus-paid density the Goodhart tripwire
#: on any continuation metric needs — five opened against five paid nets to zero however
#: mismatched the kinds are.
SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "setting",
        "characters",
        "events",
        "open",
        "delta",
        "promises_opened",
        "promises_paid",
    ],
    "properties": {
        "setting": {"type": "string"},
        "characters": {"type": "string"},
        "events": {"type": "string"},
        "open": {"type": "string"},
        "delta": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["who", "what_changed", "from", "to"],
                    "properties": {
                        "who": {"type": "string"},
                        "what_changed": {"type": "string"},
                        "from": {"type": "string"},
                        "to": {"type": "string"},
                    },
                },
                {"type": "null"},
            ]
        },
        "promises_opened": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["subject", "description"],
                "properties": {
                    "subject": {"type": "string"},
                    "description": {"type": "string"},
                    # W1 (§94). **Optional rather than required, and the choice is the
                    # safety argument.** A required field would make a model that cannot
                    # classify a debt return a malformed answer and lose the promise
                    # entirely; optional means the worst case is an untyped row, which is
                    # exactly where every row stood before migration 028. `enum` states the
                    # frozen set to a provider that enforces schemas, and
                    # `promises.normalise_kind` re-checks it for the transports that cannot.
                    "kind": {
                        "anyOf": [
                            {"type": "string", "enum": list(PROMISE_KINDS)},
                            {"type": "null"},
                        ]
                    },
                    "due_hint": {
                        "anyOf": [
                            {"type": "integer"},
                            {"type": "string"},
                            {"type": "null"},
                        ]
                    },
                    "evidence_quote": {"type": "string"},
                },
            },
        },
        "promises_paid": {
            "type": "array",
            "items": {
                "anyOf": [
                    {"type": "string"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["subject", "evidence_quote"],
                        "properties": {
                            "subject": {"type": "string"},
                            "evidence_quote": {"type": "string"},
                        },
                    },
                ]
            },
        },
    },
}

#: Rule id for the zero-delta annotation. INFO — it never blocks, never parks; it puts "this
#: scene reported no value shift" on the record for §61 Add 1's correlation work, and that is
#: all it does. No gate change of any kind rides on it.
SCENE_DELTA_RULE = "craft.scene_delta.v0"

#: The delta object's fields, in the order the prompt asks for them.
DELTA_FIELDS = ("who", "what_changed", "from", "to")


class SummaryInputError(Exception):
    """The job payload does not describe a scene this handler can summarise."""


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def render_summary_prompt(
    text: str,
    *,
    open_threads: Sequence[str] = (),
    open_promises: Sequence[Promise] = (),
) -> tuple[str, str]:
    """(system, prompt) for one scene.

    The fields are asked for by name so the answer is four short statements rather than one
    paragraph of tone, and each is asked for *fresh from the scene* — the instruction that
    keeps the model from treating them as a running log it continues.

    The book's own open threads go in the prompt so the OPEN field has something to notice
    rather than to invent. They are shown, never asserted: a scene that touches none of them
    should say so, and `check_open_threads` reads the answer rather than assuming it.

    **The promise ledger goes in beside them, and until this existed the one call that can
    settle a debt was the one call never shown what the book owed.** `promises_paid` is put
    through `normalise_subject` into `promise_id_for(book_id, subject)` and matched against a
    row already open, so a payment lands only if a one-scene, no-memory call reproduces a
    subject string coined scenes earlier. Four books measured 32/0, 40/0, 41/0 and 47/0
    opened-against-paid with the ledger absent from this prompt, and on the live serial the
    summariser reproduced a subject it had itself coined **once in forty-one** opportunities.
    That is not a model failing; it is an impossibility by construction, and showing the rows
    is the whole of the repair.

    **Its own block, never folded into the thread block, because the two are different
    classes of claim.** Open threads are canon-backed state records; promises are
    model-reported or legacy-seeded debts, which is exactly why `domain/context.py` renders
    them through `describe_owed` as a debt rather than as a fact. One list under one heading
    would launder the second into the register of the first — the packet's own rule, applied
    to the prompt that settles the ledger rather than to the one that draws on it.

    **Information, and nothing else.** No line added here says which debt is due, which to
    pay, or that anything is owed *now*: the rows are shown exactly as the ledger stores
    them, and the only instruction is about the shape of the answer — copy the name — which
    is the same class of ask as OPEN's "say so plainly if it left nothing open". A model
    choosing which debt to settle would be a verdict, and this call has no licence for one.

    **The DELTA question is unhedged on purpose, and that is §55.1's measured lesson.** The
    progression clause was hedged three times over and their sum was an instruction to leave
    the numbers alone; the mechanism was complete and the wording decided the outcome. So
    the delta ask is a direct imperative — state the one thing that changed, or say none —
    with no "if any", no "where appropriate", no softening that would make stasis the
    default answer for a scene that did move.
    """
    system = (
        "You are compressing one scene of a novel so a writer who cannot re-read it still "
        f"knows what it contained. Answer in about {TARGET_WORDS} words across the prose "
        "fields. State what is on the page and nothing else: no interpretation, no praise, "
        "no guesses about what happens next. Write each field fresh from this scene rather "
        "than continuing anything.\n"
        "SETTING: where and when.\n"
        "CHARACTERS: who was present, by the names the prose uses.\n"
        "EVENTS: what changed. Concrete actions and outcomes, not atmosphere.\n"
        "OPEN: what the scene left unresolved — promises made, questions raised, debts "
        "owed. Say so plainly if it left nothing open.\n"
        "DELTA: state the one thing that changed for a character in this scene — who it "
        "changed for, what changed, what it was before, what it is now — or say none by "
        "answering null. A dramatic shift counts even when no number moves.\n"
        "PROMISES_OPENED: new threads this scene opens that the book must later pay off. "
        "For each: a short subject name, what is now owed, which kind of debt it is "
        f"({', '.join(PROMISE_KINDS)}), and the scene number it is due by when the scene "
        "implies one. Also copy one short exact quote from this scene that opens the debt; "
        "use an empty evidence_quote when no unique quote supports it.\n"
        # **Conditional, and that is what keeps the empty-ledger prompt byte-identical.** A
        # line naming a list the prompt does not carry would be asking a model to copy from
        # nowhere, and a control that is not byte-for-byte the old prompt is not a control.
        + (
            "PROMISES_PAID: for each previously open thread this scene pays off, return its "
            "subject and one short exact payoff quote from this scene."
            if not open_promises
            else "PROMISES_PAID: for each open debt this scene pays off, return its subject "
            "copied exactly as the ledger writes it and one short exact payoff quote from "
            "this scene. Empty if this scene pays none."
        )
    )
    owed = ""
    if open_threads:
        owed = "\n\nThe book records these as still owed; note any this scene touches:\n" + (
            "\n".join(f"- {thread}" for thread in open_threads)
        )
    ledger = ""
    if open_promises:
        # The subject verbatim, then the ledger's own debt line. The subject is what
        # `pay_promise` keys on and it is stored already normalised, so the rendered name
        # round-trips through `normalise_subject` unchanged — a render that title-cased or
        # re-spaced it would silently break the one key this block exists to supply.
        ledger = (
            "\n\nThe book's ledger of debts still unpaid, as it stores them. These are the "
            "book's own record of what it owes rather than established fact; each line is "
            "the name a debt is filed under, then what is owed:\n"
        ) + "\n".join(
            f"- {promise.subject} {describe_owed(promise)}" for promise in open_promises
        )
    return system, f"The scene:\n\n{text}{owed}{ledger}"


def flatten(payload: dict[str, object]) -> str:
    """The four fields as the one line the packet renders.

    Flattened at write time rather than at render time, so the stored artifact is the thing
    that goes into the prompt: a summary reassembled differently by each reader is one whose
    effect on the book nobody can reconstruct from the record.
    """
    parts = [
        f"{label} {str(payload.get(key, '')).strip()}"
        for key, label in (
            ("setting", "Setting:"),
            ("characters", "Characters:"),
            ("events", "Events:"),
            ("open", "Left open:"),
        )
        if str(payload.get(key, "")).strip()
    ]
    return " ".join(parts)


def check_open_threads(summary_open: str, threads: Sequence[str]) -> tuple[int, int]:
    """(threads the OPEN field mentions, threads the book records). Advisory.

    **The one field in this artifact with a ground truth**, and the reason a summarizer is
    worth more in this system than in one without a state layer: the book already records
    what it owes, so "did the compression keep the promises" is checkable rather than a
    matter of taste.

    **A majority of the thread's distinctive words, not any one of them.** The first version
    of this asked for a single word over four letters and counted a thread as kept — which
    matched "the sealed letter must be read aloud at the will reading" against a summary
    whose only overlap was the word *aloud*. One shared word between two sentences about a
    book with a consistent register is not evidence of anything, and a coverage number
    inflated that way would be this project's own §2 lesson repeated at a smaller scale: a
    measurement that reports the vocabulary rather than the thing.

    Still crude, and deliberately: a stricter match would need the model to quote the record
    back, which is asking it to copy a string rather than to notice a promise. Advisory and
    never a gate. A scene may legitimately leave open something the extractor never recorded,
    and a thread the book owes that *this scene* did not touch is not an error at all. This
    reports coverage for instrumentation, which is what Stage 3 is for.
    """
    lowered = summary_open.lower()
    mentioned = 0
    for thread in threads:
        distinctive = [word for word in thread.lower().split() if len(word) > 4]
        if not distinctive:
            continue
        hits = sum(1 for word in distinctive if word in lowered)
        if hits * 2 >= len(distinctive):
            mentioned += 1
    return mentioned, len(threads)


def extract_delta(payload: object) -> dict[str, str] | None:
    """The delta object if the model reported a usable one, else None.

    None is a *reading* — "no extractable value shift" — not an error: null is the schema's
    own answer for a scene where nothing changed, and a malformed shape (the wrong type, a
    blank field) is treated as the same reading rather than failing the job, because the
    summary beside it is still good and a scene with no delta annotation is exactly where
    every scene stood before §61 Add 2.
    """
    if not isinstance(payload, dict):
        return None
    delta: dict[str, str] = {}
    for field in DELTA_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            return None
        delta[field] = value.strip()
    return delta


def exact_evidence_span(text: str, quote: object) -> tuple[int, int] | None:
    """Locate one exact non-empty quote, refusing ambiguity and reconstructed wording."""
    if not isinstance(quote, str) or not quote.strip() or text.count(quote) != 1:
        return None
    start = text.index(quote)
    return start, start + len(quote)


def _scene_beat(beats: Sequence[Beat], logical_id: str) -> Beat | None:
    return next((beat for beat in beats if beat.logical_id == logical_id), None)


def make_summary_handler(
    registry: TextGenerator,
    store: SummaryStore,
    project_id: str,
    *,
    call_class: str = CALL_CLASS,
) -> JobHandler:
    """Build a `JobHandler` that records what one accepted scene contained.

    Returns no events, and that is a decision rather than an omission. A summary is a derived
    read-side artifact: it mutates no manuscript, accepts no candidate, and §19's attribution
    clause — every mutation traceable to a recorded policy decision — does not reach it, so
    minting a decision here would put a row on the record that decided nothing. Every store
    write here is idempotent — the summary row on the scene's content hash, the promise rows
    on their content-derived ids (`INSERT OR IGNORE`), payment as a write-once open→paid
    transition, and the zero-delta finding on its content-derived `finding_id` — which is
    what makes returning no events safe under the replay the Conductor's two-transaction
    commit allows.

    **The promise ledger (§61 Add 2) is maintained here and only here — and, since
    `plan/stage-0-decisions.md` §110, it is also *read* here and put in front of the call
    that maintains it.** The writer's packet has always carried the open rows
    (`planner.packet_for` → the THREADS section) and the outline call has always seen their
    subjects; this call, the only one that can mark a debt paid, was the only one not shown
    them, and four books settled nothing. Read-only from the ledger's side: nothing about
    which debt is due, or due now, is computed or said. The story keys a
    promise carries are read off `beats_for`'s own minting — the scene's beat for
    `opened_at_key`, the hinted scene's beat for `due_key`, the last beat when the hint is
    absent or unparseable (a promise is at latest overdue if the book ends unpaid) — so
    there is exactly one padding implementation in the project. A book whose template is not
    chronological, or does not fit a template at all, gets no promise rows: the same
    abstention milestones make, no key rather than a guessed one.
    """

    def handle(job: Job, now: float) -> Sequence[Event]:
        payload = job.payload
        try:
            book_id = str(payload["book_id"])
            branch_id = str(payload["branch_id"])
            revision_id = str(payload["revision_id"])
            logical_id = str(payload["logical_id"])
            expected_hash = str(payload["content_hash"])
        except (KeyError, TypeError) as error:
            raise SummaryInputError(
                f"job {job.job_id} payload lacks book/branch/revision/logical/content_hash: "
                f"{error}"
            ) from error

        revision = store.load_revision(revision_id)
        try:
            node = revision.node(logical_id)
        except KeyError as error:
            raise SummaryInputError(
                f"job {job.job_id} names {logical_id}, which is not in {revision_id[:12]}"
            ) from error
        if node.kind is not NodeKind.SCENE or not node.content:
            raise SummaryInputError(
                f"job {job.job_id} names {logical_id}, which carries no prose to summarise"
            )

        # **The prose has to still be the prose the job was minted for.** A repair landing
        # between the enqueue and the claim leaves a job whose content hash names text that
        # no longer exists, and summarising what is there *now* under that hash would file a
        # new summary at the old scene's address — a summary silently describing different
        # prose than the packet believes it describes. Returning nothing is correct: the
        # repair minted its own summary job for the text it wrote.
        actual = content_hash(node.content)
        if actual != expected_hash:
            return ()

        threads = [
            state_mod.describe(record)
            for record in state_mod.open_threads(store.state_records(book_id, branch_id))
        ]
        # **The ledger, in the one call that can settle it.** Open rows only — a paid debt is
        # not owed — in the store's own due-soonest-first order and uncapped: the rows are one
        # line each, the largest ledger this project has measured is 47 of them, and a cap
        # would drop exactly the debts a long book most needs settled while reporting nothing.
        # If one is ever needed it belongs in the summary row as what was dropped, never as a
        # silent truncation.
        open_promises = tuple(store.promises(book_id, branch_id, open_only=True))
        system, prompt = render_summary_prompt(
            node.content, open_threads=threads, open_promises=open_promises
        )
        result, _ = registry.complete(
            CompletionRequest(
                prompt=prompt,
                system=system,
                schema=SUMMARY_SCHEMA,
                profile=PROFILE,
                call_class=call_class,
                sampler=PROFILES[PROFILE],
                max_output_tokens=512,
            )
        )
        if result.parsed is None:
            # A malformed answer is a shape result and earns the ordinary bounded retry. It
            # is not a crisis: a scene with no summary is an eviction with nothing left
            # behind, which is exactly where the packet started.
            raise SummaryInputError(
                f"job {job.job_id}: {result.provider} returned no conforming summary"
            )

        # §61 Add 2's three structural fields, read tolerantly: the summary is the artifact
        # the packet depends on, and a model that answered the four prose fields but fumbled
        # a structural one has produced a usable summary with a missing annotation, not a
        # failed job.
        delta = extract_delta(result.parsed.get("delta"))
        opened_raw = result.parsed.get("promises_opened")
        opened = (
            [item for item in opened_raw if isinstance(item, dict)]
            if isinstance(opened_raw, list)
            else []
        )
        paid_raw = result.parsed.get("promises_paid")
        paid_entries: list[dict[str, object]] = []
        if isinstance(paid_raw, list):
            for item in paid_raw:
                if isinstance(item, str):
                    paid_entries.append({"subject": item, "evidence_quote": ""})
                elif isinstance(item, dict) and isinstance(item.get("subject"), str):
                    paid_entries.append(item)
        paid = [str(item["subject"]) for item in paid_entries]

        # **What the model said, and which of it named a row on the list it was shown.** The
        # match is exact by construction — `pay_promise` keys on
        # `promise_id_for(book_id, normalise_subject(name))` and updates only `status='open'`
        # — so this is set membership against the subjects rendered into the prompt, and
        # recording both halves is what makes "did showing the ledger change anything"
        # answerable from the store rather than re-derived from prose. Deliberately not a
        # looser test: a ledger that pays on near-matches is worse than one that pays
        # nothing, because W4 grades payoff landing against the ledger's own wording.
        #
        # One case is neither, and it is named rather than folded in: a subject *this same
        # scene* opens and pays in one answer was not on the list, so it is recorded
        # unmatched, and the ledger below still settles it — pre-existing behaviour this
        # change does not touch.
        shown = {promise.subject for promise in open_promises}
        paid_matched = [name for name in paid if normalise_subject(name) in shown]
        paid_unmatched = [name for name in paid if normalise_subject(name) not in shown]

        store.record_scene_summary(
            book_id,
            branch_id,
            logical_id,
            content_hash=actual,
            summary=flatten(result.parsed),
            model=result.model,
            profile=PROFILE,
            created_at=_timestamp(now),
            delta=delta,
            promises=(
                {
                    "opened": opened,
                    "paid": paid,
                    "paid_matched": paid_matched,
                    "paid_unmatched": paid_unmatched,
                }
                if opened or paid
                else None
            ),
        )

        # The promise ledger. Story keys are read off `beats_for`'s minting, never formatted
        # here — see the factory docstring — and a book the template machinery refuses, or a
        # template that is not chronological, abstains whole.
        beats: tuple[Beat, ...]
        try:
            beats = beats_for(revision, template_for(revision))
        except TemplateMismatch:
            beats = ()
        beat = _scene_beat(beats, logical_id)
        opened_key = beat.story_order_key if beat is not None else None
        final_key = beats[-1].story_order_key if beats else None
        if opened_key is not None and final_key is not None:
            for item in opened:
                subject = normalise_subject(str(item.get("subject", "") or ""))
                description = str(item.get("description", "") or "").strip()
                if not subject or not description:
                    continue
                hinted = parse_due_hint(item.get("due_hint"))
                due_key = (
                    beats[hinted - 1].story_order_key
                    if hinted is not None and 1 <= hinted <= len(beats)
                    else None
                ) or final_key
                opening_span = exact_evidence_span(
                    node.content, item.get("evidence_quote")
                )
                store.record_promise(
                    book_id,
                    branch_id,
                    Promise(
                        promise_id=promise_id_for(book_id, subject),
                        subject=subject,
                        description=description,
                        opened_at_key=opened_key,
                        due_key=due_key,
                        opened_by_revision=revision_id,
                        model=result.model,
                        # W1: read as tolerantly as every other structural field here. An
                        # unrecognised kind is untyped, never an error and never mapped to a
                        # near neighbour — an unregistered category is a nomination, and
                        # nominations are weighed by an operator over the derivation run's
                        # distribution, not by a synonym table in a handler.
                        kind=normalise_kind(item.get("kind")),
                        opened_logical_id=logical_id if opening_span is not None else None,
                        opened_start=opening_span[0] if opening_span is not None else None,
                        opened_end=opening_span[1] if opening_span is not None else None,
                        opened_content_hash=actual if opening_span is not None else None,
                    ),
                )
            for paid_entry in paid_entries:
                name = str(paid_entry["subject"])
                subject = normalise_subject(name)
                if not subject:
                    continue
                payment_span = exact_evidence_span(
                    node.content, paid_entry.get("evidence_quote")
                )
                store.pay_promise(
                    book_id,
                    branch_id,
                    promise_id_for(book_id, subject),
                    paid_at_key=opened_key,
                    paid_by_revision=revision_id,
                    paid_logical_id=logical_id if payment_span is not None else None,
                    paid_start=payment_span[0] if payment_span is not None else None,
                    paid_end=payment_span[1] if payment_span is not None else None,
                    paid_content_hash=actual if payment_span is not None else None,
                )

        # Scene-delta annotation: a null delta is recorded as an INFO finding against this
        # scene's revision — never a gate change of any kind. INFO never blocks and never
        # becomes standing-that-parks; it puts "dramatic_function unverified" on the record
        # where §61 Add 1's correlation work can find it.
        if delta is None:
            store.record_findings(
                book_id,
                branch_id,
                [
                    Finding(
                        finding_id=finding_id_for(
                            SCENE_DELTA_RULE, logical_id, {"content_hash": actual}
                        ),
                        category=lc.FindingCategory.PACING.value,
                        severity=Severity.INFO,
                        status=Status.OPEN,
                        subtype="zero_delta",
                        rule_or_critic_id=SCENE_DELTA_RULE,
                        logical_id=logical_id,
                        # The verdict is the model's own reading of its scene, uncalibrated.
                        confidence_basis=lc.ConfidenceBasis.HEURISTIC.value,
                        message="no extractable value shift; dramatic_function unverified",
                        source={"claim": {"content_hash": actual}},
                    )
                ],
                created_at=_timestamp(now),
                revision_id=revision_id,
            )
        return ()

    return handle


__all__ = [
    "CALL_CLASS",
    "DELTA_FIELDS",
    "PROFILE",
    "SCENE_DELTA_RULE",
    "SCENE_SUMMARY",
    "SUMMARY_SCHEMA",
    "TARGET_WORDS",
    "SummaryInputError",
    "check_open_threads",
    "exact_evidence_span",
    "extract_delta",
    "flatten",
    "make_summary_handler",
    "render_summary_prompt",
]
