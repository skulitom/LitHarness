-- The reader -> writer loop, with Readers and Judges as separate roles.
--
-- Until now nothing a reader said about prose reached the thing that writes the next prose, by
-- any path. These four tables are that path, and the split they encode is not human-versus-
-- machine: it is valence-versus-location. A READER owns valence — would I keep reading, which of
-- these two would I rather continue — and nothing else may, because that is the only question
-- with a surviving validity check. A JUDGE owns location and axis and never valence, because
-- three independent attempts to get a verdict out of a machine died (T0's 0.8151 positional bias
-- over 568 decided comparisons; §89's E1/E2 VOID at 0.6408 over 142; the persona reader's
-- "keep reading" on 195 of 196), and exactly one frame survived: asked to *name the difference*,
-- the same model on the same pairs cleared three of three families.
--
-- Neither source is a signal alone. A reader gives an axis its direction; a judge gives a draft
-- its discrimination; only the pair can be applied to prose. See plan/reader-judge-loop.md.

-- The measurement firewall, pre-registered before the first verdict is routed.
--
-- §61's superiority claim dies if the prose was shaped by the readers who later judge it, and
-- once reader verdicts reach a draft prompt that stops being hypothetical: it becomes the
-- default, silently, because nothing in the pair engine records what a verdict was *used for*.
-- So readers and comparison passages are split into a steering pool and a measurement pool, the
-- split is content-derived (never random, never re-rollable, auditable after the fact — the
-- audit queue's discipline inherited whole), and the parameters are declared here first.
--
-- `registration_id` is a content address over the split's own parameters, so re-registering an
-- identical split is idempotent while a *different* one is a second row rather than an
-- overwrite. Which is active is the earliest row: a firewall that could be moved after the
-- verdicts arrived would not be one. A share of 0 or 1 is refused in the domain — at 1.0 §61 has
-- no readers left and at 0.0 nothing can ever steer, and both are declarations that cannot do
-- what they say.
CREATE TABLE pool_registrations (
    registration_id         TEXT PRIMARY KEY,
    registered_at           TEXT NOT NULL,
    reader_salt             TEXT NOT NULL,
    reader_steering_share   REAL NOT NULL CHECK (reader_steering_share > 0.0
                                                 AND reader_steering_share < 1.0),
    passage_salt            TEXT NOT NULL,
    passage_steering_share  REAL NOT NULL CHECK (passage_steering_share > 0.0
                                                 AND passage_steering_share < 1.0),
    note                    TEXT NOT NULL DEFAULT ''
) STRICT;

-- A reader-established direction on one named axis: which pole readers preferred, and the
-- interval that one bit rests on.
--
-- **Established by an explicit operator act, not derived on read**, which is `calibrate`'s shape
-- and §72's expiry pattern together. `verdicts_digest` is the content address of the steering
-- verdict set the direction was computed from; when the verdicts move the digest moves, the
-- direction is stale, and it emits nothing until somebody re-establishes it. Evidence moving
-- under a claim retires the claim.
--
-- `preferred_pole` is the whole answer: 'high' or 'low' on the axis's own counter. There is no
-- score column and none may be added — invariant I2, and a number attached to a scene is one
-- refactor away from a threshold, which is a gate (§10.4).
--
-- `cells` is counted in (reader, pair) cells, NOT comparisons. §89's rulebook records a
-- 30-decided floor that could not bind because four personas were one judge four times; both
-- orientations of one pair answered by one reader are one decision, and a reader who flips with
-- position has said nothing.
CREATE TABLE axis_directions (
    direction_id     TEXT PRIMARY KEY,
    axis_id          TEXT NOT NULL,
    preferred_pole   TEXT NOT NULL CHECK (preferred_pole IN ('high', 'low')),
    high_win_rate    REAL NOT NULL,
    lower_bound      REAL NOT NULL,
    alpha            REAL NOT NULL,
    cells            INTEGER NOT NULL,
    readers          INTEGER NOT NULL,
    pairs            INTEGER NOT NULL,
    verdicts_digest  TEXT NOT NULL,
    established_at   TEXT NOT NULL,
    note             TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE INDEX axis_directions_axis_idx ON axis_directions (axis_id, established_at DESC);

-- One judge output: an axis, a side, and a span. No verdict, and nowhere to put one.
--
-- **This is a table of its own rather than rows in `pair_samples`, and that is the laundering
-- fix made structural.** §86.1 records that the human-only property of EvidenceClass.PREFERENCE
-- was prose in an enum docstring, that `plan_search` wrote a licensed judge's verdicts through
-- the same pair machinery humans use, and that `analysable_judgments` never inspected
-- `reader_id`. The denominator half of that was closed with a reserved reader-id prefix. This is
-- the other half: the half of this design that runs at *volume* writes no PREFERENCE-shaped row
-- at all, so it has no laundering surface by construction rather than by filter.
--
-- `high_address` is decided by the deterministic counter, never by the judge. The judge names
-- which axis is salient; the counter decides which text is higher on it; the span is located by
-- the counter's own definition. So a judge cannot invert a direction, only fail to be useful.
--
-- `sentence` is the judge's answer verbatim, because it is the check the matcher cannot be:
-- §89's credibility for this frame rests on responses that can be read, and a stored match flag
-- with no sentence behind it cannot be audited later.
--
-- Exactly three statuses. 'minted' awaits a draft; 'spent' has been materialised into exactly
-- one job payload and may never be materialised again (accumulating feedback is the failure
-- mode); 'void' rode a batch whose placebo or sham control confabulated, and is kept rather than
-- deleted because a refused batch is evidence about the judge.
CREATE TABLE located_differences (
    difference_id  TEXT PRIMARY KEY,
    batch_id       TEXT NOT NULL,
    book_id        TEXT NOT NULL,
    branch_id      TEXT NOT NULL,
    logical_id     TEXT NOT NULL,
    axis_id        TEXT NOT NULL,
    high_address   TEXT NOT NULL,
    low_address    TEXT NOT NULL,
    span           TEXT NOT NULL,
    sentence       TEXT NOT NULL,
    judge_id       TEXT NOT NULL,
    pool           TEXT NOT NULL CHECK (pool IN ('steering', 'measurement')),
    created_at     TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('minted', 'spent', 'void'))
) STRICT;

CREATE INDEX located_differences_span_idx
    ON located_differences (book_id, branch_id, logical_id, status);
CREATE INDEX located_differences_batch_idx ON located_differences (batch_id);

-- Provenance, including the negative case: what shaped this scene, recorded against the prose
-- that resulted.
--
-- **A scene drafted with no feedback records an explicit empty set, not a missing field.** That
-- is invariant I4 and it is the whole reason this table exists rather than a nullable column:
-- "this scene had no feedback" and "nobody recorded whether this scene had feedback" are
-- different facts, and an absent row cannot tell them apart. `items` is a JSON array and `'[]'`
-- is a legitimate, expected value; `digest` is a real digest of the empty list, never null.
--
-- The job payload is the primary, crash-safe record — the feedback is materialised into it at
-- enqueue and the prompt is frozen there (invariant I5). This is the queryable projection,
-- keyed by the address the prose actually has.
CREATE TABLE scene_feedback (
    revision_id  TEXT NOT NULL,
    logical_id   TEXT NOT NULL,
    job_id       TEXT NOT NULL,
    digest       TEXT NOT NULL,
    items        TEXT NOT NULL,
    dropped      INTEGER NOT NULL DEFAULT 0,
    recorded_at  TEXT NOT NULL,
    PRIMARY KEY (revision_id, logical_id)
) STRICT;

CREATE INDEX scene_feedback_job_idx ON scene_feedback (job_id);
