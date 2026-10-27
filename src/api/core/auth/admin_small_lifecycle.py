"""Admin Small account provisioning, sync, and deactivation workflows."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import DatabaseError, connections, transaction

from core.slug_utils import make_slug
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.auth.service_common import (
    AdminSmallAccountConflict,
    AdminSmallDeactivationResult,
    AdminSmallDeleteConflict,
    AdminSmallProfileNotFound,
    AdminSmallProvisioningResult,
    AdminSmallSiteUnavailable,
    AdminSmallTargetNotFound,
    AuthInfrastructureUnavailable,
    AuthenticatedUser,
    _acquire_named_lock,
    _digest,
    _next_sequence_number,
    _replicated_account,
    _replicated_account_by_id,
    _resolve_principal,
    active_site_codes,
    auth_session_alias,
    auth_session_site_code,
    logger,
)

def _require_admin_small_email_configuration() -> str:
    temporary_password = settings.ADMIN_SMALL_TEMP_PASSWORD
    if not temporary_password or len(temporary_password) > 128:
        raise AuthInfrastructureUnavailable
    if "console.EmailBackend" in settings.EMAIL_BACKEND:
        raise AuthInfrastructureUnavailable
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or not settings.DEFAULT_FROM_EMAIL:
        raise AuthInfrastructureUnavailable
    return temporary_password

def _next_admin_small_account_id(target_site: str, site_codes: tuple[str, ...]) -> str:
    """Allocate an unused site-prefixed account ID, tolerating older sequence state."""
    for _ in range(1000):
        candidate = f"{target_site}-TK-{_next_sequence_number(target_site, 'Seq_TK'):06d}"
        exists = False
        try:
            for site_code in site_codes:
                with get_site_connection(site_code).cursor() as cursor:
                    cursor.execute(
                        "SELECT CASE WHEN EXISTS "
                        "(SELECT 1 FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s) "
                        "THEN 1 ELSE 0 END",
                        [candidate],
                    )
                    if int(cursor.fetchone()[0]):
                        exists = True
                        break
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
            raise AuthInfrastructureUnavailable from exc
        if not exists:
            return candidate
    raise AuthInfrastructureUnavailable

def _next_admin_small_employee_id(target_site: str) -> str:
    """Allocate an unused local employee ID even if the sequence trails existing rows."""
    for _ in range(1000):
        candidate = f"{target_site}-NV-{_next_sequence_number(target_site, 'Seq_NV'):06d}"
        try:
            with get_site_connection(target_site).cursor() as cursor:
                cursor.execute(
                    "SELECT CASE WHEN EXISTS "
                    "(SELECT 1 FROM dbo.NhanVien WHERE ma_nhan_vien = %s) "
                    "THEN 1 ELSE 0 END",
                    [candidate],
                )
                if not int(cursor.fetchone()[0]):
                    return candidate
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
            raise AuthInfrastructureUnavailable from exc
    raise AuthInfrastructureUnavailable

def _load_admin_small_deactivation(account_id: str):
    alias = auth_session_alias()
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT ma_tai_khoan, ma_co_so, ma_admin_big, phien_ban_ban_dau,
                       site_codes_json, trang_thai, ma_giao_dich
                FROM dbo.GiaoDichVoHieuHoaAdminSmall
                WHERE ma_tai_khoan = %s
                """,
                [account_id],
            )
            rows = cursor.fetchall()
        if len(rows) > 1:
            raise AuthInfrastructureUnavailable
        return tuple(rows[0]) if rows else None
    except AuthInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _insert_admin_small_deactivation_sync_event(
    cursor, site_code: str, account_id: str, job_id: str
) -> None:
    event_id = f"{site_code}-DB-{uuid.uuid5(uuid.NAMESPACE_URL, f'{job_id}:{site_code}').hex[:10]}"
    cursor.execute(
        """
        SELECT bang, ma_ban_ghi, hanh_dong, site_dich, trang_thai
        FROM dbo.NhatKyDongBo
        WHERE ma_dong_bo = %s
        """,
        [event_id],
    )
    existing = cursor.fetchone()
    expected = ("TaiKhoan", account_id, "sua", site_code, "thanh_cong")
    if existing is not None:
        if tuple(str(value) for value in existing) != expected:
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

