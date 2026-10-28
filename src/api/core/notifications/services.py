"""Global Query and per-site read receipts for admin notifications."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction
from django.utils import timezone as django_timezone

from core.sites.connections import UnknownSiteError, get_site_database_alias, get_site_connection
from core.notifications.publisher import publish_notification


class NotificationInfrastructureUnavailable(Exception):
    """A required catalog, site database, or notification table is unavailable."""


class NotificationNotFound(Exception):
    """The scoped notification does not exist or is not visible to this role."""


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


def _refresh_site_summary(site_code: str, missing_sites: tuple[str, ...] = ()) -> None:
    alias = get_site_database_alias(site_code)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                today = django_timezone.localdate().isoformat()
                publish_notification(
                    cursor,
                    site_code=site_code,
                    event_key=f"system-available:{site_code}:{today}",
                    category="system",
                    severity="success",
                    title=f"Cơ sở {site_code} đang hoạt động",
                    message=f"CSDL site {site_code} đã phản hồi trong lần kiểm tra hôm nay.",
                    target_path="/admin/dashboard",
                )
                if missing_sites:
                    unavailable = ", ".join(sorted(missing_sites))
                    digest = hashlib.sha256(unavailable.encode("utf-8")).hexdigest()[:20]
                    publish_notification(
                        cursor,
                        site_code=site_code,
                        event_key=f"system-unavailable:{today}:{digest}",
                        category="system",
                        severity="critical",
                        title="Có cơ sở không phản hồi",
                        message=f"Không đọc được hoặc cấu hình site chưa đồng bộ: {unavailable}.",
                        target_path="/admin/dashboard",
                    )
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
                row = cursor.fetchone()
                count, remaining, last_id = int(row[0]), int(row[1]), str(row[2])
                if count:
                    snapshot = f"{site_code}:{count}:{remaining}:{last_id}"
                    digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()[:32]
                    publish_notification(
                        cursor,
                        site_code=site_code,
                        event_key=f"tuition-open:{digest}",
                        category="tuition",
                        severity="warning",
                        title=f"{count} khoản học phí chưa thu đủ",
                        message=(
                            f"Tại thời điểm tổng hợp ở cơ sở {site_code}: có {count} khoản chưa thu đủ, "
                            f"tổng số tiền còn lại {remaining:,} VND. Đây là số dư hiện tại, không phải giao dịch đang xử lý."
                        ),
                        target_path=f"/admin/tuition?site_code={site_code}",
                    )
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def _site_counts(site_code: str, user_id: str, role: str, category: str | None) -> tuple[int, int]:
    alias = get_site_database_alias(site_code)
    audience = _audiences(role)
    category_sql = " AND n.danh_muc = %s" if category else ""
    params: list[Any] = [user_id, *audience]
    if category:
        params.append(category)
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT_BIG(*),
                       COALESCE(SUM(CASE WHEN d.slug IS NULL THEN CONVERT(BIGINT, 1) ELSE CONVERT(BIGINT, 0) END), 0)
                FROM dbo.ThongBao AS n
                LEFT JOIN dbo.TrangThaiDocThongBao AS d
                  ON d.ma_tai_khoan = %s AND d.slug = n.slug
                WHERE n.doi_tuong IN (%s, %s){category_sql}
                """,
                params,
            )
            row = cursor.fetchone()
            return int(row[0]), int(row[1])
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def _site_items(
    site_code: str, user_id: str, role: str, category: str | None,
    unread_only: bool, take: int,
) -> list[dict[str, Any]]:
    alias = get_site_database_alias(site_code)
    audience = _audiences(role)
    category_sql = " AND n.danh_muc = %s" if category else ""
    unread_sql = " AND d.slug IS NULL" if unread_only else ""
    params: list[Any] = [user_id, *audience]
    if category:
        params.append(category)
    params.append(take)
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                f"""
                SELECT n.slug, n.ma_co_so, n.danh_muc, n.muc_do,
                       n.tieu_de, n.noi_dung, n.duong_dan, n.tao_luc_utc,
                       CONVERT(BIT, CASE WHEN d.slug IS NULL THEN 0 ELSE 1 END)
                FROM dbo.ThongBao AS n
                LEFT JOIN dbo.TrangThaiDocThongBao AS d
                  ON d.ma_tai_khoan = %s AND d.slug = n.slug
                WHERE n.doi_tuong IN (%s, %s){category_sql}{unread_sql}
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
                "created_at": _utc_datetime(row[7]), "is_read": bool(row[8]),
            }
            for row in rows
        ]
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def _utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def list_notifications(
    *, user_id: str, role: str, user_site_code: str | None = None,
    site_code: str | None = None, category: str | None = None,
    unread_only: bool = False, limit: int = 20, offset: int = 0,
) -> dict[str, Any]:
    if role == "admin_small":
        if site_code:
            raise PermissionError("Admin Small không được chọn site trong request.")
        sites, missing = _local_site(user_site_code), ()
    else:
        sites, missing = _global_sites(site_code)

    all_count = unread_count = 0
    results: list[dict[str, Any]] = []
    unavailable = list(missing)
    take = offset + limit
    for site in sites:
        try:
            _refresh_site_summary(site, missing_sites=missing)
            total, unread = _site_counts(site, user_id, role, category)
            all_count += total
            unread_count += unread
            results.extend(_site_items(site, user_id, role, category, unread_only, take))
        except NotificationInfrastructureUnavailable:
            unavailable.append(site)
    results.sort(key=lambda item: (item["created_at"], item["site_code"], item["slug"]), reverse=True)
    count = unread_count if unread_only else all_count
    return {
        "complete": not unavailable,
        "missing_sites": sorted(set(unavailable)),
        "site_codes": list(sites),
        "count": count,
        "unread_count": unread_count,
        "limit": limit,
        "offset": offset,
        "results": results[offset:offset + limit],
    }

def mark_notification_read(
    *, user_id: str, role: str, user_site_code: str | None,
    site_code: str, slug: str,
) -> dict[str, Any]:
    if role == "admin_small":
        if site_code.strip().upper() != str(user_site_code or "").strip().upper():
            raise PermissionError("Admin Small chỉ được đánh dấu thông báo tại cơ sở của mình.")
        sites = _local_site(user_site_code)
    else:
        sites, missing = _global_sites(site_code)
        if missing:
            raise NotificationInfrastructureUnavailable
    site = sites[0]
    alias = get_site_database_alias(site)
    audiences = _audiences(role)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT n.slug, n.danh_muc, n.tao_luc_utc, n.doi_tuong
                    FROM dbo.ThongBao AS n
                    WHERE n.slug = %s AND n.ma_co_so = %s AND n.doi_tuong IN (%s, %s)
                    """,
                    [slug, site, *audiences],
                )
                row = cursor.fetchone()
                if row is None:
                    raise NotificationNotFound
                cursor.execute(
                    """
                    IF NOT EXISTS (
                        SELECT 1 FROM dbo.TrangThaiDocThongBao WITH (UPDLOCK, HOLDLOCK)
                        WHERE ma_tai_khoan = %s AND slug = %s
                    )
                    BEGIN
                        INSERT INTO dbo.TrangThaiDocThongBao (ma_tai_khoan, slug)
                        VALUES (%s, %s)
                    END
                    """,
                    [user_id, slug, user_id, slug],
                )
                cursor.execute(
                    "SELECT da_doc_luc_utc FROM dbo.TrangThaiDocThongBao "
                    "WHERE ma_tai_khoan = %s AND slug = %s",
                    [user_id, slug],
                )
                read_at = cursor.fetchone()[0]
                return {
                    "slug": str(row[0]), "site_code": site, "category": str(row[1]),
                    "created_at": _utc_datetime(row[2]), "is_read": True,
                    "read_at": _utc_datetime(read_at),
                }
    except NotificationNotFound:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def mark_all_notifications_read(
    *, user_id: str, role: str, user_site_code: str | None,
    site_code: str | None = None, category: str | None = None,
) -> dict[str, Any]:
    if role == "admin_small":
        if site_code:
            raise PermissionError("Admin Small không được chọn site trong request.")
        sites = _local_site(user_site_code)
        missing: tuple[str, ...] = ()
    else:
        sites, missing = _global_sites(site_code)
    marked_sites, failed_sites = [], list(missing)
    audience = _audiences(role)
    category_sql = " AND n.danh_muc = %s" if category else ""
    for site in sites:
        alias = get_site_database_alias(site)
        try:
            with transaction.atomic(using=alias):
                with connections[alias].cursor() as cursor:
                    cursor.execute(
                        f"""
                        MERGE dbo.TrangThaiDocThongBao WITH (HOLDLOCK) AS target
                        USING (
                            SELECT n.slug
                            FROM dbo.ThongBao AS n
                            WHERE n.doi_tuong IN (%s, %s){category_sql}
                        ) AS source
                          ON target.ma_tai_khoan = %s AND target.slug = source.slug
                        WHEN NOT MATCHED THEN
                          INSERT (ma_tai_khoan, slug) VALUES (%s, source.slug);
                        """,
                        [*audience, *([category] if category else []), user_id, user_id],
                    )
            marked_sites.append(site)
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
            failed_sites.append(site)
    return {
        "complete": not failed_sites,
        "marked_sites": marked_sites,
        "missing_sites": sorted(set(failed_sites)),
    }
