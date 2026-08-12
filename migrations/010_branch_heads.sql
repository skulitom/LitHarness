-- A stored head pointer, for the half of §19 Integrity that was unstarted.
--
-- "Every mutation is attributable to a recorded policy decision **and reversible**." The
-- first half was enforced; the second was not expressible, because `head()` inferred the
-- head from `ORDER BY created_at DESC` and there was nowhere for "make revision R the head
-- again" to be recorded. Reverting to an earlier revision would have produced a revision
-- with an older timestamp than the one it replaced — and therefore not the head.
--
-- Timestamp inference had a second problem worth naming: it made branch state depend on a
-- clock. Two commits inside the same second were resolved by lexical revision id, which is
-- a content hash, so the winner was effectively arbitrary.
--
-- Backfilled from the existing rule so an upgraded database keeps the head it had. The
-- backfill is the last statement rather than the first because it must see the table.

CREATE TABLE branch_heads (
    book_id     TEXT NOT NULL,
    branch_id   TEXT NOT NULL,
    revision_id TEXT NOT NULL REFERENCES revisions (revision_id),
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (book_id, branch_id)
) STRICT;

INSERT INTO branch_heads (book_id, branch_id, revision_id, updated_at)
SELECT book_id, branch_id, revision_id, created_at
FROM revisions r
WHERE r.created_at = (
    SELECT MAX(created_at) FROM revisions x
    WHERE x.book_id = r.book_id AND x.branch_id = r.branch_id
)
GROUP BY book_id, branch_id;