def _deactivate_admin_small_replica(
    site_code: str,
    account_id: str,
    target_site: str,
    expected_version: int,
    admin_big_id: str,
    remote_ip: str,
    job_id: str,
) -> None:
    alias = get_site_database_alias(site_code)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT vai_tro, ma_co_so, trang_thai, phien_ban
                    FROM dbo.TaiKhoan WITH (UPDLOCK, ROWLOCK)
                    WHERE ma_tai_khoan = %s
                    """,
                    [account_id],
                )
                account = cursor.fetchone()
                if account is None:
                    raise AuthInfrastructureUnavailable
                role, account_site, account_status, version = (
                    str(account[0]).lower(),
                    str(account[1]).upper() if account[1] else None,
                    str(account[2]).lower(),
                    int(account[3]),
                )
                if role != "nhan_vien" or account_site != target_site:
                    raise AdminSmallDeleteConflict

                if account_status == "hoat_dong" and version == expected_version:
                    cursor.execute(
                        """
                        UPDATE dbo.TaiKhoan
                        SET trang_thai = 'vo_hieu', phien_ban = phien_ban + 1,
                            cap_nhat_luc = SYSUTCDATETIME()
                        OUTPUT INSERTED.phien_ban
                        WHERE ma_tai_khoan = %s AND vai_tro = 'nhan_vien'
                          AND ma_co_so = %s AND trang_thai = 'hoat_dong' AND phien_ban = %s
                        """,
                        [account_id, target_site, expected_version],
                    )
                    updated_version = cursor.fetchone()
                    if updated_version is None or int(updated_version[0]) != expected_version + 1:
                        raise AdminSmallDeleteConflict
                elif account_status == "vo_hieu" and version == expected_version + 1:
                    pass  # Retry after a prior site commit is safe and idempotent.
                else:
                    raise AdminSmallDeleteConflict

                if site_code == target_site:
                    cursor.execute(
                        """
                        SELECT TOP (2) ma_nhan_vien, trang_thai
                        FROM dbo.NhanVien WITH (UPDLOCK, ROWLOCK)
                        WHERE ma_tai_khoan = %s AND ma_co_so = %s
                          AND chuc_vu = 'quan_ly_co_so'
                        """,
                        [account_id, target_site],
                    )
                    profiles = cursor.fetchall()
                    if len(profiles) != 1:
                        raise AdminSmallDeleteConflict
                    employee_id, employee_status = str(profiles[0][0]), str(profiles[0][1]).lower()
                    if employee_status == "dang_lam":
                        cursor.execute(
                            """
                            UPDATE dbo.NhanVien
                            SET trang_thai = 'nghi_viec'
                            OUTPUT INSERTED.ma_nhan_vien
                            WHERE ma_tai_khoan = %s AND ma_nhan_vien = %s AND ma_co_so = %s
                              AND chuc_vu = 'quan_ly_co_so' AND trang_thai = 'dang_lam'
                            """,
                            [account_id, employee_id, target_site],
                        )
                        if cursor.fetchone() is None:
                            raise AdminSmallDeleteConflict
                    elif employee_status != "nghi_viec":
                        raise AdminSmallDeleteConflict

                    cursor.execute(
                        """
                        SELECT COUNT_BIG(*)
                        FROM dbo.NhatKyHeThong
                        WHERE ma_co_so = %s AND ma_tai_khoan = %s
                          AND hanh_dong = 'vo_hieu_hoa_admin_small'
                          AND ma_ban_ghi = %s AND ket_qua = 'thanh_cong'
                        """,
                        [target_site, admin_big_id, account_id],
                    )
                    if int(cursor.fetchone()[0]) == 0:
                        audit_id = f"{site_code}-NK-{_next_sequence_number(site_code, 'Seq_NK'):06d}"
                        cursor.execute(
                            """
                            INSERT INTO dbo.NhatKyHeThong
                                (ma_nhat_ky, ma_co_so, ma_tai_khoan, hanh_dong,
                                 bang_tac_dong, ma_ban_ghi, ip, ket_qua, ghi_chu)
                            VALUES (%s, %s, %s, 'vo_hieu_hoa_admin_small', 'TaiKhoan', %s,
                                    %s, 'thanh_cong', N'Admin Big vo hieu hoa tai khoan Admin Small.')
                            """,
                            [audit_id, target_site, admin_big_id, account_id, remote_ip[:45]],
                        )
                else:
                    cursor.execute(
                        "SELECT COUNT_BIG(*) FROM dbo.NhanVien WHERE ma_tai_khoan = %s",
                        [account_id],
                    )
                    if int(cursor.fetchone()[0]) > 0:
                        raise AdminSmallDeleteConflict

                if site_code == auth_session_site_code():
                    cursor.execute(
                        """
                        UPDATE dbo.PhienDangNhap
                        SET thu_hoi_luc_utc = COALESCE(thu_hoi_luc_utc, SYSUTCDATETIME())
                        WHERE ma_tai_khoan = %s AND thu_hoi_luc_utc IS NULL
                        """,
                        [account_id],
                    )

                _insert_admin_small_deactivation_sync_event(cursor, site_code, account_id, job_id)
    except (AdminSmallDeleteConflict, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _complete_admin_small_deactivation(account_id: str) -> None:
    alias = auth_session_alias()
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT trang_thai
                    FROM dbo.GiaoDichVoHieuHoaAdminSmall WITH (UPDLOCK, ROWLOCK)
                    WHERE ma_tai_khoan = %s
                    """,
                    [account_id],
                )
                row = cursor.fetchone()
                if row is None:
                    raise AuthInfrastructureUnavailable
                if str(row[0]).lower() == "hoan_tat":
                    return
                if str(row[0]).lower() != "dang_xu_ly":
                    raise AdminSmallDeleteConflict

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
                    UPDATE dbo.GiaoDichVoHieuHoaAdminSmall
                    SET trang_thai = 'hoan_tat', cap_nhat_luc_utc = SYSUTCDATETIME(),
                        hoan_tat_luc_utc = SYSUTCDATETIME()
                    WHERE ma_tai_khoan = %s AND trang_thai = 'dang_xu_ly'
                    """,
                    [account_id],
                )
    except AuthInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def delete_admin_small(account_id: str, admin_big_id: str, remote_ip: str) -> AdminSmallDeactivationResult:
    """Soft-deactivate one Admin Small across its account replicas with retryable forward recovery."""
    normalized_id = str(account_id).strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,24}", normalized_id) or not remote_ip:
        raise AdminSmallTargetNotFound

    job = _load_admin_small_deactivation(normalized_id)
    if job is None:
        sites = active_site_codes()
        coordinator_alias = auth_session_alias()
        try:
            with transaction.atomic(using=coordinator_alias):
                with connections[coordinator_alias].cursor() as cursor:
                    _acquire_named_lock(cursor, f"qlttnn-admin-small-deactivate:{normalized_id}")
                    cursor.execute(
                        """
                        SELECT ma_tai_khoan, ma_co_so, ma_admin_big, phien_ban_ban_dau,
                               site_codes_json, trang_thai, ma_giao_dich
                        FROM dbo.GiaoDichVoHieuHoaAdminSmall
                        WHERE ma_tai_khoan = %s
                        """,
                        [normalized_id],
                    )
                    job_row = cursor.fetchone()
                    if job_row is None:
                        account = _replicated_account_by_id(normalized_id, sites)
                        if account is None or str(account[5]).lower() != "nhan_vien":
                            raise AdminSmallTargetNotFound
                        target_site = str(account[6]).upper() if account[6] else None
                        if not target_site or target_site not in sites:
                            raise AdminSmallTargetNotFound
                        principal = _resolve_principal(account, sites)
                        if principal is None or principal.role != "admin_small":
                            # A previously disabled account is distinguishable from a non-manager below.
                            with get_site_connection(target_site).cursor() as profile_cursor:
                                profile_cursor.execute(
                                    """
                                    SELECT TOP (2) ma_nhan_vien
                                    FROM dbo.NhanVien
                                    WHERE ma_tai_khoan = %s AND ma_co_so = %s
                                      AND chuc_vu = 'quan_ly_co_so'
                                    """,
                                    [normalized_id, target_site],
                                )
                                existing_profiles = profile_cursor.fetchall()
                            if len(existing_profiles) == 1 and str(account[7]).lower() == "vo_hieu":
                                raise AdminSmallDeleteConflict
                            raise AdminSmallTargetNotFound

                        job_id = str(uuid.uuid4())
                        cursor.execute(
                            """
                            INSERT INTO dbo.GiaoDichVoHieuHoaAdminSmall
                                (ma_giao_dich, ma_tai_khoan, ma_co_so, ma_admin_big,
                                 phien_ban_ban_dau, site_codes_json, trang_thai)
                            VALUES (CONVERT(uniqueidentifier, %s), %s, %s, %s, %s, %s, 'dang_xu_ly')
                            """,
                            [job_id, normalized_id, target_site, admin_big_id,
                             int(account[8]), json.dumps(sites)],
                        )
                        job = (
                            normalized_id, target_site, admin_big_id, int(account[8]),
                            json.dumps(sites), "dang_xu_ly", job_id,
                        )
                    else:
                        job = tuple(job_row)
        except (AdminSmallTargetNotFound, AdminSmallDeleteConflict, AuthInfrastructureUnavailable):
            raise
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
            raise AuthInfrastructureUnavailable from exc

    target_site = str(job[1]).upper()
    try:
        original_sites = tuple(str(code).upper() for code in json.loads(str(job[4])))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthInfrastructureUnavailable from exc
    if not original_sites or len(set(original_sites)) != len(original_sites):
        raise AuthInfrastructureUnavailable
    for site_code in original_sites:
        try:
            get_site_database_alias(site_code)
        except UnknownSiteError as exc:
            raise AuthInfrastructureUnavailable from exc

    if str(job[5]).lower() != "hoan_tat":
        coordinator_site = auth_session_site_code()
        ordered_sites = tuple(
            [coordinator_site] + [site for site in original_sites if site != coordinator_site]
        )
        for site_code in ordered_sites:
            _deactivate_admin_small_replica(
                site_code,
                normalized_id,
                target_site,
                int(job[3]),
                str(job[2]),
                remote_ip,
                str(job[6]),
            )
        _complete_admin_small_deactivation(normalized_id)

    return AdminSmallDeactivationResult(account_id=normalized_id, site_code=target_site)

def _account_sync_log_if_missing(cursor, site_code: str, account_id: str) -> None:
    cursor.execute(
        """
        SELECT COUNT_BIG(*)
        FROM dbo.NhatKyDongBo
        WHERE bang = 'TaiKhoan' AND ma_ban_ghi = %s AND site_dich = %s
          AND hanh_dong = 'them' AND trang_thai = 'thanh_cong'
        """,
        [account_id, site_code],
    )
    if int(cursor.fetchone()[0]) > 0:
        return
    event_id = f"{site_code}-DB-{_next_sequence_number(site_code, 'Seq_DB'):06d}"
    cursor.execute(
        """
        INSERT INTO dbo.NhatKyDongBo
            (ma_dong_bo, bang, ma_ban_ghi, hanh_dong, site_dich, trang_thai)
        VALUES (%s, 'TaiKhoan', %s, 'them', %s, 'thanh_cong')
        """,
        [event_id, account_id, site_code],
    )

def _admin_small_audit_if_missing(
    cursor,
    site_code: str,
    admin_big_id: str,
    account_id: str,
    remote_ip: str,
) -> None:
    cursor.execute(
        """
        SELECT COUNT_BIG(*)
        FROM dbo.NhatKyHeThong
        WHERE ma_co_so = %s AND ma_tai_khoan = %s
          AND hanh_dong = 'tao_admin_small' AND ma_ban_ghi = %s
          AND ket_qua = 'thanh_cong'
        """,
        [site_code, admin_big_id, account_id],
    )
    if int(cursor.fetchone()[0]) > 0:
        return
    event_id = f"{site_code}-NK-{_next_sequence_number(site_code, 'Seq_NK'):06d}"
    cursor.execute(
        """
        INSERT INTO dbo.NhatKyHeThong
            (ma_nhat_ky, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, ip, ket_qua, ghi_chu)
        VALUES (%s, %s, %s, 'tao_admin_small', 'TaiKhoan', %s, %s,
                'thanh_cong', N'Tạo Admin Small cho cơ sở.')
        """,
        [event_id, site_code, admin_big_id, account_id, remote_ip[:45]],
    )

def _ensure_admin_small_replica(site_code: str, account, job, remote_ip: str) -> None:
    account_id, slug, username, email, password_hash, role, account_site, account_status, forced_change, version = account
    employee_id, target_site, full_name, admin_big_id = job
    alias = get_site_database_alias(site_code)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP (2) ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                                   vai_tro, ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban
                    FROM dbo.TaiKhoan
                    WHERE ma_tai_khoan = %s OR LOWER(email) = %s OR LOWER(ten_dang_nhap) = %s
                    """,
                    [account_id, email, username],
                )
                rows = cursor.fetchall()
                if not rows:
                    cursor.execute(
                        """
                        INSERT INTO dbo.TaiKhoan
                            (ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro,
                             ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban)
                        VALUES (%s, %s, %s, %s, %s, 'nhan_vien', %s, 'hoat_dong', 1, %s)
                        """,
                        [account_id, slug, username, email, password_hash, account_site, version],
                    )
                elif len(rows) != 1:
                    raise AuthInfrastructureUnavailable
                else:
                    row = rows[0]
                    actual = (
                        str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]),
                        str(row[5]).lower(), str(row[6]).upper() if row[6] else None,
                        str(row[7]).lower(), bool(row[8]), int(row[9]),
                    )
                    expected = (
                        str(account_id), str(slug), str(username), str(email), str(password_hash),
                        "nhan_vien", str(account_site), str(account_status), bool(forced_change), int(version),
                    )
                    if actual != expected:
                        raise AuthInfrastructureUnavailable

                if site_code == target_site:
                    cursor.execute(
                        """
                        SELECT TOP (2) ma_nhan_vien, ma_co_so, ma_tai_khoan, ho_ten,
                                       email, chuc_vu, trang_thai
                        FROM dbo.NhanVien
                        WHERE ma_nhan_vien = %s OR ma_tai_khoan = %s
                        """,
                        [employee_id, account_id],
                    )
                    profiles = cursor.fetchall()
                    expected_profile = (
                        employee_id, target_site, account_id, full_name, email,
                        "quan_ly_co_so", "dang_lam",
                    )
                    if not profiles:
                        cursor.execute(
                            """
                            INSERT INTO dbo.NhanVien
                                (ma_nhan_vien, ma_co_so, ma_tai_khoan, ho_ten, email,
                                 chuc_vu, trang_thai)
                            VALUES (%s, %s, %s, %s, %s, 'quan_ly_co_so', 'dang_lam')
                            """,
                            [employee_id, target_site, account_id, full_name, email],
                        )
                    elif len(profiles) != 1:
                        raise AuthInfrastructureUnavailable
                    else:
                        profile = profiles[0]
                        actual_profile = (
                            str(profile[0]), str(profile[1]).upper(), str(profile[2]),
                            str(profile[3]), str(profile[4]), str(profile[5]).lower(),
                            str(profile[6]).lower(),
                        )
                        if actual_profile != expected_profile:
                            raise AuthInfrastructureUnavailable
                    _admin_small_audit_if_missing(
                        cursor, target_site, admin_big_id, account_id, remote_ip
                    )
                else:
                    cursor.execute(
                        "SELECT COUNT_BIG(*) FROM dbo.NhanVien WHERE ma_tai_khoan = %s",
                        [account_id],
                    )
                    if int(cursor.fetchone()[0]) > 0:
                        raise AuthInfrastructureUnavailable

                _account_sync_log_if_missing(cursor, site_code, account_id)
    except AuthInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _load_admin_small_job(job_id: str):
    alias = auth_session_alias()
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT j.ma_giao_dich, j.ma_tai_khoan, j.ma_nhan_vien, j.ma_co_so,
                       j.ho_ten, j.ma_admin_big, j.trang_thai, j.email_da_gui,
                       a.slug, a.ten_dang_nhap, a.email, a.mat_khau, a.vai_tro,
                       a.ma_co_so, a.trang_thai, a.bat_buoc_doi_mat_khau, a.phien_ban
                FROM dbo.GiaoDichTaoAdminSmall AS j
                INNER JOIN dbo.TaiKhoan AS a ON a.ma_tai_khoan = j.ma_tai_khoan
                WHERE j.ma_giao_dich = CONVERT(uniqueidentifier, %s)
                """,
                [job_id],
            )
            row = cursor.fetchone()
        return tuple(row) if row else None
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _complete_admin_small_job(job_id: str, *, email_sent: bool) -> None:
    alias = auth_session_alias()
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dbo.GiaoDichTaoAdminSmall
                    SET trang_thai = 'hoan_tat', email_da_gui = %s,
                        cap_nhat_luc_utc = SYSUTCDATETIME(),
                        hoan_tat_luc_utc = SYSUTCDATETIME()
                    WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                      AND trang_thai <> 'hoan_tat'
                    """,
                    [1 if email_sent else 0, job_id],
                )
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _apply_admin_small_provisioning(job_id: str, site_codes: tuple[str, ...], remote_ip: str) -> None:
    row = _load_admin_small_job(job_id)
    if row is None or str(row[6]).lower() == "hoan_tat":
        return

    target_site = str(row[3]).upper()
    if target_site not in site_codes:
        raise AuthInfrastructureUnavailable
    account = (
        str(row[1]), str(row[8]), str(row[9]), str(row[10]), str(row[11]),
        str(row[12]).lower(), str(row[13]).upper() if row[13] else None,
        str(row[14]).lower(), bool(row[15]), int(row[16]),
    )
    if account[5] != "nhan_vien" or account[6] != target_site:
        raise AuthInfrastructureUnavailable
    job = (str(row[2]), target_site, str(row[4]), str(row[5]))
    for site_code in site_codes:
        _ensure_admin_small_replica(site_code, account, job, remote_ip)

    alias = auth_session_alias()
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dbo.GiaoDichTaoAdminSmall
                    SET trang_thai = 'cho_gui_email', cap_nhat_luc_utc = SYSUTCDATETIME()
                    WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                      AND trang_thai = 'dang_xu_ly'
                    """,
                    [job_id],
                )
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _send_admin_small_credentials(job_id: str) -> bool:
    temporary_password = _require_admin_small_email_configuration()
    row = _load_admin_small_job(job_id)
    if row is None:
        raise AuthInfrastructureUnavailable
    current_state = str(row[6]).lower()
    if current_state == "hoan_tat":
        return bool(row[7])
    if current_state != "cho_gui_email":
        raise AuthInfrastructureUnavailable

    account_id, site_code = str(row[1]), str(row[3]).upper()
    username, email, password_hash = str(row[9]), str(row[10]), str(row[11])
    must_change_password = bool(row[15])
    if not must_change_password or not check_password(temporary_password, password_hash):
        _complete_admin_small_job(job_id, email_sent=False)
        return False

    alias = auth_session_alias()
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT ten_co_so FROM dbo.CoSo WHERE ma_co_so = %s", [site_code])
            site_row = cursor.fetchone()
        if site_row is None:
            raise AuthInfrastructureUnavailable
        site_name = str(site_row[0])
        sent = send_mail(
            subject="Tài khoản Admin Small của trung tâm ngoại ngữ",
            message=(
                f"Xin chào {str(row[4])},\n\n"
                f"Admin Big đã tạo tài khoản quản lý cho {site_name}.\n"
                f"Tên đăng nhập: {username}\n"
                f"Email đăng nhập: {email}\n"
                f"Mã tài khoản: {account_id}\n"
                f"Cơ sở: {site_name} ({site_code})\n"
                f"Mật khẩu tạm: {temporary_password}\n\n"
                "Đây là mật khẩu cấp ban đầu. Hệ thống bắt buộc bạn đổi mật khẩu ngay sau khi đăng nhập. "
                "Mật khẩu mới phải có ít nhất 12 ký tự và không nên dùng lại mật khẩu này.\n"
                "Nếu bạn không mong đợi thư này, hãy liên hệ Admin Big của trung tâm."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        if sent != 1:
            raise AuthInfrastructureUnavailable
        _complete_admin_small_job(job_id, email_sent=True)
        return True
    except AuthInfrastructureUnavailable:
        raise
    except Exception as exc:
        logger.warning("Admin Small credential email delivery failed; error_type=%s.", type(exc).__name__)
        raise AuthInfrastructureUnavailable from exc

def _resume_pending_admin_small_creations(site_codes: tuple[str, ...], remote_ip: str) -> None:
    alias = auth_session_alias()
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (20) ma_giao_dich
                FROM dbo.GiaoDichTaoAdminSmall
                WHERE trang_thai IN ('dang_xu_ly', 'cho_gui_email')
                ORDER BY tao_luc_utc
                """
            )
            pending_ids = [str(row[0]) for row in cursor.fetchall()]
        for job_id in pending_ids:
            _apply_admin_small_provisioning(job_id, site_codes, remote_ip)
            _send_admin_small_credentials(job_id)
    except AuthInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _existing_admin_small_creation(email: str):
    alias = auth_session_alias()
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2) a.ma_tai_khoan, j.ma_nhan_vien, a.ten_dang_nhap,
                               a.email, a.ma_co_so, a.vai_tro, j.trang_thai,
                               j.email_da_gui, a.bat_buoc_doi_mat_khau
                FROM dbo.GiaoDichTaoAdminSmall AS j
                INNER JOIN dbo.TaiKhoan AS a ON a.ma_tai_khoan = j.ma_tai_khoan
                WHERE LOWER(a.email) = %s
                """,
                [email],
            )
            rows = cursor.fetchall()
        if len(rows) > 1:
            raise AuthInfrastructureUnavailable
        return tuple(rows[0]) if rows else None
    except AuthInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def create_admin_small(
    *,
    email: str,
    full_name: str,
    site_code: str,
    admin_big_id: str,
    remote_ip: str,
    username: str | None = None,
) -> tuple[AdminSmallProvisioningResult, bool]:
    """Replicate a site-scoped staff account, create its local manager profile, then email its temporary password."""
    temporary_password = _require_admin_small_email_configuration()
    normalized_email = email.strip().casefold()
    target_site = site_code.strip().upper()
    normalized_name = full_name.strip()
    normalized_username = (username or make_slug(normalized_email, max_length=100)).strip().lower()
    slug = make_slug(f"admin-small-{target_site}-{normalized_username}", max_length=120)
    if not normalized_email or not normalized_name or not remote_ip:
        raise ValueError("Thiếu thông tin tài khoản Admin Small.")

    sites = active_site_codes()
    if target_site not in sites:
        raise AdminSmallSiteUnavailable
    _resume_pending_admin_small_creations(sites, remote_ip)

    existing_job = _existing_admin_small_creation(normalized_email)
    if existing_job is not None:
        if str(existing_job[4]).upper() != target_site or str(existing_job[5]).lower() != "nhan_vien":
            raise AdminSmallAccountConflict
        result = AdminSmallProvisioningResult(
            account_id=str(existing_job[0]), employee_id=str(existing_job[1]),
            username=str(existing_job[2]), email=str(existing_job[3]), site_code=target_site,
            must_change_password=bool(existing_job[8]),
        )
        return result, bool(existing_job[7])

    if _replicated_account(normalized_email, sites) is not None:
        raise AdminSmallAccountConflict
    if _replicated_account(normalized_username, sites) is not None:
        raise AdminSmallAccountConflict

    coordinator_alias = auth_session_alias()
    account_id = _next_admin_small_account_id(target_site, sites)
    employee_id = _next_admin_small_employee_id(target_site)
    password_hash = make_password(temporary_password)
    job_id = str(uuid.uuid4())
    identity_digest = _digest("admin-small-email", normalized_email)
    username_digest = _digest("admin-small-username", normalized_username.casefold())

    try:
        with transaction.atomic(using=coordinator_alias):
            with connections[coordinator_alias].cursor() as cursor:
                _acquire_named_lock(cursor, f"qlttnn-admin-small-email:{identity_digest}")
                _acquire_named_lock(cursor, f"qlttnn-admin-small-username:{username_digest}")
                if _replicated_account(normalized_email, sites) is not None:
                    raise AdminSmallAccountConflict
                if _replicated_account(normalized_username, sites) is not None:
                    raise AdminSmallAccountConflict
                cursor.execute(
                    """
                    INSERT INTO dbo.TaiKhoan
                        (ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro,
                         ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban)
                    VALUES (%s, %s, %s, %s, %s, 'nhan_vien', %s, 'hoat_dong', 1, 1)
                    """,
                    [account_id, slug, normalized_username, normalized_email,
                     password_hash, target_site],
                )
                cursor.execute(
                    """
                    INSERT INTO dbo.GiaoDichTaoAdminSmall
                        (ma_giao_dich, ma_tai_khoan, ma_nhan_vien, ma_co_so,
                         ho_ten, ma_admin_big, trang_thai)
                    VALUES (CONVERT(uniqueidentifier, %s), %s, %s, %s, %s, %s, 'dang_xu_ly')
                    """,
                    [job_id, account_id, employee_id, target_site,
                     normalized_name, admin_big_id],
                )
    except (AdminSmallAccountConflict, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

    _apply_admin_small_provisioning(job_id, sites, remote_ip)
    email_sent = _send_admin_small_credentials(job_id)
    return AdminSmallProvisioningResult(
        account_id=account_id,
        employee_id=employee_id,
        username=normalized_username,
        email=normalized_email,
        site_code=target_site,
        must_change_password=True,
    ), email_sent
