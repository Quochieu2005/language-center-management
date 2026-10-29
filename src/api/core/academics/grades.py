"""Teacher-authorized grade reads, writes, and append-only change history."""

from typing import Any

from django.db import connections, transaction

from core.academics.common import (
    AcademicConflict,
    AcademicInvalid,
    AcademicNotFound,
    acquire_record_lock,
    append_audit,
    next_id,
    require_active_site,
    translate_database_errors,
)
from core.sites.connections import get_site_database_alias


GRADE_TYPES = ("giua_ky", "cuoi_ky", "nghe", "noi", "doc", "viet")


def _dict_rows(cursor) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _teacher_owns_enrollment(cursor, site_code: str, teacher_id: str, enrollment_id: str):
    cursor.execute(
        """
        SELECT d.ma_dang_ky, d.ma_co_so, d.ma_hoc_vien, d.ma_lop, d.trang_thai,
               h.ho_ten, l.ma_giao_vien, l.ten_lop
        FROM dbo.DangKy AS d
        INNER JOIN dbo.HocVien AS h
            ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
        INNER JOIN dbo.LopHoc AS l
            ON l.ma_lop = d.ma_lop AND l.ma_co_so = d.ma_co_so
        INNER JOIN dbo.GiaoVien AS g
            ON g.ma_giao_vien = l.ma_giao_vien AND g.ma_co_so = l.ma_co_so
        WHERE d.ma_co_so = %s AND d.ma_dang_ky = %s AND l.ma_giao_vien = %s
          AND g.trang_thai = 'dang_day'
        """,
        [site_code, enrollment_id, teacher_id],
    )
    return cursor.fetchone()


@translate_database_errors
def list_enrollment_grades(*, site_code: str, teacher_id: str, enrollment_id: str) -> dict[str, Any]:
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        context = _teacher_owns_enrollment(cursor, site_code, teacher_id, enrollment_id)
        if context is None:
            raise AcademicNotFound
        cursor.execute(
            """
            SELECT d.ma_diem AS grade_id, d.loai_diem AS grade_type,
                   d.diem_so AS score, d.ngay_nhap AS entered_at,
                   d.ma_giao_vien_nhap AS entered_by_teacher_id
            FROM dbo.Diem AS d
            WHERE d.ma_co_so = %s AND d.ma_dang_ky = %s
            ORDER BY d.loai_diem
            """,
            [site_code, enrollment_id],
        )
        return {
            "site_code": site_code,
            "enrollment_id": str(context[0]),
            "student_id": str(context[2]),
            "student_name": str(context[5]),
            "class_id": str(context[3]),
            "class_name": str(context[7]),
            "results": _dict_rows(cursor),
        }


@translate_database_errors
def upsert_enrollment_grade(
    *, site_code: str, teacher_id: str, actor_id: str, enrollment_id: str,
    grade_type: str, score, remote_ip: str,
) -> dict[str, Any]:
    if grade_type not in GRADE_TYPES:
        raise AcademicInvalid("Loại điểm không nằm trong danh mục được hỗ trợ.")
    alias = require_active_site(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            acquire_record_lock(cursor, f"grade:{site_code}:{enrollment_id}:{grade_type}")
            context = _teacher_owns_enrollment(cursor, site_code, teacher_id, enrollment_id)
            if context is None:
                raise AcademicNotFound
            if str(context[4]).lower() not in {"da_dang_ky", "dang_hoc", "hoan_thanh"}:
                raise AcademicConflict("Chỉ cập nhật điểm cho đăng ký còn hiệu lực hoặc đã hoàn thành.")
            cursor.execute(
                """
                SELECT ma_diem, diem_so, ma_giao_vien_nhap
                FROM dbo.Diem WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_dang_ky = %s AND loai_diem = %s
                """,
                [site_code, enrollment_id, grade_type],
            )
            current = cursor.fetchone()
            if current is None:
                grade_id = next_id(cursor, site_code, "grade")
                cursor.execute(
                    """
                    INSERT INTO dbo.Diem
                        (ma_diem, ma_co_so, ma_dang_ky, loai_diem, diem_so, ma_giao_vien_nhap)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [grade_id, site_code, enrollment_id, grade_type, score, teacher_id],
                )
                before = None
            else:
                grade_id = str(current[0])
                before = {
                    "score": str(current[1]), "grade_type": grade_type,
                    "teacher_id": str(current[2]),
                }
            after = {"score": str(score), "grade_type": grade_type, "teacher_id": teacher_id}
            if before != after:
                if current is not None:
                    cursor.execute(
                        """
                        UPDATE dbo.Diem
                        SET diem_so = %s, ngay_nhap = SYSUTCDATETIME(), ma_giao_vien_nhap = %s
                        WHERE ma_co_so = %s AND ma_diem = %s
                        """,
                        [score, teacher_id, site_code, grade_id],
                    )
                append_audit(
                    cursor, site_code=site_code, actor_id=actor_id,
                    action="cap_nhat_diem", table_name="Diem", record_id=grade_id,
                    remote_ip=remote_ip, before=before, after=after,
                )
    return {
        "grade_id": grade_id, "site_code": site_code,
        "enrollment_id": enrollment_id, "grade_type": grade_type,
        "score": score, "entered_by_teacher_id": teacher_id,
    }


@translate_database_errors
def list_grade_history(*, site_code: str, teacher_id: str, enrollment_id: str) -> dict[str, Any]:
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        context = _teacher_owns_enrollment(cursor, site_code, teacher_id, enrollment_id)
        if context is None:
            raise AcademicNotFound
        cursor.execute(
            """
            SELECT l.ma_log AS log_id, l.thoi_diem_utc AS occurred_at,
                   l.ma_tai_khoan AS actor_id, l.hanh_dong AS action,
                   l.ma_ban_ghi AS grade_id, l.du_lieu_cu AS before_json,
                   l.du_lieu_moi AS after_json
            FROM dbo.Logs AS l
            INNER JOIN dbo.Diem AS d ON d.ma_diem = l.ma_ban_ghi
            WHERE l.loai_log = 'system' AND l.bang_tac_dong = 'Diem'
              AND l.ma_co_so = %s
              AND d.ma_co_so = %s AND d.ma_dang_ky = %s
            ORDER BY l.thoi_diem_utc DESC, l.ma_log DESC
            """,
            [site_code, site_code, enrollment_id],
        )
        return {
            "site_code": site_code, "enrollment_id": enrollment_id,
            "count": 0, "results": _dict_rows(cursor),
        }
