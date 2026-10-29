"""Direct active/inactive updates for replicated accounts without a job table."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.auth.account_state import account_status_bit
from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    active_site_codes,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


class AccountStatusTargetNotFound(Exception):
    """No matching active-site account/profile exists for the requested slug."""


class AccountStatusConflict(Exception):
    """The account changed concurrently or its Admin profile is inconsistent."""


@dataclass(frozen=True)
class AccountStatusResult:
    account_id: str
    slug: str
    role: str
    site_code: str
    status: str


def _read_admin_small_profile(account_id: str, site_code: str) -> tuple[str, int] | None:
    with get_site_connection(site_code).cursor() as cursor:
        cursor.execute(
            """
            SELECT TOP (2) ma_admin, trang_thai
            FROM dbo.Admin
            WHERE ma_tai_khoan = %s AND ma_co_so = %s AND loai_admin = 'admin_small'
            """,
            [account_id, site_code],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise AccountStatusConflict
    if not rows:
        return None
    bit = account_status_bit(rows[0][1])
    if bit is None:
        raise AccountStatusConflict
    return str(rows[0][0]), bit


def _read_account_by_slug(slug: str, sites: tuple[str, ...]):
    replicas = []
    for site in sites:
        with get_site_connection(site).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2) ma_tai_khoan, ten_dang_nhap, slug, email, mat_khau,
                               vai_tro, ma_co_so, trang_thai, phien_ban,
                               bat_buoc_doi_mat_khau
                FROM dbo.TaiKhoan WHERE slug = %s
                """,
                [slug],
            )
            rows = cursor.fetchall()
        if len(rows) > 1:
            raise AuthInfrastructureUnavailable
        replicas.append(tuple(rows[0]) if rows else None)
    if all(row is None for row in replicas):
        return None
    if any(row is None for row in replicas) or any(row != replicas[0] for row in replicas[1:]):
        raise AuthInfrastructureUnavailable
    return replicas[0]


