-- Slice 4: give a job its input, and make non-FIFO selection expressible.
--
-- `input_digest` is a hash. It proves two enqueues describe the same work and it
-- deduplicates a replayed tick, but it cannot reconstruct an input — so a handler
-- matching the JobHandler protocol received a job it could not build a prompt from.
-- That, not any missing subsystem, is what stood between the provider registry and a
-- wired handler (PLAN.md §20.4, corrected in the v2.2 pass). `payload` carries the
-- input beside the digest rather than replacing it; the digest keeps its dedupe job.
--
-- `priority` is the smaller half and is deliberately inert today. `claim_next`
-- hardcoded `ORDER BY rowid`, so no ordering other than FIFO was expressible at any
-- level regardless of which subsystems existed — §4.1 wants selection to be a policy
-- over the book's state, and the column is what makes that sayable later. With every
-- row at the default 0 the claim order is byte-identical to the FIFO it replaces, so
-- `fifo_selector` keeps its exact meaning. A severity policy is NOT built here: with
-- no findings store the column would have exactly one value, and a selector over a
-- constant is theatre.

ALTER TABLE jobs ADD COLUMN payload TEXT;

ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0;

-- Claim order is (priority DESC, rowid). `rowid` is deliberately absent from the index
-- key: SQLite refuses to index it by name, and does not need to — every b-tree index
-- carries the rowid as its payload and breaks ties on it in ascending order, which is
-- exactly the tiebreak the ORDER BY asks for. The existing jobs_claimable_idx covers the
-- WHERE clause; this one lets a growing queue satisfy the ORDER BY without sorting.
CREATE INDEX jobs_priority_idx ON jobs (status, priority DESC);
