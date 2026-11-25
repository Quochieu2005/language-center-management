"""Self-service profile updates for the global Admin Big account."""

from __future__ import annotations

import json
import uuid
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.hashers import check_password
from django.db import DatabaseError, connections, transaction

from core.auth.account_state import account_is_active
from core.auth.services import (
    AuthInfrastructureUnavailable,
    _replicated_account_by_id,
    active_site_codes,
    auth_session_alias,
    auth_session_site_code,
)
from core.auth.account_writes import AccountVersionConflict, update_authority_account
from core.auth.service_common import _acquire_named_lock
from core.media.avatars import AvatarConflict, AvatarUnavailable, get_admin_avatar_url
from core.sites.connections import UnknownSiteError

_IDENTITY_FIELDS = ("email", "username", "slug")


class AdminBigProfileNotFound(Exception):
    """The authenticated Admin Big account is not active on every site."""


class AdminBigProfilePasswordInvalid(Exception):
    """The supplied current password does not match the account."""


class AdminBigProfileConflict(Exception):
    """Another account uses an identity value, or a pending update conflicts."""


def _account_values(account) -> dict[str, str]:
    return {
        "username": str(account[1]),
        "slug": str(account[2]),
        "email": str(account[3]),
    }


def _response(account_id: str, values: dict[str, str], account) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "slug": values["slug"],
        "username": values["username"],
        "email": values["email"],
        "role": "admin_big",
        "site_code": None,
        "account_status": "active" if account_is_active(account[7]) else "inactive",
        "must_change_password": bool(account[9]),
    }


def _assert_admin_big(account, account_id: str) -> None:
    if (
        account is None
        or str(account[0]) != account_id
        or str(account[5]).lower() != "admin_big"
        or account[6] is not None
        or not account_is_active(account[7])
    ):
        raise AdminBigProfileNotFound


def get_admin_big_self_profile(user, slug: str) -> dict[str, Any]:
    if getattr(user, "role", None) != "admin_big" or slug != getattr(user, "slug", None):
        raise AdminBigProfileNotFound
    try:
        sites = active_site_codes()
        account = _replicated_account_by_id(user.account_id, sites)
        _assert_admin_big(account, user.account_id)
        if str(account[2]) != slug:
            raise AdminBigProfileNotFound
        profile = _response(user.account_id, _account_values(account), account)
        profile["avatar_secure_url"] = get_admin_avatar_url(user.account_id, "admin_big")
        return profile
    except AdminBigProfileNotFound:
        raise
    except (AvatarConflict, AvatarUnavailable) as exc:
        raise AuthInfrastructureUnavailable from exc
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


_ACCOUNT_SELECT = (
    "SELECT ma_tai_khoan, ten_dang_nhap, slug, email, mat_khau, vai_tro, ma_co_so, "
    "trang_thai, phien_ban, bat_buoc_doi_mat_khau FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK) "
    "WHERE ma_tai_khoan = %s"
)


def update_admin_big_self_profile(
    user,
    slug: str,
    updates: dict[str, str],
    current_password: str,
    remote_ip: str,
) -> dict[str, Any]:
    """Change Admin Big identity on the authority row; ``sync_accounts`` copies it to replicas."""
    if (
        getattr(user, "role", None) != "admin_big"
        or slug != getattr(user, "slug", None)
        or not updates
    ):
        raise AdminBigProfileNotFound
    if not set(updates).issubset(set(_IDENTITY_FIELDS)) or not remote_ip:
        raise ValueError("Dữ liệu cập nhật tài khoản Admin Big không hợp lệ.")

    alias = auth_session_alias()
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                # Same lock as account creation: email/username/slug are one global namespace.
                _acquire_named_lock(cursor, "qlttnn-account-creation")
                cursor.execute(_ACCOUNT_SELECT, [user.account_id])
                account = cursor.fetchone()
                _assert_admin_big(account, user.account_id)
                if str(account[2]) != slug:
                    raise AdminBigProfileNotFound
                if not check_password(current_password, str(account[4])):
                    raise AdminBigProfilePasswordInvalid

                old = _account_values(account)
                new = dict(old)
                new.update(updates)
                if "username" in updates and "slug" not in updates:
                    from core.slug_utils import make_slug

                    new["slug"] = make_slug(new["username"], max_length=120)
                if old == new:
                    return _response(user.account_id, old, account)

                cursor.execute(
                    "SELECT TOP (1) ma_tai_khoan FROM dbo.TaiKhoan "
                    "WHERE ma_tai_khoan <> %s AND (LOWER(email) = %s OR LOWER(ten_dang_nhap) = %s OR slug = %s)",
                    [user.account_id, new["email"].casefold(), new["username"].casefold(), new["slug"]],
                )
                if cursor.fetchone() is not None:
                    raise AdminBigProfileConflict
                try:
                    update_authority_account(
                        cursor, user.account_id, int(account[8]),
                        {"slug": new["slug"], "ten_dang_nhap": new["username"], "email": new["email"]},
                    )
                except AccountVersionConflict as exc:
                    raise AdminBigProfileConflict from exc

                changed_fields = sorted(field for field in _IDENTITY_FIELDS if old[field] != new[field])
                safe_fields = json.dumps({"changed_fields": changed_fields}, ensure_ascii=False)
                cursor.execute(
                    """
                    INSERT INTO dbo.Logs
                        (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
                         ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua, ghi_chu)
                    VALUES (%s, 'system', %s, %s, 'sua_tai_khoan_ca_nhan', 'TaiKhoan', %s,
                            %s, %s, %s, 'thanh_cong', N'Admin Big tự cập nhật tài khoản của chính mình.')
                    """,
                    [f"{auth_session_site_code()}-NK-{uuid.uuid4().hex[:10]}", auth_session_site_code(),
                     user.account_id, user.account_id, safe_fields, safe_fields, remote_ip[:45]],
                )
                return _response(user.account_id, new, account)
    except (
        AdminBigProfileNotFound,
        AdminBigProfilePasswordInvalid,
        AdminBigProfileConflict,
        AuthInfrastructureUnavailable,
    ):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
