-- The exception queue (§4.3), and the second half of §19's "parked units and exceptions
-- are visible and bounded".
--
-- The ESCALATE branch already emitted EXCEPTION_RAISED. An event is a fact in a log; it is
-- not a queue. Nothing could answer "what is waiting for me" without replaying the event
-- stream and reconstructing which escalations had since been resolved — which is exactly
-- the derived state a table exists to avoid recomputing, and exactly the kind of
-- reconstruction that silently disagrees with reality after a crash.
--
-- Shaped to contracts 1.1's `ExceptionRecord` so the wire form is already agreed. `kind`
-- carries its enum: repeated_gate_failure, constraint_conflict, budget_exhausted,
-- provider_unavailable, publication_decision, integrity_violation.
--
-- `decision_id` is the link back to the gate trail. An exception that says "this unit
-- stopped" without the decision that stopped it makes the human do the join by hand.

CREATE TABLE exceptions (
    exception_id  TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    summary       TEXT NOT NULL,
    status        TEXT NOT NULL,
    job_id        TEXT,
    logical_id    TEXT,
    decision_id   TEXT,
    raised_at     TEXT NOT NULL,
    resolved_at   TEXT,
    resolution    TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0
) STRICT;

-- The queue query: what is open, oldest first. Partial index because the closed ones are
-- history and the open ones are the working set — an operator asks about the second.
CREATE INDEX exceptions_open_idx ON exceptions (status, raised_at);

-- "Why did this unit stop" goes from the job, which is how an operator arrives.
CREATE INDEX exceptions_job_idx ON exceptions (job_id);
