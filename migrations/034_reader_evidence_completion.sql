-- Close the remaining evidence gaps without upgrading any model-sourced claim to canon.

CREATE TABLE reader_mechanism_evidence (
    version_id      TEXT PRIMARY KEY REFERENCES reader_mechanism_versions(version_id),
    evidence_json   TEXT NOT NULL,
    recorded_at     TEXT NOT NULL
) STRICT;

-- Exact, optional manuscript anchors for promise opening and payment. Historical rows and
-- answers that do not supply a uniquely locatable quote remain usable but ineligible for
-- code-certified promise interventions.
ALTER TABLE promises ADD COLUMN opened_logical_id TEXT;
ALTER TABLE promises ADD COLUMN opened_start INTEGER CHECK (opened_start IS NULL OR opened_start >= 0);
ALTER TABLE promises ADD COLUMN opened_end INTEGER CHECK (opened_end IS NULL OR opened_end > 0);
ALTER TABLE promises ADD COLUMN opened_content_hash TEXT;
ALTER TABLE promises ADD COLUMN paid_logical_id TEXT;
ALTER TABLE promises ADD COLUMN paid_start INTEGER CHECK (paid_start IS NULL OR paid_start >= 0);
ALTER TABLE promises ADD COLUMN paid_end INTEGER CHECK (paid_end IS NULL OR paid_end > 0);
ALTER TABLE promises ADD COLUMN paid_content_hash TEXT;

CREATE TABLE editorial_intervention_realizations (
    realization_id   TEXT PRIMARY KEY,
    intervention_id  TEXT NOT NULL REFERENCES editorial_interventions(intervention_id),
    directive_id     TEXT NOT NULL REFERENCES directives(directive_id),
    plan_revision_id TEXT NOT NULL REFERENCES plan_revisions(plan_revision_id),
    book_id          TEXT NOT NULL,
    branch_id        TEXT NOT NULL,
    logical_id       TEXT NOT NULL,
    revision_id      TEXT NOT NULL REFERENCES revisions(revision_id),
    content_hash     TEXT NOT NULL,
    recorded_at      TEXT NOT NULL,
    UNIQUE (intervention_id, revision_id, logical_id)
) STRICT;

CREATE INDEX editorial_realizations_target_idx
    ON editorial_intervention_realizations (book_id, branch_id, logical_id);
