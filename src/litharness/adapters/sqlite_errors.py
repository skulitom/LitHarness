"""Shared exceptions for the SQLite adapter package."""


class IntegrityFailure(Exception):
    """Storage returned something that does not rebuild. Never downgraded to a warning."""


class MigrationsMissing(Exception):
    """No migrations were found where they were expected. Never a silent empty schema."""
