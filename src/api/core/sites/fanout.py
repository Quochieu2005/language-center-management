"""Bounded concurrent reads across independent site databases."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar, cast

from django.conf import settings
from django.db import OperationalError, close_old_connections, connections


T = TypeVar("T")
MAX_SITE_READ_WORKERS = 4

# Connection-level SQLSTATEs (login/TCP failure, link lost); query errors are not cached.
_UNREACHABLE_MARKERS = ("08001", "08S01", "TCP Provider")
_unreachable_until: dict[str, float] = {}
_unreachable_lock = threading.Lock()


class SiteTemporarilyUnreachable(OperationalError):
    """A site failed to connect moments ago; skipped instead of waiting for another timeout."""


def _cooldown_seconds() -> float:
    return float(getattr(settings, "SITE_UNREACHABLE_COOLDOWN_SECONDS", 30))


def _skip_until(site_code: str) -> float | None:
    with _unreachable_lock:
        until = _unreachable_until.get(site_code)
        if until is not None and until <= time.monotonic():
            _unreachable_until.pop(site_code, None)
            return None
        return until


def _record_outcome(site_code: str, error: Exception | None) -> None:
    with _unreachable_lock:
        if error is None:
            _unreachable_until.pop(site_code, None)
        elif isinstance(error, OperationalError) and not isinstance(error, SiteTemporarilyUnreachable):
            if any(marker in str(error) for marker in _UNREACHABLE_MARKERS) and _cooldown_seconds() > 0:
                _unreachable_until[site_code] = time.monotonic() + _cooldown_seconds()


def read_sites_concurrently(
    site_codes: tuple[str, ...] | list[str],
    reader: Callable[[str], T],
) -> tuple[dict[str, T], dict[str, Exception]]:
    """Run independent read-only site work concurrently, preserving per-site errors.

    Each worker gets its own Django connection context. Results are returned in
    maps so callers can keep their existing partial-result and missing-site
    behavior without silently dropping a failed site.

    A site whose connection just failed is reported as an error immediately for
    ``SITE_UNREACHABLE_COOLDOWN_SECONDS`` so every GLOBAL page does not wait for the
    full connect timeout again; callers still list it in ``missing_sites``.
    """
    sites = tuple(dict.fromkeys(site_codes))
    if not sites:
        return {}, {}

    def run(site_code: str) -> tuple[str, T | None, Exception | None]:
        if _skip_until(site_code) is not None:
            return site_code, None, SiteTemporarilyUnreachable(
                f"Site {site_code} vừa mất kết nối; tạm bỏ qua để không chờ timeout lặp lại."
            )
        try:
            close_old_connections()
            value = reader(site_code)
            _record_outcome(site_code, None)
            return site_code, value, None
        except Exception as exc:
            _record_outcome(site_code, exc)
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