def _write_sync_and_audit(
    cursor, *, site_code: str, account_id: str, actor_id: str,
    remote_ip: str, action_id: str, status_bit: int,
) -> None:
    event_id = f"{site_code}-DB-{uuid.uuid5(uuid.NAMESPACE_URL, f'{action_id}:{site_code}').hex[:10]}"
    cursor.execute(
        "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua "
        "FROM dbo.Logs WHERE loai_log = 'sync' AND ma_log = %s",
        [event_id],
    )
    row = cursor.fetchone()
    expected = ("TaiKhoan", account_id, "sua", site_code, "thanh_cong")
    if row is None:
        cursor.execute(
            """
            INSERT INTO dbo.Logs
                (ma_log, loai_log, bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua)
            VALUES (%s, 'sync', 'TaiKhoan', %s, 'sua', %s, 'thanh_cong')
            """,
            [event_id, account_id, site_code],
        )
    elif tuple(str(value) for value in row) != expected:
        raise AuthInfrastructureUnavailable

    audit_id = f"{site_code}-NK-{uuid.uuid5(uuid.NAMESPACE_URL, f'{action_id}:{site_code}:audit').hex[:10]}"
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_moi, ip, ket_qua)
        SELECT %s, 'system', %s, %s, 'doi_trang_thai_tai_khoan', 'TaiKhoan', %s, %s, %s, 'thanh_cong'
        WHERE NOT EXISTS
        (
            SELECT 1 FROM dbo.Logs
            WHERE loai_log = 'system' AND ma_log = %s
        )
        """,
        [
            audit_id, site_code, actor_id, account_id,
            '{"trang_thai":' + str(status_bit) + '}', remote_ip[:45], audit_id,
        ],
    )


def _update_site_account(
    site_code: str, *, account_id: str, old_status: int, old_version: int,
    new_status: int, actor_id: str, remote_ip: str, action_id: str,
) -> None:
    alias = get_site_database_alias(site_code)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dbo.TaiKhoan
                    SET trang_thai = %s, phien_ban = phien_ban + 1,
                        cap_nhat_luc = SYSUTCDATETIME()
                    WHERE ma_tai_khoan = %s AND trang_thai = %s AND phien_ban = %s
                    """,
                    [new_status, account_id, old_status, old_version],
                )
                if cursor.rowcount != 1:
                    raise AccountStatusConflict
                if new_status == 0:
                    cursor.execute(
                        """
                        UPDATE dbo.PhienDangNhap
                        SET thu_hoi_luc_utc = COALESCE(thu_hoi_luc_utc, SYSUTCDATETIME())
                        WHERE ma_tai_khoan = %s AND thu_hoi_luc_utc IS NULL
                        """,
                        [account_id],
                    )
                _write_sync_and_audit(
                    cursor,
                    site_code=site_code,
                    account_id=account_id,
                    actor_id=actor_id,
                    remote_ip=remote_ip,
                    action_id=action_id,
                    status_bit=new_status,
                )
    except AccountStatusConflict:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def _compensate_site_account(
    site_code: str, *, account_id: str, old_status: int,
    new_status: int, new_version: int,
) -> bool:
    alias = get_site_database_alias(site_code)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dbo.TaiKhoan
                    SET trang_thai = %s, phien_ban = phien_ban + 1,
                        cap_nhat_luc = SYSUTCDATETIME()
                    WHERE ma_tai_khoan = %s AND trang_thai = %s AND phien_ban = %s
                    """,
                    [old_status, account_id, new_status, new_version],
                )
                return cursor.rowcount == 1
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
        return False


def change_account_status(
    *, slug: str, expected_role: str, desired_status: str,
    actor_id: str, remote_ip: str, site_code: str | None = None,
) -> AccountStatusResult:
    slug = str(slug).strip()
    desired_status = str(desired_status).strip().lower()
    if not slug or desired_status not in {"active", "inactive"} or not actor_id or not remote_ip:
        raise AccountStatusTargetNotFound
    if expected_role != "admin_small":
        raise AccountStatusTargetNotFound

    applied: list[str] = []
    account = None
    target_site = ""
    try:
        sites = active_site_codes()
        account = _read_account_by_slug(slug, sites)
        if account is None or str(account[2]) != slug:
            raise AccountStatusTargetNotFound
        if str(account[5]).lower() != "nhan_vien" or not account[6]:
            raise AccountStatusTargetNotFound
        target_site = str(account[6]).upper()
        if target_site not in sites or (site_code and target_site != str(site_code).upper()):
            raise AccountStatusTargetNotFound
        profile = _read_admin_small_profile(str(account[0]), target_site)
        if profile is None:
            raise AccountStatusTargetNotFound

        old_status = account_status_bit(account[7])
        old_version = int(account[8])
        if old_status not in (0, 1):
            raise AccountStatusConflict
        if profile[1] != old_status:
            raise AccountStatusConflict
        new_status = 1 if desired_status == "active" else 0
        if old_status == new_status:
            return AccountStatusResult(str(account[0]), slug, expected_role, target_site, desired_status)

        action_id = f"{account[0]}:{old_version}:{new_status}"
        for code in sites:
            _update_site_account(
                code,
                account_id=str(account[0]),
                old_status=old_status,
                old_version=old_version,
                new_status=new_status,
                actor_id=actor_id,
                remote_ip=remote_ip,
                action_id=action_id,
            )
            applied.append(code)

        alias = get_site_database_alias(target_site)
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    "UPDATE dbo.Admin SET trang_thai = %s "
                    "WHERE ma_tai_khoan = %s AND ma_co_so = %s "
                    "AND loai_admin = 'admin_small' AND trang_thai = %s",
                    [new_status, account[0], target_site, old_status],
                )
                if cursor.rowcount != 1:
                    raise AccountStatusConflict
        return AccountStatusResult(str(account[0]), slug, expected_role, target_site, desired_status)
    except (AccountStatusTargetNotFound, AccountStatusConflict, AuthInfrastructureUnavailable):
        if account is not None and applied:
            old_status = account_status_bit(account[7])
            new_status = 1 if desired_status == "active" else 0
            version = int(account[8])
            for code in reversed(applied):
                if not _compensate_site_account(
                    code, account_id=str(account[0]), old_status=old_status,
                    new_status=new_status, new_version=version + 1,
                ):
                    raise AuthInfrastructureUnavailable
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        if account is not None and applied:
            old_status = account_status_bit(account[7])
            new_status = 1 if desired_status == "active" else 0
            version = int(account[8])
            for code in reversed(applied):
                if not _compensate_site_account(
                    code, account_id=str(account[0]), old_status=old_status,
                    new_status=new_status, new_version=version + 1,
                ):
                    raise AuthInfrastructureUnavailable from exc
        raise AuthInfrastructureUnavailable from exc
