"""Global and local student-count queries over isolated site databases."""

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections

from core.academics.common import (
    AcademicError,
    AcademicInfrastructureUnavailable,
    active_site_state,
    require_active_site,
    translate_database_errors,
)
from core.academics.tuition import _verify_cashier
from core.sites.connections import UnknownSiteError, get_site_database_alias
from core.sites.fanout import read_sites_concurrently


def _count_staged_transfers(site_results: dict[str, dict], unavailable: list[str]) -> None:
    """Attribute students past ``da_cap_nhat_nguon`` to their destination site.

    Between the source update and destination activation the source row is
    ``da_chuyen_di`` while the destination row is still ``bao_luu``; counting only
    ``dang_hoc`` would drop the student everywhere. Destinations already active are
    skipped so the window after activation is not double counted.
    """
    by_target: dict[str, set[str]] = {}
    for row in site_results.values():
        for student_id, target in row.pop("pending", []):
            by_target.setdefault(target, set()).add(student_id)
    for row in site_results.values():
        row["in_transit_students"] = 0
    targets = [site for site in by_target if site in site_results]
    if not targets:
        return

    def read_active(site: str) -> set[str]:
        ids = sorted(by_target[site])
        placeholders = ", ".join(["%s"] * len(ids))
        with connections[get_site_database_alias(site)].cursor() as cursor:
            cursor.execute(
                "SELECT ma_hoc_vien FROM dbo.HocVien WHERE ma_co_so = %s AND trang_thai = 'dang_hoc' "
                f"AND ma_hoc_vien IN ({placeholders})",
                [site, *ids],
            )
            return {str(row[0]) for row in cursor.fetchall()}

    active_ids, errors = read_sites_concurrently(targets, read_active)
    for site, error in errors.items():
        if not isinstance(error, (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError)):
            raise error
        unavailable.append(site)
    for site, ids in active_ids.items():
        staged = len(by_target[site] - ids)
        site_results[site]["in_transit_students"] = staged
        site_results[site]["active_students"] += staged


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

    def read_count(site: str) -> dict:
        alias = get_site_database_alias(site)
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT COUNT_BIG(*) FROM dbo.HocVien WHERE ma_co_so = %s AND trang_thai = 'dang_hoc'",
                [site],
            )
            count = int(cursor.fetchone()[0])
            # Source already marked da_chuyen_di; destination is still staged until activation.
            cursor.execute(
                "SELECT ma_hoc_vien, co_so_dich FROM dbo.GiaoDichChuyenCoSo "
                "WHERE co_so_nguon = %s AND trang_thai = 'dang_xu_ly' AND buoc_cuoi = 'da_cap_nhat_nguon'",
                [site],
            )
            pending = [(str(row[0]), str(row[1]).strip().upper()) for row in cursor.fetchall()]
        return {"site_code": site, "active_students": count, "pending": pending}

    site_results, errors = read_sites_concurrently(available, read_count)
    unavailable = list(missing)
    for site, error in errors.items():
        if not isinstance(error, (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError)):
            raise error
        unavailable.append(site)
    _count_staged_transfers(site_results, unavailable)
    results = list(site_results.values())
    results.sort(key=lambda row: row["site_code"])
    if not results and unavailable:
        raise AcademicInfrastructureUnavailable
    return {
        "scope": "GLOBAL", "complete": not unavailable,
        "missing_sites": sorted(set(unavailable)), "site_codes": list(available),
        "total_active_students": sum(row["active_students"] for row in results),
        "results": results,
    }


@translate_database_errors
def _tuition_financial_summary_for_site(
    site: str, *, role: str = "admin_big", actor_id: str = "", employee_id: str = "",
) -> dict:
    site = str(site).strip().upper()
    alias = require_active_site(site)
    with connections[alias].cursor() as cursor:
        if role == "ke_toan":
            _verify_cashier(cursor, site, actor_id, employee_id, role)
        cursor.execute(
            """
            SELECT COUNT_BIG(*),
                   COALESCE(SUM(so_tien_phai_dong - giam_gia), 0),
                   COALESCE(SUM(so_tien_da_dong), 0),
                   COALESCE(SUM(so_tien_phai_dong - giam_gia - so_tien_da_dong), 0),
                   COUNT_BIG(CASE WHEN so_tien_phai_dong - giam_gia - so_tien_da_dong > 0 THEN 1 END),
                   (SELECT COALESCE(SUM(so_tien), 0) FROM dbo.PhieuThu
                    WHERE ma_co_so = %s AND loai = 'thu'),
                   (SELECT COALESCE(SUM(so_tien), 0) FROM dbo.PhieuThu
                    WHERE ma_co_so = %s AND loai = 'hoan')
            FROM dbo.HocPhi
            WHERE ma_co_so = %s
            """,
            [site, site, site],
        )
        row = cursor.fetchone()
    return {
        "site_code": site,
        "tuition_accounts": int(row[0]),
        "total_due": int(row[1]),
        "net_collected": int(row[2]),
        "outstanding": int(row[3]),
        "accounts_with_balance": int(row[4]),
        "total_collected": int(row[5]),
        "total_refunded": int(row[6]),
    }


def tuition_financial_summary(
    *, requested_site: str | None = None, role: str = "admin_big",
    actor_id: str = "", employee_id: str = "",
) -> dict:
    if requested_site:
        row = _tuition_financial_summary_for_site(
            requested_site, role=role, actor_id=actor_id, employee_id=employee_id,
        )
        return {
            "scope": "LOCAL", "complete": True, "missing_sites": [],
            "site_codes": [row["site_code"]],
            "totals": {key: value for key, value in row.items() if key != "site_code"},
            "results": [row],
        }

    available, missing = active_site_state()

    site_results, errors = read_sites_concurrently(
        available, _tuition_financial_summary_for_site,
    )
    results = list(site_results.values())
    unavailable = list(missing)
    for site, error in errors.items():
        if not isinstance(error, (AcademicError, ImproperlyConfigured, KeyError, UnknownSiteError)):
            raise error
        unavailable.append(site)
    results.sort(key=lambda row: row["site_code"])
    if not results and unavailable:
        raise AcademicInfrastructureUnavailable
    fields = ("tuition_accounts", "accounts_with_balance", "total_due", "net_collected", "outstanding", "total_collected", "total_refunded")
    return {
        "scope": "GLOBAL", "complete": not unavailable,
        "missing_sites": sorted(set(unavailable)), "site_codes": list(available),
        "totals": {key: sum(row[key] for row in results) for key in fields},
        "results": results,
    }
