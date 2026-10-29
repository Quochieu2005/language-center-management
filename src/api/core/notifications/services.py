"""Global Query for admin notifications."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections

from core.sites.connections import UnknownSiteError, get_site_database_alias, get_site_connection


class NotificationInfrastructureUnavailable(Exception):
    """A required catalog, site database, or notification table is unavailable."""


class NotificationNotFound(Exception):
    """The scoped notification does not exist or is not visible to this role."""


_AUTO_SUMMARY_EVENT_FILTER = """
AND n.event_key NOT LIKE 'system-available:%'
AND n.event_key NOT LIKE 'system-unavailable:%'
AND n.event_key NOT LIKE 'tuition-open:%'
"""


def _catalog(site_code: str) -> tuple[tuple[str, str], ...]:
    with get_site_connection(site_code).cursor() as cursor:
        cursor.execute("SELECT ma_co_so, trang_thai FROM dbo.CoSo ORDER BY ma_co_so")
        return tuple((str(row[0]).upper(), str(row[1]).lower()) for row in cursor.fetchall())


def _global_sites(requested_site: str | None = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    registry = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    if not registry:
        raise NotificationInfrastructureUnavailable
    try:
        catalog = _catalog(registry)
        active = tuple(code for code, state in catalog if state == "hoat_dong")
        if not active or registry not in active:
            raise NotificationInfrastructureUnavailable
        if requested_site:
            site = requested_site.strip().upper()
            if site not in active:
                raise NotificationNotFound
            get_site_database_alias(site)
            return (site,), ()

        available, missing = [], []
        for site in active:
            try:
                get_site_database_alias(site)
                if _catalog(site) != catalog:
                    missing.append(site)
                else:
                    available.append(site)
            except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
                missing.append(site)
        return tuple(available), tuple(sorted(set(missing)))
    except NotificationInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def _local_site(site_code: str | None) -> tuple[str, ...]:
    site = str(site_code or "").strip().upper()
    if not site:
        raise NotificationInfrastructureUnavailable
    try:
        get_site_database_alias(site)
        if (site, "hoat_dong") not in _catalog(site):
            raise NotificationNotFound
        return (site,)
    except NotificationNotFound:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def _audiences(role: str) -> tuple[str, ...]:
    if role == "admin_big":
        return ("admin_all", "admin_big")
    if role == "admin_small":
        return ("admin_all", "admin_small")
    raise PermissionError("Chỉ quản trị viên được xem thông báo quản trị.")


def _live_tuition_summary(site_code: str) -> dict[str, Any] | None:
    """Read a current tuition summary without writing an event during GET."""
    alias = get_site_database_alias(site_code)
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT_BIG(*),
                       COALESCE(SUM(so_tien_phai_dong - giam_gia - so_tien_da_dong), 0),
                       COALESCE(MAX(ma_hoc_phi), '')
                FROM dbo.HocPhi
                WHERE trang_thai IN ('chua_dong', 'dong_mot_phan')
                  AND so_tien_phai_dong - giam_gia - so_tien_da_dong > 0
                """
            )
            count, remaining, last_id = cursor.fetchone()
        count, remaining = int(count), int(remaining)
        if not count:
            return None
        snapshot = f"{site_code}:{count}:{remaining}:{last_id}"
        digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()[:32]
        return {
            "slug": f"live-{site_code.lower()}-tuition-{digest}",
            "site_code": site_code,
            "category": "tuition",
            "severity": "warning",
            "title": f"{count} khoản học phí chưa thu đủ",
            "message": (
                f"Tại cơ sở {site_code}: có {count} khoản chưa thu đủ, "
                f"tổng số tiền còn lại {remaining:,} VND. Đây là số dư hiện tại, không phải giao dịch đang xử lý."
            ),
            "target_path": f"/admin/tuition?site_code={site_code}",
            "created_at": datetime.now(timezone.utc),
        }
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def _missing_site_summary(site_code: str, missing_sites: tuple[str, ...]) -> dict[str, Any]:
    unavailable = ", ".join(sorted(missing_sites))
    digest = hashlib.sha256(unavailable.encode("utf-8")).hexdigest()[:24]
    return {
        "slug": f"live-{site_code.lower()}-site-health-{digest}",
        "site_code": site_code,
        "category": "system",
        "severity": "critical",
        "title": "Có cơ sở không phản hồi",
        "message": f"Không đọc được hoặc cấu hình chưa sẵn sàng tại: {unavailable}.",
        "target_path": "/admin/dashboard",
        "created_at": datetime.now(timezone.utc),
    }


