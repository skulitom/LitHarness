-- Durable operator controls (§4.3 "Controls: pause/resume per book, kill switch").
--
-- `Conductor.paused` was a dataclass field, which is correct for a resident daemon and
-- useless for the model §4.1 actually specifies: a cron tick launches a *fresh process*
-- every five minutes, so the field was reconstructed as False on every tick and
-- `TickOutcome.PAUSED` was unreachable in production. A pause that does not survive the
-- process is not a pause; it is a comment.
--
-- Deliberately a general key/value table rather than a `paused` column. The other §4.3
-- controls — budget ceilings, publication policy, the kill switch — are the same shape:
-- an operator sets a value out of band and the next tick honours it. One table with a
-- recorded `set_at`/`set_by` gives all of them an audit trail; a boolean column would give
-- the first one no history and the rest nowhere to live.

CREATE TABLE control (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    set_at  TEXT NOT NULL,
    set_by  TEXT
) STRICT;
