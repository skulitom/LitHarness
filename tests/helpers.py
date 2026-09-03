"""The test helpers that were one function under six names.

`worlds.world_record` proposes by design — the rail is that Architect output reaches canon only
through a recorded decision — so a test that asserts on canon has to accept its own records
first, and the pruning inventory (`plan/pruning-inventory.md` §5) found that two-line step
written eleven times: `dataclasses.replace(record, authority=ACCEPTED_CANON)` over one record
or over a seed, and once as a field-by-field reconstruction with the same result. These are
those two, plus the canon `world_record` shorthand three modules had spelled the same way.

What is deliberately **not** here: the `_canon` seeds, the `_record` builders and the three
`_system` fixtures that share a name across modules. Each of those is a different fixture with
its own subject, and `tests/test_gamesystem.py` already gives the reason a fixture is not
shared — a definition that could drift with somebody else's golden book would make the
assertions about that book instead.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

import litharness_contracts as lc

from litharness.domain import worlds


def accepted(record: lc.StateRecord) -> lc.StateRecord:
    """The same record as canon: `world_record` proposes, and canon is what a decision makes."""
    return dataclasses.replace(record, authority=lc.StateAuthority.ACCEPTED_CANON)


def accepted_all(records: Iterable[lc.StateRecord]) -> list[lc.StateRecord]:
    """`accepted` over a seed — `world accept` reduced to the one thing an assertion needs."""
    return [accepted(record) for record in records]


def canon(subject: str, predicate: str, value: object = None, **kwargs: object) -> lc.StateRecord:
    """One canon record in the world vocabulary, for a test that builds its book by hand."""
    return worlds.world_record(
        subject,
        predicate,
        value=value,
        authority=lc.StateAuthority.ACCEPTED_CANON,
        **kwargs,  # type: ignore[arg-type]
    )
