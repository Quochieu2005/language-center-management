"""Global, read-only catalog query for the public course pages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, close_old_connections, connections
from django.utils import timezone

from core.catalog.services import SharedCatalogUnavailable
from core.sites.connections import UnknownSiteError, get_site_database_alias


def _read_site_catalog(site_code: str) -> tuple[tuple[str, str, str], ...]:
    alias = get_site_database_alias(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT ma_co_so, ten_co_so, trang_thai FROM dbo.CoSo ORDER BY ma_co_so")
        return tuple((str(row[0]).upper(), str(row[1]), str(row[2]).lower()) for row in cursor.fetchall())


def _read_site_courses(site_code: str, today) -> tuple[dict, dict]:
    alias = get_site_database_alias(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT k.ma_khoa_hoc, k.slug, k.ma_mon, m.slug, m.ten_mon,
                   k.ten_khoa_hoc, k.trinh_do, k.so_buoi, k.hoc_phi_chuan, k.phien_ban,
                   COALESCE(lop.so_lop_dang_mo, 0)
            FROM dbo.KhoaHoc AS k
            INNER JOIN dbo.MonHoc AS m ON m.ma_mon = k.ma_mon
            LEFT JOIN
            (
                SELECT ma_khoa_hoc, COUNT_BIG(*) AS so_lop_dang_mo
                FROM dbo.LopHoc
                WHERE ma_co_so = %s
                  AND trang_thai IN ('sap_mo', 'dang_hoc')
                  AND si_so_hien_tai < si_so_toi_da
                  AND (ngay_ket_thuc IS NULL OR ngay_ket_thuc >= %s)
                GROUP BY ma_khoa_hoc
            ) AS lop ON lop.ma_khoa_hoc = k.ma_khoa_hoc
            ORDER BY k.ma_khoa_hoc
            """,
            [site_code, today],
        )
        catalog = {}
        openings = {}
        for row in cursor.fetchall():
            course_id = str(row[0])
            catalog[course_id] = {
                "course_id": course_id,
                "slug": str(row[1]),
                "subject_id": str(row[2]),
                "subject_slug": str(row[3]),
                "subject_name": str(row[4]),
                "name": str(row[5]),
                "level": str(row[6]),
                "session_count": int(row[7]),
                "standard_fee": int(row[8]),
                "version": int(row[9]),
            }
            openings[course_id] = int(row[10])
    return catalog, openings


def _read_site_snapshot(site_code: str, today) -> tuple[tuple, dict, dict]:
    close_old_connections()
    try:
        return _read_site_catalog(site_code), *_read_site_courses(site_code, today)
    finally:
        close_old_connections()


def _active_sites() -> tuple[tuple[str, ...], tuple[tuple[str, str, str], ...]]:
    registry_site = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    if not registry_site:
        raise SharedCatalogUnavailable("Chưa cấu hình site dùng để tra danh sách cơ sở.")
    try:
        registry_catalog = _read_site_catalog(registry_site)
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable("Không đọc được danh sách cơ sở đang hoạt động.") from exc
    active_sites = tuple(code for code, _name, state in registry_catalog if state == "hoat_dong")
    if not active_sites or registry_site not in active_sites:
        raise SharedCatalogUnavailable("Không có site hoạt động để đọc danh mục.")
    return active_sites, registry_catalog


def _signature(catalog: dict) -> tuple:
    return tuple(
        tuple(course[key] for key in (
            "course_id", "slug", "subject_id", "subject_slug", "subject_name",
            "name", "level", "session_count", "standard_fee", "version",
        ))
        for course in (catalog[key] for key in sorted(catalog))
    )


def list_public_courses() -> dict:
    """Read active sites independently and merge only in-memory response data."""
    registry_site = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    active_sites, registry_catalog = _active_sites()

    today = timezone.localdate()
    snapshots: dict[str, tuple[tuple, dict, dict]] = {}
    missing_sites: set[str] = set()
    with ThreadPoolExecutor(max_workers=min(8, len(active_sites))) as executor:
        futures = {
            executor.submit(_read_site_snapshot, site, today): site for site in active_sites
        }
        for future in as_completed(futures):
            site = futures[future]
            try:
                snapshots[site] = future.result()
            except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
                missing_sites.add(site)

    if not snapshots:
        raise SharedCatalogUnavailable(
            "Không đọc được CSDL site nào.", missing_sites=tuple(sorted(missing_sites or set(active_sites)))
        )

    canonical_site = registry_site if registry_site in snapshots else sorted(snapshots)[0]
    canonical = snapshots[canonical_site][1]
    canonical_signature = _signature(canonical)
    inconsistent_sites = set()
    for site, (site_catalog, catalog, _openings) in snapshots.items():
        if site_catalog != registry_catalog or _signature(catalog) != canonical_signature:
            inconsistent_sites.add(site)

    site_names = {code: name for code, name, state in registry_catalog if state == "hoat_dong"}
    results = []
    for course_id in sorted(canonical):
        course = canonical[course_id]
        branches = []
        for site in sorted(snapshots):
            _site_catalog, site_catalog, openings = snapshots[site]
            if site in inconsistent_sites or course_id not in site_catalog or not openings.get(course_id):
                continue
            branches.append({
                "site_code": site,
                "site_name": site_names.get(site, site),
                "open_class_count": openings[course_id],
            })
        results.append({**course, "branches": branches})

    return {
        "scope": "GLOBAL",
        "complete": not missing_sites and not inconsistent_sites,
        "site_codes": list(active_sites),
        "missing_sites": sorted(missing_sites),
        "inconsistent_sites": sorted(inconsistent_sites),
        "count": len(results),
        "results": results,
    }
