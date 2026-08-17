-- §61 Add 2: the promise/payoff ledger, and the scene-delta columns beside the summary.
--
-- **A separate table, and the separateness is the design.** The obvious home was a THREAD
-- state record with a payoff-due position folded into its value — and that home is a trap
-- three times over. `open_threads` (domain/state.py) tests `value == "open"` by exact
-- equality and both golden fixtures author exactly that, so turning the value into a mapping
-- silently empties the packet's THREADS section, the summarizer's ground truth, and the
-- status thread counts at once. `detect_contradictions` groups all canon records on
-- (subject, predicate, order_key), so a reused predicate at an existing position can fire
-- MAJOR findings about bookkeeping. And `has_story_vocabulary` freezes extraction for any
-- book whose canon gains order keys under an unrecognised registry version — the defect that
-- once froze five of a six-scene book's scenes. A table that is not state_records sidesteps
-- all three; the price is that repair propagation cannot see these rows (`changes_between`
-- reads state records only), which is acceptable for an advisory instrument.
--
-- **Everything here is model-sourced and stays PROPOSED-grade.** The rows are written by the
-- summary handler from the extended summary call's `promises_opened`/`promises_paid` fields
-- (§15's fold-asks lesson: one invocation, no new call). Nothing on the accept path treats a
-- promise as canon; the overdue check it feeds (`promise.overdue.v0`) is deterministic
-- arithmetic over these model-sourced rows and is therefore MINOR/advisory until §10.4's
-- calibration promotes it. scene_change_profile died because LEDGER delta is not DRAMATIC
-- delta — the confession scene carried zero records — which is why both features take the
-- model leg at all.
--
-- `promise_id` derives from sha256(book_id + subject), so re-summarising converges: the same
-- subject re-opened is the same row (`INSERT OR IGNORE`), never a duplicate. Payment is the
-- write-once verdict pattern — a single open→paid transition via UPDATE ... WHERE
-- status='open' — so the first payoff wins and a replay is a no-op.
--
-- `opened_at_key`/`due_key` are story order keys minted by `beats_for` (zero-padded to the
-- book's own width; s10 < s2 lexicographically is the recorded bug the padding closes). A
-- book whose template is not chronological gets no promise rows at all — the same abstention
-- milestones make: no key rather than a guessed one. `due_key` defaults to the book's final
-- scene key when the model's due_hint is absent or unparseable: a promise is at latest
-- overdue if the book ends unpaid.

ALTER TABLE scene_summaries ADD COLUMN delta_json TEXT;
ALTER TABLE scene_summaries ADD COLUMN promises_json TEXT;

CREATE TABLE promises (
    promise_id         TEXT NOT NULL PRIMARY KEY,
    book_id            TEXT NOT NULL,
    branch_id          TEXT NOT NULL,
    subject            TEXT NOT NULL,
    description        TEXT NOT NULL,
    opened_at_key      TEXT NOT NULL,
    due_key            TEXT,
    opened_by_revision TEXT NOT NULL,
    paid_at_key        TEXT,
    paid_by_revision   TEXT,
    status             TEXT NOT NULL CHECK (status IN ('open', 'paid')),
    -- Provenance: the model whose summary call asserted this promise exists. §2's
    -- traceability clause, and the reason the overdue finding's confidence basis is not
    -- `deterministic` — the arithmetic is, the rows are not.
    model              TEXT NOT NULL
) STRICT;

-- The detector and the packet both ask "what does this book still owe", once per drafted
-- scene; the status column is in the index so open-only reads never scan paid history.
CREATE INDEX promises_book_idx ON promises (book_id, branch_id, status);
