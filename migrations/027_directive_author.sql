-- The Director role: directives get an author, and directors get a table.
--
-- **The laundering path's third costume, closed while it is still free.** `judge-validity-program`
-- §1.1 found it in the pair table: a property ("a PREFERENCE verdict is a human's") enforced by
-- nothing but who happened to hold the pen. `plan/reader-judge-loop.md` §6 found two more when
-- the Judge was split out. Here it is again, checked in source before this migration was written:
--
--   * `directive_planner` writes an explicit constraint or veto into a plan item with
--     locked = TRUE, verbatim and by design, because those words are the director's.
--   * `narrative_planner` lets the MODEL set `locked` on every edit it proposes.
--   * `plans.constraints_of` selects locked constraints and `context.assemble` puts them in the
--     packet's CONSTRAINTS section — priority 2, above threads, facts and prose, never dropped.
--   * `directives` had no author column. The property "this is the director's word" was carried
--     by the fact that only a human could write one.
--
-- So the moment a machine writes a directive, its words enter every subsequent context packet as
-- a locked constraint carrying the director's authority, with nothing on the record saying a
-- machine wrote them. Inert today — no machine rows exist — and it stops being inert on the first
-- tick of the first Director.
--
-- `author` is NULL for every row written before this column existed, and NULL is read as
-- "unrecorded" rather than as "human": `is_machine_author` returns false for it, which is the
-- safe direction for a listing and the honest one for the record. New rows always carry one.
ALTER TABLE directives ADD COLUMN author TEXT;

CREATE INDEX directives_author_idx ON directives (author);

-- A director personality: a name and a brief, and nothing about what good prose is.
--
-- `director_id` is a content address over (name, canonical brief), so a brief cannot drift under
-- the books it directed. Editing one word mints a *different* director, which keeps "which
-- director wrote this book" answerable after somebody rewrites a brief they were unhappy with —
-- the same property `protocol_id` gives a comparison frame and `candidate_id` gives a draft.
--
-- **There is no column for what this director thinks good prose is, and that is the design.**
-- A brief goes straight into the drafting context, so a brief instructing about a registered
-- prose axis would bypass the whole axis-admission path (`plan/reader-judge-loop.md` §2.1) — a
-- human read, a deterministic counter, an E6-family validation, a reader-established direction.
-- `domain/directors.legal_brief` refuses those at construction, so an illegal brief is
-- unrepresentable rather than merely discouraged.
--
-- `registered_at` records when an operator admitted this personality. Admission is an operator
-- act for the same reason fixture admission is (§84): a rule the code could apply is a rule
-- somebody could satisfy without having done the work.
CREATE TABLE directors (
    director_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    brief         TEXT NOT NULL,
    note          TEXT NOT NULL DEFAULT '',
    registered_at TEXT NOT NULL
) STRICT;

CREATE INDEX directors_name_idx ON directors (name);
