-- The one text nothing kept: the prose a scene would have shipped had the reviser been held back.
--
-- **This closes an attribution hole the audit found rather than predicted.**
-- `plan/agent-impact/reviser-impact.md` §1 is three reads of the code establishing that no
-- draft/revision pair exists anywhere and none can be built later: `revise_draft` returns one
-- string, `commit_revision` stores that one, the reviser's own decision row carries provider,
-- model, tokens, cost and a containment verdict and no text, `ManuscriptRevisionAccepted`
-- carries `chars`, `em_dashes_removed` and `revised_by` and no text, and `providers/cli.py`
-- passes `--no-session-persistence` so no provider-side transcript survives either. §6 of that
-- file states the consequence plainly: no amount of later measurement recovers a scene already
-- written.
--
-- **What is stored is the gated draft, not the provider's raw string, and that is the whole
-- point of the column.** The row holds the text as `gate_draft` canonicalized it after the
-- em-dash strip -- which is exactly the prose `--no-revise` would have committed for this
-- attempt. Storing the raw string instead would make a diff against the accepted prose
-- attribute NFC normalisation, line-ending unification and every §180 em-dash rewrite to the
-- reviser, which is the second answer this project refuses to invent (§184.5). One text, one
-- offset space, comparable to the node content beside it.
--
-- **A table rather than a column, and the alternatives were each refused by something already
-- written down.**
--
--  * A column on `node_versions` would put a stage-specific field on the manuscript artifact
--    itself. A node version is the book's prose; a draft the book did not keep is not.
--  * A column on `policy_decisions` would put prose in the table that holds gate JSON, and the
--    reviser's decision row is deliberately textless (§185.7 lists what it carries).
--  * `span_candidates` (migration 024) already keeps loser drafts -- and its whole vocabulary is
--    `alternative_index` and `status IN ('candidate','selected','discarded')`, which is the
--    tournament shape §185.9 refuses in every costume. A pre-revision draft is not a loser: it
--    was never ranked against anything and nothing chose between the two texts. Writing it into
--    a table whose columns say it was selected against would make the record assert the one
--    thing the stage may not do.
--  * An event payload would carry a kilobyte of prose per scene through the append-only log,
--    which every existing consumer of that log reads whole.
--
-- **The primary key is content-derived**, over the revision the accepted prose landed in, the
-- node, and the draft's own hash, so `INSERT OR IGNORE` makes a replayed tick converge on one
-- row instead of growing the table. That is `CONTRIBUTING.md`'s replay rule at this address.
--
-- **What is deliberately absent.** No verdict, no score, no ordering, no `status`, and nothing
-- comparing the two texts: this table records that a stage was handed a text and what the text
-- was. Any comparison is the reader's, later, outside the loop. And no read path into
-- generation -- `application/ports.py` gains only the *write* keyword, so no workflow that
-- coordinates through those protocols can name this table at all. The reader lives on the
-- concrete store, where `cli.py`'s dossier is its one caller.
CREATE TABLE pre_revision_drafts (
    draft_id         TEXT PRIMARY KEY,
    book_id          TEXT NOT NULL,
    branch_id        TEXT NOT NULL,
    logical_id       TEXT NOT NULL,
    -- The revision the *accepted* prose landed in, so the pair is one join away: this row's
    -- `content` against that revision's node content for this `logical_id`.
    revision_id      TEXT NOT NULL,
    job_id           TEXT NOT NULL,
    attempt          INTEGER NOT NULL,
    -- Who wrote this text, and who wrote the prose that replaced it. Both nullable-free:
    -- a row exists only when a revision was adopted, so both models are known.
    drafted_by       TEXT NOT NULL,
    revised_by       TEXT NOT NULL,
    content          TEXT NOT NULL CHECK (trim(content) <> ''),
    content_sha256   TEXT NOT NULL,
    chars            INTEGER NOT NULL,
    -- How many em dashes §180's strip took out of *this* text. §185.8 item 2 recorded that
    -- `em_dashes_removed` on the acceptance event stops being a fact about the writer once the
    -- stage is on; this is where the writer's own rate goes on living, per scene, beside the
    -- text it was counted in.
    em_dashes_removed INTEGER NOT NULL,
    created_at       TEXT NOT NULL
) STRICT;

-- "What did this scene look like before the second call" is the only question asked of this
-- table, and it is asked by node.
CREATE INDEX pre_revision_drafts_node_idx
    ON pre_revision_drafts (book_id, branch_id, logical_id, created_at);
