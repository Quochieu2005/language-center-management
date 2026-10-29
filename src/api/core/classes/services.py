"""SQL Server operations for local class scheduling and student placement."""

from __future__ import annotations

import json
from datetime import date, time, timedelta
from functools import wraps
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction
from django.utils import timezone

from core.auth.service_common import AuthInfrastructureUnavailable, _acquire_named_lock
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


class ClassInfrastructureUnavailable(Exception):
    """The selected site's SQL Server connection or required schema is unavailable."""


class ClassNotFound(Exception):
    """A class or enrollment does not exist at the authorized site."""


class ClassConflict(Exception):
    """The requested class operation conflicts with current data or a schedule."""


class ClassInvalid(Exception):
    """The site-local class request is inconsistent with its related records."""


class ClassSiteUnavailable(Exception):
    """The site is not configured or is not active in the local site catalog."""


def _translate_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ClassInfrastructureUnavailable, ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable):
            raise
        except (
            AuthInfrastructureUnavailable,
            DatabaseError,
            ImproperlyConfigured,
            KeyError,
            UnknownSiteError,
        ) as exc:
            raise ClassInfrastructureUnavailable from exc

    return wrapped


def _active_site(cursor, site_code: str) -> None:
    cursor.execute("SELECT trang_thai FROM dbo.CoSo WHERE ma_co_so = %s", [site_code])
    row = cursor.fetchone()
    if row is None or str(row[0]).lower() != "hoat_dong":
        raise ClassSiteUnavailable


def _next_identifier(cursor, site_code: str, prefix: str, sequence_name: str) -> str:
    sequence_names = {
        "class": "Seq_LH", "session": "Seq_BH", "room": "Seq_PH",
        "enrollment": "Seq_DK", "tuition": "Seq_HP", "audit": "Seq_NK",
    }
    safe_sequence = sequence_names[sequence_name]
    cursor.execute(f"SELECT NEXT VALUE FOR dbo.{safe_sequence}")
    return f"{site_code}-{prefix}-{int(cursor.fetchone()[0]):06d}"


