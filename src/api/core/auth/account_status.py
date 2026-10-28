"""Retryable status changes for replicated internal accounts."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, IntegrityError, connections, transaction

from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    _acquire_named_lock,
    _next_sequence_number,
    active_site_codes,
    auth_session_alias,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.notifications.publisher import publish_notification


class AccountStatusTargetNotFound(Exception):
    """The requested internal account or its site-local profile does not exist."""


class AccountStatusConflict(Exception):
    """The requested status transition conflicts with the current profile state."""


@dataclass(frozen=True)
class AccountStatusResult:
    account_id: str
    slug: str
    role: str
    site_code: str
    status: str


_API_TO_DB_STATUS = {"active": "hoat_dong", "inactive": "vo_hieu"}
_DB_TO_API_STATUS = {value: key for key, value in _API_TO_DB_STATUS.items()}
_DB_TO_API_STATUS["khoa"] = "locked"
_ACCOUNT_SELECT = """
    SELECT ma_tai_khoan, ten_dang_nhap, slug, email, mat_khau,
           vai_tro, ma_co_so, trang_thai, phien_ban,
           bat_buoc_doi_mat_khau
    FROM dbo.TaiKhoan
"""


def _normalize_site(value: Any) -> str:
    return str(value or "").strip().upper()


def _read_account_by_slug(slug: str, sites: tuple[str, ...]) -> tuple[Any, ...]:
    copies = []
    for site in sites:
        with get_site_connection(site).cursor() as cursor:
            cursor.execute(_ACCOUNT_SELECT + " WHERE slug = %s", [slug])
            rows = cursor.fetchall()
        if len(rows) > 1:
            raise AuthInfrastructureUnavailable
        copies.append(tuple(rows[0]) if rows else None)
    if not copies or all(row is None for row in copies):
        raise AccountStatusTargetNotFound
    if any(row is None for row in copies) or any(row != copies[0] for row in copies[1:]):
        raise AuthInfrastructureUnavailable
    return copies[0]


def _read_coordinator_account_by_slug(slug: str) -> tuple[Any, ...] | None:
    alias = auth_session_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(_ACCOUNT_SELECT + " WHERE slug = %s", [slug])
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise AuthInfrastructureUnavailable
    return tuple(rows[0]) if rows else None


def _read_profile_status(role: str, account_id: str, site_code: str) -> str:
    alias = get_site_database_alias(site_code)
    with connections[alias].cursor() as cursor:
        if role == "admin_small":
            cursor.execute(
                """
                SELECT TOP (2) chuc_vu, trang_thai
                FROM dbo.NhanVien
                WHERE ma_tai_khoan = %s AND ma_co_so = %s
                """,
                [account_id, site_code],
            )
            rows = cursor.fetchall()
            if len(rows) != 1 or str(rows[0][0]).lower() != "quan_ly_co_so":
                raise AccountStatusTargetNotFound
            return str(rows[0][1]).lower()

        cursor.execute(
            """
            SELECT TOP (2) trang_thai
            FROM dbo.GiaoVien
            WHERE ma_tai_khoan = %s AND ma_co_so = %s
            """,
            [account_id, site_code],
        )
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise AccountStatusTargetNotFound
        return str(rows[0][0]).lower()


def _validate_target(account: tuple[Any, ...], expected_role: str, site_code: str | None) -> str:
    account_id, _username, _slug, _email, _password, raw_role, raw_site, raw_status = account[:8]
    role = str(raw_role).lower()
    actual_site = _normalize_site(raw_site)
    status = str(raw_status).lower()
    if status not in _DB_TO_API_STATUS:
        raise AccountStatusConflict
    if role != ("nhan_vien" if expected_role == "admin_small" else "giao_vien"):
        raise AccountStatusTargetNotFound
    if not actual_site or (site_code and actual_site != _normalize_site(site_code)):
        raise AccountStatusTargetNotFound
    profile_status = _read_profile_status(expected_role, str(account_id), actual_site)
    if profile_status == "nghi_viec" and status == "hoat_dong":
        raise AccountStatusConflict
    if profile_status not in ({"dang_lam"} if expected_role == "admin_small" else {"dang_day", "tam_nghi", "nghi_viec"}):
        raise AccountStatusTargetNotFound
    return actual_site


def _load_pending_job(account_id: str):
    alias = auth_session_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT ma_giao_dich, ma_tai_khoan, ma_nguoi_thuc_hien, ma_co_so,
                   vai_tro_muc_tieu, trang_thai_cu, trang_thai_moi,
                   phien_ban_ban_dau, site_codes_json, trang_thai
            FROM dbo.GiaoDichTrangThaiTaiKhoan
            WHERE ma_tai_khoan = %s AND trang_thai = 'dang_xu_ly'
            """,
            [account_id],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise AuthInfrastructureUnavailable
    return tuple(rows[0]) if rows else None


