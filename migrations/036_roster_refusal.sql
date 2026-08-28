-- The operator's NO gets somewhere to live: a writer may be refused, and the refusal is a row.
--
-- **035 declined this deliberately, and the sentence it declined it in is worth quoting**:
-- *"with no retired status in this migration the way through is a new name."* That was the
-- right call for the case 035 could see — a dossier edited after acceptance — and it is the
-- wrong call for the one that actually arrived. Twelve recruits landed on one shelf at once,
-- and an operator reading them has exactly one verb. `accept` moves a writer; there is no way
-- to say no. So a rejected proposal stays `proposed` forever, a bare `roster accept` sweeps it
-- up months later, and the pile only grows. A new name answers "this dossier was wrong"; it
-- has never answered "this writer is not wanted".
--
-- **The rail is unchanged, and that is the argument for the third member rather than against
-- it.** `RosterStatus`' own docstring says the gap between its two members is a person. A
-- refusal is also a person: the same operator, the same recorded act, the same decision row
-- carrying the same weight. What 035 made unrepresentable is a *machine's* judgment wearing an
-- operator's word, and a `refused` row that cannot exist without a `decision_id` is that same
-- guard pointed at the other verdict. The second CHECK below does for refusal exactly what
-- 035's did for admission.
--
-- **Terminal and quiet.** A refused writer is excluded from `--writer` resolution the way a
-- proposed one is — `accepted_writer` filters on `accepted` and needs no change — and there is
-- no un-refuse. A changed mind is a new proposal under the same name, which is already legal:
-- `roster_accepted_name_idx` covers `accepted` only, so refusing a name frees it completely.
--
-- **`refused_at` is its own column rather than a reuse of `accepted_at`.** A column whose name
-- says "accepted" holding the moment somebody was turned down is the kind of lie that reads
-- correctly in code and wrongly in every report built on it later.
--
-- **This is the first table rebuild in these migrations, so why it is safe, in full.** SQLite
-- cannot ALTER a CHECK constraint, and `status` is pinned by two of them, so the table has to
-- be rebuilt. The 12-step procedure's `PRAGMA foreign_keys=OFF` is *not* available here:
-- `SqliteStore.migrate` runs each migration inside a transaction and that pragma is a no-op
-- inside one. It is also not needed. The pragma in that procedure exists to stop DROP and
-- RENAME from disturbing foreign keys in **other** tables that point at the one being rebuilt,
-- and nothing in this schema references `roster_writers` — its only key is outgoing, to
-- `policy_decisions`. So the copy satisfies the live FK on the way in (every `accepted` row
-- already points at a decision that exists), the DROP cascades to nothing, and the RENAME has
-- no referring table to rewrite. Indexes go with the dropped table and are recreated below
-- under their original names.

CREATE TABLE roster_writers_rebuilt (
    writer_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    dossier         TEXT NOT NULL,
    interests_json  TEXT NOT NULL DEFAULT '[]',
    exemplar_digest TEXT CHECK (exemplar_digest IS NULL OR exemplar_digest <> ''),
    note            TEXT NOT NULL DEFAULT '',
    specialization  TEXT NOT NULL,
    shape           TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('proposed', 'accepted', 'refused')),
    proposed_at     TEXT NOT NULL,
    accepted_at     TEXT,
    refused_at      TEXT,
    decision_id     TEXT REFERENCES policy_decisions(decision_id),
    CHECK (
        (status = 'proposed'
            AND accepted_at IS NULL AND refused_at IS NULL AND decision_id IS NULL)
        OR (status = 'accepted'
            AND accepted_at IS NOT NULL AND refused_at IS NULL AND decision_id IS NOT NULL)
        OR (status = 'refused'
            AND accepted_at IS NULL AND refused_at IS NOT NULL AND decision_id IS NOT NULL)
    )
) STRICT;

-- Columns named on both sides. `SELECT *` here would bind by position, and the next migration
-- to add a column would silently shift every value one place to the left.
INSERT INTO roster_writers_rebuilt (
    writer_id, name, dossier, interests_json, exemplar_digest, note,
    specialization, shape, status, proposed_at, accepted_at, refused_at, decision_id
)
SELECT
    writer_id, name, dossier, interests_json, exemplar_digest, note,
    specialization, shape, status, proposed_at, accepted_at, NULL, decision_id
FROM roster_writers;

DROP TABLE roster_writers;

ALTER TABLE roster_writers_rebuilt RENAME TO roster_writers;

-- "Who answers to this name" is the question `--writer` asks, and the roster is listed by name.
CREATE INDEX roster_writers_name_idx ON roster_writers (name);

-- The listing's own order and its one filter, now over three statuses rather than two.
CREATE INDEX roster_writers_status_idx ON roster_writers (status, name);

-- "Who did we recruit for this shelf" is the recruitment brief's own question.
CREATE INDEX roster_writers_specialization_idx ON roster_writers (specialization);

-- **Still `accepted` only, and now that scope does a second job.** It buys `--writer <name>` a
-- deterministic answer, and because it ignores `refused`, turning a writer down releases the
-- name for a later proposal to use. That is the whole of what "a changed mind is a new
-- proposal" needs from the schema.
CREATE UNIQUE INDEX roster_accepted_name_idx ON roster_writers (name) WHERE status = 'accepted';
