"""Shared SQL Server authentication primitives and account types."""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError

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

class AdminSmallProfileNotFound(Exception):
    """The authenticated user has no active Admin Small profile at their site."""

class AdminSmallTargetNotFound(Exception):
    """The requested active Admin Small account does not exist."""

class AdminSmallDeleteConflict(Exception):
    """The requested account is not in the expected replicated state."""

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

@dataclass(frozen=True)
class AdminSmallDeactivationResult:
    account_id: str
    site_code: str
    status: str = "vo_hieu"

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

def _replicated_account_by_id(account_id: str, site_codes: tuple[str, ...]):
    replicas = []
    for code in site_codes:
        with get_site_connection(code).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2) ma_tai_khoan, ten_dang_nhap, slug, email, mat_khau,
                               vai_tro, ma_co_so, trang_thai, phien_ban,
                               bat_buoc_doi_mat_khau
                FROM dbo.TaiKhoan
                WHERE ma_tai_khoan = %s
                """,
                [account_id],
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

def auth_session_site_code() -> str:
    site_code = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    if not site_code:
        raise ImproperlyConfigured("Thiếu AUTH_SESSION_SITE_CODE trong src/api/.env.")
    return site_code