def _reserve_job(
    account: tuple[Any, ...], actor_id: str, site_code: str,
    role: str, desired_status: str, sites: tuple[str, ...],
) -> tuple[Any, ...] | None:
    alias = auth_session_alias()
    account_id = str(account[0])
    old_status = str(account[7]).lower()
    target_status = _API_TO_DB_STATUS[desired_status]
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _acquire_named_lock(cursor, f"qlttnn-account-status:{account_id}")
            cursor.execute(
                """
                SELECT ma_giao_dich, ma_tai_khoan, ma_nguoi_thuc_hien, ma_co_so,
                       vai_tro_muc_tieu, trang_thai_cu, trang_thai_moi,
                       phien_ban_ban_dau, site_codes_json, trang_thai
                FROM dbo.GiaoDichTrangThaiTaiKhoan WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_tai_khoan = %s AND trang_thai = 'dang_xu_ly'
                """,
                [account_id],
            )
            pending = cursor.fetchone()
            if pending is not None:
                return tuple(pending)
            if old_status == target_status:
                return None
            cursor.execute(
                "SELECT trang_thai, phien_ban FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_tai_khoan = %s",
                [account_id],
            )
            current = cursor.fetchone()
            if current is None or (str(current[0]).lower(), int(current[1])) != (
                old_status, int(account[8])
            ):
                raise AccountStatusConflict
            job_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO dbo.GiaoDichTrangThaiTaiKhoan
                    (ma_giao_dich, ma_tai_khoan, ma_nguoi_thuc_hien, ma_co_so,
                     vai_tro_muc_tieu, trang_thai_cu, trang_thai_moi,
                     phien_ban_ban_dau, site_codes_json, trang_thai)
                VALUES
                    (CONVERT(uniqueidentifier, %s), %s, %s, %s, %s, %s, %s, %s, %s, 'dang_xu_ly')
                """,
                [job_id, account_id, actor_id, site_code, role, old_status,
                 target_status, int(account[8]), json.dumps(sites)],
            )
    return _load_pending_job(account_id)


def _append_sync_event(cursor, job_id: str, site_code: str, account_id: str) -> None:
    event_id = f"{site_code}-DB-{uuid.uuid5(uuid.NAMESPACE_URL, f'{job_id}:{site_code}').hex[:10]}"
    cursor.execute(
        "SELECT bang, ma_ban_ghi, hanh_dong, site_dich, trang_thai "
        "FROM dbo.NhatKyDongBo WHERE ma_dong_bo = %s",
        [event_id],
    )
    event = cursor.fetchone()
    expected = ("TaiKhoan", account_id, "sua", site_code, "thanh_cong")
    if event is not None:
        if tuple(str(value) for value in event) != expected:
            raise AuthInfrastructureUnavailable
        return
    cursor.execute(
        """
        INSERT INTO dbo.NhatKyDongBo
            (ma_dong_bo, bang, ma_ban_ghi, hanh_dong, site_dich, trang_thai)
        VALUES (%s, 'TaiKhoan', %s, 'sua', %s, 'thanh_cong')
        """,
        [event_id, account_id, site_code],
    )


def _append_status_audit(
    cursor, site_code: str, actor_id: str, account_id: str,
    old_status: str, new_status: str, remote_ip: str,
) -> None:
    audit_id = f"{site_code}-NK-{_next_sequence_number(site_code, 'Seq_NK'):06d}"
    cursor.execute(
        """
        INSERT INTO dbo.NhatKyHeThong
            (ma_nhat_ky, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua)
        VALUES (%s, %s, %s, 'doi_trang_thai_tai_khoan', 'TaiKhoan', %s, %s, %s, %s, 'thanh_cong')
        """,
        [audit_id, site_code, actor_id, account_id, old_status, new_status, remote_ip[:45]],
    )


def _apply_job_site(job: tuple[Any, ...], site_code: str, remote_ip: str) -> None:
    job_id, account_id, actor_id, target_site, role, old_status, new_status, version = job[:8]
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT slug, vai_tro, ma_co_so, trang_thai, phien_ban
                FROM dbo.TaiKhoan WITH (UPDLOCK, ROWLOCK)
                WHERE ma_tai_khoan = %s
                """,
                [account_id],
            )
            row = cursor.fetchone()
            if row is None:
                raise AuthInfrastructureUnavailable
            slug, raw_role, raw_site, current_status, current_version = row
            expected_db_role = "nhan_vien" if str(role).lower() == "admin_small" else "giao_vien"
            if str(raw_role).lower() != expected_db_role or _normalize_site(raw_site) != _normalize_site(target_site):
                raise AccountStatusConflict
            current_status, current_version = str(current_status).lower(), int(current_version)
            if current_status == str(old_status).lower() and current_version == int(version):
                cursor.execute(
                    """
                    UPDATE dbo.TaiKhoan
                    SET trang_thai = %s, phien_ban = phien_ban + 1,
                        cap_nhat_luc = SYSUTCDATETIME()
                    WHERE ma_tai_khoan = %s AND trang_thai = %s AND phien_ban = %s
                    """,
                    [new_status, account_id, old_status, version],
                )
                if cursor.rowcount != 1:
                    raise AccountStatusConflict
                _append_sync_event(cursor, str(job_id), site_code, str(account_id))
                _append_status_audit(
                    cursor, site_code, str(actor_id), str(account_id),
                    str(old_status), str(new_status), remote_ip,
                )
            elif current_status == str(new_status).lower() and current_version == int(version) + 1:
                _append_sync_event(cursor, str(job_id), site_code, str(account_id))
            else:
                raise AccountStatusConflict
            if site_code == _normalize_site(target_site):
                notification_category = "teacher" if str(role).lower() == "giao_vien" else "account"
                state_label = "được kích hoạt" if str(new_status).lower() == "hoat_dong" else "bị vô hiệu hóa"
                publish_notification(
                    cursor,
                    site_code=site_code,
                    event_key=f"account-status:{account_id}:{int(version) + 1}",
                    category=notification_category,
                    severity="success" if str(new_status).lower() == "hoat_dong" else "warning",
                    title="Trạng thái tài khoản thay đổi",
                    message=f"Tài khoản {'giáo viên' if notification_category == 'teacher' else 'Admin Small'} tại cơ sở {site_code} {state_label}.",
                    target_path=(
                        f"/admin/teachers?site_code={site_code}"
                        if notification_category == "teacher"
                        else f"/admin/admins?site_code={site_code}"
                    ),
                )


