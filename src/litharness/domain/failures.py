"""The distinction between "this unit is wrong" and "the world is briefly unavailable".

The Conductor's retry ladder is bounded by an attempt budget, and that budget exists to
stop a *bad unit of work* from retrying forever. Charging infrastructure failure against it
turns the budget into a wall-clock timer against provider availability: at the plan's
5-minute cadence, `max_attempts=3` means any outage longer than fifteen minutes
permanently poisons every unit it touches — and poisoned is terminal *and* burns the
idempotency key, so the work cannot even be resubmitted.

`TransientFailure` is the marker for "nothing about this unit is wrong". A unit that hits
one is requeued without its attempt count moving, so an outage costs time and not work.

It lives in `domain` rather than in `providers` so the Conductor can catch it without the
loop taking a dependency on the adapter layer — the same reason `HealthResettable` is a
structural protocol. A future rate-limit or lease-contention error belongs here too.
"""

from __future__ import annotations


class TransientFailure(Exception):
    """The environment failed, not the work. Requeued without charging an attempt."""


__all__ = ["TransientFailure"]
