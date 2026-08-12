-- §19 Autonomy: "nothing spins". The outbox did.
--
-- `OutboxState` had only PENDING and SENT, so an entry whose sink never accepts it had no
-- terminal state to reach, and `_drain_outbox` re-attempted the first 50 pending rows on
-- every leading tick forever. Measured over the horizon the endurance test itself uses —
-- 2016 ticks, one week at the 5-minute cadence — the head entries reached
-- delivery_attempts=2016 while entries 51 and beyond reached 0: an unbounded spin *and*
-- permanent head-of-line starvation, at roughly 100,000 synchronous=FULL writes achieving
-- nothing.
--
-- The endurance test could not have caught it: it asserts the outbox is empty, so the
-- workload that exposes this is excluded from the run by construction. A test for the
-- non-empty case lands with this migration.
--
-- `next_attempt_at` gives backoff; the `failed` state gives a floor to stop at. Both are
-- needed — backoff alone still spins, just more slowly, and a terminal state alone drops
-- an entry that a transient outage would have delivered on the next try.

ALTER TABLE outbox ADD COLUMN next_attempt_at REAL;

-- The drain query filters on (state, next_attempt_at), so it must be able to skip a
-- backed-off head without scanning it.
CREATE INDEX outbox_due_idx ON outbox (state, next_attempt_at);