def _site_counts(site_code: str, role: str, category: str | None) -> int:
    alias = get_site_database_alias(site_code)
    audience = _audiences(role)
    category_sql = " AND n.danh_muc = %s" if category else ""
    params: list[Any] = [*audience]
    if category:
        params.append(category)
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT_BIG(*)
                FROM dbo.ThongBao AS n
                WHERE n.doi_tuong IN (%s, %s){category_sql}
                  {_AUTO_SUMMARY_EVENT_FILTER}
                """,
                params,
            )
            return int(cursor.fetchone()[0])
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def _site_items(
    site_code: str, role: str, category: str | None, take: int,
) -> list[dict[str, Any]]:
    alias = get_site_database_alias(site_code)
    audience = _audiences(role)
    category_sql = " AND n.danh_muc = %s" if category else ""
    params: list[Any] = [*audience]
    if category:
        params.append(category)
    params.append(take)
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                f"""
                SELECT n.slug, n.ma_co_so, n.danh_muc, n.muc_do,
                       n.tieu_de, n.noi_dung, n.duong_dan, n.tao_luc_utc
                FROM dbo.ThongBao AS n
                WHERE n.doi_tuong IN (%s, %s){category_sql}
                  {_AUTO_SUMMARY_EVENT_FILTER}
                ORDER BY n.tao_luc_utc DESC, n.slug DESC
                OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
                """,
                params,
            )
            rows = cursor.fetchall()
        return [
            {
                "slug": str(row[0]), "site_code": str(row[1]), "category": str(row[2]),
                "severity": str(row[3]), "title": str(row[4]), "message": str(row[5]),
                "target_path": str(row[6]) if row[6] is not None else None,
                "created_at": _utc_datetime(row[7]),
            }
            for row in rows
        ]
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def _utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def list_notifications(
    *, role: str, user_site_code: str | None = None,
    site_code: str | None = None, category: str | None = None,
    limit: int = 20, offset: int = 0,
) -> dict[str, Any]:
    if role == "admin_small":
        if site_code:
            raise PermissionError("Admin Small không được chọn site trong request.")
        sites, missing = _local_site(user_site_code), ()
    else:
        sites, missing = _global_sites(site_code)

    total_count = 0
    results: list[dict[str, Any]] = []
    unavailable = list(missing)
    take = offset + limit
    for site in sites:
        try:
            total_count += _site_counts(site, role, category)
            results.extend(_site_items(site, role, category, take))
            if category in (None, "tuition"):
                tuition_summary = _live_tuition_summary(site)
                if tuition_summary:
                    total_count += 1
                    results.append(tuition_summary)
        except NotificationInfrastructureUnavailable:
            unavailable.append(site)
    if role == "admin_big" and missing and category in (None, "system") and sites:
        total_count += 1
        results.append(_missing_site_summary(sites[0], missing))
    results.sort(key=lambda item: (item["created_at"], item["site_code"], item["slug"]), reverse=True)
    return {
        "complete": not unavailable,
        "missing_sites": sorted(set(unavailable)),
        "site_codes": list(sites),
        "count": total_count,
        "limit": limit,
        "offset": offset,
        "results": results[offset:offset + limit],
    }
