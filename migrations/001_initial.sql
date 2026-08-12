-- Stage 0 schema: revisions, node versions, events, outbox, jobs.
--
-- Two structural notes.
--
-- `node_versions.version_id` is a content address, so it is the primary key and an
-- `INSERT OR IGNORE` is the whole of node deduplication. That is what makes the
-- shared-immutable branch fork (domain/revision.py) free in storage: two branches
-- referencing identical text reference one row, and there is no path by which the same
-- text acquires two version ids.
--
-- `events.sequence` is a monotonic autoincrement giving the log a total order, while
-- `idempotency_key` is UNIQUE so redelivery of the same logical event collapses at
-- insert rather than being filtered downstream.

CREATE TABLE revisions (
    revision_id        TEXT PRIMARY KEY,
    book_id            TEXT NOT NULL,
    branch_id          TEXT NOT NULL,
    parent_revision_id TEXT REFERENCES revisions (revision_id),
    created_at         TEXT NOT NULL
) STRICT;

CREATE INDEX revisions_branch_idx ON revisions (book_id, branch_id, created_at);

CREATE TABLE node_versions (
    version_id         TEXT PRIMARY KEY,
    logical_id         TEXT NOT NULL,
    kind               TEXT NOT NULL,
    position_key       TEXT NOT NULL,
    parent_logical_id  TEXT,
    title              TEXT,
    content            TEXT,
    content_sha256     TEXT,
    lock_kind          TEXT NOT NULL,
    tombstoned         INTEGER NOT NULL DEFAULT 0,
    tombstone_reason   TEXT,
    block_kind         TEXT,
    block_payload      TEXT
) STRICT;

CREATE TABLE revision_nodes (
    revision_id TEXT NOT NULL REFERENCES revisions (revision_id),
    logical_id  TEXT NOT NULL,
    version_id  TEXT NOT NULL REFERENCES node_versions (version_id),
    PRIMARY KEY (revision_id, logical_id)
) STRICT;

CREATE TABLE events (
    sequence        INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,
    event_id        TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    actor           TEXT NOT NULL,
    project_id      TEXT NOT NULL,
    book_id         TEXT,
    branch_id       TEXT,
    revision_id     TEXT,
    causation_id    TEXT,
    correlation_id  TEXT,
    payload         TEXT NOT NULL,
    payload_digest  TEXT NOT NULL
);

CREATE TABLE outbox (
    idempotency_key   TEXT PRIMARY KEY REFERENCES events (idempotency_key),
    state             TEXT NOT NULL,
    delivery_attempts INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE INDEX outbox_pending_idx ON outbox (state);

CREATE TABLE jobs (
    job_id           TEXT PRIMARY KEY,
    job_kind         TEXT NOT NULL,
    status           TEXT NOT NULL,
    attempts         INTEGER NOT NULL DEFAULT 0,
    max_attempts     INTEGER NOT NULL DEFAULT 3,
    idempotency_key  TEXT UNIQUE,
    input_digest     TEXT,
    error            TEXT,
    lease_holder     TEXT,
    lease_expires_at REAL
) STRICT;

CREATE INDEX jobs_claimable_idx ON jobs (status, lease_expires_at);
