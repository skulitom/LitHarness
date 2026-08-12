-- Conductor state: the instance lease and the daily digest.
--
-- `instance_leases` is how §4.1's "single-instance execution" is enforced. The scope is
-- the primary key, so a cron invocation that overlaps a still-running one loses the
-- claim rather than running a second copy of the loop. It is deliberately a separate
-- table from `jobs`: the job lease answers "who is working this unit", the instance lease
-- answers "who is the Conductor right now", and conflating them would let two instances
-- each pick a different job and both believe they were alone.
--
-- `digest_entries` is keyed by (day, metric) and accumulates by addition, so a tick that
-- runs twice for the same clock instant cannot double-count -- see the idempotency note
-- in application/conductor.py.

CREATE TABLE instance_leases (
    scope       TEXT PRIMARY KEY,
    holder      TEXT NOT NULL,
    expires_at  REAL NOT NULL,
    acquired_at REAL NOT NULL
) STRICT;

CREATE TABLE digest_entries (
    day    TEXT NOT NULL,
    metric TEXT NOT NULL,
    value  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, metric)
) STRICT;

CREATE TABLE tick_records (
    tick_id     TEXT PRIMARY KEY,
    holder      TEXT NOT NULL,
    started_at  REAL NOT NULL,
    outcome     TEXT NOT NULL,
    job_id      TEXT,
    reconciled  INTEGER NOT NULL DEFAULT 0,
    dispatched  INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE INDEX tick_records_time_idx ON tick_records (started_at);
