"""Global, read-only listing of site-local Admin Small profiles."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections

from core.auth.account_state import account_status_label
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
                           t.trang_thai, n.trang_thai
                    FROM dbo.Admin AS n
                    INNER JOIN dbo.TaiKhoan AS t ON t.ma_tai_khoan = n.ma_tai_khoan
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
