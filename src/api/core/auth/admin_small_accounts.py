"""Global, read-only listing of site-local Admin Small profiles."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections

from core.auth.account_state import account_status_label
from core.auth.admin_small_email import credential_email_status
from core.auth.service_common import AuthInfrastructureUnavailable, active_site_codes
from core.sites.connections import UnknownSiteError, get_site_database_alias

def list_admin_small_accounts(
    *, site_code: str | None = None, limit: int, offset: int
) -> dict[str, Any]:
    """Read each selected site's local manager profiles and merge them in the API."""
    try:
        active_sites = active_site_codes()
        selected_sites = (site_code.upper(),) if site_code else active_sites
        if any(site not in active_sites for site in selected_sites):
            raise ValueError("Site không hoạt động.")

        total = 0
        rows: list[tuple[Any, ...]] = []
        fetch_count = offset + limit
        for site in selected_sites:
            alias = get_site_database_alias(site)
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT_BIG(*)
                    FROM dbo.Admin AS n
                    INNER JOIN dbo.TaiKhoan AS t ON t.ma_tai_khoan = n.ma_tai_khoan
                    WHERE n.ma_co_so = %s AND n.loai_admin = 'admin_small'
                      AND t.vai_tro = 'nhan_vien' AND t.ma_co_so = n.ma_co_so
                    """,
                    [site],
                )
                total += int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT n.ma_admin, n.ma_co_so, n.ho_ten, n.sdt,
                           t.ma_tai_khoan, t.slug, t.ten_dang_nhap, t.email,
                           t.trang_thai, n.trang_thai, email_state.hanh_dong
                    FROM dbo.Admin AS n
                    INNER JOIN dbo.TaiKhoan AS t ON t.ma_tai_khoan = n.ma_tai_khoan
                    OUTER APPLY
                    (
                        SELECT TOP (1) l.hanh_dong
                        FROM dbo.Logs AS l
                        WHERE l.loai_log = 'system' AND l.ma_co_so = n.ma_co_so
                          AND l.ma_tai_khoan = t.ma_tai_khoan
                          AND l.bang_tac_dong = 'TaiKhoan' AND l.ma_ban_ghi = t.ma_tai_khoan
                          AND l.hanh_dong IN (
                              'admin_small_email_ready', 'admin_small_email_sending',
                              'admin_small_email_sent', 'admin_small_email_failed',
                              'admin_small_email_unknown', 'admin_small_email_changed'
                          )
                        ORDER BY l.thoi_diem_utc DESC, l.ma_log DESC
                    ) AS email_state
                    WHERE n.ma_co_so = %s AND n.loai_admin = 'admin_small'
                      AND t.vai_tro = 'nhan_vien' AND t.ma_co_so = n.ma_co_so
                    ORDER BY n.ho_ten, n.ma_admin
                    OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
                    """,
                    [site, fetch_count],
                )
                rows.extend(tuple(row) for row in cursor.fetchall())

        results = []
        for row in rows:
            account_status = account_status_label(row[8])
            if account_status is None:
                raise AuthInfrastructureUnavailable
            results.append(
                {
                    "admin_id": str(row[0]),
                    "site_code": str(row[1]).upper(),
                    "full_name": str(row[2]),
                    "phone": str(row[3]) if row[3] is not None else None,
                    "account_id": str(row[4]),
                    "slug": str(row[5]),
                    "username": str(row[6]),
                    "email": str(row[7]),
                    "account_status": account_status,
                    "profile_status": "dang_lam" if bool(row[9]) else "nghi_viec",
                    "credential_email_status": credential_email_status(str(row[10]) if row[10] else None),
                }
            )
            results.sort(key=lambda item: (item["full_name"].casefold(), item["site_code"], item["admin_id"]))
        page = results[offset : offset + limit]
        return {
            "complete": True,
            "missing_sites": [],
            "site_codes": list(selected_sites),
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": page,
        }
    except ValueError:
        raise
    except AuthInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
