"""Provider OAuth and replicated student identity linking."""

from __future__ import annotations

import json
import base64
import hashlib
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    AuthenticatedUser,
    LoginRateLimitExceeded,
    _acquire_ip_lock,
    _acquire_named_lock,
    _digest,
    _rate_limit_wait,
    _record_attempt,
    _resolve_principal,
    active_site_codes,
    auth_session_alias,
    session_token_digest,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


OAUTH_STATE_COOKIE_AGE = 600
OAUTH_STATE_COOKIE_SALT = "qlttnn.oauth.state.v1"
PROVIDER_COLUMNS = {"google": "google_subject", "facebook": "facebook_subject"}


class OAuthNotConfigured(Exception):
    pass


class OAuthProviderError(Exception):
    pass


class OAuthStateInvalid(Exception):
    pass


class OAuthAccountConflict(Exception):
    pass


def oauth_state_cookie_name(provider: str) -> str:
    if provider not in PROVIDER_COLUMNS:
        raise OAuthNotConfigured
    return f"{settings.AUTH_COOKIE_NAME}_oauth_{provider}"


def _provider_settings(provider: str) -> tuple[str, str, str]:
    if provider == "google":
        values = (
            settings.GOOGLE_OAUTH_CLIENT_ID,
            settings.GOOGLE_OAUTH_CLIENT_SECRET,
            settings.GOOGLE_OAUTH_REDIRECT_URI,
        )
    elif provider == "facebook":
        values = (
            settings.FACEBOOK_OAUTH_APP_ID,
            settings.FACEBOOK_OAUTH_APP_SECRET,
            settings.FACEBOOK_OAUTH_REDIRECT_URI,
        )
    else:
        raise OAuthNotConfigured
    if not all(values):
        raise OAuthNotConfigured
    parsed = urllib.parse.urlsplit(values[2])
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise OAuthNotConfigured
    if not settings.DEBUG and parsed.scheme != "https":
        raise OAuthNotConfigured
    return values


def create_oauth_flow(provider: str, intent: str, account_id: str | None = None) -> tuple[str, dict[str, str]]:
    client_id, _secret, redirect_uri = _provider_settings(provider)
    if intent not in {"login", "link"} or (intent == "link") != bool(account_id):
        raise OAuthStateInvalid

    state = secrets.token_urlsafe(32)
    payload = {
        "provider": provider,
        "intent": intent,
        "state": state,
        "nonce": secrets.token_urlsafe(32),
        "verifier": secrets.token_urlsafe(48),
        "account_id": account_id or "",
    }
    parameters = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    if provider == "google":
        challenge = base64.urlsafe_b64encode(hashlib.sha256(payload["verifier"].encode()).digest()).decode().rstrip("=")
        parameters.update(
            {
                "scope": "openid email profile",
                "nonce": payload["nonce"],
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    else:
        parameters["scope"] = "public_profile"
        authorize_url = f"https://www.facebook.com/{settings.FACEBOOK_GRAPH_API_VERSION}/dialog/oauth"

    cookie = signing.dumps(payload, salt=OAUTH_STATE_COOKIE_SALT, compress=True)
    return f"{authorize_url}?{urllib.parse.urlencode(parameters)}", {"cookie": cookie, "state": state}


def read_oauth_flow(provider: str, cookie: str, returned_state: str) -> dict[str, str]:
    try:
        payload = signing.loads(cookie, salt=OAUTH_STATE_COOKIE_SALT, max_age=OAUTH_STATE_COOKIE_AGE)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise OAuthStateInvalid from exc
    if (
        not isinstance(payload, dict)
        or payload.get("provider") != provider
        or not isinstance(returned_state, str)
        or not secrets.compare_digest(str(payload.get("state", "")), returned_state)
    ):
        raise OAuthStateInvalid
    return payload


def _request_json(url: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    body = urllib.parse.urlencode(data).encode("ascii") if data is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=10) as response:
            raw = response.read(65_537)
        if len(raw) > 65_536:
            raise OAuthProviderError
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise OAuthProviderError
        return result
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError) as exc:
        raise OAuthProviderError from exc


def exchange_oauth_code(provider: str, code: str, flow: dict[str, str]) -> str:
    if not code or len(code) > 4096:
        raise OAuthProviderError
    client_id, client_secret, redirect_uri = _provider_settings(provider)
    if provider == "google":
        tokens = _request_json(
            "https://oauth2.googleapis.com/token",
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": flow["verifier"],
            },
        )
        token = tokens.get("id_token")
        if not isinstance(token, str) or len(token) > 16_384:
            raise OAuthProviderError
        try:
            from google.auth.exceptions import GoogleAuthError
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token

            claims = id_token.verify_oauth2_token(token, Request(), client_id)
            subject = claims.get("sub")
            if (
                claims.get("nonce") != flow.get("nonce")
                or claims.get("email_verified") is not True
                or not isinstance(subject, str)
                or not subject
                or len(subject) > 255
            ):
                raise OAuthProviderError
            return subject
        except (GoogleAuthError, ImportError, ValueError, KeyError, TypeError) as exc:
            raise OAuthProviderError from exc

    graph_version = settings.FACEBOOK_GRAPH_API_VERSION
    token_data = _request_json(
        f"https://graph.facebook.com/{graph_version}/oauth/access_token?"
        + urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            }
        )
    )
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token or len(access_token) > 8192:
        raise OAuthProviderError
    app_token = f"{client_id}|{client_secret}"
    debug = _request_json(
        f"https://graph.facebook.com/{graph_version}/debug_token?"
        + urllib.parse.urlencode({"input_token": access_token, "access_token": app_token})
    ).get("data")
    if not isinstance(debug, dict) or debug.get("is_valid") is not True or str(debug.get("app_id")) != client_id:
        raise OAuthProviderError
    subject = debug.get("user_id")
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise OAuthProviderError
    return subject


