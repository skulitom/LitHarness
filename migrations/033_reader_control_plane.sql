-- Reader output is evidence. It becomes live direction only through a qualified,
-- versioned mechanism and an immutable editorial intervention.

CREATE TABLE reader_mechanism_versions (
    version_id       TEXT PRIMARY KEY,
    mechanism_id     TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('experimental', 'qualified', 'withdrawn')),
    spec_digest      TEXT NOT NULL,
    evidence_digest  TEXT,
    registered_at    TEXT NOT NULL,
    CHECK (status != 'qualified' OR evidence_digest IS NOT NULL)
) STRICT;

CREATE INDEX reader_mechanism_current_idx
    ON reader_mechanism_versions (mechanism_id, registered_at DESC);

CREATE TABLE reader_observations (
    observation_id       TEXT PRIMARY KEY,
    source_job_id        TEXT NOT NULL UNIQUE,
    checkpoint_id        TEXT NOT NULL,
    mechanism_version_id TEXT NOT NULL REFERENCES reader_mechanism_versions(version_id),
    book_id              TEXT NOT NULL,
    branch_id            TEXT NOT NULL,
    revision_id          TEXT NOT NULL,
    logical_id           TEXT NOT NULL,
    reader_id            TEXT NOT NULL,
    pool                 TEXT NOT NULL,
    panel_size           INTEGER NOT NULL CHECK (panel_size > 0),
    source_content_hash  TEXT NOT NULL,
    persona_digest       TEXT NOT NULL,
    prompt_digest        TEXT NOT NULL,
    system_digest        TEXT NOT NULL,
    schema_digest        TEXT NOT NULL,
    context_digest       TEXT NOT NULL,
    profile              TEXT NOT NULL,
    provider             TEXT NOT NULL,
    model                TEXT NOT NULL,
    response_json        TEXT NOT NULL,
    observed_at          TEXT NOT NULL
) STRICT;

CREATE INDEX reader_observations_panel_idx
    ON reader_observations (checkpoint_id, mechanism_version_id, reader_id);

CREATE TABLE editorial_interventions (
    intervention_id         TEXT PRIMARY KEY,
    controller_job_id       TEXT NOT NULL UNIQUE,
    checkpoint_id           TEXT NOT NULL,
    mechanism_version_id    TEXT NOT NULL REFERENCES reader_mechanism_versions(version_id),
    book_id                 TEXT NOT NULL,
    branch_id               TEXT NOT NULL,
    source_revision_id      TEXT NOT NULL,
    source_logical_id       TEXT NOT NULL,
    decision                TEXT NOT NULL CHECK (
        decision IN ('satisfy', 'defer', 'subvert', 'refuse', 'challenge_lock')
    ),
    need                    TEXT NOT NULL,
    rationale               TEXT NOT NULL,
    evidence_observation_ids TEXT NOT NULL,
    evidence_digest         TEXT NOT NULL,
    target_logical_ids      TEXT NOT NULL,
    directive_id            TEXT REFERENCES directives(directive_id),
    created_at              TEXT NOT NULL,
    metadata                TEXT
) STRICT;

CREATE INDEX editorial_interventions_checkpoint_idx
    ON editorial_interventions (checkpoint_id, mechanism_version_id);