def _audit(
    cursor,
    site_code: str,
    actor_id: str,
    action: str,
    table_name: str,
    record_id: str,
    remote_ip: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    audit_id = _next_identifier(cursor, site_code, "NK", "audit")
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua)
        VALUES (%s, 'system', %s, %s, %s, %s, %s, %s, %s, %s, 'thanh_cong')
        """,
        [
            audit_id, site_code, actor_id, action, table_name, record_id,
            json.dumps(before, ensure_ascii=False) if before is not None else None,
            json.dumps(after, ensure_ascii=False) if after is not None else None,
            remote_ip[:45],
        ],
    )


def _weekday_number(value: date) -> int:
    """Map Python Monday=0 to the API/SQL schedule convention Sunday=1, Monday=2."""
    return (value.weekday() + 1) % 7 + 1


def _session_dates(start: date, end: date, weekdays: list[int], expected_count: int) -> list[date]:
    if expected_count < 1 or expected_count > 500:
        raise ClassInvalid("Số buổi của khóa học phải nằm trong khoảng 1 đến 500.")
    dates: list[date] = []
    current = start
    while current <= end and len(dates) < expected_count:
        if _weekday_number(current) in weekdays:
            dates.append(current)
        current += timedelta(days=1)
    if len(dates) != expected_count:
        raise ClassInvalid("Khoảng ngày đã chọn không đủ buổi theo lịch và số buổi của khóa học.")
    return dates


def _schedule_label(weekdays: list[int]) -> str:
    return ", ".join(f"Thứ {day}" if day > 1 else "Chủ nhật" for day in weekdays)


def _lock_schedule_resources(cursor, site_code: str, resources: set[str], dates: list[date]) -> None:
    lock_names = sorted(
        f"qlttnn:schedule:{site_code}:{resource}:{session_date.isoformat()}"
        for resource in resources
        for session_date in dates
    )
    for lock_name in lock_names:
        _acquire_named_lock(cursor, lock_name)


def _check_schedule_conflicts(
    cursor,
    *,
    site_code: str,
    dates: list[date],
    start_time: time,
    end_time: time,
    teacher_id: str | None,
    room_id: str | None,
    exclude_class_id: str | None = None,
) -> None:
    exclude_clause = "AND ma_lop <> %s" if exclude_class_id is not None else ""
    for session_date in dates:
        cursor.execute(
            f"""
            SELECT TOP (1) ma_lop, ma_giao_vien, ma_phong
            FROM dbo.BuoiHoc WITH (UPDLOCK, HOLDLOCK)
            WHERE ma_co_so = %s AND ngay_hoc = %s AND trang_thai <> 'nghi'
              {exclude_clause}
              AND (gio_bat_dau < %s AND gio_ket_thuc > %s)
              AND ((%s IS NOT NULL AND ma_giao_vien = %s)
                   OR (%s IS NOT NULL AND ma_phong = %s))
            """,
            [site_code, session_date, *([exclude_class_id] if exclude_class_id is not None else []),
             end_time, start_time, teacher_id, teacher_id, room_id, room_id],
        )
        if cursor.fetchone() is not None:
            raise ClassConflict("Giáo viên hoặc phòng đã có buổi học trùng ngày, giờ.")


def _class_select_sql(where_sql: str = "") -> str:
    return f"""
        SELECT l.ma_lop, l.ma_co_so, l.ma_khoa_hoc, k.ten_khoa_hoc,
               l.ma_giao_vien, gv.ho_ten, l.ma_phong, p.ten_phong,
               l.ten_lop, l.si_so_toi_da, l.si_so_hien_tai,
               (SELECT COUNT_BIG(*) FROM dbo.DangKy d
                WHERE d.ma_co_so = l.ma_co_so AND d.ma_lop = l.ma_lop
                  AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')) AS registered_count,
               l.ngay_khai_giang, l.ngay_ket_thuc, l.lich_hoc,
               l.gio_bat_dau, l.gio_ket_thuc, l.trang_thai
        FROM dbo.LopHoc l
        JOIN dbo.KhoaHoc k ON k.ma_khoa_hoc = l.ma_khoa_hoc
        JOIN dbo.GiaoVien gv ON gv.ma_giao_vien = l.ma_giao_vien AND gv.ma_co_so = l.ma_co_so
        JOIN dbo.PhongHoc p ON p.ma_phong = l.ma_phong AND p.ma_co_so = l.ma_co_so
        {where_sql}
    """


def _class_item(row: tuple[Any, ...]) -> dict[str, Any]:
    stored_count = int(row[10])
    registered_count = int(row[11])
    capacity = int(row[9])
    return {
        "class_id": str(row[0]),
        "site_code": str(row[1]),
        "course_id": str(row[2]),
        "course_name": str(row[3]),
        "teacher_id": str(row[4]),
        "teacher_name": str(row[5]),
        "room_id": str(row[6]),
        "room_name": str(row[7]),
        "name": str(row[8]),
        "capacity": capacity,
        "current_count": stored_count,
        "registered_count": registered_count,
        "remaining_seats": max(0, capacity - registered_count),
        "capacity_consistent": stored_count == registered_count,
        "start_date": row[12],
        "end_date": row[13],
        "schedule": str(row[14]),
        "start_time": row[15],
        "end_time": row[16],
        "status": str(row[17]),
    }


@_translate_errors
def list_classes(
    *, site_code: str, status_filter: str | None, search: str | None, limit: int, offset: int
) -> dict[str, Any]:
    connection = get_site_connection(site_code)
    with connection.cursor() as cursor:
        _active_site(cursor, site_code)
        conditions = ["l.ma_co_so = %s"]
        params: list[Any] = [site_code]
        if status_filter:
            conditions.append("l.trang_thai = %s")
            params.append(status_filter)
        if search:
            conditions.append("(l.ten_lop LIKE %s OR k.ten_khoa_hoc LIKE %s OR gv.ho_ten LIKE %s)")
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        where_sql = "WHERE " + " AND ".join(conditions)
        cursor.execute("SELECT COUNT_BIG(*) FROM dbo.LopHoc l "
                       "JOIN dbo.KhoaHoc k ON k.ma_khoa_hoc = l.ma_khoa_hoc "
                       "JOIN dbo.GiaoVien gv ON gv.ma_giao_vien = l.ma_giao_vien AND gv.ma_co_so = l.ma_co_so "
                       + where_sql, params)
        count = int(cursor.fetchone()[0])
        cursor.execute(
            _class_select_sql(where_sql) + " ORDER BY l.ngay_khai_giang DESC, l.ma_lop "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            [*params, offset, limit],
        )
        results = [_class_item(tuple(row)) for row in cursor.fetchall()]
    return {"site_code": site_code, "count": count, "limit": limit, "offset": offset, "results": results}


@_translate_errors
def get_class(*, site_code: str, class_id: str) -> dict[str, Any]:
    connection = get_site_connection(site_code)
    with connection.cursor() as cursor:
        _active_site(cursor, site_code)
        cursor.execute(_class_select_sql("WHERE l.ma_co_so = %s AND l.ma_lop = %s"), [site_code, class_id])
        row = cursor.fetchone()
        if row is None:
            raise ClassNotFound
        result = _class_item(tuple(row))
        cursor.execute(
            "SELECT COUNT_BIG(*) FROM dbo.BuoiHoc WHERE ma_co_so = %s AND ma_lop = %s",
            [site_code, class_id],
        )
        result["session_count"] = int(cursor.fetchone()[0])
    return result


@_translate_errors
def create_class(*, site_code: str, actor_id: str, remote_ip: str, data: dict[str, Any]) -> dict[str, Any]:
    alias = get_site_database_alias(site_code)
    generated_dates: list[date] = []
    schedule = _schedule_label(data["weekdays"])
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site_code)
            cursor.execute(
                "SELECT so_buoi FROM dbo.KhoaHoc WITH (UPDLOCK, HOLDLOCK) WHERE ma_khoa_hoc = %s",
                [data["course_id"]],
            )
            course = cursor.fetchone()
            if course is None:
                raise ClassInvalid("Khóa học không tồn tại ở cơ sở đã chọn.")
            expected_sessions = int(course[0])
            if expected_sessions > 500:
                raise ClassInvalid("Số buổi khóa học vượt giới hạn tạo lịch tự động của API.")
            generated_dates = _session_dates(
                data["start_date"], data["end_date"], data["weekdays"], expected_sessions
            )
            if data["start_date"] < timezone.localdate():
                raise ClassInvalid("Ngày khai giảng không được ở trước ngày hiện tại.")

            cursor.execute(
                "SELECT trang_thai FROM dbo.GiaoVien WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_giao_vien = %s AND ma_co_so = %s",
                [data["teacher_id"], site_code],
            )
            teacher = cursor.fetchone()
            if teacher is None or str(teacher[0]).lower() != "dang_day":
                raise ClassInvalid("Giáo viên không tồn tại tại cơ sở hoặc không ở trạng thái đang dạy.")
            cursor.execute(
                "SELECT suc_chua, trang_thai FROM dbo.PhongHoc WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_phong = %s AND ma_co_so = %s",
                [data["room_id"], site_code],
            )
            room = cursor.fetchone()
            if room is None or str(room[1]).lower() != "hoat_dong":
                raise ClassInvalid("Phòng học không tồn tại tại cơ sở hoặc đang bảo trì.")
            if data["capacity"] > int(room[0]):
                raise ClassInvalid("Sĩ số tối đa của lớp vượt sức chứa phòng học.")

            resources = {f"teacher:{data['teacher_id']}", f"room:{data['room_id']}"}
            _lock_schedule_resources(cursor, site_code, resources, generated_dates)
            _check_schedule_conflicts(
                cursor, site_code=site_code, dates=generated_dates,
                start_time=data["start_time"], end_time=data["end_time"],
                teacher_id=data["teacher_id"], room_id=data["room_id"],
            )

            class_id = _next_identifier(cursor, site_code, "LH", "class")
            cursor.execute(
                """
                INSERT INTO dbo.LopHoc
                    (ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ma_phong, ten_lop,
                     si_so_toi_da, si_so_hien_tai, ngay_khai_giang, ngay_ket_thuc,
                     lich_hoc, gio_bat_dau, gio_ket_thuc, trang_thai)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, 'sap_mo')
                """,
                [
                    class_id, site_code, data["course_id"], data["teacher_id"], data["room_id"],
                    data["name"], data["capacity"], data["start_date"], data["end_date"],
                    schedule, data["start_time"], data["end_time"],
                ],
            )
            for number, session_date in enumerate(generated_dates, start=1):
                session_id = _next_identifier(cursor, site_code, "BH", "session")
                cursor.execute(
                    """
                    INSERT INTO dbo.BuoiHoc
                        (ma_buoi, ma_co_so, ma_lop, so_thu_tu, ngay_hoc,
                         gio_bat_dau, gio_ket_thuc, ma_phong, ma_giao_vien, trang_thai)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'du_kien')
                    """,
                    [
                        session_id, site_code, class_id, number, session_date,
                        data["start_time"], data["end_time"], data["room_id"], data["teacher_id"],
                    ],
                )
            _audit(
                cursor, site_code, actor_id, "tao", "LopHoc", class_id, remote_ip,
                after={
                    "course_id": data["course_id"], "teacher_id": data["teacher_id"],
                    "room_id": data["room_id"], "capacity": data["capacity"],
                    "sessions_created": len(generated_dates),
                },
            )
    result = get_class(site_code=site_code, class_id=class_id)
    result["sessions_created"] = len(generated_dates)
    return result


@_translate_errors
def list_rooms(
    *, site_code: str, status_filter: str | None, search: str | None, limit: int, offset: int
) -> dict[str, Any]:
    connection = get_site_connection(site_code)
    with connection.cursor() as cursor:
        _active_site(cursor, site_code)
        conditions = ["ma_co_so = %s"]
        params: list[Any] = [site_code]
        if status_filter:
            conditions.append("trang_thai = %s")
            params.append(status_filter)
        if search:
            conditions.append("ten_phong LIKE %s")
            params.append(f"%{search}%")
        where_sql = " AND ".join(conditions)
        cursor.execute(f"SELECT COUNT_BIG(*) FROM dbo.PhongHoc WHERE {where_sql}", params)
        count = int(cursor.fetchone()[0])
        cursor.execute(
            f"SELECT ma_phong, ma_co_so, ten_phong, suc_chua, trang_thai "
            f"FROM dbo.PhongHoc WHERE {where_sql} ORDER BY ten_phong, ma_phong "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            [*params, offset, limit],
        )
        results = [
            {
                "room_id": str(row[0]), "site_code": str(row[1]),
                "name": str(row[2]), "capacity": int(row[3]), "status": str(row[4]),
            }
            for row in cursor.fetchall()
        ]
    return {"site_code": site_code, "count": count, "limit": limit, "offset": offset, "results": results}


@_translate_errors
def create_room(*, site_code: str, actor_id: str, remote_ip: str, name: str, capacity: int) -> dict[str, Any]:
    alias = get_site_database_alias(site_code)
    normalized_name = name.strip().casefold()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site_code)
            _acquire_named_lock(cursor, f"qlttnn:room-name:{site_code}:{normalized_name}")
            cursor.execute(
                "SELECT TOP (1) ma_phong FROM dbo.PhongHoc WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND LOWER(ten_phong) = LOWER(%s)",
                [site_code, name],
            )
            if cursor.fetchone() is not None:
                raise ClassConflict("Tên phòng đã được sử dụng tại cơ sở này.")
            room_id = _next_identifier(cursor, site_code, "PH", "room")
            cursor.execute(
                "INSERT INTO dbo.PhongHoc (ma_phong, ma_co_so, ten_phong, suc_chua, trang_thai) "
                "VALUES (%s, %s, %s, %s, 'hoat_dong')",
                [room_id, site_code, name, capacity],
            )
            _audit(
                cursor, site_code, actor_id, "tao", "PhongHoc", room_id, remote_ip,
                after={"name": name, "capacity": capacity, "status": "hoat_dong"},
            )
    return {
        "room_id": room_id, "site_code": site_code, "name": name,
        "capacity": capacity, "status": "hoat_dong",
    }


@_translate_errors
def register_student_to_class(
    *, site_code: str, student_id: str, class_id: str,
    actor_id: str, remote_ip: str,
) -> dict[str, Any]:
    """Create one local enrollment and its unpaid tuition row atomically."""
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site_code)
            # Every operation that can change a student's schedule locks student before class.
            _acquire_named_lock(cursor, f"qlttnn:student:{site_code}:{student_id}")
            _acquire_named_lock(cursor, f"qlttnn:class:{site_code}:{class_id}")
            cursor.execute(
                "SELECT trang_thai FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_hoc_vien = %s AND ma_co_so = %s",
                [student_id, site_code],
            )
            student = cursor.fetchone()
            if student is None:
                raise ClassNotFound("Không tìm thấy học viên tại cơ sở đã chọn.")
            if str(student[0]).lower() != "dang_hoc":
                raise ClassConflict("Chỉ học viên đang học mới được đăng ký lớp.")

            cursor.execute(
                """
                SELECT l.ma_khoa_hoc, l.si_so_hien_tai, l.si_so_toi_da,
                       l.ngay_ket_thuc, l.trang_thai, k.hoc_phi_chuan
                FROM dbo.LopHoc l WITH (UPDLOCK, HOLDLOCK)
                JOIN dbo.KhoaHoc k ON k.ma_khoa_hoc = l.ma_khoa_hoc
                WHERE l.ma_co_so = %s AND l.ma_lop = %s
                """,
                [site_code, class_id],
            )
            target = cursor.fetchone()
            if target is None:
                raise ClassNotFound("Không tìm thấy lớp tại cơ sở đã chọn.")
            course_id = str(target[0])
            if str(target[4]).lower() not in {"sap_mo", "dang_hoc"}:
                raise ClassConflict("Lớp không nhận đăng ký mới.")
            if target[3] is not None and target[3] < timezone.localdate():
                raise ClassConflict("Lớp đã kết thúc.")

            cursor.execute(
                """
                SELECT TOP (1) d.ma_dang_ky, d.ma_lop, d.trang_thai,
                       hp.ma_hoc_phi, hp.so_tien_phai_dong, hp.trang_thai
                FROM dbo.DangKy d WITH (UPDLOCK, HOLDLOCK)
                JOIN dbo.LopHoc existing_class
                  ON existing_class.ma_co_so = d.ma_co_so AND existing_class.ma_lop = d.ma_lop
                LEFT JOIN dbo.HocPhi hp ON hp.ma_co_so = d.ma_co_so AND hp.ma_dang_ky = d.ma_dang_ky
                WHERE d.ma_co_so = %s AND d.ma_hoc_vien = %s
                  AND existing_class.ma_khoa_hoc = %s
                  AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
                """,
                [site_code, student_id, course_id],
            )
            existing = cursor.fetchone()
            if existing is not None:
                if str(existing[1]) == class_id and existing[3] is not None:
                    cursor.execute(
                        "SELECT si_so_hien_tai, si_so_toi_da FROM dbo.LopHoc "
                        "WHERE ma_co_so = %s AND ma_lop = %s",
                        [site_code, class_id],
                    )
                    counts = cursor.fetchone()
                    return {
                        "enrollment_id": str(existing[0]), "student_id": student_id,
                        "class_id": class_id, "course_id": course_id,
                        "tuition_id": str(existing[3]), "amount_due": existing[4],
                        "enrollment_status": str(existing[2]), "tuition_status": str(existing[5]),
                        "site_code": site_code, "current_count": int(counts[0]),
                        "remaining_seats": max(0, int(counts[1]) - int(counts[0])),
                        "created": False,
                    }
                raise ClassConflict("Học viên đã có đăng ký hiệu lực cho khóa học này.")

            cursor.execute(
                "SELECT TOP (1) ma_dang_ky, trang_thai FROM dbo.DangKy WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND ma_hoc_vien = %s AND ma_lop = %s",
                [site_code, student_id, class_id],
            )
            if cursor.fetchone() is not None:
                raise ClassConflict("Đã tồn tại đăng ký cho học viên và lớp này; không thể tạo trùng.")

            cursor.execute(
                "SELECT COUNT_BIG(*) FROM dbo.DangKy WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND ma_lop = %s AND trang_thai IN ('da_dang_ky', 'dang_hoc')",
                [site_code, class_id],
            )
            registered_count = int(cursor.fetchone()[0])
            stored_count, capacity = int(target[1]), int(target[2])
            if registered_count != stored_count:
                raise ClassConflict("Sĩ số lưu trong lớp không khớp số đăng ký; cần đối soát trước khi đăng ký.")
            if registered_count >= capacity:
                raise ClassConflict("Lớp đã đủ sĩ số tối đa.")

            cursor.execute(
                """
                SELECT TOP (1) 1
                FROM dbo.BuoiHoc target_session
                JOIN dbo.DangKy other_enrollment
                  ON other_enrollment.ma_co_so = target_session.ma_co_so
                 AND other_enrollment.ma_hoc_vien = %s
                 AND other_enrollment.ma_lop <> %s
                 AND other_enrollment.trang_thai IN ('da_dang_ky', 'dang_hoc')
                JOIN dbo.BuoiHoc other_session
                  ON other_session.ma_co_so = other_enrollment.ma_co_so
                 AND other_session.ma_lop = other_enrollment.ma_lop
                 AND other_session.ngay_hoc = target_session.ngay_hoc
                WHERE target_session.ma_co_so = %s AND target_session.ma_lop = %s
                  AND target_session.ngay_hoc >= %s
                  AND target_session.trang_thai <> 'nghi' AND other_session.trang_thai <> 'nghi'
                  AND target_session.gio_bat_dau < other_session.gio_ket_thuc
                  AND target_session.gio_ket_thuc > other_session.gio_bat_dau
                """,
                [student_id, class_id, site_code, class_id, timezone.localdate()],
            )
            if cursor.fetchone() is not None:
                raise ClassConflict("Lịch lớp bị trùng với một lớp khác của học viên.")

            cursor.execute(
                "UPDATE dbo.LopHoc SET si_so_hien_tai = si_so_hien_tai + 1 "
                "WHERE ma_co_so = %s AND ma_lop = %s AND si_so_hien_tai < si_so_toi_da",
                [site_code, class_id],
            )
            if cursor.rowcount != 1:
                raise ClassConflict("Lớp vừa hết chỗ; tải lại sĩ số rồi thử lại.")
            enrollment_id = _next_identifier(cursor, site_code, "DK", "enrollment")
            tuition_id = _next_identifier(cursor, site_code, "HP", "tuition")
            amount_due = target[5]
            cursor.execute(
                "INSERT INTO dbo.DangKy (ma_dang_ky, ma_co_so, ma_hoc_vien, ma_lop, trang_thai) "
                "VALUES (%s, %s, %s, %s, 'da_dang_ky')",
                [enrollment_id, site_code, student_id, class_id],
            )
            cursor.execute(
                """
                INSERT INTO dbo.HocPhi
                    (ma_hoc_phi, ma_co_so, ma_dang_ky, so_tien_phai_dong,
                     giam_gia, so_tien_da_dong, trang_thai)
                VALUES (%s, %s, %s, %s, 0, 0, 'chua_dong')
                """,
                [tuition_id, site_code, enrollment_id, amount_due],
            )
            _audit(
                cursor, site_code, actor_id, "dang_ky", "DangKy", enrollment_id, remote_ip,
                after={
                    "student_id": student_id, "class_id": class_id,
                    "course_id": course_id, "tuition_id": tuition_id,
                },
            )
            current_count = registered_count + 1
    return {
        "enrollment_id": enrollment_id, "student_id": student_id,
        "class_id": class_id, "course_id": course_id, "tuition_id": tuition_id,
        "amount_due": amount_due, "enrollment_status": "da_dang_ky",
        "tuition_status": "chua_dong", "site_code": site_code,
        "current_count": current_count, "remaining_seats": capacity - current_count,
        "created": True,
    }


@_translate_errors
def list_class_students(
    *, site_code: str, class_id: str, limit: int, offset: int
) -> dict[str, Any]:
    connection = get_site_connection(site_code)
    with connection.cursor() as cursor:
        _active_site(cursor, site_code)
        cursor.execute(
            "SELECT ma_lop FROM dbo.LopHoc WHERE ma_co_so = %s AND ma_lop = %s",
            [site_code, class_id],
        )
        if cursor.fetchone() is None:
            raise ClassNotFound
        cursor.execute(
            "SELECT COUNT_BIG(*) FROM dbo.DangKy WHERE ma_co_so = %s AND ma_lop = %s "
            "AND trang_thai IN ('da_dang_ky', 'dang_hoc')",
            [site_code, class_id],
        )
        count = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT d.ma_dang_ky, h.ma_hoc_vien, h.slug, h.ho_ten, d.trang_thai, h.trang_thai
            FROM dbo.DangKy d
            JOIN dbo.HocVien h ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
            WHERE d.ma_co_so = %s AND d.ma_lop = %s
              AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
            ORDER BY h.ho_ten, h.ma_hoc_vien
            OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """,
            [site_code, class_id, offset, limit],
        )
        results = [
            {
                "enrollment_id": str(row[0]), "student_id": str(row[1]),
                "student_slug": str(row[2]), "full_name": str(row[3]),
                "enrollment_status": str(row[4]), "student_status": str(row[5]),
            }
            for row in cursor.fetchall()
        ]
    return {
        "class_id": class_id, "site_code": site_code, "count": count,
        "limit": limit, "offset": offset, "results": results,
    }


