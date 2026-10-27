"""Admin password-reset flow, OTP throttling, and recovery helpers."""

from __future__ import annotations

import hmac
import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import DatabaseError, connections, transaction

from core.sites.connections import UnknownSiteError, get_site_database_alias
from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    PasswordResetRateLimitExceeded,
    _acquire_named_lock,
    _digest,
    _replicated_account,
    _resolve_principal,
    active_site_codes,
    auth_session_alias,
)
from core.auth.service_common import logger

def _record_password_reset_event(
    cursor,
    identifier_digest: str,
    ip_digest: str,
    event_type: str,
    token_id: str | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO dbo.SuKienQuenMatKhau
            (ma_su_kien, dinh_danh_bam, ip_bam, ma_token, loai_su_kien)
        VALUES (NEWID(), %s, %s, %s, %s)
        """,
        [identifier_digest, ip_digest, token_id, event_type],
    )

def _password_reset_request_is_limited(cursor, identifier_digest: str, ip_digest: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT_BIG(*)
        FROM dbo.SuKienQuenMatKhau
        WHERE ip_bam = %s AND loai_su_kien = 'yeu_cau'
          AND thoi_diem_utc >= DATEADD(HOUR, -1, SYSUTCDATETIME())
        """,
        [ip_digest],
    )
    if int(cursor.fetchone()[0]) >= settings.AUTH_PASSWORD_RESET_IP_LIMIT_PER_HOUR:
        return True

    cursor.execute(
        """
        SELECT COUNT_BIG(*)
        FROM dbo.SuKienQuenMatKhau
        WHERE dinh_danh_bam = %s AND loai_su_kien = 'yeu_cau'
          AND thoi_diem_utc >= DATEADD(HOUR, -1, SYSUTCDATETIME())
        """,
        [identifier_digest],
    )
    if int(cursor.fetchone()[0]) >= settings.AUTH_PASSWORD_RESET_IDENTITY_LIMIT_PER_HOUR:
        return True

    cursor.execute(
        """
        SELECT COUNT_BIG(*)
        FROM dbo.SuKienQuenMatKhau
        WHERE dinh_danh_bam = %s AND ip_bam = %s AND loai_su_kien = 'yeu_cau'
          AND thoi_diem_utc >= DATEADD(SECOND, -%s, SYSUTCDATETIME())
        """,
        [identifier_digest, ip_digest, settings.AUTH_PASSWORD_RESET_COOLDOWN_SECONDS],
    )
    return int(cursor.fetchone()[0]) > 0

def _password_reset_verify_retry_after(cursor, identifier_digest: str, ip_digest: str) -> int | None:
    window_seconds = 3600
    cursor.execute(
        """
        SELECT COUNT_BIG(*), DATEDIFF(SECOND, MIN(thoi_diem_utc), SYSUTCDATETIME())
        FROM dbo.SuKienQuenMatKhau
        WHERE ip_bam = %s AND loai_su_kien = 'otp_sai'
          AND thoi_diem_utc >= DATEADD(SECOND, -%s, SYSUTCDATETIME())
        """,
        [ip_digest, window_seconds],
    )
    count, age = cursor.fetchone()
    if int(count) >= settings.AUTH_PASSWORD_RESET_VERIFY_IP_LIMIT_PER_HOUR:
        return max(1, window_seconds - int(age or 0))

    cursor.execute(
        """
        SELECT COUNT_BIG(*), DATEDIFF(SECOND, MIN(thoi_diem_utc), SYSUTCDATETIME())
        FROM dbo.SuKienQuenMatKhau
        WHERE dinh_danh_bam = %s AND loai_su_kien = 'otp_sai'
          AND thoi_diem_utc >= DATEADD(SECOND, -%s, SYSUTCDATETIME())
        """,
        [identifier_digest, window_seconds],
    )
    count, age = cursor.fetchone()
    if int(count) >= settings.AUTH_PASSWORD_RESET_VERIFY_IDENTITY_LIMIT_PER_HOUR:
        return max(1, window_seconds - int(age or 0))
    return None

def _eligible_admin_from_email(email: str, site_codes: tuple[str, ...]):
    account = _replicated_account(email, site_codes)
    user = _resolve_principal(account, site_codes) if account is not None else None
    if user is None or user.role not in {"admin_big", "admin_small"}:
        return None, None
    return account, user

def _invalidate_reset_token(token_id: str) -> None:
    alias = auth_session_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "UPDATE dbo.TokenDatLaiMatKhau SET da_dung = 1 WHERE ma_token = %s AND da_dung = 0",
            [token_id],
        )

