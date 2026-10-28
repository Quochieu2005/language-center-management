"""Admin Small self-service profile reads and updates."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.sites.connections import UnknownSiteError, get_site_database_alias
from core.auth.service_common import (
    AdminSmallProfileNotFound,
    AuthInfrastructureUnavailable,
    AuthenticatedUser,
    _next_sequence_number,
)

def _admin_small_profile_cursor(
    site_code: str, account_id: str, slug: str, profile_id: str | None = None
):
    cursor = connections[get_site_database_alias(site_code)].cursor()
    query = """
        SELECT TOP (2) n.ma_nhan_vien, n.ma_co_so, n.ho_ten, n.sdt,
                       t.ten_dang_nhap, t.email, t.slug
        FROM dbo.NhanVien AS n
        INNER JOIN dbo.TaiKhoan AS t ON t.ma_tai_khoan = n.ma_tai_khoan
        WHERE n.ma_tai_khoan = %s AND n.ma_co_so = %s
          AND n.chuc_vu = 'quan_ly_co_so' AND n.trang_thai = 'dang_lam'
          AND t.vai_tro = 'nhan_vien' AND t.ma_co_so = %s AND t.trang_thai = 'hoat_dong'
          AND t.slug = %s
    """
    params: list[Any] = [account_id, site_code, site_code, slug]
    if profile_id is not None:
        query += " AND n.ma_nhan_vien = %s"
        params.append(profile_id)
    cursor.execute(query, params)
    return cursor

def get_admin_small_self_profile(user: AuthenticatedUser, slug: str) -> dict[str, Any]:
    if (
        user.role != "admin_small" or not user.site_code or not user.profile_id
        or slug != user.slug
    ):
        raise AdminSmallProfileNotFound
    try:
        with _admin_small_profile_cursor(
            user.site_code, user.account_id, slug, user.profile_id
        ) as cursor:
            rows = cursor.fetchall()
        if len(rows) != 1:
            raise AdminSmallProfileNotFound
        row = rows[0]
        return {
            "account_id": user.account_id,
            "profile_id": str(row[0]),
            "site_code": str(row[1]).upper(),
            "role": "admin_small",
            "full_name": str(row[2]),
            "phone": str(row[3]) if row[3] is not None else None,
            "username": str(row[4]),
            "email": str(row[5]),
            "slug": str(row[6]),
        }
    except AdminSmallProfileNotFound:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def update_admin_small_self_profile(
    user: AuthenticatedUser, slug: str, updates: dict[str, Any], remote_ip: str
) -> dict[str, Any]:
    if (
        user.role != "admin_small" or not user.site_code or not user.profile_id
        or slug != user.slug
    ):
        raise AdminSmallProfileNotFound
    if not updates or not set(updates).issubset({"full_name", "phone"}):
        raise ValueError("Chỉ được cập nhật họ tên hoặc số điện thoại hồ sơ của chính mình.")

    try:
        alias = get_site_database_alias(user.site_code)
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT n.ho_ten, n.sdt
                    FROM dbo.NhanVien AS n WITH (UPDLOCK, ROWLOCK)
                    INNER JOIN dbo.TaiKhoan AS t WITH (UPDLOCK, ROWLOCK)
                        ON t.ma_tai_khoan = n.ma_tai_khoan
                    WHERE n.ma_tai_khoan = %s AND n.ma_nhan_vien = %s AND n.ma_co_so = %s
                      AND n.chuc_vu = 'quan_ly_co_so' AND n.trang_thai = 'dang_lam'
                      AND t.vai_tro = 'nhan_vien' AND t.ma_co_so = %s AND t.trang_thai = 'hoat_dong'
                      AND t.slug = %s
                    """,
                    [user.account_id, user.profile_id, user.site_code, user.site_code, slug],
                )
                row = cursor.fetchone()
                if row is None:
                    raise AdminSmallProfileNotFound
                full_name = updates.get("full_name", str(row[0]))
                phone = updates.get("phone", str(row[1]) if row[1] is not None else None)
                cursor.execute(
                    """
                    UPDATE dbo.NhanVien
                    SET ho_ten = %s, sdt = %s
                    OUTPUT INSERTED.ma_nhan_vien
                    WHERE ma_tai_khoan = %s AND ma_nhan_vien = %s AND ma_co_so = %s
                      AND chuc_vu = 'quan_ly_co_so' AND trang_thai = 'dang_lam'
                    """,
                    [full_name, phone, user.account_id, user.profile_id, user.site_code],
                )
                if cursor.fetchone() is None:
                    raise AdminSmallProfileNotFound
                audit_id = f"{user.site_code}-NK-{_next_sequence_number(user.site_code, 'Seq_NK'):06d}"
                cursor.execute(
                    """
                    INSERT INTO dbo.NhatKyHeThong
                        (ma_nhat_ky, ma_co_so, ma_tai_khoan, hanh_dong,
                         bang_tac_dong, ma_ban_ghi, ip, ket_qua, ghi_chu)
                    VALUES (%s, %s, %s, 'sua_ho_so_ca_nhan', 'NhanVien', %s, %s,
                            'thanh_cong', N'Admin Small tự cập nhật hồ sơ của chính mình.')
                    """,
                    [audit_id, user.site_code, user.account_id, user.profile_id, remote_ip[:45]],
                )
        return get_admin_small_self_profile(user, slug)
    except AdminSmallProfileNotFound:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
