"""Self-service profile updates for the global Admin Big account."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.hashers import check_password
from django.db import DatabaseError, connections, transaction

from core.auth.account_state import account_is_active
from core.auth.services import (
    AuthInfrastructureUnavailable,
    _digest,
    _replicated_account_by_id,
    active_site_codes,
    auth_session_alias,
    auth_session_site_code,
)
from core.media.avatars import AvatarConflict, AvatarUnavailable, get_admin_avatar_url
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


logger = logging.getLogger("core.auth")
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


def _acquire_session_lock(cursor, resource: str) -> None:
    cursor.execute(
        """
        DECLARE @lock_result INT;
        EXEC @lock_result = sys.sp_getapplock
            @Resource = %s,
            @LockMode = 'Exclusive',
            @LockOwner = 'Session',
            @LockTimeout = 10000;
        SELECT @lock_result;
        """,
        [resource],
    )
    if cursor.fetchone()[0] < 0:
        raise AuthInfrastructureUnavailable


def _release_session_lock(cursor, resource: str) -> None:
    cursor.execute(
        """
        DECLARE @release_result INT;
        EXEC @release_result = sys.sp_releaseapplock
            @Resource = %s,
            @LockOwner = 'Session';
        SELECT @release_result;
        """,
        [resource],
    )
    cursor.fetchone()


def _identity_lock_resources(values: dict[str, str]) -> list[str]:
    purposes = {
        "email": "admin-small-email",
        "username": "admin-small-username",
        "slug": "account-slug",
    }
    return [
        f"qlttnn-{purposes[field]}:{_digest(purposes[field], values[field].casefold())}"
        for field in _IDENTITY_FIELDS
    ]


def _load_pending_job(cursor, account_id: str):
    cursor.execute(
        """
        SELECT TOP (2) ma_giao_dich, site_codes_json, gia_tri_cu_json, gia_tri_moi_json
        FROM dbo.GiaoDichCapNhatAdminBig
        WHERE ma_admin_big = %s AND trang_thai = 'dang_xu_ly'
        ORDER BY tao_luc_utc
        """,
        [account_id],
    )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise AuthInfrastructureUnavailable
    if not rows:
        return None
    row = rows[0]
    try:
        return {
            "job_id": str(row[0]),
            "sites": tuple(str(code).upper() for code in json.loads(row[1])),
            "old": json.loads(row[2]),
            "new": json.loads(row[3]),
        }
    except (TypeError, ValueError, KeyError) as exc:
        raise AuthInfrastructureUnavailable from exc


def _ensure_account_identity_available(
    account_id: str, values: dict[str, str], sites: tuple[str, ...]
) -> None:
    for site_code in sites:
        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (1) ma_tai_khoan
                FROM dbo.TaiKhoan
                WHERE ma_tai_khoan <> %s
                  AND (LOWER(email) = %s OR LOWER(ten_dang_nhap) = %s OR slug = %s)
                """,
                [account_id, values["email"].casefold(), values["username"].casefold(), values["slug"]],
            )
            if cursor.fetchone() is not None:
                raise AdminBigProfileConflict


