-- The loop's only deployment is a foreground session (stage-0 §57), and these three
-- tables existed for the deployment it no longer has.
--
-- `instance_leases` (002) elected a leader among overlapping cron invocations; one
-- process driving `tick` has nobody to lose the claim to. `control` (007) made pause
-- durable because a cron tick is a fresh process and an in-memory flag "is a comment";
-- in a foreground session Ctrl+C is the pause, and the table's one key was never joined
-- by the others its comment reserved room for. `outbox` (001, backoff in 006) carried
-- delivery to a consumer who was not looking at a terminal; the operator now *is* the
-- terminal, and no dispatcher remains to drain it.
--
-- Delivery, leadership and durable-pause storage therefore have no reader left, and this
-- repo treats a promise with no caller as a defect rather than a reserve.
--
-- `events` is untouched: it is the provenance record, and it was always the durable half —
-- the outbox only ever tracked delivery of rows the event log already owned. The job
-- lease columns on `jobs` are untouched too; they answer "who is working this unit",
-- which a crashed or suspended foreground session still needs answered.

DROP TABLE outbox;
DROP TABLE instance_leases;
DROP TABLE control;
