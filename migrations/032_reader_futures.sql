-- The steering lane stops asking readers what they think of a chapter and starts asking what
-- they think happens next.
--
-- The operator, 2026-08-25: "The readers should be fed text only up until a point and then the
-- rest left out. The readers have to predict what happens next. The readers shouldn't critique
-- what is already written that's for the writers to do. From the readers we want to read their
-- emotions about what they read, and find out what they predict and want to happen next."
--
-- **Why this is a schema change and not a prompt change.** `hoping_for` and `dreading` were the
-- columns and they were also the question, and the question is what broke. Measured on *Patch
-- Notes For Earth*, 2026-08-25: four steering readers asked for "a real changelog with version
-- numbers, nerfs", "not 'he's good at games' but repro steps, edge cases", and the revision put
-- six of the operator's seven quoted defects into a hundred-word listing -- every one of them
-- absent from the draft those readers had seen. `dreading` is where a reader puts what it wants
-- the *writing* to stop doing, and a writer handed that transcribes it.
--
-- So the three new columns are the three things a reader may say, and there is no column for
-- the fourth. `felt` is what reading it did to them; `expect_next` is their prediction;
-- `want_next` is a JSON array of what they want to happen in the story. A critique has nowhere
-- to go that is not a lie about the column.
--
-- **The old columns stay.** Migration checksums are verified at startup and an applied
-- migration is never edited (CONTRIBUTING), so rows written before today keep their answers
-- where they were written; `hoping_for` maps onto `want_next` closely enough to read and
-- `dreading` has no successor by design. `sqlite_store.reader_reads` returns both shapes and
-- `readers.Anticipation.of` reads either, so a book part-drafted across the change still has a
-- direction.
--
-- **`rival_id` and `ours_first` belong to the measurement lane and are NULL for a steering
-- row.** A measurement reader now chooses between our text and a real published book that
-- cleared `domain/rivals.admit` -- rated above four stars, in one of this readership's genres.
-- Which competitor it was and which side of the page ours was on are recorded because a
-- pairwise choice with neither is a measurement of position: SS89 clocked a verdict channel
-- running 4,676x position over text.
ALTER TABLE reader_reads ADD COLUMN felt TEXT;
ALTER TABLE reader_reads ADD COLUMN expect_next TEXT;
ALTER TABLE reader_reads ADD COLUMN want_next TEXT;
ALTER TABLE reader_reads ADD COLUMN rival_id TEXT;
ALTER TABLE reader_reads ADD COLUMN ours_first INTEGER;