def _ensure_site_logs(
    cursor,
    site_code: str,
    account_id: str,
    job_id: str,
    actor_id: str,
    remote_ip: str,
    changed_fields: list[str],
) -> None:
    audit_id = f"{site_code}-NK-{uuid.uuid5(uuid.NAMESPACE_URL, f'{job_id}:{site_code}:audit').hex[:10]}"
    sync_id = f"{site_code}-DB-{uuid.uuid5(uuid.NAMESPACE_URL, f'{job_id}:{site_code}:sync').hex[:10]}"
    safe_fields = json.dumps({"changed_fields": changed_fields}, ensure_ascii=False)

    cursor.execute(
        "SELECT ma_tai_khoan, hanh_dong, bang_tac_dong, ma_ban_ghi "
        "FROM dbo.Logs WHERE loai_log = 'system' AND ma_log = %s",
        [audit_id],
    )
    audit = cursor.fetchone()
    expected_audit = (actor_id, "sua_tai_khoan_ca_nhan", "TaiKhoan", account_id)
    if audit is not None:
        if tuple(str(value) for value in audit) != expected_audit:
            raise AuthInfrastructureUnavailable
    else:
        cursor.execute(
            """
            INSERT INTO dbo.Logs
                (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
                 ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua, ghi_chu)
            VALUES (%s, 'system', %s, %s, 'sua_tai_khoan_ca_nhan', 'TaiKhoan', %s,
                    %s, %s, %s, 'thanh_cong', N'Admin Big tự cập nhật tài khoản của chính mình.')
            """,
            [audit_id, site_code, actor_id, account_id, safe_fields, safe_fields, remote_ip[:45]],
        )

    cursor.execute(
        "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua "
        "FROM dbo.Logs WHERE loai_log = 'sync' AND ma_log = %s",
        [sync_id],
    )
    sync_event = cursor.fetchone()
    expected_sync = ("TaiKhoan", account_id, "sua", site_code, "thanh_cong")
    if sync_event is not None:
        if tuple(str(value) for value in sync_event) != expected_sync:
            raise AuthInfrastructureUnavailable
        return
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua)
        VALUES (%s, 'sync', 'TaiKhoan', %s, 'sua', %s, 'thanh_cong')
        """,
        [sync_id, account_id, site_code],
    )


def _apply_profile_job(
    account_id: str,
    actor_id: str,
    job: dict[str, Any],
    sites: tuple[str, ...],
    remote_ip: str,
) -> None:
    old = job["old"]
    new = job["new"]
    changed_fields = sorted(field for field in _IDENTITY_FIELDS if old[field] != new[field])
    coordinator_site = auth_session_site_code()
    ordered_sites = (coordinator_site,) + tuple(code for code in sites if code != coordinator_site)

    for site_code in ordered_sites:
        alias = get_site_database_alias(site_code)
        try:
            with transaction.atomic(using=alias):
                with connections[alias].cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT slug, ten_dang_nhap, email, vai_tro, ma_co_so, trang_thai
                        FROM dbo.TaiKhoan WITH (UPDLOCK, ROWLOCK)
                        WHERE ma_tai_khoan = %s
                        """,
                        [account_id],
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise AdminBigProfileConflict
                    current = {"slug": str(row[0]), "username": str(row[1]), "email": str(row[2])}
                    if (
                        str(row[3]).lower() != "admin_big"
                        or row[4] is not None
                        or str(row[5]).lower() != "hoat_dong"
                    ):
                        raise AdminBigProfileConflict

                    if current == old:
                        cursor.execute(
                            """
                            UPDATE dbo.TaiKhoan
                            SET slug = %s, ten_dang_nhap = %s, email = %s,
                                cap_nhat_luc = SYSUTCDATETIME()
                            WHERE ma_tai_khoan = %s AND vai_tro = 'admin_big'
                              AND ma_co_so IS NULL AND trang_thai = 1
                              AND slug = %s AND ten_dang_nhap = %s AND email = %s
                            """,
                            [new["slug"], new["username"], new["email"], account_id,
                             old["slug"], old["username"], old["email"]],
                        )
                        if cursor.rowcount != 1:
                            raise AdminBigProfileConflict
                    elif current != new:
                        raise AdminBigProfileConflict

                    _ensure_site_logs(
                        cursor, site_code, account_id, job["job_id"], actor_id,
                        remote_ip, changed_fields,
                    )
        except (AdminBigProfileConflict, AuthInfrastructureUnavailable):
            raise
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
            logger.warning(
                "Admin Big profile replication paused; site=%s; error_type=%s.",
                site_code,
                type(exc).__name__,
            )
            raise AuthInfrastructureUnavailable from exc


def _complete_profile_job(alias: str, job_id: str) -> None:
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT trang_thai
                FROM dbo.GiaoDichCapNhatAdminBig WITH (UPDLOCK, ROWLOCK)
                WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                """,
                [job_id],
            )
            row = cursor.fetchone()
            if row is None:
                raise AuthInfrastructureUnavailable
            if str(row[0]).lower() == "hoan_tat":
                return
            if str(row[0]).lower() != "dang_xu_ly":
                raise AuthInfrastructureUnavailable
            cursor.execute(
                """
                UPDATE dbo.GiaoDichCapNhatAdminBig
                SET trang_thai = 'hoan_tat',
                    gia_tri_cu_json = NULL,
                    gia_tri_moi_json = NULL,
                    hoan_tat_luc_utc = SYSUTCDATETIME(),
                    cap_nhat_luc_utc = SYSUTCDATETIME()
                WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                  AND trang_thai = 'dang_xu_ly'
                """,
                [job_id],
            )
            if cursor.rowcount != 1:
                raise AuthInfrastructureUnavailable


def _expanded_sites(job: dict[str, Any], active_sites: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(job["sites"]).union(active_sites)))


def _persist_expanded_sites(alias: str, job_id: str, sites: tuple[str, ...]) -> None:
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                UPDATE dbo.GiaoDichCapNhatAdminBig
                SET site_codes_json = %s, cap_nhat_luc_utc = SYSUTCDATETIME()
                WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                  AND trang_thai = 'dang_xu_ly'
                """,
                [json.dumps(sites), job_id],
            )
            if cursor.rowcount != 1:
                raise AuthInfrastructureUnavailable


