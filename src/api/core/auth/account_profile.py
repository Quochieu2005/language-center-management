"""Basic profile of a website account (role ``nguoi_dung``), kept on the authority ``TaiKhoan`` row."""

import json

from django.conf import settings
from django.db import DatabaseError, connections, transaction

from core.auth.service_common import AuthInfrastructureUnavailable, _acquire_named_lock, auth_session_alias


class AccountProfileNotAllowed(Exception):
    pass


_COLUMNS = {
    "full_name": "ho_ten", "birth_date": "ngay_sinh", "gender": "gioi_tinh", "phone": "sdt", "address": "dia_chi",
}


def _row(cursor, account_id: str, lock: bool = False):
    hint = " WITH (UPDLOCK, HOLDLOCK)" if lock else ""
    cursor.execute(
        "SELECT vai_tro, ma_co_so, trang_thai, slug, email, ten_dang_nhap, ho_ten, ngay_sinh, gioi_tinh, sdt, "
        f"dia_chi, avatar_secure_url FROM dbo.TaiKhoan{hint} WHERE ma_tai_khoan = %s", [account_id],
    )
    return cursor.fetchone()


def _profile(row) -> dict:
    if row is None or str(row[0]) != "nguoi_dung" or row[1] is not None or not bool(row[2]):
        raise AccountProfileNotAllowed
    return {
        "slug": str(row[3]), "email": str(row[4]), "username": str(row[5]),
        "full_name": row[6], "birth_date": row[7], "gender": row[8], "phone": row[9], "address": row[10],
        "avatar_secure_url": row[11],
    }


def get_account_profile(user) -> dict:
    try:
        with connections[auth_session_alias()].cursor() as cursor:
            return _profile(_row(cursor, user.account_id))
    except DatabaseError as exc:
        raise AuthInfrastructureUnavailable from exc


def update_account_profile(user, changes: dict, remote_ip: str) -> dict:
    """Write only the authority row; the TaiKhoan outbox trigger queues every site.

    ``phien_ban`` is deliberately not bumped: a profile edit must not revoke the user's sessions.
    """
    alias = auth_session_alias()
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                _acquire_named_lock(cursor, f"qlttnn-account-sync:{user.account_id}")
                current = _profile(_row(cursor, user.account_id, lock=True))
                merged = {key: changes.get(key, current[key]) for key in _COLUMNS}
                cursor.execute(
                    "UPDATE dbo.TaiKhoan SET ho_ten = %s, ngay_sinh = %s, gioi_tinh = %s, sdt = %s, dia_chi = %s, "
                    "cap_nhat_luc = SYSUTCDATETIME() WHERE ma_tai_khoan = %s AND vai_tro = 'nguoi_dung'",
                    [merged["full_name"], merged["birth_date"], merged["gender"], merged["phone"], merged["address"],
                     user.account_id],
                )
                if cursor.rowcount != 1:
                    raise AccountProfileNotAllowed
                cursor.execute(
                    "INSERT dbo.Logs(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
                    "ma_ban_ghi, du_lieu_moi, ip, ket_qua) "
                    "VALUES (CONVERT(nvarchar(120), NEWID()), 'system', %s, %s, 'nguoi_dung_cap_nhat_ho_so', "
                    "'TaiKhoan', %s, %s, %s, 'thanh_cong')",
                    [settings.AUTH_SESSION_SITE_CODE, user.account_id, user.account_id,
                     json.dumps({"fields": sorted(changes)}), str(remote_ip or "")[:45]],
                )
                return _profile(_row(cursor, user.account_id))
    except DatabaseError as exc:
        raise AuthInfrastructureUnavailable from exc
