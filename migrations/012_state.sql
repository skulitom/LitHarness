-- The objective-story-state layer: §11's spine listed "manuscript truth / director canon /
-- plans / objective story state / perspective state / derived artifacts / proposals", and
-- this is the one layer that had no table. `state.json` ships beside `manuscript.json` and
-- `plans.json` in both golden fixtures — sixteen span-backed records per book — and `import`
-- read two of the three and dropped the other on the floor.
--
-- **Both remaining Stage 1 items sit on this table, which is why it comes first.** §12 step 2
-- wants a context packet carrying "game state + legal actions, POV-visible knowledge, open
-- threads"; §12 steps 5-6 want extracted state candidates replayed through an integrity gate.
-- Neither has anywhere to read from or write to without this, and building either one first
-- would have meant inventing a private store for it.
--
-- **Re-anchor, do not deserialize** — the third time this store makes the same decision, and
-- for the same reason each time. A contracts `StateSnapshot` pins `revision_id` to the
-- upstream UUID5 (mystery `1462725a…`), which by construction is never the sha256 content
-- address LitHarness mints on import, so matching records to their manuscript by that field
-- would never succeed. Rows are keyed on the local book and branch; the upstream id is kept
-- as provenance. See `domain/plans.py` and `domain/revision.py::import_manuscript`.
--
-- **`order_key` is a column; `pov_visibility` is not.** Story-time ordering is a real query —
-- "what was established before the scene being drafted" — and it is the one thing a packet
-- must slice on, so it gets a column and an index. `pov_visibility` is list-valued and the
-- only operation over it is membership; a junction table to index a set membership over
-- sixteen rows would be machinery in front of a filter. It rides inside `record_json` and is
-- filtered in `domain/state.py::visible_to`, promotable the day a query needs an index —
-- the same rule migration 011 applied to `PlanItem`'s `authority` and `links`.
--
-- **`authority` is a column**, because it partitions what may enter a packet at all:
-- `author_locked` and `accepted_canon` are canon, `proposed` is a candidate nothing has
-- accepted, and a packet that fed proposals back to the generator as established fact would
-- launder a guess into canon in one loop iteration.
--
-- **There is deliberately no `state_candidates` table.** §12 step 5's extraction does not
-- exist, so a table for proposals nothing proposes is a shape with no consumer — the exact
-- guess §20.3's sequencing rule forbids, and the reason `CharacterSheet` is still deferred.
-- `StateCandidateBatch` is in contracts and will be waiting when an extractor is.

CREATE TABLE state_records (
    book_id            TEXT NOT NULL,
    branch_id          TEXT NOT NULL,
    record_id          TEXT NOT NULL,
    kind               TEXT NOT NULL,
    subject            TEXT NOT NULL,
    predicate          TEXT NOT NULL,
    -- The contract types `value` as `Any`: a scalar for `life_status`, an object for
    -- `discovered_item`. Stored as JSON text so both round-trip, NULL when absent.
    value_json         TEXT,
    -- `StoryPosition.order_key`, which sorts lexicographically within a branch. NULL is
    -- legitimate and means "no narrative position asserted", which sorts last rather than
    -- first — an unplaced record is not established-before-everything.
    order_key          TEXT,
    authority          TEXT NOT NULL,
    record_json        TEXT NOT NULL,
    source_revision_id TEXT,
    created_at         TEXT NOT NULL,
    PRIMARY KEY (book_id, branch_id, record_id)
) STRICT;

-- The packet's slice: everything established up to a point in story time, in that order.
CREATE INDEX state_records_position_idx ON state_records (book_id, branch_id, order_key);

-- "What is known about this subject" — the query a continuity gate asks per entity, and
-- the one §12 step 6 will reach for first.
CREATE INDEX state_records_subject_idx ON state_records (book_id, branch_id, subject);
