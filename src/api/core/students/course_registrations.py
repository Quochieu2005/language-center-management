"""Who registered for a course: students with a class enrollment, and whether they already have a login."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, connections

from core.auth.service_common import active_site_codes, auth_session_alias
from core.sites.connections import get_site_database_alias
from core.students.services import (
    _dict_rows, _local_datetime, _site_code, _translate_infrastructure_errors, _verify_active_site,
)

_ACTIVE_ENROLLMENT = "('da_dang_ky', 'dang_hoc')"


def _website_account_emails(emails: list[str]) -> set[str] | None:
    """Emails that already own a website account (role nguoi_dung); None if the authority cannot answer."""
    if not emails:
        return set()
    try:
        with connections[auth_session_alias()].cursor() as cursor:
            cursor.execute(
                "SELECT LOWER(email) FROM dbo.TaiKhoan WHERE vai_tro = 'nguoi_dung' AND LOWER(email) IN ("
                + ",".join(["%s"] * len(emails)) + ")", emails,
            )
            return {str(row[0]) for row in cursor.fetchall()}
    except DatabaseError:
        return None


@_translate_infrastructure_errors
def list_course_registrations(
    *, site_code: str, pending_only: bool, search: str | None, limit: int, offset: int,
) -> dict[str, Any]:
    site = _site_code(site_code)
    _verify_active_site(site, active_site_codes())
    predicates = ["d.ma_co_so = %s", f"d.trang_thai IN {_ACTIVE_ENROLLMENT}"]
    params: list[Any] = [site]
    if pending_only:
        predicates.append("h.ma_tai_khoan IS NULL")
    if search:
        pattern = f"%{search.strip()}%"
        predicates.append("(h.ho_ten LIKE %s OR h.email LIKE %s OR h.sdt LIKE %s OR l.ten_lop LIKE %s OR k.ten_khoa_hoc LIKE %s)")
        params.extend([pattern] * 5)
    where_sql = " AND ".join(predicates)
    source = (
        "FROM dbo.DangKy AS d "
        "INNER JOIN dbo.HocVien AS h ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so "
        "INNER JOIN dbo.LopHoc AS l ON l.ma_lop = d.ma_lop AND l.ma_co_so = d.ma_co_so "
        "INNER JOIN dbo.KhoaHoc AS k ON k.ma_khoa_hoc = l.ma_khoa_hoc "
    )
    with connections[get_site_database_alias(site)].cursor() as cursor:
        cursor.execute(f"SELECT COUNT_BIG(*) {source} WHERE {where_sql}", params)
        count = int(cursor.fetchone()[0])
        cursor.execute(
            f"""
            SELECT d.ma_dang_ky AS enrollment_id, d.ngay_dang_ky AS enrolled_at, d.trang_thai AS enrollment_status,
                   h.ma_hoc_vien AS student_id, h.slug, h.ma_co_so AS site_code, h.ho_ten AS full_name,
                   h.email, h.sdt AS phone, l.ma_lop AS class_id, l.ten_lop AS class_name,
                   k.ten_khoa_hoc AS course_name,
                   CONVERT(bit, CASE WHEN h.ma_tai_khoan IS NULL THEN 0 ELSE 1 END) AS account_issued,
                   CONVERT(bit, CASE WHEN h.ma_tai_khoan IS NULL AND h.trang_thai = 'dang_hoc'
                       AND NULLIF(LTRIM(RTRIM(h.email)), N'') IS NOT NULL THEN 1 ELSE 0 END) AS account_issue_eligible
            {source}
            WHERE {where_sql}
            ORDER BY d.ngay_dang_ky DESC, d.ma_dang_ky DESC
            OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """,
            [*params, offset, limit],
        )
        rows = _dict_rows(cursor)
    waiting = sorted({str(row["email"]).strip().casefold() for row in rows if not row["account_issued"] and row["email"]})
    holders = _website_account_emails(waiting)
    for row in rows:
        row["enrolled_at"] = _local_datetime(row["enrolled_at"])
        email = str(row["email"] or "").strip().casefold()
        row["has_website_account"] = None if holders is None else (not row["account_issued"] and email in holders)
        if row["account_issue_eligible"]:
            try:
                validate_email(email)
            except ValidationError:
                row["account_issue_eligible"] = False
    return {"site_code": site, "count": count, "limit": limit, "offset": offset, "results": rows}
