"""SQL Server backed authentication services for the distributed sites."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction
from django.core.mail import send_mail

from core.slug_utils import make_slug
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


logger = logging.getLogger("core.auth")


class AuthInfrastructureUnavailable(Exception):
    """The API could not safely verify the replicated account or session store."""


class LoginRateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, int(retry_after))
        super().__init__("Login attempt limit reached.")


class PasswordResetRateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, int(retry_after))
        super().__init__("Password reset verification limit reached.")


class AdminSmallAccountConflict(Exception):
    """An email or login name is already assigned to a different account."""


class AdminSmallSiteUnavailable(Exception):
    """The requested branch is not an active site."""


@dataclass(frozen=True)
class AuthenticatedUser:
    account_id: str
    email: str
    username: str
    slug: str
    role: str
    site_code: str | None = None
    profile_id: str | None = None
    must_change_password: bool = False

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def pk(self) -> str:
        return self.account_id


@dataclass(frozen=True)
class AuthenticatedSession:
    token_digest: str
    session_id: str
    expires_at: Any


@dataclass(frozen=True)
class AdminSmallProvisioningResult:
    account_id: str
    employee_id: str
    username: str
    email: str
    site_code: str
    must_change_password: bool = True


def auth_session_alias() -> str:
    site_code = getattr(settings, "AUTH_SESSION_SITE_CODE", "")
    if not site_code:
        raise ImproperlyConfigured("Thiếu AUTH_SESSION_SITE_CODE trong src/api/.env.")
    try:
        return get_site_database_alias(site_code)
    except UnknownSiteError as exc:
        raise ImproperlyConfigured("AUTH_SESSION_SITE_CODE chưa có kết nối CSDL.") from exc


def _digest(purpose: str, value: str) -> str:
    key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    message = f"qlttnn:{purpose}:{value}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def session_token_digest(token: str) -> str:
    return _digest("session", token)


def _read_catalog(site_code: str) -> tuple[tuple[str, str], ...]:
    with get_site_connection(site_code).cursor() as cursor:
        cursor.execute("SELECT ma_co_so, trang_thai FROM dbo.CoSo ORDER BY ma_co_so")
        return tuple((str(row[0]).upper(), str(row[1]).lower()) for row in cursor.fetchall())


def active_site_codes() -> tuple[str, ...]:
    """Read active sites from replicated CoSo and reject incomplete site copies."""
    registry_site = getattr(settings, "AUTH_SESSION_SITE_CODE", "")
    try:
        registry_catalog = _read_catalog(registry_site)
        active_codes = tuple(code for code, status in registry_catalog if status == "hoat_dong")
        if not active_codes or registry_site not in active_codes:
            raise AuthInfrastructureUnavailable

        for code in active_codes:
            if _read_catalog(code) != registry_catalog:
                raise AuthInfrastructureUnavailable
        return active_codes
    except (DatabaseError, KeyError, ImproperlyConfigured, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def _replicated_account(identifier: str, site_codes: tuple[str, ...]):
    replicas = []
    for code in site_codes:
        with get_site_connection(code).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2) ma_tai_khoan, ten_dang_nhap, slug, email, mat_khau,
                               vai_tro, ma_co_so, trang_thai, phien_ban,
                               bat_buoc_doi_mat_khau
                FROM dbo.TaiKhoan
                WHERE LOWER(email) = %s OR LOWER(ten_dang_nhap) = %s
                """,
                [identifier, identifier],
            )
            rows = cursor.fetchall()
        if len(rows) > 1:
            raise AuthInfrastructureUnavailable
        replicas.append(tuple(rows[0]) if rows else None)

    if not replicas or all(row is None for row in replicas):
        return None
    if any(row is None for row in replicas) or any(row != replicas[0] for row in replicas[1:]):
        raise AuthInfrastructureUnavailable
    return replicas[0]