def request_admin_password_reset(email: str, remote_ip: str) -> None:
    """Send a short-lived OTP without revealing whether the address is eligible."""
    normalized_email = email.strip().casefold()
    if not normalized_email or not remote_ip:
        raise ValueError("Thiếu email hoặc địa chỉ IP.")

    _resume_pending_password_resets()
    alias = auth_session_alias()
    identifier_digest = _digest("password-reset-identity", normalized_email)
    ip_digest = _digest("password-reset-ip", remote_ip)
    mail_payload = None
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                _acquire_named_lock(cursor, f"qlttnn-reset-ip:{ip_digest}")
                _acquire_named_lock(cursor, f"qlttnn-reset-id:{identifier_digest}")
                limited = _password_reset_request_is_limited(cursor, identifier_digest, ip_digest)
                _record_password_reset_event(cursor, identifier_digest, ip_digest, "yeu_cau")
                if not limited:
                    sites = active_site_codes()
                    account, user = _eligible_admin_from_email(normalized_email, sites)
                    if account is not None and user is not None:
                        token_id = secrets.token_hex(15)
                        otp = f"{secrets.randbelow(1_000_000):06d}"
                        otp_digest = _digest(
                            "password-reset-otp",
                            f"{user.account_id}:{token_id}:{otp}",
                        )
                        cursor.execute(
                            """
                            UPDATE dbo.TokenDatLaiMatKhau
                            SET da_dung = 1
                            WHERE ma_tai_khoan = %s AND da_dung = 0
                            """,
                            [user.account_id],
                        )
                        cursor.execute(
                            """
                            INSERT INTO dbo.TokenDatLaiMatKhau
                                (ma_token, ma_tai_khoan, token_bam, ngay_tao, het_han,
                                 da_dung, so_lan_sai, ip_yeu_cau)
                            VALUES
                                (%s, %s, %s, SYSUTCDATETIME(),
                                 DATEADD(SECOND, %s, SYSUTCDATETIME()), 0, 0, NULL)
                            """,
                            [token_id, user.account_id, otp_digest, settings.PASSWORD_RESET_TIMEOUT],
                        )
                        mail_payload = (str(account[3]), otp, token_id)
        if mail_payload is None:
            return

        recipient, otp, token_id = mail_payload
        try:
            sent = send_mail(
                subject="Mã OTP đặt lại mật khẩu quản trị",
                message=(
                    f"Mã OTP đặt lại mật khẩu của bạn là: {otp}\n\n"
                    "Mã chỉ dùng một lần và hết hạn sau 2 phút. Nếu bạn không yêu cầu, "
                    "hãy bỏ qua email này. Không chia sẻ mã OTP cho bất kỳ ai."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL or None,
                recipient_list=[recipient],
                fail_silently=False,
            )
            if sent != 1:
                _invalidate_reset_token(token_id)
                logger.warning("Password reset OTP delivery returned no accepted message.")
        except Exception as exc:
            _invalidate_reset_token(token_id)
            logger.warning("Password reset OTP delivery failed; error_type=%s.", type(exc).__name__)
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _apply_password_reset_transaction(transaction_id, site_codes: tuple[str, ...]) -> None:
    coordinator_alias = auth_session_alias()
    try:
        with connections[coordinator_alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT ma_tai_khoan, mat_khau_moi_bam, trang_thai
                FROM dbo.GiaoDichDatLaiMatKhau
                WHERE ma_giao_dich = %s
                """,
                [transaction_id],
            )
            job = cursor.fetchone()
        if job is None or str(job[2]).lower() == "hoan_tat":
            return
        account_id, new_password_hash = str(job[0]), str(job[1])

        # Each site commits locally; the coordinator row makes this forward-only
        # operation retryable if a site is unavailable during the replica write.
        for site_code in site_codes:
            site_alias = get_site_database_alias(site_code)
            with transaction.atomic(using=site_alias):
                with connections[site_alias].cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE dbo.TaiKhoan
                        SET mat_khau = %s,
                            bat_buoc_doi_mat_khau = 0,
                            ngay_doi_mat_khau_cuoi = SYSUTCDATETIME(),
                            phien_ban = phien_ban + 1,
                            cap_nhat_luc = SYSUTCDATETIME()
                        WHERE ma_tai_khoan = %s
                          AND (CONVERT(VARBINARY(510), mat_khau) <> CONVERT(VARBINARY(510), %s)
                               OR bat_buoc_doi_mat_khau = 1)
                        """,
                        [new_password_hash, account_id, new_password_hash],
                    )
                    cursor.execute(
                        "SELECT COUNT_BIG(*), MIN(mat_khau) FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s",
                        [account_id],
                    )
                    count, actual_hash = cursor.fetchone()
                    if int(count) != 1 or not hmac.compare_digest(str(actual_hash), new_password_hash):
                        raise AuthInfrastructureUnavailable

        with transaction.atomic(using=coordinator_alias):
            with connections[coordinator_alias].cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dbo.GiaoDichDatLaiMatKhau
                    SET mat_khau_moi_bam = NULL,
                        trang_thai = 'hoan_tat',
                        cap_nhat_luc_utc = SYSUTCDATETIME(),
                        hoan_tat_luc_utc = SYSUTCDATETIME()
                    WHERE ma_giao_dich = %s AND trang_thai = 'dang_xu_ly'
                    """,
                    [transaction_id],
                )
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def _resume_pending_password_resets() -> None:
    coordinator_alias = auth_session_alias()
    try:
        with connections[coordinator_alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (20) ma_giao_dich
                FROM dbo.GiaoDichDatLaiMatKhau
                WHERE trang_thai = 'dang_xu_ly'
                ORDER BY tao_luc_utc
                """
            )
            pending_ids = [row[0] for row in cursor.fetchall()]
        if not pending_ids:
            return
        sites = active_site_codes()
        for transaction_id in pending_ids:
            _apply_password_reset_transaction(transaction_id, sites)
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

