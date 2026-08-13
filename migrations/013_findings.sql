-- The findings store: §12 step 6's input, and the half of §20.4 that was still missing.
--
-- **Two things were blocked on this table and it is worth naming both.** §20.4 records that
-- "a real work-selection policy is blocked on the plan graph and findings store"; the plan
-- graph landed with slice 7, and `jobs.priority` has been deliberately inert ever since
-- because "a severity policy waits on a findings store, or it is a selector over a column
-- with one value". This is that store. And §12 step 6's integrity gate needs somewhere for a
-- finding to live between the evaluator that produced it and the policy that acts on it.
--
-- **Findings arrive as contract artifacts, not as a package dependency.** §8.4 assigns the
-- LitRPG rule and predicate vocabulary to ContinuityEvaluation's game-mechanics pack, and
-- §13's consumption rule is that siblings depend on contracts and never on each other. So an
-- evaluator writes an `EvaluationArtifact` and LitHarness ingests it — the seam is a file of
-- a shared schema, which is the only coupling either project can afford. Rebuilding CE's six
-- detectors here would produce exactly the "two divergent predicate vocabularies over one
-- fixture and a permanent reconciliation tax" §8.4 exists to prevent.
--
-- **`status` is a column and `finding_id` is the key, because a finding has a lifecycle.**
-- `FindingStatus` runs open → confirmed/fixed/false_positive/accepted_intentional, and the
-- last of those is the one that matters most here: both golden fixtures ship *negative
-- controls* — an intentional motif, a character's deliberate lie — which are findings a
-- correct detector emits and a correct policy must not block on. A store that could not
-- record "this was looked at and it is fine" would make every intentional device a permanent
-- blocker.
--
-- **`severity` and `rule_or_critic_id` are columns; the rest rides in `finding_json`.** Those
-- two are what the gate and the selector query on. `claim`, `reproduction`, the evidence
-- spans and the scope stay in the artifact, promotable when a query needs them — migration
-- 011's rule, applied a third time.
--
-- **No `resolved_at`/`resolved_by` here.** An exception has those (migration 009) because
-- closing one is a human act on a queue §4.3 reserves for the director. A finding's status
-- changes because a detector re-ran or a policy decided, and both of those are already events
-- in the log; a second timestamp would be a denormalised copy of one.

CREATE TABLE findings (
    finding_id        TEXT PRIMARY KEY,
    book_id           TEXT NOT NULL,
    branch_id         TEXT NOT NULL,
    -- The revision the finding was raised against. Findings are not carried forward
    -- automatically: a revision is a new content address, and a defect that survived an edit
    -- is something a re-run establishes rather than something this table assumes.
    revision_id       TEXT,
    category          TEXT NOT NULL,
    subtype           TEXT,
    severity          TEXT NOT NULL,
    status            TEXT NOT NULL,
    rule_or_critic_id TEXT,
    -- Which scene it lands on, lifted out of `primary_span` so the gate for one beat can ask
    -- "is anything open against this node" without deserialising every finding in the book.
    logical_id        TEXT,
    message           TEXT NOT NULL,
    finding_json      TEXT NOT NULL,
    run_id            TEXT,
    created_at        TEXT NOT NULL
) STRICT;

-- The gate's query: what is open against this node, worst first.
CREATE INDEX findings_open_idx ON findings (book_id, branch_id, status, logical_id);

-- The selector's query, and the reason `jobs.priority` can stop being inert.
CREATE INDEX findings_severity_idx ON findings (book_id, branch_id, severity, status);
