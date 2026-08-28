-- The exemplar socket gets something to hold: a passage a writer drew, and what aimed the draw.
--
-- **035 built `exemplar_digest` and deliberately left it empty**, and its own header says why:
-- populating an exemplar later *should* mint a new writer, because an exemplar changes what the
-- writer drafts, while adding the *field* later would re-address every writer that already
-- existed. The socket has been in the address since the first mint and nothing could fill it.
-- `plan/dossier-voice-direction.md` is the operator act that fills it, and this table is what a
-- digest points at. Without it the column addresses a passage nobody kept, which is a content
-- address to nowhere.
--
-- **A separate table rather than a column on `roster_writers`, and the reason is arity rather
-- than tidiness.** A digest is shared by construction: two writers drawn from one passage are
-- one exemplar and two rows, and the same passage re-drawn by a later run converges rather than
-- duplicating, because the primary key is the content address. A `text` column on the writer
-- would store the passage once per writer and let two copies drift under one digest, which is
-- the exact failure content addressing exists to make impossible.
--
-- **`descriptor_json` is NOT NULL, and that is a design rule in the schema rather than in a
-- comment.** An unaimed draw is the circularity the whole path exists to escape: a passage drawn
-- under a house-voiced dossier with nothing else aiming it is our own register in a new costume,
-- and a dossier rewritten against it reproduces the homogeneity instead of breaking it.
-- `plan/dossier-voice-direction.md` calls our own books "legal but circular" as an exemplar
-- source, and an exemplar drawn with no descriptor is that source at one remove. So a row that
-- cannot say what aimed it cannot exist.
--
-- The descriptor is stored inline rather than in a table of its own. It is content-addressed
-- over its own numbers, so `descriptor_id` is already its checksum and a second table would add
-- a join and a foreign key to guard a value that guards itself. What inline storage buys is that
-- a replay needs this database and not also the measurement side's results file.
--
-- **What is deliberately absent, so the absence reads as a decision.** No corpus identifier of
-- any kind: not the shard, not the fiction, not the cohort the descriptor was distilled from. RS1
-- says no corpus digest crosses to the generation side, and `voice.StyleDescriptor` has no field
-- that could carry one, so this column cannot hold one either. The map from a descriptor back to
-- what it was distilled from lives on the measurement side, which is the side allowed to know.
--
-- And **no status column**. An exemplar is not admitted or refused; the *writer* minted from it
-- is, through `roster_writers.status`, which migration 036 gave its third member. A second status
-- machine over the same act is two places one decision could disagree with itself.
CREATE TABLE voice_exemplars (
    exemplar_digest TEXT PRIMARY KEY CHECK (exemplar_digest LIKE 'exm-%'),
    passage         TEXT NOT NULL CHECK (trim(passage) <> ''),
    -- Which writer drew it, as that writer stood when it drew. Not a foreign key into
    -- `roster_writers`: the four compiled writers in `writers.CAST` have no row there by
    -- design -- 035 refused to seed them because they were admitted by being written into code
    -- and there is no decision row for `accepted` to point at -- so a foreign key here would
    -- make the cast the only writers unable to draw a passage.
    drawn_by        TEXT NOT NULL,
    descriptor_id   TEXT NOT NULL CHECK (descriptor_id LIKE 'sty-%'),
    descriptor_json TEXT NOT NULL,
    profile         TEXT NOT NULL,
    drawn_at        TEXT NOT NULL
) STRICT;

-- "What did this writer draw" is the only question anybody asks of this table that the primary
-- key does not already answer, and a revoice run asks it to avoid paying for a passage twice.
CREATE INDEX voice_exemplars_drawn_by_idx ON voice_exemplars (drawn_by, drawn_at);
