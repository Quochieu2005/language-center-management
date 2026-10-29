"""Admin Small account creation and delete-button status changes."""

from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import DatabaseError, IntegrityError, connections, transaction

from core.auth.account_state import account_status_bit
from core.auth.service_common import (
    AdminSmallAccountConflict,
    AdminSmallDeactivationResult,
    AdminSmallDeleteConflict,
    AdminSmallSiteUnavailable,
    AdminSmallTargetNotFound,
    AdminSmallProvisioningResult,
    AuthInfrastructureUnavailable,
    _next_sequence_number,
    _replicated_account,
    active_site_codes,
    logger,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.slug_utils import make_slug
from core.notifications.publisher import publish_notification


def _require_admin_small_email_configuration() -> str:
    password = str(getattr(settings, "ADMIN_SMALL_TEMP_PASSWORD", "")).strip()
    if not password or len(password) > 128:
        raise AuthInfrastructureUnavailable
    if "console.EmailBackend" in settings.EMAIL_BACKEND:
        raise AuthInfrastructureUnavailable
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or not settings.DEFAULT_FROM_EMAIL:
        raise AuthInfrastructureUnavailable
    return password


def _next_admin_small_account_id(site_code: str, sites: tuple[str, ...]) -> str:
    for _ in range(1000):
        candidate = f"{site_code}-TK-{_next_sequence_number(site_code, 'Seq_TK'):06d}"
        if all(
            not _account_id_exists(code, candidate)
            for code in sites
        ):
            return candidate
    raise AuthInfrastructureUnavailable


def _account_id_exists(site_code: str, account_id: str) -> bool:
    with get_site_connection(site_code).cursor() as cursor:
        cursor.execute(
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s) "
            "THEN 1 ELSE 0 END",
            [account_id],
        )
        return bool(cursor.fetchone()[0])


def _next_admin_id(site_code: str) -> str:
    for _ in range(1000):
        candidate = f"{site_code}-AD-{_next_sequence_number(site_code, 'Seq_AD'):06d}"
        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.Admin WHERE ma_admin = %s) "
                "THEN 1 ELSE 0 END",
                [candidate],
            )
            if not cursor.fetchone()[0]:
                return candidate
    raise AuthInfrastructureUnavailable


