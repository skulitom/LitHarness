-- The bounded variation session: a durable multi-attempt loop in front of the existing
-- commit path, and the four tables that make its state inspectable rather than conversational.
--
-- **What this is, and the one dis-analogy that shapes every column.** NVIDIA's AVO work
-- reports that an evolutionary search improves sharply when the variation step is an agent
-- that inspects prior candidates, proposes an edit, evaluates it, reads the failure, and
-- revises — repeatedly — before anything is committed. This repository already has the other
-- half: immutable revisions, pure pre-commit gates, recorded policy decisions, a linear head.
-- What was missing is exactly the durable multi-attempt session. What is *not* imported with
-- it is the scoring function. AVO's objective is ground truth (a kernel is correct, a measured
-- throughput is a number); this project has no instrument entitled to order prose by quality,
-- and research/quality-measurement/BRIEF.md is twenty refutations of the belief that it does.
-- So this session optimises nothing. It repairs to **mechanical feasibility** and commits the
-- first candidate that passes, and there is deliberately nowhere in this schema to put a
-- score, a rank, or a preference.
--
-- **The session's state is rows, never hidden conversation history.** Every attempt is
-- recorded including the ones that failed — AVO reports a committed lineage of 40 and discards
-- the record of the 500+ directions it explored, and the difference between those two numbers
-- is the only part of the run that could ever answer why. When the loop needs the model to see
-- its own history it re-renders it from these rows, so a restart resumes with exactly what a
-- crash-free run would have had.

-- One session: what it is repairing, what it may spend, what it has spent, and how it ended.
--
-- **Every limit is its own column and every counter beside it, because a refusal has to be
-- able to say which ceiling stopped it.** A single fused "budget" would report "the session
-- ran out" for six different situations that call for six different responses — raise the step
-- allowance, raise the token allowance, or accept that the repair is not mechanically
-- reachable and let the finding stand. The domain's limit check evaluates them in a fixed
-- order and returns the name of the one that tripped.
--
-- **`steps` and `provider_calls` are not the same counter, and the difference is the point.**
-- A step is an executed mediated action; a provider call is a round trip. A malformed response
-- costs a call and executes no action, so a session that keeps failing to produce a usable
-- action exhausts `max_provider_calls` while `steps` stands still — which is a different
-- failure from a session whose candidates are well-formed and keep failing gates, and it is
-- the second one `max_steps` is for. `max_provider_calls` is therefore set above `max_steps`
-- by default: calls are always at least steps, so the reverse ordering would leave `max_steps`
-- unreachable, and a ceiling that cannot bind is a declared bar that cannot do what it says.
--
-- **`max_cost_usd` is nullable and the others are not**, for the budget module's measured
-- reason: the pinned provider on a subscription reports no dollars at all and the deterministic
-- fake reports zero, so a dollars ceiling silently fails open on exactly the providers this
-- system runs on. Steps, calls, evaluations, tokens and wall time always apply.
--
-- **These counters are stored, and that is a deliberate exception to a recorded refusal.**
-- `spend_on` derives the day's spend by summing policy_decisions rather than keeping a running
-- counter, on the stated grounds that "a counter and the decisions it summarises can disagree
-- after a crash and there would be no way to tell which was right". The objection is exact and
-- it is about *separate writes*: that counter would be bumped in a different transaction from
-- the decision it counted. These are not. Every counter here advances in the same transaction
-- as the attempt row, the settling decision and the follow-up job, so no crash can land one
-- without the others — and the same reason means they cannot be derived instead, because three
-- of them count things that mint no attempt row at all: a lineage inspection, a knowledge
-- consultation, and a response that named no executable action.


--
-- `opened_at_epoch` is the injected clock reading, not a parsed timestamp: wall-clock
-- enforcement has to work off the same clock every test injects, or the one limit that cannot
-- be exercised without waiting is the one nothing checks.
CREATE TABLE variation_sessions (
    session_id           TEXT PRIMARY KEY,
    objective            TEXT NOT NULL CHECK (objective IN ('candidate_repair')),
    book_id              TEXT NOT NULL,
    branch_id            TEXT NOT NULL,
    logical_id           TEXT NOT NULL,
    finding_id           TEXT,
    base_revision_id     TEXT NOT NULL,
    opened_by_job_id     TEXT NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('open', 'closed')),

    max_steps            INTEGER NOT NULL CHECK (max_steps > 0),
    max_provider_calls   INTEGER NOT NULL CHECK (max_provider_calls > 0),
    max_evaluations      INTEGER NOT NULL CHECK (max_evaluations > 0),
    max_tokens           INTEGER NOT NULL CHECK (max_tokens > 0),
    max_wall_seconds     REAL    NOT NULL CHECK (max_wall_seconds > 0.0),
    max_cost_usd         REAL,

    steps                INTEGER NOT NULL DEFAULT 0,
    provider_calls       INTEGER NOT NULL DEFAULT 0,
    evaluations          INTEGER NOT NULL DEFAULT 0,
    tokens               INTEGER NOT NULL DEFAULT 0,
    cost_usd             REAL    NOT NULL DEFAULT 0.0,
    malformed            INTEGER NOT NULL DEFAULT 0,

    -- What the session has pulled into its own view. Both are re-render switches rather than
    -- stored text: `lineage_inspections` says the model asked for the attempt history and the
    -- prompt renders it from variation_attempts; `consulted_item_ids` is the evidence link back
    -- to knowledge_items, which is how "consulting one is recorded" stays true without a join
    -- table for a list that is never long.
    lineage_inspections  INTEGER NOT NULL DEFAULT 0,
    consulted_item_ids   TEXT NOT NULL DEFAULT '[]',

    outcome              TEXT CHECK (outcome IS NULL OR outcome IN (
                             'committed', 'refused_limit', 'refused_budget',
                             'stalled_repeat_patch', 'stalled_repeated_gate',
                             'stalled_malformed', 'stopped', 'stale_base')),
    outcome_detail       TEXT,
    opened_at            TEXT NOT NULL,
    opened_at_epoch      REAL NOT NULL,
    closed_at            TEXT
) STRICT;