def _resolve_principal(account, active_codes: tuple[str, ...] | None = None):
    """Resolve the user's effective role and site from trusted account/profile rows."""
    if account is None or str(account[7]).lower() != "hoat_dong":
        return None

    account_id, username, slug, email = map(str, account[:4])
    account_role = str(account[5]).lower()
    site_code = str(account[6]).upper() if account[6] else None

    if account_role == "admin_big":
        if site_code is not None:
            return None
        return AuthenticatedUser(
            account_id=account_id,
            username=username,
            slug=slug,
            email=email,
            role="admin_big",
            must_change_password=bool(account[9]),
        )

    if not site_code or (active_codes is not None and site_code not in active_codes):
        return None

    try:
        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(
                "SELECT trang_thai FROM dbo.CoSo WHERE ma_co_so = %s",
                [site_code],
            )
            site = cursor.fetchone()
            if site is None or str(site[0]).lower() != "hoat_dong":
                return None

            if account_role == "nhan_vien":
                cursor.execute(
                    """
                    SELECT TOP (2) ma_nhan_vien, chuc_vu
                    FROM dbo.NhanVien
                    WHERE ma_tai_khoan = %s AND ma_co_so = %s AND trang_thai = 'dang_lam'
                    """,
                    [account_id, site_code],
                )
                profiles = cursor.fetchall()
                if len(profiles) != 1:
                    return None
                profile_id, position = str(profiles[0][0]), str(profiles[0][1]).lower()
                role = {
                    "quan_ly_co_so": "admin_small",
                    "le_tan": "le_tan",
                    "ke_toan": "ke_toan",
                }.get(position)
            elif account_role == "giao_vien":
                cursor.execute(
                    """
                    SELECT TOP (2) ma_giao_vien
                    FROM dbo.GiaoVien
                    WHERE ma_tai_khoan = %s AND ma_co_so = %s AND trang_thai = 'dang_day'
                    """,
                    [account_id, site_code],
                )
                profiles = cursor.fetchall()
                if len(profiles) != 1:
                    return None
                profile_id, role = str(profiles[0][0]), "giao_vien"
            else:
                return None
    except (DatabaseError, KeyError, ImproperlyConfigured, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

    if not role:
        return None
    return AuthenticatedUser(
        account_id=account_id,
        username=username,
        slug=slug,
        email=email,
        role=role,
        site_code=site_code,
        profile_id=profile_id,
        must_change_password=bool(account[9]),
    )


def _acquire_ip_lock(cursor, ip_digest: str) -> None:
    cursor.execute(
        """
        DECLARE @lock_result INT;
        EXEC @lock_result = sys.sp_getapplock
            @Resource = %s,
            @LockMode = 'Exclusive',
            @LockOwner = 'Transaction',
            @LockTimeout = 5000;
        SELECT @lock_result;
        """,
        [f"qlttnn-login:{ip_digest}"],
    )
    result = cursor.fetchone()[0]
    if result < 0:
        raise AuthInfrastructureUnavailable


def _rate_limit_wait(cursor, ip_digest: str, identifier_digest: str) -> int | None:
    cursor.execute(
        """
        SELECT COUNT_BIG(*), MIN(thoi_diem_utc),
               DATEDIFF(SECOND, MIN(thoi_diem_utc), SYSUTCDATETIME())
        FROM dbo.SuKienDangNhap
        WHERE ip_bam = %s
          AND thoi_diem_utc >= DATEADD(SECOND, -60, SYSUTCDATETIME())
        """,
        [ip_digest],
    )
    ip_count, _oldest, ip_age = cursor.fetchone()
    if ip_count >= settings.AUTH_LOGIN_IP_LIMIT_PER_MINUTE:
        return max(1, 60 - int(ip_age or 0))

    cursor.execute(
        """
        SELECT COUNT_BIG(*), MIN(thoi_diem_utc),
               DATEDIFF(SECOND, MIN(thoi_diem_utc), SYSUTCDATETIME())
        FROM dbo.SuKienDangNhap
        WHERE ip_bam = %s AND dinh_danh_bam = %s AND ket_qua = 'that_bai'
          AND thoi_diem_utc >= DATEADD(SECOND, -%s, SYSUTCDATETIME())
        """,
        [ip_digest, identifier_digest, settings.AUTH_LOGIN_IDENTITY_WINDOW_SECONDS],
    )
    failures, _oldest, age = cursor.fetchone()
    if failures >= settings.AUTH_LOGIN_IDENTITY_FAILURE_LIMIT:
        return max(1, settings.AUTH_LOGIN_IDENTITY_WINDOW_SECONDS - int(age or 0))
    return None


def _record_attempt(cursor, ip_digest: str, identifier_digest: str, outcome: str) -> None:
    cursor.execute(
        """
        INSERT INTO dbo.SuKienDangNhap (ma_su_kien, dinh_danh_bam, ip_bam, ket_qua)
        VALUES (NEWID(), %s, %s, %s)
        """,
        [identifier_digest, ip_digest, outcome],
    )


def _acquire_named_lock(cursor, resource: str) -> None:
    cursor.execute(
        """
        DECLARE @lock_result INT;
        EXEC @lock_result = sys.sp_getapplock
            @Resource = %s,
            @LockMode = 'Exclusive',
            @LockOwner = 'Transaction',
            @LockTimeout = 5000;
        SELECT @lock_result;
        """,
        [resource],
    )
    if cursor.fetchone()[0] < 0:
        raise AuthInfrastructureUnavailable


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


def _require_admin_small_email_configuration() -> str:
    temporary_password = settings.ADMIN_SMALL_TEMP_PASSWORD
    if not temporary_password or len(temporary_password) > 128:
        raise AuthInfrastructureUnavailable
    if "console.EmailBackend" in settings.EMAIL_BACKEND:
        raise AuthInfrastructureUnavailable
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or not settings.DEFAULT_FROM_EMAIL:
        raise AuthInfrastructureUnavailable
    return temporary_password


def _next_sequence_number(site_code: str, sequence_name: str) -> int:
    allowed_sequences = {"Seq_TK", "Seq_NV", "Seq_DB", "Seq_NK"}
    if sequence_name not in allowed_sequences:
        raise ValueError("Sequence không được phép.")
    try:
        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(f"SELECT NEXT VALUE FOR dbo.{sequence_name}")
            return int(cursor.fetchone()[0])
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


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


def auth_session_site_code() -> str:
    site_code = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    if not site_code:
        raise ImproperlyConfigured("Thiếu AUTH_SESSION_SITE_CODE trong src/api/.env.")
    return site_code


def change_authenticated_password(user: AuthenticatedUser, current_password: str, new_password: str) -> bool:
    """Verify the current password and replicate the replacement hash to every active site."""
    _resume_pending_password_resets()
    normalized_email = user.email.strip().casefold()
    sites = active_site_codes()
    alias = auth_session_alias()
    identifier_digest = _digest("password-reset-identity", normalized_email)
    transaction_id = None
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                _acquire_named_lock(cursor, f"qlttnn-reset-id:{identifier_digest}")
                account = _replicated_account(normalized_email, sites)
                if account is None or str(account[0]) != user.account_id:
                    return False
                if not check_password(current_password, str(account[4])):
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
        _apply_password_reset_transaction(transaction_id, sites)
        return True
    except AuthInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def login_user(identifier: str, password: str, remote_ip: str) -> tuple[AuthenticatedUser, str, Any] | None:
    """Authenticate any provisioned role using replicated account data and a local profile."""
    identifier = identifier.strip().casefold()
    if not identifier or not remote_ip:
        raise ValueError("Thiếu định danh hoặc địa chỉ IP.")

    _resume_pending_password_resets()
    registry_alias = auth_session_alias()
    ip_digest = _digest("ip", remote_ip)
    identifier_digest = _digest("identity", identifier)
    token = secrets.token_urlsafe(48)
    token_digest = session_token_digest(token)
    dummy_hash = settings.AUTH_DUMMY_PASSWORD_HASH

    try:
        with transaction.atomic(using=registry_alias):
            with connections[registry_alias].cursor() as cursor:
                _acquire_ip_lock(cursor, ip_digest)
                retry_after = _rate_limit_wait(cursor, ip_digest, identifier_digest)
                if retry_after is not None:
                    raise LoginRateLimitExceeded(retry_after)

                sites = active_site_codes()
                account = _replicated_account(identifier, sites)
                password_matches = check_password(
                    password,
                    account[4] if account is not None else dummy_hash,
                )
                user = _resolve_principal(account, sites) if account is not None and password_matches else None

                if user is None:
                    _record_attempt(cursor, ip_digest, identifier_digest, "that_bai")
                    return None

                cursor.execute(
                    """
                    INSERT INTO dbo.PhienDangNhap
                        (ma_phien, ma_tai_khoan, phien_ban_tai_khoan, token_bam,
                         tao_luc_utc, hoat_dong_cuoi_utc, het_han_utc)
                    OUTPUT INSERTED.het_han_utc
                    VALUES
                        (NEWID(), %s, %s, %s, SYSUTCDATETIME(), SYSUTCDATETIME(),
                         DATEADD(SECOND, %s, SYSUTCDATETIME()))
                    """,
                    [user.account_id, int(account[8]), token_digest, settings.AUTH_IDLE_TIMEOUT_SECONDS],
                )
                expires_at = cursor.fetchone()[0]
                _record_attempt(cursor, ip_digest, identifier_digest, "thanh_cong")
        return user, token, expires_at
    except (LoginRateLimitExceeded, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError) as exc:
        raise AuthInfrastructureUnavailable from exc


def load_user_session(token: str):
    _resume_pending_password_resets()
    token_digest = session_token_digest(token)
    alias = auth_session_alias()
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT s.ma_phien, s.ma_tai_khoan, s.het_han_utc,
                       a.ten_dang_nhap, a.slug, a.email, a.vai_tro,
                       a.ma_co_so, a.trang_thai, a.phien_ban,
                       a.bat_buoc_doi_mat_khau
                FROM dbo.PhienDangNhap AS s
                INNER JOIN dbo.TaiKhoan AS a ON a.ma_tai_khoan = s.ma_tai_khoan
                WHERE s.token_bam = %s
                  AND s.thu_hoi_luc_utc IS NULL
                  AND s.het_han_utc > SYSUTCDATETIME()
                  AND s.hoat_dong_cuoi_utc > DATEADD(SECOND, -%s, SYSUTCDATETIME())
                  AND s.phien_ban_tai_khoan = a.phien_ban
                  AND a.trang_thai = 'hoat_dong'
                """,
                [token_digest, settings.AUTH_IDLE_TIMEOUT_SECONDS],
            )
            row = cursor.fetchone()
        if row is None:
            return None
        account = (
            row[1], row[3], row[4], row[5], None, row[6], row[7], row[8], row[9], row[10]
        )
        user = _resolve_principal(account)
        if user is None:
            return None
        session = AuthenticatedSession(
            token_digest=token_digest,
            session_id=str(row[0]),
            expires_at=row[2],
        )
        return user, session
    except (DatabaseError, ImproperlyConfigured, KeyError) as exc:
        raise AuthInfrastructureUnavailable from exc


def extend_user_session(token_digest: str):
    alias = auth_session_alias()
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                UPDATE s
                SET hoat_dong_cuoi_utc = SYSUTCDATETIME(),
                    het_han_utc = DATEADD(SECOND, %s, SYSUTCDATETIME())
                OUTPUT INSERTED.het_han_utc
                FROM dbo.PhienDangNhap AS s
                INNER JOIN dbo.TaiKhoan AS a ON a.ma_tai_khoan = s.ma_tai_khoan
                WHERE s.token_bam = %s
                  AND s.thu_hoi_luc_utc IS NULL
                  AND s.het_han_utc > SYSUTCDATETIME()
                  AND s.phien_ban_tai_khoan = a.phien_ban
                  AND a.trang_thai = 'hoat_dong'
                """,
                [settings.AUTH_IDLE_TIMEOUT_SECONDS, token_digest],
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return row[0]
    except (DatabaseError, ImproperlyConfigured, KeyError) as exc:
        raise AuthInfrastructureUnavailable from exc


def revoke_user_session(token_digest: str) -> None:
    alias = auth_session_alias()
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                UPDATE dbo.PhienDangNhap
                SET thu_hoi_luc_utc = SYSUTCDATETIME()
                WHERE token_bam = %s AND thu_hoi_luc_utc IS NULL
                """,
                [token_digest],
            )
    except (DatabaseError, ImproperlyConfigured, KeyError) as exc:
        raise AuthInfrastructureUnavailable from exc
