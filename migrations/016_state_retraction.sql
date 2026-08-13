-- Retraction: a state record read out of prose that is no longer the head.
--
-- §12 step 5's extraction writes records whose evidence cites one node version. `revert`
-- moves the head backwards past that version, so the prose the record was read from is no
-- longer in the book — but the record is, and it is `ACCEPTED_CANON`.
--
-- The trap that makes this worth a migration rather than a note. Revert past a drafted
-- scene, redraft it with different numbers, and extraction produces a record that
-- contradicts the orphan. `state.contradiction.v0` fires MAJOR and the beat is refused —
-- and **no operator action clears it**, because the detector runs in-process on every
-- attempt and mints its finding `OPEN` each time, while `litharness dismiss` only satisfies
-- the *pre-flight* standing gate. The candidate-level gate re-detects and refuses again.
-- That converts §19.1's free revivable park into a paid unclearable one, through a door
-- §19.1 did not know existed.
--
-- Nullable and forward-only, like everything else here: retraction records that a record
-- left the book and when, rather than deleting the row. The mistake and the correction both
-- stay in the record, which is the same rule `revert` itself follows.
ALTER TABLE state_records ADD COLUMN retracted_by_revision_id TEXT;
ALTER TABLE state_records ADD COLUMN retracted_at TEXT;

CREATE INDEX state_records_live_idx
    ON state_records (book_id, branch_id, retracted_by_revision_id);
