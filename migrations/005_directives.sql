-- Slice 5: the direction inbox (§4.3).
--
-- A durable queue the director drops premises, constraints, arc notes, tone guidance and
-- vetoes into at any time, which the Conductor drains at the top of each tick. §4.1 puts
-- ingest first in the tick for a reason: a directive that arrives mid-tick must land as
-- input to the *next* selection, never as a mid-flight mutation of a running job.
--
-- Only capture is built. Interpretation needs the Narrative Planner (§9), which does not
-- exist, so directives stop at `received` and are visible as a growing count there. That
-- is the honest failure mode — work queued and unread rather than work silently dropped —
-- and it is why `ingested_at` is separate from `received_at`: the gap between them is the
-- inbox's latency, and the gap between `ingested_at` and `interpreted_at` is the planner's
-- absence, measured rather than assumed.
--
-- `directive_id` is content-derived from (kind, body, received_at) so a double submission
-- of one instruction collapses. `received_at` is deliberately in that material: a director
-- who repeats "more dungeon crawling" next week means it again.

CREATE TABLE directives (
    directive_id            TEXT PRIMARY KEY,
    kind                    TEXT NOT NULL,
    body                    TEXT NOT NULL,
    status                  TEXT NOT NULL,
    book_id                 TEXT,
    branch_id               TEXT,
    target_logical_ids      TEXT,
    interpretation          TEXT,
    produced_constraint_ids TEXT,
    received_at             TEXT,
    ingested_at             TEXT,
    interpreted_at          TEXT,
    precedence              INTEGER NOT NULL DEFAULT 0,
    superseded_by           TEXT,
    metadata                TEXT
) STRICT;

-- The drain query: un-ingested directives, highest precedence first, then arrival order.
-- A veto issued Monday must outrank a tone note issued Tuesday, so precedence leads.
CREATE INDEX directives_pending_idx ON directives (ingested_at, precedence DESC);

-- "What is queued and unread" — the count that makes the planner's absence visible.
CREATE INDEX directives_status_idx ON directives (status, precedence DESC);
