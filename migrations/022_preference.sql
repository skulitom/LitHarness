-- §61's pairwise preference engine: the tables under the one evidence channel with no
-- refutation against it, because it is the one this project never funded.
--
-- The goal is now a bound, not a mood: "superhuman" means the lower bound of a 95%
-- confidence interval on blinded, position-swapped pairwise win rate against matched
-- published-human prose exceeds 0.5, judged by paid genre readers. These three tables are
-- where that claim's evidence lives — the comparator prose, the pre-registered frame, and
-- the judgment rows. The production loop reads none of them to tick: preference evidence
-- gates promotions, never units, and with all three tables empty the system drafts whole
-- books exactly as before. Empty is the honest starting state, the same way the audit
-- queue's NULL count measures missing judgment.
--
-- **`audit_samples` is deliberately NOT widened with nullable second-text columns.** Its
-- `sample_id` derives from exactly one (revision_id, logical_id), and every consumer it has
-- — the verdict digest, the audit listing, the answered-count check, `audit_counts` —
-- assumes one referent per row. A pair is a different thing with a different identity
-- (hashed from the unordered member pair), so it gets its own table rather than a second
-- meaning smuggled into an existing one.

-- The matched published-human excerpts: the other side of the superiority claim.
--
-- `excerpt_id` is a content address over the canonical text, so the same passage pasted
-- twice is one row and an excerpt cannot drift under the judgments that cite it. `source`,
-- `genre` and `era` are the matching covariates the craft corpus's standing demand requires
-- recorded — §56.3 measured revealed labels selecting story size and era rather than prose,
-- so a comparison that cannot say what it was matched on is a comparison against a
-- confound. All three are NOT NULL: §59's discipline, the permissive answer must be said
-- rather than inherited. `words` is stored because length is the first covariate every
-- refuted proxy fell to (§1a.1's shallow incumbent won outright at 0.5733).
CREATE TABLE comparison_corpus (
    excerpt_id TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    source     TEXT NOT NULL,
    genre      TEXT NOT NULL,
    era        TEXT NOT NULL,
    words      INTEGER NOT NULL,
    added_at   TEXT NOT NULL
) STRICT;

-- The pre-registered comparison frames — §61 pre-registration (4): the frame IS the claim.
--
-- Beating median tier-matched serials and beating the genre's best are different claims,
-- and a win rate reported without its frame reads as either. So the frame is declared
-- before the first reader is paid, the tie policy before the first judgment (§61
-- pre-registration 2), and `protocol_id` is derived from the declaration's content with
-- `declared_at` deliberately outside the hash: re-declaring the same frame later collides
-- here (INSERT OR IGNORE) and is refused with its original id, rather than minting a
-- fresh-looking sibling with a newer timestamp. Drawing or judging a pair that references
-- no row in this table is refused outright.
CREATE TABLE preference_protocols (
    protocol_id      TEXT PRIMARY KEY,
    comparator_frame TEXT NOT NULL,
    tie_policy       TEXT NOT NULL,
    grain            TEXT NOT NULL,
    declared_at      TEXT NOT NULL
) STRICT;

-- One presented pair per row, awaiting one reader's verdict. The audit queue's discipline,
-- inherited whole (§67): the draw is bucket arithmetic on the content-derived pair id —
-- `rate` and `bucket` are stored so "why was this pair drawn" stays arithmetic anyone can
-- repeat — and a verdict lands write-once via UPDATE ... WHERE verdict IS NULL, because the
-- first reading is the blind one and a reader who has since seen provenance is a different
-- instrument.
--
-- `left_addr`/`right_addr` are the PRESENTED order and `orientation` says which way the
-- unordered pair was turned: orientation 0 presents (min, max), 1 presents (max, min), and
-- both orientations of a drawn pair are sibling rows sharing `pair_id`. Position is
-- recorded, not just randomized, because RevisionBench measured 43-65% positional artifacts
-- in judges — the swap only becomes a measurement if the record says which way each row
-- faced.
--
-- `recognized` is §61 pre-registration (3): §58 measured a scorer's familiarity with
-- published text swinging a score several times harder than real damage, the matched corpus
-- includes some of the genre's most-read serials, so recognition is the expected case. The
-- flag is stored on the row and the row is excluded from analysis — never dropped, because
-- the exclusion count is itself a finding.
--
-- `book_id` is nullable: the one book a pair's members belong to, or NULL for a cross-book
-- pair, so the per-book slice §61 pre-registration (5) divides the family over cannot be
-- poisoned by an invented owner. `reader_id` is nullable because a queue row is drawn
-- before anyone has agreed to read it; the answering reader is stamped with the verdict.
CREATE TABLE pair_samples (
    sample_id   TEXT PRIMARY KEY,
    pair_id     TEXT NOT NULL,
    orientation INTEGER NOT NULL,
    protocol_id TEXT NOT NULL,
    left_addr   TEXT NOT NULL,
    right_addr  TEXT NOT NULL,
    grain       TEXT NOT NULL,
    book_id     TEXT,
    sampled_at  TEXT NOT NULL,
    rate        REAL NOT NULL,
    bucket      INTEGER NOT NULL,
    reader_id   TEXT,
    verdict     TEXT,
    recognized  INTEGER,
    note        TEXT,
    judged_at   TEXT
) STRICT;

CREATE INDEX pair_samples_pending_idx ON pair_samples (verdict, sampled_at);
CREATE INDEX pair_samples_protocol_idx ON pair_samples (protocol_id, verdict);
CREATE INDEX pair_samples_pair_idx ON pair_samples (pair_id);
