"""Shared exceptions for the SQLite adapter package."""


class IntegrityFailure(Exception):
    """Storage returned something that does not rebuild. Never downgraded to a warning."""


class MigrationsMissing(Exception):
    """No migrations were found where they were expected. Never a silent empty schema."""


class MigrationsPending(MigrationsMissing):
    """The store lags the migration set, and this open refuses to apply the difference.

    A subclass of `MigrationsMissing` so every caller that already maps that fault to an
    operational exit (`cli.main`) maps this one the same way without learning a new name.
    Raised by the opens that never migrate (`SqliteStore.open_read_only`, `open_existing`,
    stage-0 §241): an agent-facing process must not move the operator's schema, so it says
    what is pending and which verb applies it, and stops.
    """
