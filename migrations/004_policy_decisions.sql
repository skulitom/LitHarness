-- Slice 5: acceptance decisions become an artifact instead of an event-payload dict.
--
-- §4.2 says every candidate meets a policy ladder rather than an author, and §19 makes
-- "every mutation is attributable to a recorded policy decision" part of the definition
-- of operator-grade. Slice 4 approximated that by stuffing gate results into an event
-- payload — honest as a placeholder, useless as an audit surface, because answering "why
-- was this accepted" meant parsing a free-form map. Contracts 1.1.0 added
-- PolicyDecisionRecord; this is where it lands.
--
-- `decision_id` is content-derived from (job_id, attempt, gates), so a replayed job
-- produces the same id and INSERT OR IGNORE collapses it. A random id would accumulate
-- duplicate rows for one judgment every time a tick was retried after a crash.
--
-- `gates` is JSON rather than a child table. The ladder is read whole, always, and never
-- queried across decisions by individual gate — a join table would buy nothing and add a
-- second place for the ordering to be lost. Revisit if a query ever needs "every decision
-- where the integrity gate failed"; until then, the shape follows the access pattern.

CREATE TABLE policy_decisions (
    decision_id           TEXT PRIMARY KEY,
    outcome               TEXT NOT NULL,
    job_id                TEXT,
    logical_id            TEXT,
    base_revision_id      TEXT,
    resulting_revision_id TEXT,
    attempt               INTEGER NOT NULL DEFAULT 0,
    provider              TEXT,
    model                 TEXT,
    profile               TEXT,
    fell_back_from        TEXT,
    invocations           INTEGER NOT NULL DEFAULT 0,
    total_tokens          INTEGER NOT NULL DEFAULT 0,
    policy_config_digest  TEXT,
    reason                TEXT,
    gates                 TEXT NOT NULL,
    decided_at            TEXT NOT NULL
) STRICT;

-- "What happened to this unit of work" is the question the exception queue and the digest
-- both ask, and both ask it by job.
CREATE INDEX policy_decisions_job_idx ON policy_decisions (job_id, attempt);

-- "Which revisions carry a recorded acceptance" — the §19 integrity claim, checkable.
CREATE INDEX policy_decisions_revision_idx ON policy_decisions (resulting_revision_id);
