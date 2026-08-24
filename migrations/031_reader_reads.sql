-- The simulated readership's record: what it did with a chapter, and what it wants next.
--
-- One table for both lanes, with `pool` on the row, because the firewall is that a reader is
-- in exactly one pool for life (application/readers.py) and a query that has to join two
-- tables to check it is a query somebody will forget to write.
--
-- `choice` is behavioural and is the only vocabulary a measurement reader has: carry_on,
-- put_it_down, come_back_later (§97.4). It is NULL for a steering row, which does not choose
-- anything. `hoping_for` and `dreading` are JSON arrays and are NULL for a measurement row,
-- which is not asked. A row therefore carries one lane's answer and never both, and the pool
-- says which without the reader needing to know.
--
-- Keyed on (revision, logical_id, reader_id): one reader reads one version of one scene once.
-- A replayed read converges on the same row rather than accumulating, which is the same rule
-- the decision ledger runs on. Re-reading a *changed* scene is a different revision and a
-- different row, so a chapter's history survives a repair.
--
-- What this table is not: a verdict store. Nothing here is a score, nothing orders two scenes,
-- and no column holds a judgment. `audit_samples` was the human path and is deleted; this is
-- not its replacement, because §95 closed that channel permanently and nothing here asks a
-- person anything.
CREATE TABLE IF NOT EXISTS reader_reads (
    book_id           TEXT NOT NULL,
    branch_id         TEXT NOT NULL,
    revision_id       TEXT NOT NULL,
    logical_id        TEXT NOT NULL,
    reader_id         TEXT NOT NULL,
    pool              TEXT NOT NULL,
    choice            TEXT,
    because           TEXT,
    hoping_for        TEXT,
    dreading          TEXT,
    created_at        TEXT NOT NULL,
    PRIMARY KEY (revision_id, logical_id, reader_id)
);

CREATE INDEX IF NOT EXISTS reader_reads_by_branch
    ON reader_reads (book_id, branch_id, logical_id);