def _complete_job(job: tuple[Any, ...]) -> None:
    job_id, account_id = str(job[0]), str(job[1])
    alias = auth_session_alias()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                UPDATE dbo.PhienDangNhap
                SET thu_hoi_luc_utc = COALESCE(thu_hoi_luc_utc, SYSUTCDATETIME())
                WHERE ma_tai_khoan = %s AND thu_hoi_luc_utc IS NULL
                """,
                [account_id],
            )
            cursor.execute(
                """
                UPDATE dbo.GiaoDichTrangThaiTaiKhoan
                SET trang_thai = 'hoan_tat', cap_nhat_luc_utc = SYSUTCDATETIME(),
                    hoan_tat_luc_utc = SYSUTCDATETIME()
                WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                  AND trang_thai = 'dang_xu_ly'
                """,
                [job_id],
            )
            if cursor.rowcount != 1:
                cursor.execute(
                    "SELECT trang_thai FROM dbo.GiaoDichTrangThaiTaiKhoan "
                    "WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)",
                    [job_id],
                )
                row = cursor.fetchone()
                if row is None or str(row[0]).lower() != "hoan_tat":
                    raise AuthInfrastructureUnavailable


def _resume_job(job: tuple[Any, ...], remote_ip: str) -> None:
    if str(job[9]).lower() == "hoan_tat":
        return
    sites = active_site_codes()
    alias = auth_session_alias()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                UPDATE dbo.GiaoDichTrangThaiTaiKhoan
                SET site_codes_json = %s, cap_nhat_luc_utc = SYSUTCDATETIME()
                WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                  AND trang_thai = 'dang_xu_ly'
                """,
                [json.dumps(sites), str(job[0])],
            )
    resumed = (*job[:8], json.dumps(sites), "dang_xu_ly")
    for site in sites:
        _apply_job_site(resumed, site, remote_ip)
    _complete_job(resumed)


def change_account_status(
    *, slug: str, expected_role: str, desired_status: str, actor_id: str,
    remote_ip: str, site_code: str | None = None,
) -> AccountStatusResult:
    slug = str(slug).strip()
    target_status = str(desired_status).strip().lower()
    if not slug or target_status not in _API_TO_DB_STATUS or not actor_id or not remote_ip:
        raise AccountStatusTargetNotFound
    if expected_role not in {"admin_small", "giao_vien"}:
        raise AccountStatusTargetNotFound
    try:
        for _attempt in range(5):
            sites = active_site_codes()
            coordinator_account = _read_coordinator_account_by_slug(slug)
            if coordinator_account is None:
                raise AccountStatusTargetNotFound
            account_id = str(coordinator_account[0])
            pending = _load_pending_job(account_id)
            if pending is not None:
                _resume_job(pending, remote_ip)
                continue
            account = _read_account_by_slug(slug, sites)
            target_site = _validate_target(account, expected_role, site_code)
            account_id = str(account[0])
            job = _reserve_job(
                account, actor_id, target_site, expected_role, target_status, sites
            )
            if job is None:
                return AccountStatusResult(
                    account_id=account_id,
                    slug=slug,
                    role=expected_role,
                    site_code=target_site,
                    status=target_status,
                )
            _resume_job(job, remote_ip)
        raise AuthInfrastructureUnavailable
    except (AccountStatusTargetNotFound, AccountStatusConflict, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, IntegrityError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
