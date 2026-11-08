"""Public class discovery and single-site course enrollment."""

from __future__ import annotations

import hashlib

from django.db import connections, transaction
from django.utils import timezone

from core.auth.service_common import _acquire_named_lock, active_site_codes
from core.classes.services import (
    ClassConflict,
    ClassInfrastructureUnavailable,
    ClassNotFound,
    ClassSiteUnavailable,
    _active_site,
    _audit,
    _next_identifier,
    _translate_errors,
    register_student_to_class,
)
from core.sites.connections import get_site_connection, get_site_database_alias
from core.slug_utils import make_slug


@_translate_errors
def list_public_course_classes(*, site_code: str, course_slug: str) -> dict:
    site = site_code.strip().upper()
    with get_site_connection(site).cursor() as cursor:
        _active_site(cursor, site)
        cursor.execute(
            """
            SELECT l.ma_lop, l.ten_lop, l.ngay_khai_giang, l.ngay_ket_thuc,
                   l.lich_hoc, l.gio_bat_dau, l.gio_ket_thuc,
                   l.si_so_toi_da - COALESCE(r.si_so_dang_ky, 0) AS cho_con_lai
            FROM dbo.LopHoc AS l
            INNER JOIN dbo.KhoaHoc AS k ON k.ma_khoa_hoc = l.ma_khoa_hoc
            LEFT JOIN
            (
                SELECT ma_co_so, ma_lop, COUNT_BIG(*) AS si_so_dang_ky
                FROM dbo.DangKy
                WHERE trang_thai IN ('da_dang_ky', 'dang_hoc')
                GROUP BY ma_co_so, ma_lop
            ) AS r ON r.ma_co_so = l.ma_co_so AND r.ma_lop = l.ma_lop
            WHERE l.ma_co_so = %s AND k.slug = %s
              AND l.trang_thai IN ('sap_mo', 'dang_hoc')
              AND (l.ngay_ket_thuc IS NULL OR l.ngay_ket_thuc >= %s)
              AND l.si_so_hien_tai = COALESCE(r.si_so_dang_ky, 0)
              AND l.si_so_toi_da > COALESCE(r.si_so_dang_ky, 0)
            ORDER BY l.ngay_khai_giang, l.ma_lop
            """,
            [site, course_slug, timezone.localdate()],
        )
        rows = cursor.fetchall()
    results = [
        {
            "class_id": str(row[0]), "site_code": site, "name": str(row[1]),
            "start_date": row[2], "end_date": row[3], "schedule": str(row[4]),
            "start_time": row[5], "end_time": row[6], "remaining_seats": int(row[7]),
        }
        for row in rows
    ]
    return {"site_code": site, "course_slug": course_slug, "count": len(results), "results": results}


def _sites_with_email(email: str, site_codes: tuple[str, ...]) -> tuple[str, ...]:
    matches = []
    for site in site_codes:
        with get_site_connection(site).cursor() as cursor:
            cursor.execute(
                "SELECT TOP (1) 1 FROM dbo.HocVien "
                "WHERE LOWER(LTRIM(RTRIM(email))) = %s",
                [email],
            )
            if cursor.fetchone() is not None:
                matches.append(site)
    return tuple(matches)


@_translate_errors
def create_public_enrollment(
    *, site_code: str, class_id: str, full_name: str, email: str,
    phone: str | None, remote_ip: str,
) -> dict:
    """Create a student, local enrollment and tuition in the selected site's transaction."""
    site = site_code.strip().upper()
    sites = active_site_codes()
    if site not in sites:
        raise ClassSiteUnavailable
    # shortcut: global email preflight can race across different site databases; use a shared reservation protocol if strict global uniqueness is required.
    other_matches = tuple(code for code in _sites_with_email(email, sites) if code != site)
    if other_matches:
        raise ClassConflict("Không thể hoàn tất yêu cầu bằng thông tin này. Vui lòng liên hệ cơ sở.")

    alias = get_site_database_alias(site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site)
            lock_key = hashlib.sha256(email.encode("utf-8")).hexdigest()
            _acquire_named_lock(cursor, f"qlttnn:public-enrollment:{site}:{lock_key}")
            cursor.execute(
                "SELECT TOP (2) h.ma_hoc_vien FROM dbo.HocVien AS h WITH (UPDLOCK, HOLDLOCK) "
                "WHERE LOWER(LTRIM(RTRIM(h.email))) = %s",
                [email],
            )
            existing = cursor.fetchall()
            if len(existing) > 1:
                raise ClassInfrastructureUnavailable
            if existing:
                student_id = str(existing[0][0])
                cursor.execute(
                    "SELECT TOP (1) ma_dang_ky FROM dbo.DangKy WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_co_so = %s AND ma_hoc_vien = %s AND ma_lop = %s "
                    "AND trang_thai IN ('da_dang_ky', 'dang_hoc')",
                    [site, student_id, class_id],
                )
                if cursor.fetchone() is None:
                    raise ClassConflict("Không thể hoàn tất yêu cầu bằng thông tin này. Vui lòng liên hệ cơ sở.")
                return {
                    "site_code": site, "class_id": class_id,
                    "accepted": True, "already_registered": True,
                }

            student_id = _next_identifier(cursor, site, "HV", "student")
            slug = make_slug(f"{full_name}-{student_id}", max_length=160)
            cursor.execute(
                """
                INSERT INTO dbo.HocVien
                    (ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, sdt, email,
                     ngay_nhap_hoc, trang_thai)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'dang_hoc')
                """,
                [student_id, slug, site, site, full_name, phone, email, timezone.localdate()],
            )
            _audit(
                cursor, site, None, "dang_ky_cong_khai", "HocVien", student_id, remote_ip,
                after={"slug": slug},
            )
        result = register_student_to_class(
            site_code=site, student_id=student_id, class_id=class_id,
            actor_id=None, remote_ip=remote_ip,
        )
    return {
        "site_code": site, "class_id": class_id,
        "accepted": True, "already_registered": not result["created"],
    }
