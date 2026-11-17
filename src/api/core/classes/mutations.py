"""Site-local class updates and safe cancellation."""

from __future__ import annotations

from typing import Any

from django.db import connections, transaction
from django.utils import timezone

from core.auth.service_common import _acquire_named_lock
from core.sites.connections import get_site_database_alias

from .services import (
    ClassConflict,
    ClassNotFound,
    _active_site,
    _audit,
    _translate_errors,
    get_class,
)


@_translate_errors
def update_class(
    *, site_code: str, class_id: str, actor_id: str, remote_ip: str,
    name: str | None = None, capacity: int | None = None,
) -> dict[str, Any]:
    alias = get_site_database_alias(site_code)
    updates: list[str] = []
    values: list[Any] = []
    if name is not None:
        updates.append("ten_lop = %s")
        values.append(name)
    if capacity is not None:
        updates.append("si_so_toi_da = %s")
        values.append(capacity)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site_code)
            _acquire_named_lock(cursor, f"qlttnn:class:{site_code}:{class_id}")
            cursor.execute(
                "SELECT ten_lop, si_so_toi_da, ma_phong, trang_thai "
                "FROM dbo.LopHoc WITH (UPDLOCK, HOLDLOCK) WHERE ma_co_so = %s AND ma_lop = %s",
                [site_code, class_id],
            )
            row = cursor.fetchone()
            if row is None:
                raise ClassNotFound
            old_name, old_capacity, room_id, class_status = str(row[0]), int(row[1]), str(row[2]), str(row[3])
            if class_status in {"ket_thuc", "huy"}:
                raise ClassConflict("Không thể sửa lớp đã kết thúc hoặc đã hủy.")
            cursor.execute(
                "SELECT COUNT_BIG(*), COUNT_BIG(CASE WHEN trang_thai IN ('da_dang_ky', 'dang_hoc') "
                "THEN 1 END) FROM dbo.DangKy WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND ma_lop = %s",
                [site_code, class_id],
            )
            registration_count, active_count = (int(value) for value in cursor.fetchone())
            cursor.execute(
                "SELECT si_so_hien_tai FROM dbo.LopHoc WHERE ma_co_so = %s AND ma_lop = %s",
                [site_code, class_id],
            )
            stored_count = int(cursor.fetchone()[0])
            if stored_count != active_count:
                raise ClassConflict("Sĩ số lưu trong lớp không khớp số đăng ký; cần đối soát trước khi sửa.")
            next_capacity = capacity if capacity is not None else old_capacity
            if next_capacity < active_count:
                raise ClassConflict("Sĩ số tối đa không được thấp hơn số học viên đang đăng ký.")
            if capacity is not None:
                cursor.execute(
                    "SELECT suc_chua FROM dbo.PhongHoc WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_co_so = %s AND ma_phong = %s",
                    [site_code, room_id],
                )
                room = cursor.fetchone()
                if room is None or next_capacity > int(room[0]):
                    raise ClassConflict("Sĩ số tối đa của lớp không được vượt sức chứa phòng.")
            next_name = name if name is not None else old_name
            if next_name == old_name and next_capacity == old_capacity:
                return get_class(site_code=site_code, class_id=class_id)
            cursor.execute(
                f"UPDATE dbo.LopHoc SET {', '.join(updates)} WHERE ma_co_so = %s AND ma_lop = %s",
                [*values, site_code, class_id],
            )
            _audit(
                cursor, site_code, actor_id, "sua", "LopHoc", class_id, remote_ip,
                before={"name": old_name, "capacity": old_capacity},
                after={"name": next_name, "capacity": next_capacity, "registrations": registration_count},
            )
    return get_class(site_code=site_code, class_id=class_id)


@_translate_errors
def delete_class(*, site_code: str, class_id: str, actor_id: str, remote_ip: str) -> dict[str, Any]:
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _active_site(cursor, site_code)
            _acquire_named_lock(cursor, f"qlttnn:class:{site_code}:{class_id}")
            cursor.execute(
                "SELECT ten_lop, trang_thai FROM dbo.LopHoc WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND ma_lop = %s",
                [site_code, class_id],
            )
            row = cursor.fetchone()
            if row is None:
                raise ClassNotFound
            class_name, class_status = str(row[0]), str(row[1])
            if class_status != "sap_mo":
                raise ClassConflict("Chỉ hủy được lớp sắp mở chưa bắt đầu.")
            cursor.execute(
                "SELECT COUNT_BIG(*) FROM dbo.DangKy WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND ma_lop = %s",
                [site_code, class_id],
            )
            if int(cursor.fetchone()[0]):
                raise ClassConflict("Lớp đã có đăng ký; không thể hủy để giữ lịch sử học phí và học tập.")
            cursor.execute(
                "SELECT COUNT_BIG(*), COUNT_BIG(CASE WHEN ngay_hoc <= %s OR trang_thai <> 'du_kien' "
                "THEN 1 END) FROM dbo.BuoiHoc WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND ma_lop = %s",
                [timezone.localdate(), site_code, class_id],
            )
            session_count, protected_sessions = (int(value) for value in cursor.fetchone())
            if protected_sessions:
                raise ClassConflict("Lớp có buổi đã diễn ra hoặc có trạng thái lịch sử; không thể hủy.")
            cursor.execute(
                "UPDATE dbo.LopHoc SET trang_thai = 'huy' "
                "WHERE ma_co_so = %s AND ma_lop = %s AND trang_thai = 'sap_mo'",
                [site_code, class_id],
            )
            if cursor.rowcount != 1:
                raise ClassNotFound
            _audit(
                cursor, site_code, actor_id, "huy", "LopHoc", class_id, remote_ip,
                before={"name": class_name, "status": class_status, "sessions": session_count},
                after={"status": "huy"},
            )
    return {"class_id": class_id, "site_code": site_code, "cancelled": True}