CREATE INDEX variation_sessions_target_idx
    ON variation_sessions (book_id, branch_id, logical_id, status);
CREATE INDEX variation_sessions_finding_idx ON variation_sessions (finding_id);
CREATE INDEX variation_sessions_job_idx ON variation_sessions (opened_by_job_id);

-- The proposed patch itself, content-addressed and stored once.
--
-- **An attempt references a patch, it does not carry one**, so a session that proposes the same
-- edit twice occupies one artifact row and the attempt table stays narrow enough to read. The
-- digest is also what the identical-patch stall detector keys on, which it gets for free from
-- the addressing rather than from a second derivation that could drift.
--
-- The payload is the bounded patch as JSON. It is kept rather than reconstructed because a
-- patch is what was actually proposed: rebuilding it from the attempt row would produce
-- whatever the current code would build today, which is the one thing an audit of a past
-- session must not be told.
CREATE TABLE variation_patches (
    patch_digest  TEXT PRIMARY KEY,
    patch_json    TEXT NOT NULL,
    created_at    TEXT NOT NULL
) STRICT;

-- One attempt: a proposed edit, the exact vector the gates returned for it, and how it ended.
--
-- **The gate vector is stored whole, not summarised.** `evaluation` is the full list of gate
-- results as JSON — every gate that ran, passing ones included, with its rule id, its vetoes
-- and its detail — because "which gates ran" is the question an audit asks first, and a row
-- listing only failures cannot distinguish a candidate that cleared the ladder from one that
-- was never checked. The agent is handed this same object as its diagnostic feedback, so the
-- record and the input cannot disagree.
--
-- **`strategy` is recorded and never enforced.** The model classifies its own edit — structural
-- against local_patch — so that the hypothesis "structural early, micro late" can later be
-- *measured* against outcomes rather than assumed into the loop. Nothing reads it to decide
-- anything, and a free string is the honest shape for a label whose taxonomy has not been
-- established.
--
-- The outcome list carries two non-terminal members the design's own list does not, because a
-- session that spends one Conductor tick per action necessarily has a proposal that exists
-- before it has been evaluated: 'proposed' is minted by the propose action and 'evaluated' by
-- the evaluate action, and every other member is terminal. Without them the two actions could
-- not be two actions, and an attempt abandoned between them would leave no row at all — which
-- would make "every attempt is recorded, including failures" false for exactly the attempts
-- that failed earliest.
CREATE TABLE variation_attempts (
    attempt_id         TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    ordinal            INTEGER NOT NULL,
    parent_attempt_id  TEXT,
    base_revision_id   TEXT NOT NULL,
    patch_digest       TEXT NOT NULL,
    strategy           TEXT NOT NULL DEFAULT '',
    evaluation         TEXT NOT NULL DEFAULT '[]',
    diagnostics        TEXT NOT NULL DEFAULT '',
    provider           TEXT,
    model              TEXT,
    tokens             INTEGER NOT NULL DEFAULT 0,
    cost_usd           REAL,
    evaluations        INTEGER NOT NULL DEFAULT 0,
    wall_ms            INTEGER NOT NULL DEFAULT 0,
    outcome            TEXT NOT NULL CHECK (outcome IN (
                           'proposed', 'evaluated', 'committed', 'rejected_gate',
                           'rejected_budget', 'abandoned', 'superseded')),
    abandon_reason     TEXT,
    created_at         TEXT NOT NULL,
    UNIQUE (session_id, ordinal)
) STRICT;

CREATE INDEX variation_attempts_session_idx ON variation_attempts (session_id, ordinal);
CREATE INDEX variation_attempts_patch_idx ON variation_attempts (patch_digest);

-- What repeated failure taught, with the attempts that taught it.
--
-- **Derived deterministically from attempt rows, never written by the model.** An item is
-- minted the moment two attempts fail the same gate for the same veto against the same target,
-- and it says only that — patches touching this node keep failing this gate for this reason.
-- No claim about prose, no ranking, nothing a later session could mistake for a judgment. It is
-- the one thing this design carries over from AVO's knowledge base and the only form of it that
-- survives the missing scoring function.
--
-- `item_id` addresses the *claim* — target, gate, veto — while `evidence` accumulates the
-- attempt ids that support it and `observations` counts them. So a second session meeting the
-- same wall extends the record instead of minting a near-duplicate row nobody would join, and
-- the evidence link stays checkable: every id in `evidence` is an attempt row whose stored gate
-- vector can be read back and disagreed with.
--
-- `consultations` is why the column exists at all: an item that is read is an item that reached
-- a prompt, and a knowledge base whose influence is unrecorded is a hidden input to every
-- session after the first.
CREATE TABLE knowledge_items (
    item_id        TEXT PRIMARY KEY,
    objective      TEXT NOT NULL CHECK (objective IN ('candidate_repair')),
    target_key     TEXT NOT NULL,
    gate_rule_id   TEXT NOT NULL,
    veto           TEXT NOT NULL,
    statement      TEXT NOT NULL,
    evidence       TEXT NOT NULL DEFAULT '[]',
    observations   INTEGER NOT NULL DEFAULT 0,
    consultations  INTEGER NOT NULL DEFAULT 0,
    first_seen_at  TEXT NOT NULL,
    last_seen_at   TEXT NOT NULL
) STRICT;

CREATE INDEX knowledge_items_target_idx ON knowledge_items (objective, target_key);
