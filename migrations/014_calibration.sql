-- The calibration spine: §10.3–§10.5, and the only path by which a craft metric can ever
-- become a gate.
--
-- **What this is not.** It is not a craft gate. §10.6 records a design pass over nine
-- candidate craft proxies that promoted exactly one, and the rejections were not failures of
-- implementation — two would have flagged the fixture's *best* prose, one ranks the book
-- upside down, and the two §10.2 names by name need a corpus the program does not have (77
-- words of dialogue in total). §1a.4 states the rule those refutations follow from: **any
-- craft proxy is a hypothesis about human judgment until validated against it.**
--
-- **What is actually scarce, measured rather than assumed.** RevisionJudge holds 104 exported
-- pairs and *two* collected verdicts, at roughly 57 seconds of human attention each. The
-- binding constraint on craft work is not detector cleverness; it is that judgment is
-- expensive, uncollected, and — until this migration — had nowhere to be stored if it were
-- collected. §20.7 names the same gap from the other end: nothing anywhere reads
-- `verdicts.jsonl`.
--
-- So these three tables exist to make judgment cheap to collect, impossible to lose, and
-- mechanically connected to promotion. The day a §10.6 corpus exists, promoting a metric is
-- an INSERT here rather than an engineering project.

-- §10.2: "cheap, deterministic proxies logged per scene and chapter ... advisory until
-- validated". Stored per accepted revision so a metric's distribution can be read back over a
-- whole book later, which is what a calibration is measured against.
--
-- **Recorded even though nothing consumes them yet, and that is the point.** A metric whose
-- history begins on the day it is promoted has no held-out data to be promoted *on*.
CREATE TABLE craft_metrics (
    revision_id TEXT NOT NULL,
    logical_id  TEXT NOT NULL,
    metric_id   TEXT NOT NULL,
    value       REAL NOT NULL,
    detail      TEXT,
    measured_at TEXT NOT NULL,
    PRIMARY KEY (revision_id, logical_id, metric_id)
) STRICT;

CREATE INDEX craft_metrics_metric_idx ON craft_metrics (metric_id, value);

-- §10.5's standing audit: "the policy engine routes a sample (e.g. 5% of accepted chapters)
-- to the digest for human spot-reading; audit disagreement re-opens calibration."
--
-- **Sampling is derived from content, never random.** A random sampler would make a replayed
-- tick select a different scene, which breaks the convergence property every other derived id
-- in this store has — and, worse, would let a re-run quietly reshape which prose a human ever
-- sees. Deriving it from `(revision_id, logical_id)` means the sample is a fact about the
-- book rather than about when the tick happened, and it cannot be re-rolled by anyone hoping
-- for a kinder sample.
--
-- `verdict` is NULL until a human answers. That is the whole asset: the count of NULLs is the
-- honest measure of how much judgment the project actually has, in the same way the unread
-- directive count measures direction the planner cannot yet read.
CREATE TABLE audit_samples (
    sample_id   TEXT PRIMARY KEY,
    book_id     TEXT NOT NULL,
    branch_id   TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    logical_id  TEXT NOT NULL,
    sampled_at  TEXT NOT NULL,
    -- Why this one was drawn: the rate in force and the bucket it fell in, so a sample can be
    -- re-derived and defended rather than merely trusted.
    rate        REAL NOT NULL,
    bucket      INTEGER NOT NULL,
    verdict     TEXT,
    -- Free-text from the reader. The single most valuable column in this file and the one
    -- least amenable to schema: §1a.3 items 1-4 are what a human notices and no proxy reaches.
    note        TEXT,
    judged_at   TEXT,
    judged_by   TEXT
) STRICT;

CREATE INDEX audit_samples_pending_idx ON audit_samples (verdict, sampled_at);

-- §10.4: "a critic (or metric) becomes a blocking gate only after held-out calibration shows
-- usable precision at an acceptable workload, with order-consistency and abstention
-- measured." This is where that evidence lives, and `GateResult.calibration_id` — a contract
-- field that has had no producer since 1.1.0 — is a foreign key to it.
--
-- **§19's Trust clause says blocking critics carry *current* calibration evidence**, so a
-- calibration carries `measured_at` and `expires_at` and staleness is a query rather than a
-- memory. A gate citing an expired calibration is not a gate with old evidence; it is a gate
-- with none, and `domain/calibration.py` treats it that way.
--
-- `verdicts_digest` pins *which* judgments produced the number. Without it a calibration is a
-- claim about a sample nobody can reconstruct, which is exactly the standard §8.3 refuses to
-- accept from a detector and there is no reason to accept it from a critic.
CREATE TABLE calibrations (
    calibration_id  TEXT PRIMARY KEY,
    metric_id       TEXT NOT NULL,
    -- Held-out, never in-sample. Named in the column so a future writer has to lie
    -- deliberately rather than by omission.
    holdout_size    INTEGER NOT NULL,
    precision       REAL NOT NULL,
    recall          REAL,
    threshold       REAL NOT NULL,
    -- Which side of the threshold is the *failing* side; a metric is not inherently
    -- directional and guessing wrong inverts the gate silently.
    direction       TEXT NOT NULL,
    verdicts_digest TEXT NOT NULL,
    measured_at     TEXT NOT NULL,
    expires_at      TEXT,
    note            TEXT
) STRICT;

CREATE INDEX calibrations_metric_idx ON calibrations (metric_id, measured_at);
