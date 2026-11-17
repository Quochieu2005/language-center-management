"""Site-local room management operations."""

from __future__ import annotations

from typing import Any

from django.db import connections, transaction

from core.auth.service_common import _acquire_named_lock
from core.classes.services import (
    ClassConflict,
    ClassNotFound,
    _active_site,
    _audit,
    _next_identifier,
    _translate_errors,
)
from core.sites.connections import get_site_connection, get_site_database_alias


@_translate_errors
def list_rooms(
    *, site_code: str, status_filter: str | None, search: str | None, limit: int, offset: int
) -> dict[str, Any]:
    connection = get_site_connection(site_code)
    with connection.cursor() as cursor:
        _active_site(cursor, site_code)
        conditions = ["p.ma_co_so = %s"]
        params: list[Any] = [site_code]
        if status_filter:
            conditions.append("p.trang_thai = %s")
            params.append(status_filter)
        if search:
            conditions.append("p.ten_phong LIKE %s")
            params.append(f"%{search}%")
        where_sql = " AND ".join(conditions)
        cursor.execute(f"SELECT COUNT_BIG(*) FROM dbo.PhongHoc AS p WHERE {where_sql}", params)
        count = int(cursor.fetchone()[0])
        cursor.execute(
            f"""
            SELECT p.ma_phong, p.ma_co_so, p.ten_phong, p.suc_chua, p.trang_thai,
                   COALESCE(room_stats.class_count, 0) AS class_count,
                   COALESCE(room_stats.student_count, 0) AS student_count
            FROM dbo.PhongHoc AS p
            OUTER APPLY (
                SELECT COUNT_BIG(DISTINCT l.ma_lop) AS class_count,
                       COUNT_BIG(DISTINCT h.ma_hoc_vien) AS student_count
                FROM dbo.LopHoc AS l
                LEFT JOIN dbo.DangKy AS d
                    ON d.ma_lop = l.ma_lop AND d.ma_co_so = l.ma_co_so
                   AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
                LEFT JOIN dbo.HocVien AS h
                    ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
                   AND h.trang_thai = 'dang_hoc'
                WHERE l.ma_co_so = p.ma_co_so
                  AND (
                      l.ma_phong = p.ma_phong OR EXISTS (
                          SELECT 1 FROM dbo.BuoiHoc AS b
                          WHERE b.ma_lop = l.ma_lop AND b.ma_co_so = l.ma_co_so
                            AND b.ma_phong = p.ma_phong
                      )
                  )
                  AND l.trang_thai IN ('sap_mo', 'dang_hoc')
            ) AS room_stats
            WHERE {where_sql} ORDER BY p.ten_phong, p.ma_phong
            OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """
            [*params, offset, limit],
        )
        results = [
            {
                "room_id": str(row[0]), "site_code": str(row[1]),
                "name": str(row[2]), "capacity": int(row[3]), "status": str(row[4]),
                "class_count": int(row[5]), "student_count": int(row[6]),
            }
            for row in cursor.fetchall()
        ]
    return {"site_code": site_code, "count": count, "limit": limit, "offset": offset, "results": results}


@_translate_errors
def list_room_rosters(*, site_code: str, room_id: str) -> dict[str, Any]:
    connection = get_site_connection(site_code)
    with connection.cursor() as cursor:
        _active_site(cursor, site_code)
        cursor.execute(
            "SELECT ten_phong FROM dbo.PhongHoc WHERE ma_co_so = %s AND ma_phong = %s",
            [site_code, room_id],
        )
        room = cursor.fetchone()
        if room is None:
            raise ClassNotFound
        cursor.execute(
            """
            SELECT l.ma_lop, l.ten_lop, l.trang_thai,
                   h.ma_hoc_vien, h.slug, h.ho_ten,
                   COUNT_BIG(hp.ma_hoc_phi) AS tuition_count,
                   COALESCE(SUM(hp.so_tien_phai_dong - hp.giam_gia), 0) AS total_due,
                   COALESCE(SUM(hp.so_tien_da_dong), 0) AS amount_paid
            FROM dbo.LopHoc AS l
            LEFT JOIN dbo.DangKy AS d
                ON d.ma_lop = l.ma_lop AND d.ma_co_so = l.ma_co_so
               AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
            LEFT JOIN dbo.HocVien AS h
                ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
               AND h.trang_thai = 'dang_hoc'
            LEFT JOIN dbo.HocPhi AS hp
                ON hp.ma_dang_ky = d.ma_dang_ky AND hp.ma_co_so = d.ma_co_so
            WHERE l.ma_co_so = %s
              AND (
                  l.ma_phong = %s OR EXISTS (
                      SELECT 1 FROM dbo.BuoiHoc AS b
                      WHERE b.ma_lop = l.ma_lop AND b.ma_co_so = l.ma_co_so
                        AND b.ma_phong = %s
                  )
              )
              AND l.trang_thai IN ('sap_mo', 'dang_hoc')
            GROUP BY l.ma_lop, l.ten_lop, l.trang_thai,
                     h.ma_hoc_vien, h.slug, h.ho_ten
            ORDER BY l.ten_lop, h.ho_ten, h.ma_hoc_vien
            """,
            [site_code, room_id, room_id],
        )
        rows = cursor.fetchall()

    classes: dict[str, dict[str, Any]] = {}
    unique_students: set[str] = set()
    for row in rows:
        class_id = str(row[0])
        class_item = classes.setdefault(
            class_id,
            {
                "class_id": class_id,
                "class_name": str(row[1]),
                "status": str(row[2]),
                "student_count": 0,
                "students": [],
            },
        )
        if row[3] is None:
            continue
        tuition_count = int(row[6])
        total_due = int(row[7])
        amount_paid = int(row[8])
        balance = max(0, total_due - amount_paid)
        if tuition_count == 0:
            tuition_status = "chua_co_khoan_phi"
        elif balance == 0:
            tuition_status = "da_dong"
        elif amount_paid > 0:
            tuition_status = "dong_mot_phan"
        else:
            tuition_status = "chua_dong"
        student_id = str(row[3])
        class_item["students"].append(
            {
                "student_id": student_id,
                "student_slug": str(row[4]),
                "student_name": str(row[5]),
                "total_due": total_due,
                "amount_paid": amount_paid,
                "balance": balance,
                "tuition_status": tuition_status,
            }
        )
        class_item["student_count"] += 1
        unique_students.add(student_id)

    return {
        "room_id": room_id,
        "site_code": site_code,
        "room_name": str(room[0]),
        "class_count": len(classes),
        "student_count": len(unique_students),
        "classes": list(classes.values()),
    }


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
    return {"room_id": room_id, "site_code": site_code, "name": name, "capacity": capacity, "status": "hoat_dong"}


