"""Teacher roster and attendance operations, always confined to one site DB."""

from typing import Any

from django.db import connections, transaction
from django.utils import timezone

from core.academics.common import (
    AcademicConflict,
    AcademicForbidden,
    AcademicInvalid,
    AcademicNotFound,
    acquire_record_lock,
    append_audit,
    next_id,
    require_active_site,
    translate_database_errors,
)
from core.sites.connections import get_site_database_alias
from core.academics.email_reminders import send_monthly_absence_warnings


def _items(cursor) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@translate_database_errors
def list_teacher_classes(*, site_code: str, teacher_id: str) -> list[dict[str, Any]]:
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT l.ma_lop AS class_id, l.ma_co_so AS site_code, l.ten_lop AS name,
                   l.ma_khoa_hoc AS course_id, k.ten_khoa_hoc AS course_name,
                   l.si_so_hien_tai AS current_count, l.si_so_toi_da AS capacity,
                   l.ngay_khai_giang AS start_date, l.ngay_ket_thuc AS end_date,
                   l.trang_thai AS status
            FROM dbo.LopHoc AS l
            INNER JOIN dbo.KhoaHoc AS k ON k.ma_khoa_hoc = l.ma_khoa_hoc
            INNER JOIN dbo.GiaoVien AS g
                ON g.ma_giao_vien = l.ma_giao_vien AND g.ma_co_so = l.ma_co_so
            WHERE l.ma_co_so = %s AND l.ma_giao_vien = %s AND g.trang_thai = 'dang_day'
            ORDER BY l.ngay_khai_giang DESC, l.ma_lop
            """,
            [site_code, teacher_id],
        )
        return _items(cursor)


@translate_database_errors
def list_teacher_sessions(*, site_code: str, teacher_id: str, class_id: str) -> list[dict[str, Any]]:
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT b.ma_buoi AS session_id, b.so_thu_tu AS sequence,
                   b.ngay_hoc AS session_date, b.gio_bat_dau AS start_time,
                   b.gio_ket_thuc AS end_time, b.ma_phong AS room_id,
                   p.ten_phong AS room_name, b.trang_thai AS status, b.ghi_chu AS note
            FROM dbo.BuoiHoc AS b
            INNER JOIN dbo.LopHoc AS l
                ON l.ma_lop = b.ma_lop AND l.ma_co_so = b.ma_co_so
            LEFT JOIN dbo.PhongHoc AS p
                ON p.ma_phong = b.ma_phong AND p.ma_co_so = b.ma_co_so
            WHERE b.ma_co_so = %s AND b.ma_lop = %s
              AND b.ma_giao_vien = %s AND l.ma_giao_vien = %s
            ORDER BY b.ngay_hoc, b.gio_bat_dau, b.so_thu_tu
            """,
            [site_code, class_id, teacher_id, teacher_id],
        )
        return _items(cursor)


