"""Global and local student-count queries over isolated site databases."""

from django.db import connections
from django.db import DatabaseError
from django.core.exceptions import ImproperlyConfigured

from core.academics.common import (
    AcademicInfrastructureUnavailable,
    AcademicNotFound,
    active_site_state,
    require_active_site,
    translate_database_errors,
)
from core.sites.connections import get_site_database_alias
from core.sites.connections import UnknownSiteError


@translate_database_errors
def student_counts_by_site(*, requested_site: str | None = None) -> dict:
    if requested_site:
        site = str(requested_site).strip().upper()
        alias = require_active_site(site)
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT COUNT_BIG(*) FROM dbo.HocVien WHERE ma_co_so = %s AND trang_thai = 'dang_hoc'",
                [site],
            )
            count = int(cursor.fetchone()[0])
        return {
            "scope": "LOCAL", "complete": True, "missing_sites": [],
            "site_codes": [site], "total_active_students": count,
            "results": [{"site_code": site, "active_students": count}],
        }

    available, missing = active_site_state()
    results = []
    unavailable = list(missing)
    for site in available:
        try:
            alias = get_site_database_alias(site)
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.HocVien WHERE ma_co_so = %s AND trang_thai = 'dang_hoc'",
                    [site],
                )
                results.append({"site_code": site, "active_students": int(cursor.fetchone()[0])})
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
            unavailable.append(site)
    results.sort(key=lambda row: row["site_code"])
    if not results and unavailable:
        raise AcademicInfrastructureUnavailable
    return {
        "scope": "GLOBAL", "complete": not unavailable,
        "missing_sites": sorted(set(unavailable)), "site_codes": list(available),
        "total_active_students": sum(row["active_students"] for row in results),
        "results": results,
    }
