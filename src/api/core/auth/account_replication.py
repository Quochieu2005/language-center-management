"""Durable delivery of authority account snapshots to the other site databases."""

from functools import wraps
from dataclasses import replace

from django.conf import settings
from django.db import DatabaseError, connections, transaction

from core.auth.service_common import (
    AuthInfrastructureUnavailable, _acquire_named_lock, active_site_codes, auth_session_alias,
)
from core.sites.connections import UnknownSiteError, get_site_database_alias


class AccountReplicaConflict(Exception):
    """Preserve an unexplained newer or conflicting replica during authority cutover."""


def provisioning_sites(site_code):
    """Only the account authority and the owning profile must be reachable to issue a login."""
    active = active_site_codes()
    site = str(site_code).upper()
    if site not in active:
        raise ValueError("Cơ sở không hoạt động.")
    return tuple(dict.fromkeys((site, settings.AUTH_SESSION_SITE_CODE)))


def serialize_account_creation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            with transaction.atomic(using=auth_session_alias()):
                with connections[auth_session_alias()].cursor() as cursor:
                    # All account-creation paths reserve the shared email/username namespace here.
                    _acquire_named_lock(cursor, "qlttnn-account-creation")
                result = function(*args, **kwargs)
                pending = replication_status(result.account_id)["replication_pending_sites"]
                return replace(result, replication_pending_sites=tuple(pending))
        except DatabaseError as exc:
            raise AuthInfrastructureUnavailable from exc
    return wrapped


def replication_status(account_id):
    with connections[auth_session_alias()].cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT site_dich FROM dbo.DongBoTaiKhoan WHERE ma_tai_khoan = %s "
            "AND site_dich <> %s ORDER BY site_dich",
            [account_id, settings.AUTH_SESSION_SITE_CODE],
        )
        pending = [str(row[0]) for row in cursor.fetchall()]
    return {"replication_complete": not pending, "replication_pending_sites": pending}


# Explicit columns: never propagate SQL-generated fields or arbitrarily named input columns.
ACCOUNT_COLUMNS = (
    "ma_tai_khoan", "slug", "ten_dang_nhap", "email", "mat_khau", "vai_tro",
    "ma_co_so", "trang_thai", "bat_buoc_doi_mat_khau", "phien_ban",
    "ngay_doi_mat_khau_cuoi", "avatar_public_id", "avatar_secure_url",
    "google_subject", "facebook_subject",
)


def deliver_account(account_id, target):
    """Lock the current authority row, deliver it, then ACK only that queue generation."""
    authority = auth_session_alias()
    alias = get_site_database_alias(target)
    if target != settings.AUTH_SESSION_SITE_CODE:
        # A known-offline subscriber must not hold locks in the login/account authority.
        with connections[alias].cursor() as probe:
            probe.execute("SELECT 1", [])
    with transaction.atomic(using=authority):
        with connections[authority].cursor() as cursor:
            _acquire_named_lock(cursor, f"qlttnn-account-sync:{account_id}")
            cursor.execute(
                f"SELECT {','.join(ACCOUNT_COLUMNS)} FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_tai_khoan = %s", [account_id],
            )
            account = cursor.fetchone()
            cursor.execute(
                "SELECT TOP (1) 1 FROM dbo.GiaoDichDatLaiMatKhau "
                "WHERE ma_tai_khoan = %s AND trang_thai = 'dang_xu_ly'", [account_id],
            )
            if cursor.fetchone() is not None:
                raise AuthInfrastructureUnavailable
            cursor.execute(
                "SELECT MAX(ma_su_kien) FROM dbo.DongBoTaiKhoan "
                "WHERE ma_tai_khoan = %s AND site_dich = %s", [account_id, target],
            )
            generation = cursor.fetchone()[0]
            if generation is None:
                return
            if target != settings.AUTH_SESSION_SITE_CODE:
                with transaction.atomic(using=alias):
                    with connections[alias].cursor() as replica:
                        replica.execute(
                            f"SELECT {','.join(ACCOUNT_COLUMNS)} FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK) "
                            "WHERE ma_tai_khoan = %s", [account_id],
                        )
                        existing = replica.fetchone()
                        exists = existing is not None
                        if account is not None and existing is not None:
                            security = (0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 14)
                            if (int(existing[9]) > int(account[9]) or
                                    (int(existing[9]) == int(account[9]) and any(
                                        existing[index] != account[index] for index in security))):
                                raise AccountReplicaConflict
                        if account is None:
                            # FK-protected history is retained; a failed delete stays queued for review.
                            replica.execute("DELETE FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s", [account_id])
                        elif exists and tuple(existing) != tuple(account):
                            replica.execute(
                                "UPDATE dbo.TaiKhoan SET " + ",".join(f"{c} = %s" for c in ACCOUNT_COLUMNS[1:])
                                + " WHERE ma_tai_khoan = %s", [*account[1:], account_id],
                            )
                        elif not exists:
                            replica.execute(
                                f"INSERT dbo.TaiKhoan ({','.join(ACCOUNT_COLUMNS)}) VALUES "
                                f"({','.join(['%s'] * len(ACCOUNT_COLUMNS))})", list(account),
                            )
            cursor.execute(
                "DELETE FROM dbo.DongBoTaiKhoan WHERE ma_tai_khoan = %s AND site_dich = %s "
                "AND ma_su_kien <= %s", [account_id, target, generation],
            )


def sync_accounts(limit=50):
    authority = auth_session_alias()
    with connections[authority].cursor() as cursor:
        cursor.execute(
            "SELECT TOP (%s) ma_tai_khoan, site_dich FROM dbo.DongBoTaiKhoan "
            "WHERE thu_lai_luc_utc <= SYSUTCDATETIME() GROUP BY ma_tai_khoan, site_dich "
            "ORDER BY MIN(ma_su_kien)", [limit],
        )
        pending = cursor.fetchall()
    delivered = 0
    for account_id, target in pending:
        try:
            deliver_account(str(account_id), str(target))
            delivered += 1
        except (DatabaseError, AuthInfrastructureUnavailable, AccountReplicaConflict, UnknownSiteError, KeyError, ValueError) as exc:
            with connections[authority].cursor() as cursor:
                cursor.execute(
                    "UPDATE dbo.DongBoTaiKhoan SET so_lan_thu = so_lan_thu + 1, loi = %s, "
                    "thu_lai_luc_utc = DATEADD(SECOND, 10, SYSUTCDATETIME()) "
                    "WHERE ma_tai_khoan = %s AND site_dich = %s",
                    [type(exc).__name__, account_id, target],
                )
    return {"delivered": delivered, "deferred": len(pending) - delivered}


def queue_account_reconciliation():
    """Also repair a subscriber restored from an old backup after its ACK was committed."""
    with connections[auth_session_alias()].cursor() as cursor:
        cursor.execute(
            "INSERT dbo.DongBoTaiKhoan(ma_tai_khoan, site_dich) "
            "SELECT a.ma_tai_khoan, c.ma_co_so FROM dbo.TaiKhoan a CROSS JOIN dbo.CoSo c "
            "WHERE c.trang_thai = 'hoat_dong' AND c.ma_co_so <> %s "
            "AND NOT EXISTS (SELECT 1 FROM dbo.DongBoTaiKhoan q "
            "WHERE q.ma_tai_khoan = a.ma_tai_khoan AND q.site_dich = c.ma_co_so)",
            [settings.AUTH_SESSION_SITE_CODE],
        )