@_translate_errors
def update_room(
    *, site_code: str, room_id: str, actor_id: str, remote_ip: str,
    name: str | None = None, capacity: int | None = None, status: str | None = None,
) -> dict[str, Any]:
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site_code)
            cursor.execute(
                "SELECT ten_phong, suc_chua, trang_thai FROM dbo.PhongHoc WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_phong = %s AND ma_co_so = %s",
                [room_id, site_code],
            )
            row = cursor.fetchone()
            if row is None:
                raise ClassNotFound
            old_name, old_capacity, old_status = str(row[0]), int(row[1]), str(row[2])
            new_name = name if name is not None else old_name
            new_capacity = capacity if capacity is not None else old_capacity
            new_status = status if status is not None else old_status

            if new_name.casefold() != old_name.casefold():
                _acquire_named_lock(cursor, f"qlttnn:room-name:{site_code}:{new_name.casefold()}")
                cursor.execute(
                    "SELECT TOP (1) ma_phong FROM dbo.PhongHoc WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_co_so = %s AND LOWER(ten_phong) = LOWER(%s) AND ma_phong <> %s",
                    [site_code, new_name, room_id],
                )
                if cursor.fetchone() is not None:
                    raise ClassConflict("Tên phòng đã được sử dụng tại cơ sở này.")

            if new_capacity != old_capacity:
                cursor.execute(
                    "SELECT TOP (1) ma_lop FROM dbo.LopHoc WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_co_so = %s AND ma_phong = %s AND si_so_toi_da > %s",
                    [site_code, room_id, new_capacity],
                )
                capacity_reference = cursor.fetchone()
                if capacity_reference is None:
                    cursor.execute(
                        "SELECT TOP (1) b.ma_buoi FROM dbo.BuoiHoc b WITH (UPDLOCK, HOLDLOCK) "
                        "JOIN dbo.LopHoc l WITH (UPDLOCK, HOLDLOCK) "
                        "ON l.ma_lop = b.ma_lop AND l.ma_co_so = b.ma_co_so "
                        "WHERE b.ma_co_so = %s AND b.ma_phong = %s AND l.si_so_toi_da > %s",
                        [site_code, room_id, new_capacity],
                    )
                    capacity_reference = cursor.fetchone()
                if capacity_reference is not None:
                    raise ClassConflict("Sức chứa mới thấp hơn sĩ số tối đa của lớp đang tham chiếu phòng.")

            before = {"name": old_name, "capacity": old_capacity, "status": old_status}
            after = {"name": new_name, "capacity": new_capacity, "status": new_status}
            if before != after:
                cursor.execute(
                    "UPDATE dbo.PhongHoc SET ten_phong = %s, suc_chua = %s, trang_thai = %s "
                    "WHERE ma_phong = %s AND ma_co_so = %s",
                    [new_name, new_capacity, new_status, room_id, site_code],
                )
                if cursor.rowcount != 1:
                    raise ClassNotFound
                _audit(cursor, site_code, actor_id, "sua", "PhongHoc", room_id, remote_ip, before=before, after=after)
    return {"room_id": room_id, "site_code": site_code, **after}