@translate_database_errors
def get_attendance_roster(*, site_code: str, teacher_id: str, session_id: str) -> dict[str, Any]:
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT b.ma_buoi, b.ma_lop, b.ngay_hoc, b.trang_thai
            FROM dbo.BuoiHoc AS b
            INNER JOIN dbo.LopHoc AS l
                ON l.ma_lop = b.ma_lop AND l.ma_co_so = b.ma_co_so
            WHERE b.ma_co_so = %s AND b.ma_buoi = %s
              AND b.ma_giao_vien = %s AND l.ma_giao_vien = %s
            """,
            [site_code, session_id, teacher_id, teacher_id],
        )
        session = cursor.fetchone()
        if session is None:
            raise AcademicNotFound
        cursor.execute(
            """
            SELECT d.ma_dang_ky AS enrollment_id, h.ma_hoc_vien AS student_id,
                   h.slug AS student_slug, h.ho_ten AS student_name,
                   d.trang_thai AS enrollment_status,
                   dd.trang_thai AS attendance_status, dd.ghi_chu AS note
            FROM dbo.DangKy AS d
            INNER JOIN dbo.HocVien AS h
                ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
            LEFT JOIN dbo.DiemDanh AS dd
                ON dd.ma_buoi = %s AND dd.ma_dang_ky = d.ma_dang_ky
                 AND dd.ma_co_so = d.ma_co_so
            WHERE d.ma_co_so = %s AND d.ma_lop = %s
              AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
            ORDER BY h.ho_ten, d.ma_dang_ky
            """,
            [session_id, site_code, str(session[1])],
        )
        return {
            "session_id": str(session[0]),
            "class_id": str(session[1]),
            "session_date": session[2],
            "session_status": str(session[3]),
            "site_code": site_code,
            "results": _items(cursor),
        }


@translate_database_errors
def save_attendance_batch(
    *, site_code: str, teacher_id: str, actor_id: str, session_id: str,
    items: list[dict[str, Any]], remote_ip: str,
) -> dict[str, Any]:
    alias = require_active_site(site_code)
    saved: list[dict[str, Any]] = []
    class_id = ""
    session_date = None
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            acquire_record_lock(cursor, f"attendance:{site_code}:{session_id}")
            cursor.execute(
                """
                SELECT b.ma_lop, b.ma_giao_vien, b.ngay_hoc, b.trang_thai
                FROM dbo.BuoiHoc AS b WITH (UPDLOCK, HOLDLOCK)
                INNER JOIN dbo.LopHoc AS l
                    ON l.ma_lop = b.ma_lop AND l.ma_co_so = b.ma_co_so
                WHERE b.ma_co_so = %s AND b.ma_buoi = %s
                  AND b.ma_giao_vien = %s AND l.ma_giao_vien = %s
                """,
                [site_code, session_id, teacher_id, teacher_id],
            )
            session = cursor.fetchone()
            if session is None:
                raise AcademicNotFound
            class_id = str(session[0])
            session_date = session[2]
            if session[2] > timezone.localdate():
                raise AcademicConflict("Không thể điểm danh cho buổi học trong tương lai.")
            if str(session[3]).lower() in {"nghi", "doi_lich"}:
                raise AcademicConflict("Buổi học đã nghỉ hoặc đang đổi lịch, không thể ghi điểm danh.")

            for item in items:
                enrollment_id = item["enrollment_id"]
                cursor.execute(
                    """
                    SELECT h.ma_hoc_vien, h.ho_ten
                    FROM dbo.DangKy AS d WITH (UPDLOCK, HOLDLOCK)
                    INNER JOIN dbo.HocVien AS h
                        ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
                    WHERE d.ma_co_so = %s AND d.ma_dang_ky = %s AND d.ma_lop = %s
                      AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
                    """,
                    [site_code, enrollment_id, str(session[0])],
                )
                student = cursor.fetchone()
                if student is None:
                    raise AcademicInvalid("Có đăng ký không thuộc lớp/buổi học hoặc không còn hiệu lực.")

                cursor.execute(
                    """
                    SELECT ma_diem_danh, trang_thai, ghi_chu
                    FROM dbo.DiemDanh WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_co_so = %s AND ma_buoi = %s AND ma_dang_ky = %s
                    """,
                    [site_code, session_id, enrollment_id],
                )
                current = cursor.fetchone()
                after = {"status": item["status"], "note": item.get("note")}
                if current is None:
                    attendance_id = next_id(cursor, site_code, "attendance")
                    cursor.execute(
                        """
                        INSERT INTO dbo.DiemDanh
                            (ma_diem_danh, ma_co_so, ma_buoi, ma_dang_ky,
                             trang_thai, ghi_chu, ma_tai_khoan_ghi)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        [attendance_id, site_code, session_id, enrollment_id,
                         item["status"], item.get("note"), actor_id],
                    )
                    before = None
                    changed_id = attendance_id
                else:
                    changed_id = str(current[0])
                    before = {"status": str(current[1]), "note": current[2]}
                    cursor.execute(
                        """
                        UPDATE dbo.DiemDanh
                        SET trang_thai = %s, ghi_chu = %s, ma_tai_khoan_ghi = %s
                        WHERE ma_co_so = %s AND ma_diem_danh = %s
                        """,
                        [item["status"], item.get("note"), actor_id, site_code, changed_id],
                    )
                if before != after:
                    append_audit(
                        cursor, site_code=site_code, actor_id=actor_id,
                        action="ghi_diem_danh", table_name="DiemDanh",
                        record_id=changed_id, remote_ip=remote_ip,
                        before=before, after=after,
                    )
                saved.append({
                    "attendance_id": changed_id, "enrollment_id": enrollment_id,
                    "student_id": str(student[0]), "student_name": str(student[1]),
                    **after,
                })
    absent_student_ids = sorted({
        str(row["student_id"])
        for row in saved
        if row.get("status") == "vang_khong_phep"
    })
    alerts = {"status": "not_applicable", "sent_count": 0, "already_sent_count": 0,
              "missing_email_count": 0, "failed_count": 0}
    if absent_student_ids and session_date is not None:
        try:
            alerts = send_monthly_absence_warnings(
                site_code=site_code,
                class_id=class_id,
                student_ids=absent_student_ids,
                month_date=session_date,
                actor_id=actor_id,
            )
        except Exception:  # The attendance commit is final even if notification infrastructure fails.
            alerts = {"status": "unavailable", "sent_count": 0, "already_sent_count": 0,
                      "missing_email_count": 0, "failed_count": len(absent_student_ids)}
    return {
        "session_id": session_id, "site_code": site_code,
        "saved_count": len(saved), "results": saved, "email_alerts": alerts,
    }
