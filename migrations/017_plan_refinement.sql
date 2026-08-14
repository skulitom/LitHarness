-- Immutable Narrative Planner snapshots and proposal outcomes.
--
-- plan_items remains the imported Stage 0 source. The first read/write bootstraps it into
-- a content-addressed root revision; every accepted planner change is then a full child
-- snapshot. Full snapshots are intentionally cheap here (plans are small) and make both
-- conflict detection and forward rollback unambiguous.

CREATE TABLE plan_revisions (
    plan_revision_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    parent_plan_revision_id TEXT REFERENCES plan_revisions(plan_revision_id),
    items_json TEXT NOT NULL,
    source_snapshot_id TEXT,
    proposal_id TEXT,
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX plan_revisions_lineage_idx
    ON plan_revisions (book_id, branch_id, created_at);

CREATE TABLE plan_heads (
    book_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    plan_revision_id TEXT NOT NULL REFERENCES plan_revisions(plan_revision_id),
    PRIMARY KEY (book_id, branch_id)
) STRICT;

CREATE TABLE plan_proposals (
    proposal_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    base_plan_revision_id TEXT NOT NULL,
    proposal_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('applied', 'conflicted')),
    resulting_plan_revision_id TEXT REFERENCES plan_revisions(plan_revision_id),
    error TEXT,
    created_at TEXT NOT NULL,
    applied_at TEXT
) STRICT;

CREATE INDEX plan_proposals_branch_idx
    ON plan_proposals (book_id, branch_id, created_at);
