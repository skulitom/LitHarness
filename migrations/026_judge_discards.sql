-- The discard corpus: every judge sentence that located nothing, kept verbatim.
--
-- **Counting these was not enough, and that is the whole reason this table exists.** The E6
-- channel is asked "name the single most salient difference" and its answer is scored by a
-- frozen matcher over three registered axes. A sentence the matchers miss is not noise — it is a
-- field report about a salient difference **the axis registry cannot yet name**, which is the
-- same object the first human read produced (§74's three defects), arriving from a channel that
-- runs at volume instead of once. A corpus not persisted from the first batch is gone.
--
-- Four discard reasons and they are different facts about different things, which is why they
-- are distinct codes rather than one "skipped" flag:
--
--   unmatched     no registered axis was named. The discovery corpus proper.
--   undirected    a registered axis was named and no reader has given it a direction. The
--                 composition rule biting, and a queue of what reader evidence would unlock.
--   unseparated   an axis was named that no counter separates on this pair — the judge claiming
--                 a difference the material does not carry, which is a judge-quality signal.
--   ambiguous     more than one separating axis named, so "the single most salient" was not.
--   control       a placebo or sham response. Retained because a confabulating judge's own
--                 sentence is the evidence that it confabulated.
--
-- `batch_ok` is false for a sentence from a batch whose controls failed or whose orientation
-- read ASYMMETRIC. Those rows are retained and marked rather than dropped: a sentence from a
-- void batch is evidence about the *judge*, not about prose, and the row says which it is.
--
-- **The rail, written here as well as in the domain, because a table outlives a docstring.**
-- This corpus may NOMINATE a candidate axis; it may never VALIDATE one. A matcher drafted from
-- these sentences and then scored against these sentences is a rubric fitted to its own answers
-- — the exact failure the frozen `AXIS_MATCHERS` exists to prevent. A nominated axis takes the
-- full admission path: a deterministic counter, an E6-family validation on fresh pairs this
-- corpus never touched, and a reader-established direction, before it emits anything.
--
-- `discard_id` hashes the batch, the reason, the two addresses and the sentence itself. The
-- sentence is in the hash because a judge asked one question twice may answer differently, and
-- two different answers to one pair are two field reports rather than a duplicate.
CREATE TABLE judge_discards (
    discard_id     TEXT PRIMARY KEY,
    batch_id       TEXT NOT NULL,
    book_id        TEXT NOT NULL,
    branch_id      TEXT NOT NULL,
    logical_id     TEXT NOT NULL,
    reason         TEXT NOT NULL CHECK (reason IN ('unmatched', 'undirected', 'unseparated',
                                                   'ambiguous', 'control')),
    sentence       TEXT NOT NULL,
    orientation    INTEGER NOT NULL CHECK (orientation IN (0, 1)),
    left_address   TEXT NOT NULL,
    right_address  TEXT NOT NULL,
    separating     TEXT NOT NULL DEFAULT '',
    judge_id       TEXT NOT NULL,
    batch_ok       INTEGER NOT NULL CHECK (batch_ok IN (0, 1)),
    created_at     TEXT NOT NULL
) STRICT;

CREATE INDEX judge_discards_reason_idx ON judge_discards (reason, created_at);
CREATE INDEX judge_discards_batch_idx ON judge_discards (batch_id);
CREATE INDEX judge_discards_book_idx ON judge_discards (book_id, branch_id);
