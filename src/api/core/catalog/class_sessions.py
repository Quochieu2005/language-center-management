"""Read per-class scheduled-session counts from their owning sites."""

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections

from core.academics.common import (
    AcademicInfrastructureUnavailable,
    AcademicSiteUnavailable,
    active_site_state,
    normalize_site,
    require_active_site,
)
from core.sites.connections import UnknownSiteError, get_site_database_alias
from core.sites.fanout import read_sites_concurrently


def _read_site_classes(site_code: str, alias: str) -> list[dict]:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT l.ma_khoa_hoc, l.ma_lop, l.ten_lop, l.trang_thai,
                   COUNT_BIG(b.ma_buoi) AS session_count
            FROM dbo.LopHoc AS l
            LEFT JOIN dbo.BuoiHoc AS b
              ON b.ma_co_so = l.ma_co_so AND b.ma_lop = l.ma_lop
            WHERE l.ma_co_so = %s
            GROUP BY l.ma_khoa_hoc, l.ma_lop, l.ten_lop, l.trang_thai
            ORDER BY l.ma_khoa_hoc, l.ten_lop, l.ma_lop
            """,
            [site_code],
        )
        rows = cursor.fetchall()
    return [
        {
            "course_id": str(row[0]),
            "class_id": str(row[1]),
            "class_name": str(row[2]),
            "class_status": str(row[3]),
            "site_code": site_code,
            "session_count": int(row[4]),
        }
        for row in rows
    ]


def list_course_class_sessions(*, role: str, user_site_code: str | None) -> dict:
    if role == "admin_big":
        available, initially_missing = active_site_state()
        missing = set(initially_missing)
        site_results, errors = read_sites_concurrently(
            available, lambda site: _read_site_classes(site, get_site_database_alias(site)),
        )
        results = [row for site in sorted(site_results) for row in site_results[site]]
        for site, error in errors.items():
            if not isinstance(error, (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError)):
                raise error
            missing.add(site)
        site_codes = sorted(set(available) | missing)
        results.sort(key=lambda row: (row["course_id"], row["site_code"], row["class_name"], row["class_id"]))
        return {
            "scope": "GLOBAL",
            "complete": not missing,
            "site_codes": site_codes,
            "missing_sites": sorted(missing),
            "count": len(results),
            "results": results,
        }

    if role not in {"tu_van", "ke_toan"} or not user_site_code:
        raise PermissionError
    site = normalize_site(user_site_code)
    alias = require_active_site(site)
    results = _read_site_classes(site, alias)
    return {
        "scope": "LOCAL",
        "complete": True,
        "site_codes": [site],
        "missing_sites": [],
        "count": len(results),
        "results": results,
    }