def reset_admin_password(email: str, otp: str, new_password: str, remote_ip: str) -> bool:
    """Consume a valid OTP and replicate the new bcrypt hash to all active sites."""
    normalized_email = email.strip().casefold()
    if not normalized_email or not remote_ip:
        raise ValueError("Thiếu email hoặc địa chỉ IP.")

    _resume_pending_password_resets()
    alias = auth_session_alias()
    identifier_digest = _digest("password-reset-identity", normalized_email)
    ip_digest = _digest("password-reset-ip", remote_ip)
    sites = active_site_codes()
    transaction_id = None
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                _acquire_named_lock(cursor, f"qlttnn-reset-ip:{ip_digest}")
                _acquire_named_lock(cursor, f"qlttnn-reset-id:{identifier_digest}")
                retry_after = _password_reset_verify_retry_after(cursor, identifier_digest, ip_digest)
                if retry_after is not None:
                    raise PasswordResetRateLimitExceeded(retry_after)

                account, user = _eligible_admin_from_email(normalized_email, sites)
                if account is None or user is None:
                    _record_password_reset_event(cursor, identifier_digest, ip_digest, "otp_sai")
                    return False

                cursor.execute(
                    """
                    UPDATE dbo.TokenDatLaiMatKhau
                    SET da_dung = 1
                    WHERE ma_tai_khoan = %s AND da_dung = 0
                      AND het_han <= SYSUTCDATETIME()
                    """,
                    [user.account_id],
                )
                cursor.execute(
                    """
                    SELECT TOP (1) ma_token, token_bam, so_lan_sai
                    FROM dbo.TokenDatLaiMatKhau WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_tai_khoan = %s AND da_dung = 0
                      AND het_han > SYSUTCDATETIME()
                      AND so_lan_sai < %s
                    ORDER BY ngay_tao DESC
                    """,
                    [user.account_id, settings.AUTH_PASSWORD_RESET_OTP_ATTEMPT_LIMIT],
                )
                token_row = cursor.fetchone()
                expected_digest = (
                    _digest("password-reset-otp", f"{user.account_id}:{token_row[0]}:{otp}")
                    if token_row is not None
                    else ""
                )
                if token_row is None or not hmac.compare_digest(str(token_row[1]), expected_digest):
                    if token_row is not None:
                        cursor.execute(
                            """
                            UPDATE dbo.TokenDatLaiMatKhau
                            SET so_lan_sai = so_lan_sai + 1,
                                da_dung = CASE
                                    WHEN so_lan_sai + 1 >= %s THEN 1 ELSE da_dung END
                            WHERE ma_token = %s AND da_dung = 0
                            """,
                            [settings.AUTH_PASSWORD_RESET_OTP_ATTEMPT_LIMIT, token_row[0]],
                        )
                    _record_password_reset_event(
                        cursor,
                        identifier_digest,
                        ip_digest,
                        "otp_sai",
                        str(token_row[0]) if token_row is not None else None,
                    )
                    return False

                new_password_hash = make_password(new_password)
                transaction_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO dbo.GiaoDichDatLaiMatKhau
                        (ma_giao_dich, ma_tai_khoan, mat_khau_moi_bam, trang_thai)
                    VALUES (CONVERT(uniqueidentifier, %s), %s, %s, 'dang_xu_ly')
                    """,
                    [transaction_id, user.account_id, new_password_hash],
                )
                cursor.execute(
                    "UPDATE dbo.TokenDatLaiMatKhau SET da_dung = 1 WHERE ma_token = %s AND da_dung = 0",
                    [token_row[0]],
                )
                _record_password_reset_event(
                    cursor, identifier_digest, ip_digest, "dat_lai", str(token_row[0])
                )
        _apply_password_reset_transaction(transaction_id, sites)
        return True
    except (PasswordResetRateLimitExceeded, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
