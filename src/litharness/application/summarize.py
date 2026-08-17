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
from litharness.domain.promises import Promise, parse_due_hint, promise_id_for
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
                    "due_hint": {
                        "anyOf": [
                            {"type": "integer"},
                            {"type": "string"},
                            {"type": "null"},
                        ]
                    },
                },
            },
        },
        "promises_paid": {"type": "array", "items": {"type": "string"}},
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


def render_summary_prompt(text: str, *, open_threads: Sequence[str] = ()) -> tuple[str, str]:
    """(system, prompt) for one scene.

    The fields are asked for by name so the answer is four short statements rather than one
    paragraph of tone, and each is asked for *fresh from the scene* — the instruction that
    keeps the model from treating them as a running log it continues.

    The book's own open threads go in the prompt so the OPEN field has something to notice
    rather than to invent. They are shown, never asserted: a scene that touches none of them
    should say so, and `check_open_threads` reads the answer rather than assuming it.

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
        "For each: a short subject name, what is now owed, and the scene number it is due "
        "by when the scene implies one.\n"
        "PROMISES_PAID: the subject names of previously open threads this scene pays off."
    )
    owed = ""
    if open_threads:
        owed = "\n\nThe book records these as still owed; note any this scene touches:\n" + (
            "\n".join(f"- {thread}" for thread in open_threads)
        )
    return system, f"The scene:\n\n{text}{owed}"


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

    **The promise ledger (§61 Add 2) is maintained here and only here.** The story keys a
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
        system, prompt = render_summary_prompt(node.content, open_threads=threads)
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
        paid = (
            [item for item in paid_raw if isinstance(item, str)]
            if isinstance(paid_raw, list)
            else []
        )

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
            promises={"opened": opened, "paid": paid} if opened or paid else None,
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
                    ),
                )
            for name in paid:
                subject = normalise_subject(name)
                if not subject:
                    continue
                store.pay_promise(
                    book_id,
                    branch_id,
                    promise_id_for(book_id, subject),
                    paid_at_key=opened_key,
                    paid_by_revision=revision_id,
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
    "extract_delta",
    "flatten",
    "make_summary_handler",
    "render_summary_prompt",
]
