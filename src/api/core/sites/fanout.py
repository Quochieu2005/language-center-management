"""Bounded concurrent reads across independent site databases."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar, cast

from django.db import close_old_connections, connections


T = TypeVar("T")
MAX_SITE_READ_WORKERS = 4


def read_sites_concurrently(
    site_codes: tuple[str, ...] | list[str],
    reader: Callable[[str], T],
) -> tuple[dict[str, T], dict[str, Exception]]:
    """Run independent read-only site work concurrently, preserving per-site errors.

    Each worker gets its own Django connection context. Results are returned in
    maps so callers can keep their existing partial-result and missing-site
    behavior without silently dropping a failed site.
    """
    sites = tuple(dict.fromkeys(site_codes))
    if not sites:
        return {}, {}

    def run(site_code: str) -> tuple[str, T | None, Exception | None]:
        try:
            close_old_connections()
            return site_code, reader(site_code), None
        except Exception as exc:
            return site_code, None, exc
        finally:
            try:
                connections.close_all()
            except Exception:
                pass

    values: dict[str, T] = {}
    errors: dict[str, Exception] = {}
    with ThreadPoolExecutor(max_workers=min(len(sites), MAX_SITE_READ_WORKERS)) as executor:
        futures = [executor.submit(run, site) for site in sites]
        for future in as_completed(futures):
            site, value, error = future.result()
            if error is not None:
                errors[site] = error
            else:
                values[site] = cast(T, value)
    return values, errors