@_translate_errors
def list_class_sessions(
    *, site_code: str, class_id: str, limit: int, offset: int
) -> dict[str, Any]:
    connection = get_site_connection(site_code)
    with connection.cursor() as cursor:
        _active_site(cursor, site_code)
        cursor.execute(
            "SELECT ma_lop FROM dbo.LopHoc WHERE ma_co_so = %s AND ma_lop = %s",
            [site_code, class_id],
        )
        if cursor.fetchone() is None:
            raise ClassNotFound
        cursor.execute(
            "SELECT COUNT_BIG(*) FROM dbo.BuoiHoc WHERE ma_co_so = %s AND ma_lop = %s",
            [site_code, class_id],
        )
        count = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT b.ma_buoi, b.so_thu_tu, b.ngay_hoc, b.gio_bat_dau, b.gio_ket_thuc,
                   b.ma_phong, p.ten_phong, b.ma_giao_vien, gv.ho_ten, b.trang_thai, b.ghi_chu
            FROM dbo.BuoiHoc b
            JOIN dbo.PhongHoc p ON p.ma_phong = b.ma_phong AND p.ma_co_so = b.ma_co_so
            JOIN dbo.GiaoVien gv ON gv.ma_giao_vien = b.ma_giao_vien AND gv.ma_co_so = b.ma_co_so
            WHERE b.ma_co_so = %s AND b.ma_lop = %s
            ORDER BY b.so_thu_tu
            OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """,
            [site_code, class_id, offset, limit],
        )
        results = [
            {
                "session_id": str(row[0]), "session_number": int(row[1]),
                "date": row[2], "start_time": row[3], "end_time": row[4],
                "room_id": str(row[5]), "room_name": str(row[6]),
                "teacher_id": str(row[7]), "teacher_name": str(row[8]),
                "status": str(row[9]), "note": row[10],
            }
            for row in cursor.fetchall()
        ]
    return {
        "class_id": class_id, "site_code": site_code, "count": count,
        "limit": limit, "offset": offset, "results": results,
    }


@_translate_errors
def assign_class_teacher(
    *, site_code: str, class_id: str, teacher_id: str, actor_id: str, remote_ip: str
) -> dict[str, Any]:
    alias = get_site_database_alias(site_code)
    today = timezone.localdate()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site_code)
            _acquire_named_lock(cursor, f"qlttnn:class:{site_code}:{class_id}")
            cursor.execute(
                """
                SELECT ma_giao_vien, ma_phong, trang_thai
                FROM dbo.LopHoc WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_lop = %s
                """,
                [site_code, class_id],
            )
            class_row = cursor.fetchone()
            if class_row is None:
                raise ClassNotFound
            old_teacher, room_id, class_status = str(class_row[0]), str(class_row[1]), str(class_row[2])
            if class_status in {"ket_thuc", "huy"}:
                raise ClassConflict("Không thể đổi giáo viên cho lớp đã kết thúc hoặc đã hủy.")
            if old_teacher == teacher_id:
                cursor.execute(_class_select_sql("WHERE l.ma_co_so = %s AND l.ma_lop = %s"), [site_code, class_id])
                row = cursor.fetchone()
                result = _class_item(tuple(row))
                cursor.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.BuoiHoc WHERE ma_co_so = %s AND ma_lop = %s",
                    [site_code, class_id],
                )
                result["session_count"] = int(cursor.fetchone()[0])
                result["changed"] = False
                return result
            cursor.execute(
                "SELECT trang_thai FROM dbo.GiaoVien WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_giao_vien = %s AND ma_co_so = %s",
                [teacher_id, site_code],
            )
            teacher = cursor.fetchone()
            if teacher is None or str(teacher[0]).lower() != "dang_day":
                raise ClassInvalid("Giáo viên mới không tồn tại tại cơ sở hoặc không ở trạng thái đang dạy.")
            cursor.execute(
                """
                SELECT ngay_hoc, gio_bat_dau, gio_ket_thuc
                FROM dbo.BuoiHoc WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_lop = %s AND ngay_hoc >= %s
                  AND trang_thai IN ('du_kien', 'doi_lich')
                ORDER BY ngay_hoc, so_thu_tu
                """,
                [site_code, class_id, today],
            )
            future_sessions = [tuple(row) for row in cursor.fetchall()]
            dates = [row[0] for row in future_sessions]
            _lock_schedule_resources(cursor, site_code, {f"teacher:{teacher_id}"}, dates)
            for session_date, start_time, end_time in future_sessions:
                _check_schedule_conflicts(
                    cursor, site_code=site_code, dates=[session_date],
                    start_time=start_time, end_time=end_time,
                    teacher_id=teacher_id, room_id=None, exclude_class_id=class_id,
                )
            before = {"teacher_id": old_teacher}
            cursor.execute(
                "UPDATE dbo.LopHoc SET ma_giao_vien = %s WHERE ma_co_so = %s AND ma_lop = %s",
                [teacher_id, site_code, class_id],
            )
            cursor.execute(
                """
                UPDATE dbo.BuoiHoc SET ma_giao_vien = %s
                WHERE ma_co_so = %s AND ma_lop = %s AND ngay_hoc >= %s
                  AND trang_thai IN ('du_kien', 'doi_lich')
                """,
                [teacher_id, site_code, class_id, today],
            )
            _audit(
                cursor, site_code, actor_id, "phan_cong_giao_vien", "LopHoc", class_id, remote_ip,
                before=before, after={"teacher_id": teacher_id, "future_sessions_updated": len(future_sessions)},
            )
    result = get_class(site_code=site_code, class_id=class_id)
    result["changed"] = True
    return result


def _lock_class_rows(cursor, site_code: str, class_ids: set[str]) -> None:
    for class_id in sorted(class_ids):
        _acquire_named_lock(cursor, f"qlttnn:class:{site_code}:{class_id}")
    for class_id in sorted(class_ids):
        cursor.execute(
            "SELECT ma_lop FROM dbo.LopHoc WITH (UPDLOCK, HOLDLOCK) "
            "WHERE ma_co_so = %s AND ma_lop = %s",
            [site_code, class_id],
        )
        if cursor.fetchone() is None:
            raise ClassNotFound


@_translate_errors
def assign_enrollment_to_class(
    *, site_code: str, enrollment_id: str, target_class_id: str,
    actor_id: str, remote_ip: str,
) -> dict[str, Any]:
    """Move one existing site-local enrollment; protects both class seat counters."""
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site_code)
            _acquire_named_lock(cursor, f"qlttnn:enrollment:{site_code}:{enrollment_id}")
            cursor.execute(
                """
                SELECT d.ma_hoc_vien, d.ma_lop, d.trang_thai, h.trang_thai
                FROM dbo.DangKy d WITH (UPDLOCK, HOLDLOCK)
                JOIN dbo.HocVien h WITH (UPDLOCK, HOLDLOCK)
                  ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
                WHERE d.ma_co_so = %s AND d.ma_dang_ky = %s
                """,
                [site_code, enrollment_id],
            )
            enrollment = cursor.fetchone()
            if enrollment is None:
                raise ClassNotFound
            student_id, old_class_id = str(enrollment[0]), str(enrollment[1])
            enrollment_status, student_status = str(enrollment[2]), str(enrollment[3])
            if enrollment_status not in {"da_dang_ky", "dang_hoc"} or student_status != "dang_hoc":
                raise ClassConflict("Chỉ xếp lớp cho đăng ký đang hoạt động của học viên đang học.")
            if old_class_id == target_class_id:
                cursor.execute(
                    "SELECT si_so_hien_tai, si_so_toi_da FROM dbo.LopHoc "
                    "WHERE ma_co_so = %s AND ma_lop = %s",
                    [site_code, old_class_id],
                )
                counts = cursor.fetchone()
                return {
                    "enrollment_id": enrollment_id, "student_id": student_id,
                    "previous_class_id": old_class_id, "class_id": old_class_id,
                    "previous_class_current_count": int(counts[0]),
                    "previous_class_remaining_seats": max(0, int(counts[1]) - int(counts[0])),
                    "site_code": site_code, "enrollment_status": enrollment_status,
                    "current_count": int(counts[0]),
                    "remaining_seats": max(0, int(counts[1]) - int(counts[0])), "changed": False,
                }

            _acquire_named_lock(cursor, f"qlttnn:student:{site_code}:{student_id}")
            _lock_class_rows(cursor, site_code, {old_class_id, target_class_id})
            cursor.execute(
                """
                SELECT ma_khoa_hoc, si_so_hien_tai, si_so_toi_da, ngay_ket_thuc, trang_thai
                FROM dbo.LopHoc WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_lop = %s
                """,
                [site_code, old_class_id],
            )
            old_class = cursor.fetchone()
            cursor.execute(
                """
                SELECT ma_khoa_hoc, si_so_hien_tai, si_so_toi_da, ngay_khai_giang, ngay_ket_thuc, trang_thai
                FROM dbo.LopHoc WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_lop = %s
                """,
                [site_code, target_class_id],
            )
            target = cursor.fetchone()
            if old_class is None or target is None:
                raise ClassNotFound
            if str(old_class[0]) != str(target[0]):
                raise ClassInvalid("Chỉ được chuyển đăng ký sang lớp cùng khóa học.")
            if str(target[5]).lower() not in {"sap_mo", "dang_hoc"}:
                raise ClassConflict("Lớp đích không nhận thêm học viên.")
            if target[4] is not None and target[4] < timezone.localdate():
                raise ClassConflict("Lớp đích đã kết thúc.")

            for current_class_id, class_row in ((old_class_id, old_class), (target_class_id, target)):
                cursor.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.DangKy WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_co_so = %s AND ma_lop = %s AND trang_thai IN ('da_dang_ky', 'dang_hoc')",
                    [site_code, current_class_id],
                )
                actual_count = int(cursor.fetchone()[0])
                if actual_count != int(class_row[1]):
                    raise ClassConflict("Sĩ số lưu trong lớp không khớp số đăng ký; cần đối soát trước khi xếp lớp.")

            if int(target[1]) >= int(target[2]):
                raise ClassConflict("Lớp đã đủ sĩ số tối đa.")
            cursor.execute(
                "SELECT 1 FROM dbo.DangKy WHERE ma_co_so = %s AND ma_hoc_vien = %s AND ma_lop = %s",
                [site_code, student_id, target_class_id],
            )
            if cursor.fetchone() is not None:
                raise ClassConflict("Học viên đã có đăng ký ở lớp đích.")

            cursor.execute(
                """
                SELECT TOP (1) 1
                FROM dbo.BuoiHoc target_session
                JOIN dbo.DangKy other_enrollment
                  ON other_enrollment.ma_co_so = target_session.ma_co_so
                 AND other_enrollment.ma_hoc_vien = %s
                 AND other_enrollment.ma_lop <> %s
                 AND other_enrollment.trang_thai IN ('da_dang_ky', 'dang_hoc')
                JOIN dbo.BuoiHoc other_session
                  ON other_session.ma_co_so = other_enrollment.ma_co_so
                 AND other_session.ma_lop = other_enrollment.ma_lop
                 AND other_session.ngay_hoc = target_session.ngay_hoc
                WHERE target_session.ma_co_so = %s AND target_session.ma_lop = %s
                  AND target_session.ngay_hoc >= %s
                  AND target_session.trang_thai <> 'nghi' AND other_session.trang_thai <> 'nghi'
                  AND target_session.gio_bat_dau < other_session.gio_ket_thuc
                  AND target_session.gio_ket_thuc > other_session.gio_bat_dau
                """,
                [student_id, old_class_id, site_code, target_class_id, timezone.localdate()],
            )
            if cursor.fetchone() is not None:
                raise ClassConflict("Lịch lớp đích bị trùng với lớp khác của học viên.")

            cursor.execute(
                "UPDATE dbo.LopHoc SET si_so_hien_tai = si_so_hien_tai - 1 "
                "WHERE ma_co_so = %s AND ma_lop = %s AND si_so_hien_tai > 0",
                [site_code, old_class_id],
            )
            if cursor.rowcount != 1:
                raise ClassConflict("Không thể giảm sĩ số lớp hiện tại; dữ liệu cần được đối soát.")
            cursor.execute(
                "UPDATE dbo.LopHoc SET si_so_hien_tai = si_so_hien_tai + 1 "
                "WHERE ma_co_so = %s AND ma_lop = %s AND si_so_hien_tai < si_so_toi_da",
                [site_code, target_class_id],
            )
            if cursor.rowcount != 1:
                raise ClassConflict("Lớp vừa hết chỗ; tải lại sĩ số rồi thử lại.")
            cursor.execute(
                "UPDATE dbo.DangKy SET ma_lop = %s WHERE ma_co_so = %s AND ma_dang_ky = %s",
                [target_class_id, site_code, enrollment_id],
            )
            _audit(
                cursor, site_code, actor_id, "xep_lai_lop", "DangKy", enrollment_id, remote_ip,
                before={"class_id": old_class_id}, after={"class_id": target_class_id},
            )
            new_count = int(target[1]) + 1
            remaining = int(target[2]) - new_count
            previous_count = int(old_class[1]) - 1
            previous_remaining = int(old_class[2]) - previous_count
    return {
        "enrollment_id": enrollment_id, "student_id": student_id,
        "previous_class_id": old_class_id, "class_id": target_class_id,
        "previous_class_current_count": previous_count,
        "previous_class_remaining_seats": previous_remaining,
        "site_code": site_code, "enrollment_status": enrollment_status,
        "current_count": new_count, "remaining_seats": remaining, "changed": True,
    }