def _replicate_account(site_code: str, account: tuple, action: str) -> None:
    alias = get_site_database_alias(site_code)
    account_id, slug, username, email, password_hash, site, forced, version = account
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP (2) ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                                   vai_tro, ma_co_so, trang_thai,
                                   bat_buoc_doi_mat_khau, phien_ban
                    FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_tai_khoan = %s OR LOWER(email) = %s OR LOWER(ten_dang_nhap) = %s
                    """,
                    [account_id, email, username],
                )
                rows = cursor.fetchall()
                if len(rows) > 1:
                    raise AdminSmallAccountConflict
                expected = (
                    str(account_id), str(slug), str(username), str(email), str(password_hash),
                    "nhan_vien", site, 1, bool(forced), int(version),
                )
                if rows:
                    actual = tuple(rows[0])
                    normalized = (
                        str(actual[0]), str(actual[1]), str(actual[2]), str(actual[3]),
                        str(actual[4]), str(actual[5]).lower(),
                        str(actual[6]).upper() if actual[6] else None,
                        account_status_bit(actual[7]), bool(actual[8]), int(actual[9]),
                    )
                    if normalized != expected:
                        raise AdminSmallAccountConflict
                else:
                    cursor.execute(
                        """
                        INSERT INTO dbo.TaiKhoan
                            (ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                             vai_tro, ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban)
                        VALUES (%s, %s, %s, %s, %s, 'nhan_vien', %s, 1, %s, %s)
                        """,
                        [account_id, slug, username, email, password_hash, site, forced, version],
                    )
                event_id = f"{site_code}-DB-{uuid.uuid5(uuid.NAMESPACE_URL, f'{account_id}:{site_code}:{action}').hex[:10]}"
                cursor.execute(
                    "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua "
                    "FROM dbo.Logs WHERE loai_log = 'sync' AND ma_log = %s",
                    [event_id],
                )
                event = cursor.fetchone()
                expected_event = ("TaiKhoan", account_id, action, site_code, "thanh_cong")
                if event is not None and tuple(str(value) for value in event) != expected_event:
                    raise AuthInfrastructureUnavailable
                if event is None:
                    cursor.execute(
                        """
                        INSERT INTO dbo.Logs
                            (ma_log, loai_log, bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua)
                        VALUES (%s, 'sync', 'TaiKhoan', %s, %s, %s, 'thanh_cong')
                        """,
                        [event_id, account_id, action, site_code],
                    )
    except (AdminSmallAccountConflict, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def _create_admin_profile(
    site_code: str, admin_id: str, account_id: str, full_name: str,
    phone: str | None, remote_ip: str,
) -> None:
    alias = get_site_database_alias(site_code)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ma_admin, ma_co_so, loai_admin, ho_ten, sdt, trang_thai
                    FROM dbo.Admin WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_tai_khoan = %s
                    """,
                    [account_id],
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        """
                        INSERT INTO dbo.Admin
                            (ma_admin, ma_tai_khoan, ma_co_so, loai_admin, ho_ten, sdt, trang_thai)
                        VALUES (%s, %s, %s, 'admin_small', %s, %s, 1)
                        """,
                        [admin_id, account_id, site_code, full_name, phone],
                    )
                elif (
                    str(row[0]) != admin_id or str(row[1]).upper() != site_code
                    or str(row[2]).lower() != "admin_small" or str(row[3]) != full_name
                    or row[4] != phone or not bool(row[5])
                ):
                    raise AdminSmallAccountConflict
                cursor.execute(
                    """
                    INSERT INTO dbo.Logs
                        (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong,
                         bang_tac_dong, ma_ban_ghi, ip, ket_qua)
                    SELECT %s, 'system', %s, %s, 'tao_admin_small', 'Admin', %s, %s, 'thanh_cong'
                    WHERE NOT EXISTS
                    (
                        SELECT 1 FROM dbo.Logs
                        WHERE loai_log = 'system' AND ma_co_so = %s AND ma_tai_khoan = %s
                          AND hanh_dong = 'tao_admin_small' AND bang_tac_dong = 'Admin'
                          AND ma_ban_ghi = %s AND ket_qua = 'thanh_cong'
                    )
                    """,
                    [
                        f"{site_code}-NK-{uuid.uuid4().hex[:10]}", site_code, account_id,
                        admin_id, remote_ip[:45], site_code, account_id, admin_id,
                    ],
                )
                publish_notification(
                    cursor,
                    site_code=site_code,
                    event_key=f"admin-small-created:{account_id}",
                    category="account",
                    severity="success",
                    title="Admin Small được tạo",
                    message=f"Tài khoản quản lý cơ sở {site_code} đã được tạo.",
                    target_path=f"/admin/admins?site_code={site_code}",
                )
    except (AdminSmallAccountConflict,):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def _send_credentials(email: str, full_name: str, username: str, password: str) -> bool:
    try:
        return send_mail(
            subject="Tài khoản Admin Small Trung tâm Ngoại ngữ",
            message=(
                f"Chào {full_name},\n\n"
                "Tài khoản Admin Small của bạn đã được tạo.\n"
                f"Tên đăng nhập: {username}\n"
                f"Mật khẩu tạm thời: {password}\n\n"
                "Hãy đổi mật khẩu ngay lần đăng nhập đầu tiên và không chia sẻ mật khẩu."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        ) == 1
    except Exception as exc:
        logger.warning("Admin Small credential email failed; error_type=%s.", type(exc).__name__)
        return False


def _recover_admin_small_provisioning(
    *, site_code: str, email: str, username: str, full_name: str, temporary_password: str,
) -> tuple[tuple, str] | None:
    """Return a committed local provision so a retry can finish account replication."""
    try:
        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2)
                       t.ma_tai_khoan, t.slug, t.ten_dang_nhap, t.email, t.mat_khau,
                       t.vai_tro, t.ma_co_so, t.trang_thai,
                       t.bat_buoc_doi_mat_khau, t.phien_ban,
                       a.ma_admin, a.ma_co_so, a.loai_admin, a.ho_ten, a.sdt, a.trang_thai
                FROM dbo.TaiKhoan AS t
                LEFT JOIN dbo.Admin AS a ON a.ma_tai_khoan = t.ma_tai_khoan
                WHERE LOWER(t.email) = %s OR LOWER(t.ten_dang_nhap) = %s
                """,
                [email, username],
            )
            rows = cursor.fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise AdminSmallAccountConflict
        row = rows[0]
        account_id, slug, stored_username, stored_email = map(str, row[:4])
        password_hash = str(row[4])
        role = str(row[5]).lower()
        account_site = str(row[6]).upper() if row[6] else None
        if (
            role != "nhan_vien" or account_site != site_code
            or not account_status_bit(row[7]) or not bool(row[8])
            or stored_email.casefold() != email or stored_username.lower() != username
            or not check_password(temporary_password, password_hash)
            or row[10] is None or str(row[11]).upper() != site_code
            or str(row[12]).lower() != "admin_small" or str(row[13]) != full_name
            or row[14] is not None or not bool(row[15])
        ):
            raise AdminSmallAccountConflict
        account = (
            account_id, slug, stored_username, stored_email, password_hash,
            account_site, bool(row[8]), int(row[9]),
        )
        return account, str(row[10])
    except AdminSmallAccountConflict:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def create_admin_small(
    *, email: str, full_name: str, site_code: str, username: str | None,
    admin_big_id: str, remote_ip: str,
) -> tuple[AdminSmallProvisioningResult, bool]:
    temporary_password = _require_admin_small_email_configuration()
    sites = active_site_codes()
    target_site = str(site_code).strip().upper()
    if target_site not in sites:
        raise AdminSmallSiteUnavailable
    normalized_email = email.strip().casefold()
    normalized_username = (username or make_slug(normalized_email.partition("@")[0], max_length=100)).strip().lower()
    normalized_name = full_name.strip()
    if not normalized_email or not normalized_name or not normalized_username or not remote_ip:
        raise ValueError("Thiếu thông tin Admin Small.")
    recovered = _recover_admin_small_provisioning(
        site_code=target_site, email=normalized_email, username=normalized_username,
        full_name=normalized_name, temporary_password=temporary_password,
    )
    if recovered is not None:
        account, admin_id = recovered
        account_id, account_slug, normalized_username, normalized_email = account[:4]
    else:
        if (
            _replicated_account(normalized_email, sites) is not None
            or _replicated_account(normalized_username, sites) is not None
        ):
            raise AdminSmallAccountConflict
        account_id = _next_admin_small_account_id(target_site, sites)
        admin_id = _next_admin_id(target_site)
        account_slug = make_slug(f"admin-small-{target_site}-{normalized_username}", max_length=120)
        password_hash = make_password(temporary_password)
        account = (
            account_id, account_slug, normalized_username, normalized_email,
            password_hash, target_site, True, 1,
        )

    target_alias = get_site_database_alias(target_site)
    try:
        # Commit the profile and its login account together at the owning site first.
        with transaction.atomic(using=target_alias):
            _replicate_account(target_site, account, "them")
            _create_admin_profile(target_site, admin_id, account_id, normalized_name, None, remote_ip)
        for site in sites:
            if site != target_site:
                _replicate_account(site, account, "them")
    except AdminSmallAccountConflict:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
    email_sent = _send_credentials(normalized_email, normalized_name, normalized_username, temporary_password)
    return (
        AdminSmallProvisioningResult(
            account_id=account_id,
            admin_id=admin_id,
            username=normalized_username,
            email=normalized_email,
            site_code=target_site,
            must_change_password=True,
            slug=account_slug,
        ),
        email_sent,
    )


def delete_admin_small(account_id: str, admin_big_id: str, remote_ip: str) -> AdminSmallDeactivationResult:
    from core.auth.service_common import _replicated_account_by_id

    sites = active_site_codes()
    account = _replicated_account_by_id(account_id.strip(), sites)
    if account is None:
        raise AdminSmallTargetNotFound
    if str(account[5]).lower() != "nhan_vien" or not account[6]:
        raise AdminSmallTargetNotFound
    target_site = str(account[6]).upper()
    if target_site not in sites:
        raise AdminSmallTargetNotFound

    with get_site_connection(target_site).cursor() as cursor:
        cursor.execute(
            "SELECT ma_admin FROM dbo.Admin WHERE ma_tai_khoan = %s "
            "AND ma_co_so = %s AND loai_admin = 'admin_small'",
            [account_id, target_site],
        )
        if cursor.fetchone() is None:
            raise AdminSmallTargetNotFound

    for site in sites:
        alias = get_site_database_alias(site)
        try:
            with transaction.atomic(using=alias):
                with connections[alias].cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE dbo.TaiKhoan
                        SET trang_thai = 0, phien_ban = phien_ban + 1,
                            cap_nhat_luc = SYSUTCDATETIME()
                        WHERE ma_tai_khoan = %s AND vai_tro = 'nhan_vien'
                          AND ma_co_so = %s AND trang_thai = 1
                        """,
                        [account_id, target_site],
                    )
                    if cursor.rowcount not in (0, 1):
                        raise AdminSmallDeleteConflict
                    cursor.execute(
                        """
                        UPDATE dbo.PhienDangNhap
                        SET thu_hoi_luc_utc = COALESCE(thu_hoi_luc_utc, SYSUTCDATETIME())
                        WHERE ma_tai_khoan = %s AND thu_hoi_luc_utc IS NULL
                        """,
                        [account_id],
                    )
                    if site == target_site:
                        cursor.execute(
                            "UPDATE dbo.Admin SET trang_thai = 0 "
                            "WHERE ma_tai_khoan = %s AND ma_co_so = %s AND loai_admin = 'admin_small'",
                            [account_id, target_site],
                        )
                        if cursor.rowcount != 1:
                            raise AdminSmallDeleteConflict
                        cursor.execute(
                            """
                            INSERT INTO dbo.Logs
                                (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong,
                                 bang_tac_dong, ma_ban_ghi, ip, ket_qua)
                            VALUES (%s, 'system', %s, %s, 'xoa_admin_small', 'Admin', %s, %s, 'thanh_cong')
                            """,
                            [
                                f"{site}-NK-{uuid.uuid4().hex[:10]}", site,
                                admin_big_id, account_id, remote_ip[:45],
                            ],
                        )
        except AdminSmallDeleteConflict:
            raise
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
            raise AuthInfrastructureUnavailable from exc

    return AdminSmallDeactivationResult(account_id=account_id, site_code=target_site)
