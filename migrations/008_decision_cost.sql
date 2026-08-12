-- §19 Economics: "per-book cost is measured, bounded, and enforced".
--
-- It was not even fully measured. `providers/cli.py` parses `total_cost_usd` out of the
-- `claude -p` envelope into `CompletionResult.cost_usd`, and the handler then dropped it:
-- `policy_decisions` had no column for it, so every recorded decision reported dollars as
-- unknown no matter what the provider said. Tokens and invocations were kept; the one
-- number an operator would actually reconcile against a bill was thrown away at the last
-- step before storage.
--
-- Nullable on purpose, and it will often be null. `claude -p` on a subscription reports no
-- cost, and Ollama's cost is hardware time — so a dollars-only budget fails open on
-- exactly the providers this system uses by default. That is why the ceilings in
-- `domain/budget.py` are tokens and invocations first, with dollars as an extra that
-- applies when the provider happens to report it.
--
-- The index is on (day, provider): "what did today cost, and where did it go" is the
-- question the budget gate asks before every call and the operator asks at any tick.

ALTER TABLE policy_decisions ADD COLUMN cost_usd REAL;

CREATE INDEX policy_decisions_spend_idx ON policy_decisions (decided_at, provider);
