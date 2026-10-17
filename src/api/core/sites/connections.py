"""Resolve a trusted site code to its isolated SQL Server connection alias."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections


class UnknownSiteError(LookupError):
    """Raised when the requested site has no configured database connection."""


def get_site_database_alias(site_code: str) -> str:
    """Return the configured alias; callers must obtain site_code from trusted context."""
    aliases = settings.SITE_DATABASE_ALIASES
    try:
        return aliases[site_code]
    except (KeyError, TypeError) as exc:
        raise UnknownSiteError(f"Không có cấu hình kết nối cho cơ sở {site_code!r}.") from exc


def get_site_connection(site_code: str):
    """Return a lazy Django connection for a configured site without opening it."""
    alias = get_site_database_alias(site_code)
    if alias not in settings.DATABASES or alias == "default":
        raise ImproperlyConfigured(f"Alias database của cơ sở {site_code!r} không hợp lệ.")
    return connections[alias]
