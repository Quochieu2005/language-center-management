"""Shared catalog errors and subject update entry point."""


class SharedCatalogError(Exception):
    """Base error for a replicated catalog write."""


class SharedCatalogConflict(SharedCatalogError):
    """The request key or an existing site copy conflicts with this write."""


class SharedCatalogNotFound(SharedCatalogError):
    """The shared subject does not exist at every active site."""


class SharedCatalogUnavailable(SharedCatalogError):
    """A required site or the coordinator registry is unavailable."""

    def __init__(self, message: str = "", *, missing_sites=()):
        self.missing_sites = tuple(missing_sites)
        super().__init__(message)


def update_shared_subject(*, slug: str, patch: dict, idempotency_key: str, actor_id: str) -> dict:
    from core.catalog.publisher_subjects import write_subject

    return write_subject(action="sua", slug=slug, payload=patch,
                         idempotency_key=idempotency_key, actor_id=actor_id)
