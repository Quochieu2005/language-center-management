"""Site-local and global read queries for the existing append-only Logs tables."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections

from core.academics.common import AcademicInfrastructureUnavailable, AcademicSiteUnavailable, active_site_state, require_active_site
from core.sites.connections import UnknownSiteError, get_site_database_alias

_VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


class AuditInfrastructureUnavailable(Exception):
    pass


class AuditNotFound(Exception):
    pass


def _read_site(site: str, filters: dict, take: int) -> tuple[int, list[dict]]:
    alias = get_site_database_alias(site)
    where, params = [], []
    if filters.get("ma_tai_khoan"):
        where.append("ma_tai_khoan = %s")
        params.append(filters["ma_tai_khoan"])
    if filters.get("loai_log"):
        where.append("loai_log = %s")
        params.append(filters["loai_log"])
    if filters.get("tu_ngay"):
        where.append("thoi_diem_utc >= %s")
        params.append(datetime.combine(filters["tu_ngay"], time.min, _VIETNAM).astimezone(timezone.utc).replace(tzinfo=None))
    if filters.get("den_ngay"):
        where.append("thoi_diem_utc < %s")
        params.append(datetime.combine(filters["den_ngay"] + timedelta(days=1), time.min, _VIETNAM).astimezone(timezone.utc).replace(tzinfo=None))
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    with connections[alias].cursor() as cursor:
        cursor.execute(f"SELECT COUNT_BIG(*) FROM dbo.Logs {clause}", params)
        count = int(cursor.fetchone()[0])
        cursor.execute(
            f"""
            SELECT ma_log, loai_log, thoi_diem_utc, ma_tai_khoan,
                   hanh_dong, bang_tac_dong, ma_ban_ghi, ket_qua, site_dich
            FROM dbo.Logs {clause}
            ORDER BY thoi_diem_utc DESC, ma_log DESC
            OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
            """,
            [*params, take],
        )
        rows = cursor.fetchall()
    return count, [
        {
            "log_id": str(row[0]), "log_type": str(row[1]),
            "occurred_at": row[2].replace(tzinfo=timezone.utc) if row[2].tzinfo is None else row[2].astimezone(timezone.utc),
            "site_code": site, "account_id": str(row[3]) if row[3] is not None else None,
            "action": str(row[4]) if row[4] is not None else None,
            "affected_table": str(row[5]) if row[5] is not None else None,
            "record_id": str(row[6]) if row[6] is not None else None,
            "result": str(row[7]) if row[7] is not None else None,
            "destination_site": str(row[8]) if row[8] is not None else None,
        }
        for row in rows
    ]


def _local_result(site: str, filters: dict, limit: int, offset: int) -> dict:
    try:
        require_active_site(site)
        count, rows = _read_site(site, filters, offset + limit)
    except AcademicSiteUnavailable as exc:
        raise AuditNotFound from exc
    except (AcademicInfrastructureUnavailable, DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
        return {
            "scope": "LOCAL", "complete": False, "missing_sites": [site],
            "site_codes": [site], "count": 0, "limit": limit, "offset": offset, "results": [],
        }
    rows.sort(key=lambda row: (row["occurred_at"], row["site_code"], row["log_id"]), reverse=True)
    return {
        "scope": "LOCAL", "complete": True, "missing_sites": [], "site_codes": [site],
        "count": count, "limit": limit, "offset": offset, "results": rows[offset:offset + limit],
    }


def list_audit_logs(
    *, role: str, user_site_code: str | None, site_code: str | None = None,
    account_id: str | None = None, log_type: str | None = None,
    from_date=None, to_date=None, limit: int = 20, offset: int = 0,
) -> dict:
    if role not in {"admin_big", "admin_small"}:
        raise PermissionError("Chỉ Admin Big hoặc Admin Small được xem nhật ký.")
    if role == "admin_small":
        own_site = str(user_site_code or "").strip().upper()
        if not own_site or (site_code and site_code.strip().upper() != own_site):
            raise PermissionError("Admin Small chỉ được xem nhật ký của cơ sở mình.")
        requested_site = own_site
    else:
        requested_site = site_code.strip().upper() if site_code else None

    filters = {
        "ma_tai_khoan": account_id, "loai_log": log_type,
        "tu_ngay": from_date, "den_ngay": to_date,
    }
    if requested_site:
        return _local_result(requested_site, filters, limit, offset)

    try:
        available, missing = active_site_state()
    except AcademicInfrastructureUnavailable as exc:
        raise AuditInfrastructureUnavailable from exc
    candidates = tuple(sorted(set(available) | set(missing)))
    unavailable = list(missing)
    sites_to_read = tuple(site for site in available if site in candidates)
    total = 0
    rows: list[dict] = []
    if sites_to_read:
        with ThreadPoolExecutor(max_workers=min(8, len(sites_to_read))) as executor:
            futures = {executor.submit(_read_site, site, filters, offset + limit): site for site in sites_to_read}
            for future in as_completed(futures):
                site = futures[future]
                try:
                    count, site_rows = future.result()
                    total += count
                    rows.extend(site_rows)
                except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
                    unavailable.append(site)

    rows.sort(key=lambda row: (row["occurred_at"], row["site_code"], row["log_id"]), reverse=True)
    return {
        "scope": "GLOBAL", "complete": not unavailable,
        "missing_sites": sorted(set(unavailable)), "site_codes": list(candidates),
        "count": total, "limit": limit, "offset": offset,
        "results": rows[offset:offset + limit],
    }
