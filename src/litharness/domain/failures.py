"""The distinction between "this unit is wrong" and operational refusal.

The Conductor's retry ladder is bounded by an attempt budget, and that budget exists to
stop a *bad unit of work* from retrying forever. Charging infrastructure failure against it
turns the budget into a wall-clock timer against provider availability: at the plan's
5-minute cadence, `max_attempts=3` means any outage longer than fifteen minutes
permanently poisons every unit it touches — and poisoned is terminal *and* burns the
idempotency key, so the work cannot even be resubmitted.

`TransientFailure` is the marker for "nothing about this unit is wrong, and trying later
may work". A unit that hits one is requeued without its attempt count moving, so an outage
costs time and not work.

`ParkedFailure` is the corresponding marker for an operational condition that retrying the
same input cannot clear: expired authentication, a request the provider rejects as invalid,
or a context packet larger than the selected model can accept. It also gives the attempt
back, but parks the unit and raises an exception instead of spinning it through the retry
budget. The operator changes configuration or input, then revives it.

It lives in `domain` rather than in `providers` so the Conductor can catch it without the
loop taking a dependency on the adapter layer — the same reason `HealthResettable` is a
structural protocol. A future rate-limit or lease-contention error belongs here too.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class OperationalFailure(Exception):
    """A typed failure outside the candidate under judgment.

    `classification` and `details` are deliberately provider-neutral. The Conductor lives
    above the adapter layer, but the event and exception it records still need enough
    structure to distinguish a timeout from authentication failure without parsing prose.
    """

    def __init__(
        self,
        message: str,
        *,
        classification: str = "operational",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.details = dict(details or {})

    def diagnostic(self) -> dict[str, object]:
        return {
            "classification": self.classification,
            **{key: value for key, value in self.details.items() if value is not None},
        }


class TransientFailure(OperationalFailure):
    """The environment failed, not the work. Requeued without charging an attempt."""


class ParkedFailure(OperationalFailure):
    """The environment or input configuration needs intervention before another try."""


__all__ = ["OperationalFailure", "ParkedFailure", "TransientFailure"]
