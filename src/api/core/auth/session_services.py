"""Authentication, idle-session lifecycle, and session-password services."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.sites.connections import UnknownSiteError
from core.auth.password_reset import _apply_password_reset_transaction, _resume_pending_password_resets
from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    AuthenticatedSession,
    AuthenticatedUser,
    LoginRateLimitExceeded,
    _acquire_ip_lock,
    _acquire_named_lock,
    _digest,
    _rate_limit_wait,
    _record_attempt,
    _replicated_account,
    _resolve_principal,
    active_site_codes,
    auth_session_alias,
    session_token_digest,
)

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
                  AND a.trang_thai = 1
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
                  AND a.trang_thai = 1
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
