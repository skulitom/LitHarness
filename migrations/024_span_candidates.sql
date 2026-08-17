-- §61 Add 3: the tournament's candidate drafts, persisted for judgment and nothing else.
--
-- A candidate is a draft that was generated and gated and deliberately NOT committed. The
-- §21 invariant (one draft in flight per book) survives K-way drafting only because losers
-- never reach commit_revision — `gate_draft` is pure and returns an un-persisted Revision —
-- so the store's revision history never sees a candidate. This table is where the K texts
-- wait while readers (or a licensed judge) decide between them, and it is a table of its own
-- for the reason migration 017's status CHECK forced: plan_proposals admits only
-- 'applied'/'conflicted', so a rejected tournament alternative cannot be recorded there
-- without widening a constraint that exists to keep the proposal ledger honest.
--
-- `candidate_id` is content-addressed from the candidate text plus its plan-alternative
-- provenance (statement, alternative index, base revision, tournament job), so a replayed
-- tournament converges onto the same rows and "why did this candidate win the tie-break" is
-- arithmetic anyone can repeat — the tie-break is by candidate_id, and a content-derived id
-- is what keeps that deterministic rather than insertion-ordered.
--
-- `base_revision_id` is the frozen manuscript head every candidate of one tournament was
-- drafted against; re-gating `text` against it MUST reproduce the same revision id, which is
-- how the winner's un-committed Revision is rebuilt at selection time without ever storing
-- one. `plan_epoch` is §22's versioning carried onto the evidence: a tournament whose epoch
-- has moved is stale and its rows are discarded, never re-judged.
--
-- Exactly three statuses, per the design: 'candidate' (awaiting selection), 'selected' (the
-- one winner, committed through the normal accept path), 'discarded' (a loser or a stale
-- tournament's remnant — kept as a record, because deleting refused work is how a selection
-- stops being auditable). A candidate refused by the pure gates before persistence is
-- recorded on the tournament's policy decision, not here: it never entered the tournament.
CREATE TABLE span_candidates (
    candidate_id      TEXT PRIMARY KEY,
    job_id            TEXT NOT NULL,
    book_id           TEXT NOT NULL,
    branch_id         TEXT NOT NULL,
    logical_id        TEXT NOT NULL,
    alternative_index INTEGER NOT NULL,
    statement         TEXT NOT NULL,
    text              TEXT NOT NULL,
    base_revision_id  TEXT NOT NULL,
    plan_epoch        INTEGER NOT NULL,
    created_at        TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('candidate', 'selected', 'discarded'))
) STRICT;

CREATE INDEX span_candidates_span_idx ON span_candidates (book_id, branch_id, logical_id, status);
CREATE INDEX span_candidates_job_idx ON span_candidates (job_id);
CREATE INDEX span_candidates_pending_idx ON span_candidates (status);