def _release_session_locks(connection, cursor, held_locks: list[str]) -> None:
    for resource in reversed(held_locks):
        try:
            _release_session_lock(cursor, resource)
        except DatabaseError:
            connection.close()
            break


def _resume_pending_profile_job(
    account_id: str,
    active_sites: tuple[str, ...],
    remote_ip: str,
    lock_cursor,
    held_locks: list[str],
) -> None:
    coordinator_alias = auth_session_alias()
    with connections[coordinator_alias].cursor() as cursor:
        pending = _load_pending_job(cursor, account_id)
    if pending is None:
        return

    for resource in sorted(_identity_lock_resources(pending["new"])):
        if resource in held_locks:
            continue
        _acquire_session_lock(lock_cursor, resource)
        held_locks.append(resource)

    expanded = _expanded_sites(pending, active_sites)
    if expanded != tuple(sorted(pending["sites"])):
        _persist_expanded_sites(coordinator_alias, pending["job_id"], expanded)
        pending["sites"] = expanded
    _apply_profile_job(account_id, account_id, pending, expanded, remote_ip)
    _complete_profile_job(coordinator_alias, pending["job_id"])


def update_admin_big_self_profile(
    user,
    slug: str,
    updates: dict[str, str],
    current_password: str,
    remote_ip: str,
) -> dict[str, Any]:
    if (
        getattr(user, "role", None) != "admin_big"
        or slug != getattr(user, "slug", None)
        or not updates
    ):
        raise AdminBigProfileNotFound
    if not set(updates).issubset(set(_IDENTITY_FIELDS)) or not remote_ip:
        raise ValueError("Dữ liệu cập nhật tài khoản Admin Big không hợp lệ.")

    held_locks: list[str] = []

    try:
        sites = active_site_codes()
        coordinator_alias = auth_session_alias()
        connection = connections[coordinator_alias]
        account_lock = f"qlttnn-admin-big-profile:{_digest('admin-big-profile', user.account_id)}"
        with connection.cursor() as lock_cursor:
            _acquire_session_lock(lock_cursor, account_lock)
            held_locks.append(account_lock)
            try:
                _resume_pending_profile_job(
                    user.account_id, sites, remote_ip, lock_cursor, held_locks
                )

                account = _replicated_account_by_id(user.account_id, sites)
                _assert_admin_big(account, user.account_id)
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

                for resource in sorted(_identity_lock_resources(old) + _identity_lock_resources(new)):
                    if resource in held_locks:
                        continue
                    _acquire_session_lock(lock_cursor, resource)
                    held_locks.append(resource)

                account = _replicated_account_by_id(user.account_id, sites)
                _assert_admin_big(account, user.account_id)
                if _account_values(account) != old:
                    raise AdminBigProfileConflict
                _ensure_account_identity_available(user.account_id, new, sites)

                job_id = str(uuid.uuid4())
                with transaction.atomic(using=coordinator_alias):
                    with connections[coordinator_alias].cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO dbo.GiaoDichCapNhatAdminBig
                                (ma_giao_dich, ma_admin_big, site_codes_json,
                                 gia_tri_cu_json, gia_tri_moi_json, trang_thai)
                            VALUES (CONVERT(uniqueidentifier, %s), %s, %s, %s, %s, 'dang_xu_ly')
                            """,
                            [job_id, user.account_id, json.dumps(sites),
                             json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False)],
                        )

                job = {"job_id": job_id, "sites": sites, "old": old, "new": new}
                _apply_profile_job(user.account_id, user.account_id, job, sites, remote_ip)
                _complete_profile_job(coordinator_alias, job_id)
                return _response(user.account_id, new, account)
            finally:
                _release_session_locks(connection, lock_cursor, held_locks)
    except (
        AdminBigProfileNotFound,
        AdminBigProfilePasswordInvalid,
        AdminBigProfileConflict,
        AuthInfrastructureUnavailable,
    ):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