def _consume_oauth_state(cursor, state: str, ip_digest: str) -> None:
    state_digest = _digest("oauth-state", state)
    _acquire_named_lock(cursor, f"qlttnn-oauth-state:{state_digest}")
    cursor.execute(
        "SELECT TOP (1) ma_log FROM dbo.Logs WHERE loai_log = 'system' AND hanh_dong = 'oauth_state' AND dinh_danh_bam = %s",
        [state_digest],
    )
    if cursor.fetchone():
        raise OAuthStateInvalid
    cursor.execute(
        """
        INSERT INTO dbo.Logs (ma_log, loai_log, hanh_dong, dinh_danh_bam, ip_bam, ket_qua)
        VALUES (CONVERT(NVARCHAR(120), NEWID()), 'system', 'oauth_state', %s, %s, 'thanh_cong')
        """,
        [state_digest, ip_digest],
    )


def consume_oauth_state_once(state: str, remote_ip: str) -> None:
    """Persist one-time callback use before contacting a provider or changing data."""
    alias = auth_session_alias()
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                _consume_oauth_state(cursor, state, _digest("ip", remote_ip or "unknown"))
    except (OAuthStateInvalid, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def _replicated_provider_account(provider: str, subject: str, sites: tuple[str, ...]):
    column = PROVIDER_COLUMNS[provider]
    rows_by_site = []
    for site in sites:
        with get_site_connection(site).cursor() as cursor:
            cursor.execute(
                f"""
                SELECT TOP (2) ma_tai_khoan, ten_dang_nhap, slug, email, mat_khau,
                               vai_tro, ma_co_so, trang_thai, phien_ban,
                               bat_buoc_doi_mat_khau, google_subject, facebook_subject
                FROM dbo.TaiKhoan WHERE {column} = %s
                """,
                [subject],
            )
            rows = cursor.fetchall()
        if len(rows) > 1:
            raise AuthInfrastructureUnavailable
        rows_by_site.append(tuple(rows[0]) if rows else None)
    if all(row is None for row in rows_by_site):
        return None
    if any(row is None for row in rows_by_site) or any(row != rows_by_site[0] for row in rows_by_site[1:]):
        raise AuthInfrastructureUnavailable
    return rows_by_site[0]


def login_with_oauth_provider(provider: str, subject: str, remote_ip: str):
    if provider not in PROVIDER_COLUMNS or not remote_ip:
        raise OAuthProviderError
    alias = auth_session_alias()
    ip_digest = _digest("ip", remote_ip)
    identity_digest = _digest("identity", f"oauth:{provider}:{subject}")
    token = secrets.token_urlsafe(48)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                _acquire_ip_lock(cursor, ip_digest)
                retry_after = _rate_limit_wait(cursor, ip_digest, identity_digest)
                if retry_after is not None:
                    raise LoginRateLimitExceeded(retry_after)
                sites = active_site_codes()
                account = _replicated_provider_account(provider, subject, sites)
                user = _resolve_principal(account[:10], sites) if account else None
                if user is None or user.role != "hoc_vien":
                    _record_attempt(cursor, ip_digest, identity_digest, "that_bai")
                    return None
                cursor.execute(
                    """
                    INSERT INTO dbo.PhienDangNhap
                        (ma_phien, ma_tai_khoan, phien_ban_tai_khoan, token_bam,
                         tao_luc_utc, hoat_dong_cuoi_utc, het_han_utc)
                    OUTPUT INSERTED.het_han_utc
                    VALUES (NEWID(), %s, %s, %s, SYSUTCDATETIME(), SYSUTCDATETIME(),
                            DATEADD(SECOND, %s, SYSUTCDATETIME()))
                    """,
                    [user.account_id, int(account[8]), session_token_digest(token), settings.AUTH_IDLE_TIMEOUT_SECONDS],
                )
                expires_at = cursor.fetchone()[0]
                _record_attempt(cursor, ip_digest, identity_digest, "thanh_cong")
        return user, token, expires_at
    except (AuthInfrastructureUnavailable, LoginRateLimitExceeded, OAuthStateInvalid):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def _read_account_for_link(site: str, account_id: str, column: str, subject: str):
    other_column = "facebook_subject" if column == "google_subject" else "google_subject"
    with get_site_connection(site).cursor() as cursor:
        cursor.execute(
            f"""
            SELECT TOP (3) ma_tai_khoan, ten_dang_nhap, slug, email, mat_khau,
                           vai_tro, ma_co_so, trang_thai, phien_ban,
                           bat_buoc_doi_mat_khau, {column}, {other_column}
            FROM dbo.TaiKhoan
            WHERE ma_tai_khoan = %s OR {column} = %s
            """,
            [account_id, subject],
        )
        return [tuple(row) for row in cursor.fetchall()]


def link_oauth_provider(user: AuthenticatedUser, provider: str, subject: str, remote_ip: str) -> None:
    if provider not in PROVIDER_COLUMNS or user.role != "hoc_vien":
        raise OAuthAccountConflict
    column = PROVIDER_COLUMNS[provider]
    sites = active_site_codes()
    registry_alias = auth_session_alias()
    target_rows = []
    try:
        with transaction.atomic(using=registry_alias):
            with connections[registry_alias].cursor() as cursor:
                subject_digest = _digest(f"oauth-{provider}", subject)
                _acquire_named_lock(cursor, f"qlttnn-oauth-link-account:{user.account_id}")
                _acquire_named_lock(cursor, f"qlttnn-oauth-link-subject:{subject_digest}")
                for site in sites:
                    rows = _read_account_for_link(site, user.account_id, column, subject)
                    account_rows = [row for row in rows if str(row[0]) == user.account_id]
                    if len(account_rows) != 1 or len(rows) != 1:
                        raise OAuthAccountConflict
                    target_rows.append(account_rows[0])

                base = target_rows[0][:10]
                other_identity = target_rows[0][11]
                if any(row[:10] != base or row[11] != other_identity for row in target_rows[1:]):
                    raise AuthInfrastructureUnavailable
                if any(row[5] != "hoc_vien" for row in target_rows):
                    raise OAuthAccountConflict
                principal = _resolve_principal(base, sites)
                if (
                    principal is None
                    or principal.account_id != user.account_id
                    or principal.role != "hoc_vien"
                    or principal.profile_id != user.profile_id
                ):
                    raise OAuthAccountConflict
                if any(row[10] not in (None, subject) for row in target_rows):
                    raise OAuthAccountConflict

                for site, row in zip(sites, target_rows):
                    if row[10] == subject:
                        continue
                    alias = get_site_database_alias(site)
                    with transaction.atomic(using=alias):
                        with connections[alias].cursor() as site_cursor:
                            site_cursor.execute(
                                f"UPDATE dbo.TaiKhoan SET {column} = %s, cap_nhat_luc = SYSUTCDATETIME() "
                                f"WHERE ma_tai_khoan = %s AND {column} IS NULL",
                                [subject, user.account_id],
                            )
                            if site_cursor.rowcount != 1:
                                raise OAuthAccountConflict
                            site_cursor.execute(
                                """
                                INSERT INTO dbo.Logs
                                    (ma_log, loai_log, ma_tai_khoan, hanh_dong,
                                     bang_tac_dong, ma_ban_ghi, ket_qua)
                                VALUES
                                    (CONVERT(NVARCHAR(120), NEWID()), 'system', %s, %s,
                                     'TaiKhoan', %s, 'thanh_cong')
                                """,
                                [user.account_id, f"oauth_link_{provider}", user.account_id],
                            )
    except (AuthInfrastructureUnavailable, OAuthAccountConflict, OAuthStateInvalid):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def get_oauth_connections(user: AuthenticatedUser, slug: str) -> dict[str, bool]:
    if user.role != "hoc_vien" or slug != user.slug:
        raise OAuthAccountConflict
    sites = active_site_codes()
    replicas = []
    try:
        for site in sites:
            with get_site_connection(site).cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP (2) ma_tai_khoan, ten_dang_nhap, slug, email, mat_khau,
                                   vai_tro, ma_co_so, trang_thai, phien_ban,
                                   bat_buoc_doi_mat_khau, google_subject, facebook_subject
                    FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s
                    """,
                    [user.account_id],
                )
                rows = cursor.fetchall()
            if len(rows) != 1:
                raise AuthInfrastructureUnavailable
            replicas.append(tuple(rows[0]))
        if any(row != replicas[0] for row in replicas[1:]):
            raise AuthInfrastructureUnavailable
        if replicas[0][5] != "hoc_vien" or _resolve_principal(replicas[0][:10], sites) is None:
            raise OAuthAccountConflict
        return {"google": bool(replicas[0][10]), "facebook": bool(replicas[0][11])}
    except (AuthInfrastructureUnavailable, OAuthAccountConflict):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
