-- What an accepted scene contained, in one paragraph, for the packet that can no longer hold it.
--
-- **This table exists because the eviction path became reachable, not before it.** §47
-- measured the 6,000-token context budget binding at scene 24 when a 3B model wrote 160-word
-- scenes, and at scene 5 at the 900-word target — and recorded that the counter "stays at
-- zero for every six-scene fixture, which is exactly why this limit went unnoticed". The
-- scenes this system actually wrote averaged 172 words, so nothing was ever evicted and a
-- summary would have had nothing to summarise. That changed when the length instruction
-- started reaching the prompt; `domain/context.py::SUMMARIES` is the slot, and this is where
-- what fills it lives. Migration 012 refused to author a `state_candidates` table for a
-- producer that did not exist, and the same rule is why this arrives with its handler.
--
-- **Keyed on the scene's content, not on the revision.** A summary is a function of the prose
-- it summarises, and every accepted draft mints a new revision id for the whole book — so
-- keying on `revision_id` would invalidate every summary in the book each time any one scene
-- landed, and re-summarise forty scenes to draft the forty-first. `content_hash` is the
-- address of that scene's text alone: a repaired scene gets a new summary, an untouched one
-- keeps the summary already paid for, and the cache is correct rather than merely cheap.
--
-- `model` and `profile` ride along because §2 requires each generated claim to be traceable
-- to the tool and version that produced it, and this is a generated claim that goes back into
-- the prompt — the one artifact here whose provenance a reader of the book would care about.
CREATE TABLE scene_summaries (
    book_id      TEXT NOT NULL,
    branch_id    TEXT NOT NULL,
    logical_id   TEXT NOT NULL,
    -- sha256 of the canonical scene text this summarises. See above.
    content_hash TEXT NOT NULL,
    summary      TEXT NOT NULL,
    model        TEXT NOT NULL,
    profile      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (book_id, branch_id, logical_id, content_hash)
) STRICT;

-- The packet asks "what summaries does this book have", once per drafted scene.
CREATE INDEX scene_summaries_book_idx ON scene_summaries (book_id, branch_id);
