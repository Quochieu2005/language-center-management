"""Read public Blog categories and articles from independent site databases."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone as datetime_timezone

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, close_old_connections, connections

from core.academics.common import AcademicError, active_site_state
from core.sites.connections import UnknownSiteError, get_site_database_alias


class PublicBlogError(Exception):
    def __init__(self, detail: str, *, site_codes=(), missing_sites=(), inconsistent_sites=()):
        super().__init__(detail)
        self.site_codes = tuple(site_codes)
        self.missing_sites = tuple(missing_sites)
        self.inconsistent_sites = tuple(inconsistent_sites)


class PublicBlogUnavailable(PublicBlogError):
    pass


class PublicBlogNotFound(PublicBlogError):
    pass


class PublicBlogConflict(PublicBlogError):
    pass


def _site_state() -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        available, missing = active_site_state()
    except AcademicError as exc:
        raise PublicBlogUnavailable("Không đọc được danh sách cơ sở đang hoạt động.") from exc
    site_codes = tuple(sorted(set(available) | set(missing)))
    if not site_codes:
        raise PublicBlogUnavailable("Không có cơ sở hoạt động để đọc Blog.")
    return site_codes, tuple(sorted(missing))


def _read_site_categories(site_code: str) -> tuple[dict, ...]:
    alias = get_site_database_alias(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT category.slug, category.ten_danh_muc, category.mo_ta,
                   COUNT_BIG(post.ma_bai_viet_blog)
            FROM dbo.DanhMucBlog AS category
            LEFT JOIN dbo.BaiVietBlog AS post
              ON post.ma_danh_muc_blog = category.ma_danh_muc_blog
             AND post.trang_thai = 'da_xuat_ban'
             AND (post.ngay_xuat_ban_utc IS NULL OR post.ngay_xuat_ban_utc <= SYSUTCDATETIME())
            WHERE category.trang_thai = 'hoat_dong'
            GROUP BY category.slug, category.ten_danh_muc, category.mo_ta
            ORDER BY category.slug
            """
        )
        return tuple(
            {
                "slug": str(row[0]),
                "name": str(row[1]),
                "description": None if row[2] is None else str(row[2]),
                "post_count": int(row[3]),
            }
            for row in cursor.fetchall()
        )


def _read_site_article(site_code: str, slug: str) -> dict | None:
    alias = get_site_database_alias(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT post.slug, post.tieu_de, post.tom_tat, post.noi_dung,
                   post.so_phut_doc, post.ngay_xuat_ban_utc,
                   category.slug, category.ten_danh_muc
            FROM dbo.BaiVietBlog AS post
            INNER JOIN dbo.DanhMucBlog AS category
              ON category.ma_danh_muc_blog = post.ma_danh_muc_blog
            WHERE post.slug = %s
              AND post.trang_thai = 'da_xuat_ban'
              AND (post.ngay_xuat_ban_utc IS NULL OR post.ngay_xuat_ban_utc <= SYSUTCDATETIME())
              AND category.trang_thai = 'hoat_dong'
            """,
            [slug],
        )
        row = cursor.fetchone()
    if row is None:
        return None
    published_at = row[5]
    if published_at is not None and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=datetime_timezone.utc)
    return {
        "slug": str(row[0]),
        "title": str(row[1]),
        "excerpt": str(row[2]),
        "content": str(row[3]),
        "reading_time_minutes": int(row[4]),
        "published_at": published_at,
        "category": {"slug": str(row[6]), "name": str(row[7])},
    }


def _read_snapshots(site_codes: tuple[str, ...], reader, initial_missing=()):
    snapshots = {}
    missing_sites = set(initial_missing)
    query_sites = tuple(site for site in site_codes if site not in missing_sites)
    if not query_sites:
        return snapshots, tuple(sorted(missing_sites))

    def read(site_code):
        close_old_connections()
        try:
            return reader(site_code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=min(8, len(query_sites))) as executor:
        futures = {executor.submit(read, site): site for site in query_sites}
        for future in as_completed(futures):
            site = futures[future]
            try:
                snapshots[site] = future.result()
            except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
                missing_sites.add(site)
    return snapshots, tuple(sorted(missing_sites))


def _canonical_site(snapshots: dict) -> str:
    registry_site = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    return registry_site if registry_site in snapshots else sorted(snapshots)[0]


def list_public_blog_categories() -> dict:
    site_codes, initial_missing = _site_state()
    snapshots, missing_sites = _read_snapshots(site_codes, _read_site_categories, initial_missing)
    if not snapshots:
        raise PublicBlogUnavailable(
            "Không đọc được danh mục Blog ở site nào.",
            site_codes=site_codes,
            missing_sites=missing_sites or site_codes,
        )

    canonical_site = _canonical_site(snapshots)
    canonical = snapshots[canonical_site]
    inconsistent_sites = tuple(sorted(
        site for site, categories in snapshots.items() if categories != canonical
    ))
    return {
        "scope": "GLOBAL",
        "complete": not missing_sites and not inconsistent_sites,
        "site_codes": list(site_codes),
        "missing_sites": list(missing_sites),
        "inconsistent_sites": list(inconsistent_sites),
        "count": len(canonical),
        "results": list(canonical),
    }


def get_public_blog_article(slug: str) -> dict:
    normalized_slug = str(slug or "").strip().lower()
    if not normalized_slug or len(normalized_slug) > 160:
        raise PublicBlogNotFound("Không tìm thấy bài Blog đã xuất bản với slug này.")

    site_codes, initial_missing = _site_state()
    if initial_missing:
        raise PublicBlogUnavailable(
            "Thiếu site hoạt động; không thể xác nhận chi tiết Blog toàn cục.",
            site_codes=site_codes,
            missing_sites=initial_missing,
        )
    snapshots, missing_sites = _read_snapshots(
        site_codes, lambda site: _read_site_article(site, normalized_slug)
    )
    if missing_sites or len(snapshots) != len(site_codes):
        raise PublicBlogUnavailable(
            "Không đọc đủ các site hoạt động để xác nhận slug Blog.",
            site_codes=site_codes,
            missing_sites=missing_sites or tuple(sorted(set(site_codes) - set(snapshots))),
        )

    found = {site: article for site, article in snapshots.items() if article is not None}
    if not found:
        raise PublicBlogNotFound(
            "Không tìm thấy bài Blog đã xuất bản với slug này.", site_codes=site_codes
        )

    canonical_site = _canonical_site(found)
    canonical = found[canonical_site]
    inconsistent_sites = tuple(sorted(
        site for site in site_codes if snapshots[site] != canonical
    ))
    if inconsistent_sites:
        raise PublicBlogConflict(
            "Các bản Blog có slug này không nhất quán giữa các site.",
            site_codes=site_codes,
            inconsistent_sites=inconsistent_sites,
        )
    return {"scope": "GLOBAL", "complete": True, "site_codes": list(site_codes), "result": canonical}
