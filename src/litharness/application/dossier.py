"""One scene's dossier: every stored row that explains it, joined, with the gaps named.

Lifted out of `cli.py` (stage-0 §241) so that the command line and the agent surface print
one dict from one function. Nothing here is computed from the prose: the prompt is the one
frozen on the job payload at enqueue (invariant I5), the gate ladder is the one that ran,
and an absence is a named gap rather than a re-rendering. `cmd_why` and the server's `why`
tool both call `scene_dossier`; `render_dossier` is the person's version of the same dict.

Read-only and fenced. `plan/serial-pilot-1.md` §6 and stage-0 §97.1 keep diagnostics on the
operator's side of the loop: nothing this module returns is a channel back into generation,
and the one thing it withholds — an exemplar shelf spliced into a frozen prompt
(`redact_shelf`) — it withholds because the shelf is other writers' text that may be shown to
the writer and never quoted anywhere else (stage-0 §196).
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from litharness.application import exemplars as exemplars_mod
from litharness.application.handlers import SCENE_DRAFT
from litharness.application.ports import DossierStore
from litharness.domain.findings import Finding
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.plans import scene_plan_for
from litharness.domain.policy import GateOutcome, PolicyDecision
from litharness.domain.revision import Revision

#: The keys `scene_dossier` builds, in the order it builds them. One constant so the skill,
#: the server's description and a test can name the shape without a second copy of it.
DOSSIER_KEYS: tuple[str, ...] = (
    "book_id",
    "branch_id",
    "logical_id",
    "scene",
    "decision",
    "attempts",
    "job",
    "prompt",
    "selected_by",
    "context",
    "context_omitted",
    "plan_item",
    "findings",
    "draft_before_revision",
    "absent",
)


def finding_row(item: Finding) -> dict[str, Any]:
    """One finding as an agent reads it. Shared by `findings --json` and the dossier, so
    the two verbs an agent chains cannot describe the same row differently."""
    return {
        "finding_id": item.finding_id,
        "severity": item.severity.value,
        "status": item.status.value,
        "blocks": item.blocks,
        "category": item.category,
        "subtype": item.subtype,
        "rule_or_critic_id": item.rule_or_critic_id,
        "logical_id": item.logical_id,
        "message": item.message,
        "deterministic": item.deterministic,
    }


UNANSWERED = ("prose", "decision", "prompt")


def gate_row(gate: GateOutcome) -> dict[str, Any]:
    """One rung of the ladder as stored. `_gate_to_row` in the store is the write side."""
    return {
        "gate": gate.gate.value,
        "rule_or_critic_id": gate.rule_or_critic_id,
        "passed": gate.passed,
        "blocking": gate.blocking,
        "verdict_source": gate.verdict_source.value,
        "vetoes": [veto.value for veto in gate.vetoes],
        "detail": gate.detail,
        "calibration_id": gate.calibration_id,
    }


def decision_row(decision: PolicyDecision) -> dict[str, Any]:
    """One policy decision, whole. A refusal is carried as fully as an acceptance."""
    return {
        "decision_id": decision.decision_id,
        "outcome": decision.outcome.value,
        "attempt": decision.attempt,
        "job_id": decision.job_id,
        "logical_id": decision.logical_id,
        "base_revision_id": decision.base_revision_id,
        "resulting_revision_id": decision.resulting_revision_id,
        "provider": decision.provider,
        "model": decision.model,
        "profile": decision.profile,
        "fell_back_from": list(decision.fell_back_from),
        "invocations": decision.invocations,
        "total_tokens": decision.total_tokens,
        "cost_usd": decision.cost_usd,
        "policy_config_digest": decision.policy_config_digest,
        "reason": decision.reason,
        "gates": [gate_row(gate) for gate in decision.gates],
    }


def scenes_of(revision: Revision) -> list[Node]:
    return [
        node
        for node in revision.in_reading_order()
        if node.kind is NodeKind.SCENE and not node.tombstoned
    ]


def scene_node(head: Revision, wanted: str) -> Node | None:
    """The scene `--scene` names: a logical id, or a 1-based place in reading order.

    Both, because the two callers differ. A logical id is what every other verb prints and
    what an agent chains from; an ordinal is what a human reading the book has. `new_book`
    mints `scene-3`, so a digit resolves through that id first and falls back to counting —
    an imported book whose scenes are named otherwise still answers `--scene 3`.
    """
    scenes = scenes_of(head)
    by_id = {node.logical_id: node for node in scenes}
    if wanted in by_id:
        return by_id[wanted]
    if wanted.isdigit():
        derived = f"scene-{int(wanted)}"
        if derived in by_id:
            return by_id[derived]
        index = int(wanted) - 1
        if 0 <= index < len(scenes):
            return scenes[index]
    return None


def introduced_in(store: DossierStore, head: Revision, logical_id: str) -> tuple[str | None, int]:
    """The revision that put the head's current prose into this scene, and how deep it sits.

    Walked oldest-first along the lineage and remembered on every *change* of the node's
    content hash, so a scene a repair rewrote reports the repair rather than the first
    draft — the decision an operator wants is the one that produced the text they are
    reading. Revisions predating the node are skipped rather than assumed empty.
    """
    previous: str | None = None
    introduced: str | None = None
    depth = 0
    for index, revision_id in enumerate(reversed(store.lineage(head.revision_id))):
        try:
            node = store.load_revision(revision_id).node(logical_id)
        except KeyError:
            continue
        if node.content_sha256 != previous:
            previous = node.content_sha256
            if node.content:
                introduced, depth = revision_id, index + 1
    return introduced, depth


def payload_prompt(job: Job | None) -> dict[str, Any] | None:
    """The frozen prompt off the job payload, or None when the unit carries no prose to send.

    A payload with no prompt is not always a defect — an evaluation unit has none at
    all —
    but for a scene dossier it is still a gap, which is why this returns None rather than an
    empty string and lets the caller record the absence.
    """
    if job is None:
        return None
    prompt = job.payload.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return None
    system = job.payload.get("system")
    return {"system": system if isinstance(system, str) else None, "prompt": prompt}


#: The states a unit can be in without an accepted revision naming it, in the order the
#: dossier prefers one: still working, then stopped by policy, then stopped by exhaustion.
_UNFINISHED_UNIT_STATUSES = (
    JobStatus.RUNNING,
    JobStatus.QUEUED,
    JobStatus.PARKED,
    JobStatus.POISONED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
)


def unit_for_scene(
    store: DossierStore, book_id: str, branch_id: str, logical_id: str
) -> Job | None:
    """The drafting unit that names this scene and has not produced an accepted revision.

    Read off the job's own payload — the planner writes `logical_id`, `book_id` and
    `branch_id` there when it mints the unit — so a scene's parked or poisoned job is found
    the way the accepting decision would have found it, by the scene it was for. The first
    match in `_UNFINISHED_UNIT_STATUSES` order wins; a book holds at most a handful of these.
    """
    for status in _UNFINISHED_UNIT_STATUSES:
        for job in store.jobs_by_status(status, limit=1000):
            payload = job.payload
            if (
                job.job_kind == SCENE_DRAFT
                and payload.get("logical_id") == logical_id
                and payload.get("book_id") == book_id
                and payload.get("branch_id") == branch_id
            ):
                return job
    return None


def scene_dossier(
    store: DossierStore, book_id: str, branch_id: str, node: Node, head: Revision
) -> dict[str, Any]:
    """Every stored row that explains one scene, joined, with the gaps named.

    **Nothing here is computed from the prose.** Every field is a column somebody wrote at
    the time, which is what makes the answer a record rather than a re-reading: the prompt is
    the one actually sent (frozen at enqueue, invariant I5), the gate ladder is the one that
    ran. A dossier that re-rendered the prompt from live tables would be answering a
    question about today.
    """
    logical_id = node.logical_id
    absent: list[str] = []
    introduced, depth = introduced_in(store, head, logical_id)
    if introduced is None:
        absent.append("prose")

    decision = None if introduced is None else store.decision_for_revision(introduced)
    if introduced is not None and decision is None:
        absent.append("decision")

    job_id = decision.job_id if decision else None
    job: Job | None = None
    if job_id:
        with suppress(KeyError):
            job = store.load_job(job_id)
    if job is None and decision is None:
        # **A scene nobody has accepted still has a unit, and until §234 this verb could
        # not find it.** The job was reached only through the decision that accepted the
        # revision, so a parked or poisoned unit — the two the skill lists under *a scene was
        # never written* — read as `ABSENT - no queued unit is on record`, while `jobs`
        # counted it one line away. Pilot 25 draw 6 held one of each. The unit is found by
        # the scene it names, its latest decision stands in for the one that never accepted,
        # and the frozen prompt on its payload is printed exactly as for a drafted scene.
        job = unit_for_scene(store, book_id, branch_id, logical_id)
        if job is not None:
            job_id = job.job_id
            decision = store.latest_decision_for(job.job_id)
    prompt = payload_prompt(job)
    if prompt is None:
        absent.append("prompt")

    payload: dict[str, Any] = dict(job.payload) if job is not None else {}
    plan_item = scene_plan_for(store.plan_items(book_id, branch_id), logical_id)
    if plan_item is None:
        absent.append("plan_item")

    # **The text the reviser replaced, when there is one** (§187). Scoped to the revision that
    # introduced this scene's prose, so what comes back is the *pair*: this row's text against
    # the node content beside it. Absence is not a gap and is deliberately not on `absent` —
    # a scene drafted with the stage held back, or drafted before §187, has no such text
    # because the accepted prose is the writer's own. Nothing is computed from either string
    # here; §97.1 keeps this verb on the operator's side and a diff is a reader's act.
    kept = (
        [
            item
            for item in store.pre_revision_drafts(book_id, branch_id, logical_id=logical_id)
            if item.revision_id == introduced
        ]
        if introduced is not None
        else []
    )

    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "logical_id": logical_id,
        "scene": {
            "title": node.title,
            "position_key": node.position_key,
            "accepted_in": introduced,
            "lineage_depth": depth or None,
            "head_revision_id": head.revision_id,
            "chars": len(node.content or ""),
            "content_sha256": node.content_sha256,
            "lock": node.lock.value,
        },
        "decision": decision_row(decision) if decision else None,
        "attempts": [
            decision_row(item) for item in (store.decisions_for_job(job_id) if job_id else [])
        ],
        "job": None
        if job is None
        else {
            "job_id": job.job_id,
            "job_kind": job.job_kind,
            "status": job.status.value,
            "attempts": job.attempts,
            "priority": job.priority,
            "input_digest": job.input_digest,
        },
        "prompt": prompt,
        "selected_by": payload.get("selected_by"),
        "context": payload.get("context"),
        "context_omitted": payload.get("context_omitted"),
        "plan_item": None
        if plan_item is None
        else {
            "plan_item_id": plan_item.logical_id,
            "text": plan_item.text,
            "locked": plan_item.locked,
            "authority": plan_item.authority.value,
        },
        "findings": [
            finding_row(item)
            for item in store.findings(book_id, branch_id, logical_id=logical_id, open_only=False)
        ],
        "draft_before_revision": None
        if not kept
        else {
            "draft_id": kept[0].draft_id,
            "attempt": kept[0].attempt,
            "drafted_by": kept[0].drafted_by,
            "revised_by": kept[0].revised_by,
            "chars": len(kept[0].content),
            "content_sha256": kept[0].content_sha256,
            "em_dashes_removed": kept[0].em_dashes_removed,
            "recorded_at": kept[0].recorded_at,
            # **The text itself, so the diff needs no second tool.** The report that
            # commissioned this had to open a copy of the store to reach what no verb could
            # answer; `why --json` beside `export` is now the whole pair.
            "content": kept[0].content,
        },
        "absent": absent,
    }


def render_dossier(dossier: dict[str, Any]) -> str:
    """The same dict `--json` prints, as lines. One source, so the two cannot disagree."""
    scene: dict[str, Any] = dossier["scene"]
    lines = [
        f"{dossier['logical_id']}  {scene['title'] or '(untitled)'}  "
        f"[{dossier['book_id']}/{dossier['branch_id']}]"
    ]

    def field(label: str, value: str) -> None:
        lines.append(f"  {label:<13} {value}")

    # **An undrafted scene is a different report, not a report full of gaps.** Saying "no
    # policy decision explains this revision" of a scene that has no revision would send a
    # reader looking for an attribution failure that is not there; the scene simply has not
    # been written. `absent` already draws the line — the renderer has to draw it too.
    undrafted = scene["accepted_in"] is None
    decision: dict[str, Any] | None = dossier["decision"]
    if undrafted:
        field("prose", "ABSENT - no accepted revision carries this scene yet")
        if decision is None:
            field("decision", "n/a - nothing has been accepted here, so nothing decided it")
    else:
        field(
            "accepted in",
            f"{scene['accepted_in']}  (step {scene['lineage_depth']} of the lineage)",
        )
        field("prose", f"{scene['chars']} char(s), sha256 {scene['content_sha256']}")

    if decision is None and not undrafted:
        field(
            "decision",
            "ABSENT - no policy decision explains this revision (§19; `verify` counts these)",
        )
    elif decision is not None:
        cost = (
            "cost not reported" if decision["cost_usd"] is None else f"${decision['cost_usd']:.4f}"
        )
        # On an undrafted scene this is the latest decision on a unit that never accepted
        # (§234): the refusal an operator reads, and never a claim that prose exists.
        standing_in = "  (latest on an unfinished unit; nothing accepted)" if undrafted else ""
        field(
            "decision",
            f"{decision['decision_id']}  {decision['outcome']}  attempt {decision['attempt']}"
            f"{standing_in}",
        )
        field(
            "",
            f"{decision['provider'] or '?'}/{decision['model'] or '?'}  "
            f"profile {decision['profile'] or '?'}",
        )
        field(
            "",
            f"{decision['invocations']} call(s), {decision['total_tokens']} token(s), {cost}",
        )
        field("", f"config {decision['policy_config_digest'] or '(none)'}")
        if decision["reason"]:
            field("", f"reason: {decision['reason']}")
        if not decision["gates"]:
            field("gates", "(none recorded on this decision)")
        for index, gate in enumerate(decision["gates"]):
            mark = "PASS" if gate["passed"] else "FAIL"
            weight = "blocking" if gate["blocking"] else "advisory"
            field(
                "gates" if index == 0 else "",
                f"{mark}  {gate['gate']:<10}{gate['rule_or_critic_id']:<26}"
                f"{gate['verdict_source']}  {weight}",
            )
            if gate["vetoes"]:
                field("", f"        vetoes: {', '.join(gate['vetoes'])}")
            if gate["detail"]:
                field("", f"        {gate['detail']}")

    attempts: list[dict[str, Any]] = dossier["attempts"]
    if len(attempts) > 1:
        # The ladder across attempts, not just the rung that landed. A scene accepted on the
        # third try was refused twice and those refusals are on record.
        ladder = ", ".join(f"{item['attempt']}:{item['outcome']}" for item in attempts)
        field("attempts", f"{len(attempts)} decision(s) on this job - {ladder}")

    job: dict[str, Any] | None = dossier["job"]
    if job is None:
        field("job", "ABSENT - no queued unit is on record for this scene")
    else:
        field(
            "job",
            f"{job['job_id']}  {job['job_kind']}  {job['status']}  {job['attempts']} attempt(s)",
        )

    selected = dossier["selected_by"]
    if isinstance(selected, dict):
        field(
            "selected by",
            f"beat {selected.get('ordinal')}/{selected.get('of_total')} "
            f"{selected.get('beat_function')}  template {selected.get('template_id')}",
        )
        field(
            "",
            f"plan epoch {selected.get('plan_epoch')}  "
            f"predicate {selected.get('predicate')}  "
            f"story order {selected.get('story_order_key')}",
        )

    context = dossier["context"]
    if isinstance(context, dict):
        field(
            "context",
            f"{context.get('items')} item(s), {context.get('tokens')}/"
            f"{context.get('budget')} token(s)  query {context.get('query_id')}",
        )
        sections = context.get("sections")
        if isinstance(sections, dict) and sections:
            field("", "  ".join(f"{name} {count}" for name, count in sorted(sections.items())))

    omitted = dossier["context_omitted"]
    if isinstance(omitted, list):
        # **Printed even when empty.** This is the honest half of the packet: a baseline that
        # packs by priority rather than relevance drops things a scorer would have kept, and
        # a scene that ignores canon is usually a scene whose canon is on this list.
        field("omitted", f"{len(omitted)} context item(s) the packet could not hold")
        for item in omitted:
            if isinstance(item, dict):
                field("", f"  {item.get('source')}  {item.get('reason')}")

    plan_item = dossier["plan_item"]
    if plan_item is None:
        field("plan item", "ABSENT - the plan holds no statement for this scene")
    else:
        field(
            "plan item",
            f"{plan_item['plan_item_id']}  "
            f"{'locked' if plan_item['locked'] else 'unlocked'}  {plan_item['authority']}",
        )
        field("", plan_item["text"])

    findings: list[dict[str, Any]] = dossier["findings"]
    blocking = sum(1 for item in findings if item["blocks"])
    field("findings", f"{len(findings)} recorded, {blocking} blocking")
    for item in findings:
        field(
            "",
            f"  {item['finding_id']}  {item['severity']:<8}{item['status']:<20}"
            f"{item['rule_or_critic_id'] or item['category']}",
        )
        field("", f"    {item['message']}")

    # **Named and not printed, which is the rule this renderer already keeps for prose.**
    # `scene` above prints a length and a hash and sends the reader to `export` for the text;
    # the draft is prose too and gets the same treatment. `--json` carries both strings, so the
    # diff the attribution report could not compute is two verbs away and neither of them
    # opens the database. The prompt at the bottom is printed whole because a prompt is not
    # prose. Silence here means the accepted prose is the writer's own.
    kept: dict[str, Any] | None = dossier["draft_before_revision"]
    if kept is not None:
        field(
            "draft",
            f"{kept['chars']} char(s), sha256 {kept['content_sha256']} "
            f"({kept['em_dashes_removed']} em dash(es) removed)",
        )
        field(
            "",
            f"written by {kept['drafted_by']}, replaced by {kept['revised_by']} "
            f"on attempt {kept['attempt']}",
        )
        field("", "the text is in `--json`; the prose that replaced it is in `export`")

    if dossier["absent"]:
        field("absent", ", ".join(dossier["absent"]))

    prompt = dossier["prompt"]
    lines.append("")
    if prompt is None:
        lines.append("(no rendered prompt on record for this scene)")
    else:
        # **Last, and whole.** The prompt is the thing this verb exists to show and also the
        # longest thing here, so it follows the summary rather than burying it.
        lines.append(f"--- system ({len(prompt['system'] or '')} char(s)) ---")
        lines.append(prompt["system"] or "(none)")
        lines.append("")
        lines.append(f"--- prompt ({len(prompt['prompt'])} char(s)) ---")
        lines.append(prompt["prompt"])
    return "\n".join(lines)


#: A packet-like heading can also appear inside an exemplar. Without stored boundaries,
#: withholding the entire prompt is the only safe inference from its shelf heading.
PROMPT_WITHHELD = (
    "[prompt withheld: an exemplar shelf was spliced into it without a verified boundary]"
)

_SHELF_HEADINGS = (exemplars_mod.OPENINGS_HEADING, exemplars_mod.BLURBS_HEADING)


def _cut_shelf(prompt: str) -> str | None:
    """Return None for a shelf-bearing prompt; headings cannot verify its boundaries."""
    return None if any(heading in prompt for heading in _SHELF_HEADINGS) else prompt


def redact_shelf(dossier: dict[str, Any]) -> dict[str, Any]:
    """Withhold shelf-bearing prompt text without guessing where its source prose ends.

    **Why a tool result differs from what the operator's `why` prints.** The shelf is
    openings the operator placed by hand, shown to the writer as register (stage-0 §196), never
    committed and never quoted on the page — and `planner.render_prompt` splices it whole
    into the frozen prompt the dossier prints. The operator reading their own shelf back is
    the diagnostic channel; a tool result reaches whatever process asked, so it carries the
    count of characters withheld and the payload's identity record, never the text. The
    system's one shelf sentence goes with it, because it is only true of a prompt that shows
    one. The writer's own draft cannot legally hold an eight-word run of the shelf
    (`exemplar.leak.v0`), so its check here is a belt over that gate's braces.
    """
    redacted = dict(dossier)
    prompt = dossier.get("prompt")
    if isinstance(prompt, dict):
        body = prompt.get("prompt")
        system = prompt.get("system")
        cleaned = _cut_shelf(body) if isinstance(body, str) else body
        withheld = isinstance(body, str) and cleaned is None
        if isinstance(system, str):
            system = system.replace("\n" + exemplars_mod.SHELF_SYSTEM, "").replace(
                exemplars_mod.SHELF_SYSTEM, ""
            )
        redacted["prompt"] = {
            **prompt,
            "system": system,
            "prompt": PROMPT_WITHHELD if withheld else cleaned,
        }
        if withheld and isinstance(body, str):
            redacted["prompt"].update(
                system_chars=len(prompt.get("system") or ""),
                prompt_chars=len(body),
                withheld="exemplar_shelf_boundary_not_recorded",
            )
    kept = dossier.get("draft_before_revision")
    if isinstance(kept, dict) and isinstance(kept.get("content"), str):
        content = kept["content"]
        if any(heading in content for heading in _SHELF_HEADINGS):
            redacted["draft_before_revision"] = {**kept, "content": PROMPT_WITHHELD}
    return redacted


__all__ = [
    "DOSSIER_KEYS",
    "PROMPT_WITHHELD",
    "UNANSWERED",
    "decision_row",
    "finding_row",
    "gate_row",
    "introduced_in",
    "payload_prompt",
    "redact_shelf",
    "render_dossier",
    "scene_dossier",
    "scene_node",
    "scenes_of",
    "unit_for_scene",
]
