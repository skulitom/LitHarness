-- The plan store: the statements `cli import` currently reads and throws away.
--
-- **What is deliberately NOT here, and why.** There is no `beats` table, no `scene_plan`
-- row per node, and no `status`/`done`/`ordinal`/`depends_on` column. Beats are derived
-- from the head revision — order from `position_key` (already a total order,
-- `Revision.in_reading_order`), completeness from `node.content is None`. A second copy of
-- "is this beat done" would drift from the manuscript, and the drift is not benign:
-- `TARGET_HAS_NO_CONTENT` and `CONTENT_LOCKED` are in neither RETRYABLE nor REGENERABLE,
-- so a selector that offered a beat the gate refuses escalates on attempt one and files an
-- exception. Deriving makes the selector's precondition literally the gate's — see
-- `domain/draft.py::draft_block`.
--
-- What DOES need storing is the half `import` discards: the premise, promises and locked
-- constraints in the fixtures' plans.json. The premise is the one thing a prompt cannot be
-- rendered without, and the constraints are the raw material for context assembly in the
-- next slice. `PlanItem`'s `authority`, `locked` and `links` have no reader in Stage 1, so
-- they ride inside `item_json` rather than becoming columns — promotable when a query
-- needs them, per §20.3's rule that shapes get proven by a consumer first.
--
-- `item_json` holds the contract PlanItem verbatim so the artifact round-trips faithfully
-- even though selection reads only two fields of it.

CREATE TABLE plan_items (
    book_id            TEXT NOT NULL,
    branch_id          TEXT NOT NULL,
    logical_id         TEXT NOT NULL,
    kind               TEXT NOT NULL,
    text               TEXT NOT NULL,
    scope_logical_id   TEXT,
    item_json          TEXT NOT NULL,
    source_revision_id TEXT,
    created_at         TEXT NOT NULL,
    PRIMARY KEY (book_id, branch_id, logical_id)
) STRICT;

-- "Find the premise for this book" runs on every planning tick.
CREATE INDEX plan_items_kind_idx ON plan_items (book_id, branch_id, kind);

-- The epoch is what lets a *burned* derived job id be reissued.
--
-- Job ids are derived so a replayed tick converges instead of re-enqueueing, and
-- `idempotency_key` is UNIQUE — which means a poisoned beat's id is spent forever. Without
-- a version in the derivation, "try scene 3 again after I unlocked it" would be
-- unexpressible and the operator's only recourse would be a new database. Bumping the
-- epoch changes every derived id for the book, so `replan` reissues exactly the beats that
-- are still draftable and silently skips the ones already drafted.
CREATE TABLE plan_epochs (
    book_id   TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    epoch     INTEGER NOT NULL DEFAULT 0,
    bumped_at TEXT NOT NULL,
    reason    TEXT,
    PRIMARY KEY (book_id, branch_id)
) STRICT;
