"""Shared primitives for site-scoped academic APIs."""

from __future__ import annotations

import json
import re
from functools import wraps
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections

from core.auth.service_common import AuthInfrastructureUnavailable, _acquire_named_lock
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


class AcademicError(Exception):
    """Base class for expected academic API errors."""


class AcademicInfrastructureUnavailable(AcademicError):
    """A required site, database, table, or sequence could not be reached."""


class AcademicNotFound(AcademicError):
    """The requested record does not exist within the authorized site."""


class AcademicConflict(AcademicError):
    """The operation conflicts with the current business state."""


class AcademicInvalid(AcademicError):
    """The operation violates a business rule."""


class AcademicForbidden(AcademicError):
    """The authenticated actor is outside the record's authorized scope."""


class AcademicSiteUnavailable(AcademicError):
    """The site is not active or has no configured connection."""


_SEQUENCES = {
    "attendance": ("DD", "Seq_DD"),
    "grade": ("DM", "Seq_DM"),
    "receipt": ("PT", "Seq_PT"),
    "installment": ("DH", "Seq_DH"),
    "transfer": ("CC", "Seq_CC"),
    "transfer_event": ("LS", "Seq_LS"),
    "audit": ("NK", "Seq_NK"),
}


def translate_database_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except AcademicError:
            raise
        except (
            AuthInfrastructureUnavailable,
            DatabaseError,
            ImproperlyConfigured,
            KeyError,
            UnknownSiteError,
        ) as exc:
            raise AcademicInfrastructureUnavailable from exc

    return wrapped


def normalize_site(site_code: str | None) -> str:
    site = str(site_code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{1,10}", site):
        raise AcademicSiteUnavailable
    return site


def require_active_site(site_code: str) -> str:
    site = normalize_site(site_code)
    alias = get_site_database_alias(site)
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT trang_thai FROM dbo.CoSo WHERE ma_co_so = %s", [site])
        row = cursor.fetchone()
    if row is None or str(row[0]).lower() != "hoat_dong":
        raise AcademicSiteUnavailable
    return alias


def next_id(cursor, site_code: str, kind: str) -> str:
    try:
        prefix, sequence = _SEQUENCES[kind]
    except KeyError as exc:
        raise ValueError("Unknown sequence kind") from exc
    cursor.execute(f"SELECT NEXT VALUE FOR dbo.{sequence}")
    return f"{normalize_site(site_code)}-{prefix}-{int(cursor.fetchone()[0]):06d}"


def acquire_record_lock(cursor, key: str) -> None:
    _acquire_named_lock(cursor, f"qlttnn:academic:{key}")


def append_audit(
    cursor,
    *,
    site_code: str,
    actor_id: str | None,
    action: str,
    table_name: str,
    record_id: str,
    remote_ip: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    note: str | None = None,
) -> str:
    log_id = next_id(cursor, site_code, "audit")
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua, ghi_chu)
        VALUES (%s, 'system', %s, %s, %s, %s, %s, %s, %s, %s, 'thanh_cong', %s)
        """,
        [
            log_id, site_code, actor_id, action, table_name, record_id,
            json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
            json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
            str(remote_ip or "")[:45], (note or "")[:1000] or None,
        ],
    )
    return log_id


def site_catalog(site_code: str) -> tuple[tuple[str, str], ...]:
    with get_site_connection(normalize_site(site_code)).cursor() as cursor:
        cursor.execute("SELECT ma_co_so, trang_thai FROM dbo.CoSo ORDER BY ma_co_so")
        return tuple((str(row[0]).upper(), str(row[1]).lower()) for row in cursor.fetchall())


@translate_database_errors
def active_site_state() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return active sites and missing/inconsistent replicas using the configured registry."""
    registry = normalize_site(getattr(settings, "AUTH_SESSION_SITE_CODE", ""))
    catalog = site_catalog(registry)
    active = tuple(code for code, state in catalog if state == "hoat_dong")
    if not active or registry not in active:
        raise AcademicInfrastructureUnavailable
    available: list[str] = []
    missing: list[str] = []
    for site in active:
        try:
            get_site_database_alias(site)
            if site_catalog(site) == catalog:
                available.append(site)
            else:
                missing.append(site)
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
            missing.append(site)
    return tuple(available), tuple(sorted(set(missing)))


def site_scope(user, requested_site: str | None, *, roles: set[str]):
    """Resolve local access; Admin Big must name one site for local writes."""
    role = str(getattr(user, "role", ""))
    if role not in roles:
        raise AcademicForbidden
    own_site = normalize_site(getattr(user, "site_code", None)) if role != "admin_big" else ""
    requested = normalize_site(requested_site) if requested_site else ""
    if role == "admin_big":
        if not requested:
            raise AcademicInvalid("Admin Big cần chọn site_code để thao tác trên một CSDL site.")
        return requested
    if not own_site or (requested and requested != own_site):
        raise AcademicForbidden
    return own_site


def actor_identity(user) -> tuple[str, str | None]:
    return str(getattr(user, "account_id", "")), getattr(user, "profile_id", None)


def local_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value
