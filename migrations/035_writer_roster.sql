-- The writer roster becomes records: a Recruiter may propose, and only a person may accept.
--
-- **The roster was four dossiers compiled into `domain/writers.py` and nothing could grow it**,
-- and what that cost is visible in the prose those four produced: each cast dossier names an
-- inciting beat as well as an appetite, and its writer opens every empty-brief listing on that
-- beat. The counts and the reading are `plan/reader-read-5.md` 4.3's; they live there and this
-- file points at them. Variety is a roster property before it is a prompt property, and a
-- roster that can only grow by editing Python only grows when somebody edits Python.
--
-- **`status` and its CHECK are the laundering path in its fourth costume, closed while it is
-- still free.** 027_directive_author.sql found it in `directives`: the property "these are the
-- director's words" carried by nothing but the fact that only a human could write one.
-- `judge-validity-program` 1.1 found it in the pair table and `plan/reader-judge-loop.md` 6
-- found two more. Here the property is "a person admitted this writer", the dossier rides in
-- the system message of every scene call for a whole book, and a Recruiter agent is about to be
-- holding the pen. So `accepted` is not a word a row may simply contain: the second CHECK makes
-- a row that claims it without a policy_decisions id to point at unrepresentable, and the
-- foreign key makes that id point at a decision that exists.
--
-- `writer_id` is `domain/writers.writer_id_for`'s address over (name, dossier, interests,
-- exemplar_digest), so editing one word of a dossier mints a different writer and a roster
-- cannot drift under the books it wrote. `specialization` and `shape` are deliberately
-- **outside** that address: they say why this writer was drafted, not who they are. Two
-- recruits drafted for different shelves whose dossiers came out byte-identical are therefore
-- one writer and one row, which is the correct and slightly surprising answer, and the
-- idempotent insert keeps the first row's shelf.
--
-- `interests_json` is a JSON array rather than a child table because order and exact bytes are
-- load-bearing. `writer_id_for` length-prefixes the interest field precisely so that ("a", "b")
-- and ("a\x1fb",) cannot address to the same writer, and a separator-joined column would hand
-- that forgery straight back. A child table would be correct only while every read carried an
-- explicit ORDER BY, which is a latent defect rather than a loud one. There is no validity
-- CHECK on this column and none is wanted: the content address is already its checksum, so a
-- list that comes back changed re-addresses to a different writer and `Writer.__post_init__`
-- refuses it on read. The cost, stated: "which writers list cultivation" is not an indexed
-- query. Nothing asks it; `specialization` is what the roster is filtered by.
--
-- `shape` carries no CHECK where `status` does, and the asymmetry is deliberate. `status` is a
-- rail. `shape` is the dossier-form variable of a registered arm, and a fourth form must cost a
-- line of Python rather than a table rebuild, so its vocabulary lives in
-- `domain/writers.DOSSIER_SHAPES` and the adapter refuses a value that is not in it.
--
-- `exemplar_digest` is the socket `plan/writer-roster.md` 3.1 argues for, present from the
-- first mint and unpopulated. The empty string is refused rather than stored, because
-- `writer_id_for` addresses NULL and '' identically while `Writer` keeps them apart, and two
-- rows that address the same and compare differently is the confusion the column exists to
-- avoid.
--
-- **The four writers in `writers.CAST` are not seeded here.** They were admitted by being
-- written into code, so there is no decision row for `accepted` to point at, and inventing one
-- is the exact move the CHECK above exists to prevent. Two homes for one dossier would also
-- drift, and the drifting copy would be the one in a file that can never be edited. They stay
-- the compiled control fixtures the roster is read against, and `writers.RESERVED_NAMES` keeps
-- this table out of their namespace so store-first resolution cannot shadow a control.
CREATE TABLE roster_writers (
    writer_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    dossier         TEXT NOT NULL,
    interests_json  TEXT NOT NULL DEFAULT '[]',
    exemplar_digest TEXT CHECK (exemplar_digest IS NULL OR exemplar_digest <> ''),
    note            TEXT NOT NULL DEFAULT '',
    specialization  TEXT NOT NULL,
    shape           TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('proposed', 'accepted')),
    proposed_at     TEXT NOT NULL,
    accepted_at     TEXT,
    decision_id     TEXT REFERENCES policy_decisions(decision_id),
    CHECK (
        (status = 'proposed' AND accepted_at IS NULL AND decision_id IS NULL)
        OR (status = 'accepted' AND accepted_at IS NOT NULL AND decision_id IS NOT NULL)
    )
) STRICT;

-- "Who answers to this name" is the question `--writer` asks, and the roster is listed by name.
CREATE INDEX roster_writers_name_idx ON roster_writers (name);

-- The listing's own order and its one filter.
CREATE INDEX roster_writers_status_idx ON roster_writers (status, name);

-- "Who did we recruit for this shelf" is the recruitment brief's own question, and the only
-- reason `specialization` is a column rather than a line in `note`.
CREATE INDEX roster_writers_specialization_idx ON roster_writers (specialization);

-- **At most one accepted writer answers to a name, and any number may be proposed under one.**
-- A plain UNIQUE (name) would make a second proposal fail at INSERT, which is wrong twice: a
-- Recruiter drafting one shelf at a time cannot be asked to care what a previous run proposed,
-- and content-addressing says an edited dossier is a *different* writer that has to be able to
-- coexist with the one that already wrote books. The partial index buys exactly what
-- `--writer <name>` needs, a deterministic answer, and it fails at the operator's decision
-- point rather than at the agent's drafting one. Its cost, stated: re-accepting an edited
-- dossier under a name already accepted is refused, and with no retired status in this
-- migration the way through is a new name.
CREATE UNIQUE INDEX roster_accepted_name_idx ON roster_writers (name) WHERE status = 'accepted';
