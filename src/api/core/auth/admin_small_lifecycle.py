"""Admin Small account creation and delete-button status changes."""

from __future__ import annotations

import hashlib
import json
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, IntegrityError, connections, transaction

from core.auth.account_state import account_status_bit
from core.auth.service_common import (
    AdminSmallAccountConflict,
    AdminSmallDeletionResult,
    AdminSmallDeleteConflict,
    AdminSmallSiteUnavailable,
    AdminSmallTargetNotFound,
    AdminSmallProvisioningResult,
    AuthInfrastructureUnavailable,
    _next_sequence_number,
    _replicated_account,
    active_site_codes,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.slug_utils import make_slug
from core.notifications.publisher import publish_notification
from core.auth.admin_small_email import EMAIL_READY, record_admin_small_email_event


def _require_admin_small_temporary_password() -> str:
    password = str(getattr(settings, "ADMIN_SMALL_TEMP_PASSWORD", "")).strip()
    if not password or len(password) > 128:
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


def _account_slug_exists(slug: str, site_codes: tuple[str, ...]) -> bool:
    try:
        found = []
        for site in site_codes:
            with get_site_connection(site).cursor() as cursor:
                cursor.execute("SELECT TOP (2) ma_tai_khoan FROM dbo.TaiKhoan WHERE slug = %s", [slug])
                rows = cursor.fetchall()
            if len(rows) > 1:
                raise AuthInfrastructureUnavailable
            found.append(str(rows[0][0]) if rows else None)
        if any(account_id is not None for account_id in found):
            if any(account_id is None for account_id in found) or len(set(found)) != 1:
                raise AuthInfrastructureUnavailable
            return True
        return False
    except AuthInfrastructureUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


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
    phone: str | None, remote_ip: str, credential_email_ready: bool,
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
                if credential_email_ready:
                    cursor.execute(
                        "SELECT 1 FROM dbo.Logs WHERE loai_log = 'system' AND ma_co_so = %s "
                        "AND ma_tai_khoan = %s AND bang_tac_dong = 'TaiKhoan' "
                        "AND ma_ban_ghi = %s AND hanh_dong = %s",
                        [site_code, account_id, account_id, EMAIL_READY],
                    )
                    if cursor.fetchone() is None:
                        record_admin_small_email_event(
                            cursor, site_code=site_code, account_id=account_id,
                            action=EMAIL_READY, result="thanh_cong", remote_ip=remote_ip,
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


def _recover_admin_small_provisioning(
    *, site_code: str, email: str, username: str, full_name: str, slug: str,
    temporary_password: str,
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
        account_id, stored_slug, stored_username, stored_email = map(str, row[:4])
        password_hash = str(row[4])
        role = str(row[5]).lower()
        account_site = str(row[6]).upper() if row[6] else None
        if (
            role != "nhan_vien" or account_site != site_code
            or not account_status_bit(row[7]) or not bool(row[8])
            or stored_slug != slug
            or stored_email.casefold() != email or stored_username.lower() != username
            or not check_password(temporary_password, password_hash)
            or row[10] is None or str(row[11]).upper() != site_code
            or str(row[12]).lower() != "admin_small" or str(row[13]) != full_name
            or row[14] is not None or not bool(row[15])
        ):
            raise AdminSmallAccountConflict
        account = (
            account_id, stored_slug, stored_username, stored_email, password_hash,
            account_site, bool(row[8]), int(row[9]),
        )
        return account, str(row[10])
    except AdminSmallAccountConflict:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def create_admin_small(
    *, email: str, full_name: str, site_code: str, username: str | None,
    admin_big_id: str, remote_ip: str, slug: str | None = None,
) -> AdminSmallProvisioningResult:
    temporary_password = _require_admin_small_temporary_password()
    sites = active_site_codes()
    target_site = str(site_code).strip().upper()
    if target_site not in sites:
        raise AdminSmallSiteUnavailable
    normalized_email = email.strip().casefold()
    normalized_username = (username or make_slug(normalized_email.partition("@")[0], max_length=100)).strip().lower()
    normalized_name = full_name.strip()
    if not normalized_email or not normalized_name or not normalized_username or not remote_ip:
        raise ValueError("Thiếu thông tin Admin Small.")
    account_slug = make_slug(f"admin-small-{target_site}-{normalized_name}", slug, max_length=120)
    recovered = _recover_admin_small_provisioning(
        site_code=target_site, email=normalized_email, username=normalized_username,
        full_name=normalized_name, slug=account_slug, temporary_password=temporary_password,
    )
    if recovered is not None:
        account, admin_id = recovered
        account_id, account_slug, normalized_username, normalized_email = account[:4]
    else:
        if (
            _replicated_account(normalized_email, sites) is not None
            or _replicated_account(normalized_username, sites) is not None
            or _account_slug_exists(account_slug, sites)
        ):
            raise AdminSmallAccountConflict
        account_id = _next_admin_small_account_id(target_site, sites)
        admin_id = _next_admin_id(target_site)
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
            _create_admin_profile(
                target_site, admin_id, account_id, normalized_name, None, remote_ip,
                credential_email_ready=recovered is None,
            )
        for site in sites:
            if site != target_site:
                _replicate_account(site, account, "them")
    except AdminSmallAccountConflict:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
    return AdminSmallProvisioningResult(
        account_id=account_id,
        admin_id=admin_id,
        username=normalized_username,
        email=normalized_email,
        site_code=target_site,
        must_change_password=True,
        slug=account_slug,
        credential_email_status="ready" if recovered is None else "unknown",
    )


def _admin_small_delete_event_id(site_code: str, account_id: str) -> str:
    digest = hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:32]
    return f"admin-small-delete:{site_code}:{digest}"


def _read_admin_small_delete_marker(cursor, site_code: str, account_id: str):
    cursor.execute(
        """
        SELECT ma_co_so, hanh_dong, bang_tac_dong, ma_ban_ghi, du_lieu_cu,
               site_dich, ket_qua
        FROM dbo.Logs WHERE ma_log = %s
        """,
        [_admin_small_delete_event_id(site_code, account_id)],
    )
    row = cursor.fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(str(row[4]))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AdminSmallDeleteConflict from exc
    if (
        str(row[0]).upper() != site_code or str(row[1]) != "xoa_admin_small"
        or str(row[2]) != "TaiKhoan" or str(row[3]) != account_id
        or str(row[5]).upper() != str(payload.get("target_site", "")).upper()
        or str(row[6]) != "thanh_cong" or payload.get("account_id") != account_id
    ):
        raise AdminSmallDeleteConflict
    return payload


def _normalized_admin_small_account(row):
    return (
        str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]),
        str(row[5]).lower(), str(row[6]).upper() if row[6] else None,
        account_status_bit(row[7]), int(row[8]), bool(row[9]),
        str(row[10]) if row[10] else None, str(row[11]) if row[11] else None,
    )


def delete_admin_small(account_id: str, admin_big_id: str, remote_ip: str) -> AdminSmallDeletionResult:
    account_id = account_id.strip()
    active_sites = active_site_codes()
    sites = tuple(sorted(getattr(settings, "SITE_DATABASE_ALIASES", {})))
    if not account_id or not sites or not set(active_sites).issubset(sites):
        raise AdminSmallTargetNotFound

    account_copies = []
    deletion_markers = {}
    try:
        for site in sites:
            with get_site_connection(site).cursor() as cursor:
                deletion_markers[site] = _read_admin_small_delete_marker(cursor, site, account_id)
                cursor.execute(
                    """
                    SELECT TOP (2) ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                           vai_tro, ma_co_so, trang_thai, phien_ban,
                           bat_buoc_doi_mat_khau, avatar_public_id, avatar_secure_url
                    FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s
                    """,
                    [account_id],
                )
                rows = cursor.fetchall()
                if len(rows) > 1:
                    raise AdminSmallDeleteConflict
                copied_account = _normalized_admin_small_account(rows[0]) if rows else None
                if deletion_markers[site] is not None and copied_account is not None:
                    raise AdminSmallDeleteConflict
                if site in active_sites and deletion_markers[site] is None and copied_account is None:
                    raise AdminSmallDeleteConflict
                if copied_account is not None:
                    account_copies.append(copied_account)
        if not account_copies and not any(deletion_markers.values()):
            raise AdminSmallTargetNotFound
        account = account_copies[0] if account_copies else None
        for copy in account_copies[1:]:
            if copy != account:
                raise AdminSmallDeleteConflict
        target_sites = {
            str(copy[6]).upper() for copy in account_copies if copy[6]
        } | {
            str(marker["target_site"]).upper()
            for marker in deletion_markers.values() if marker
        }
        if len(target_sites) != 1:
            raise AdminSmallDeleteConflict
        target_site = target_sites.pop()
        if target_site not in sites or (account and (
            account[5] != "nhan_vien" or account[6] != target_site
        )):
            raise AdminSmallTargetNotFound
        if account is None and any(marker is None for marker in deletion_markers.values()):
            raise AdminSmallDeleteConflict
        for site in sites:
            with get_site_connection(site).cursor() as cursor:
                for table in ("HocVien", "GiaoVien", "NhanVien"):
                    cursor.execute(
                        f"SELECT COUNT_BIG(*) FROM dbo.{table} WHERE ma_tai_khoan = %s",
                        [account_id],
                    )
                    if int(cursor.fetchone()[0]):
                        raise AdminSmallDeleteConflict
                cursor.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.GiaoDichChuyenCoSo "
                    "WHERE (ma_tai_khoan_de_nghi = %s OR ma_tai_khoan_quyet_dinh = %s) "
                    "AND trang_thai IN ('cho_duyet', 'dang_xu_ly')",
                    [account_id, account_id],
                )
                if int(cursor.fetchone()[0]):
                    raise AdminSmallDeleteConflict
                cursor.execute(
                    "IF OBJECT_ID(N'dbo.YeuCauThanhToan', N'U') IS NOT NULL "
                    "SELECT COUNT_BIG(*) FROM dbo.YeuCauThanhToan WHERE ma_tai_khoan = %s "
                    "ELSE SELECT CONVERT(bigint, 0)",
                    [account_id],
                )
                if int(cursor.fetchone()[0]):
                    raise AdminSmallDeleteConflict
        avatar_ids = {
            copy[10] for copy in account_copies if copy[10]
        } | {
            str(marker["avatar_public_id"])
            for marker in deletion_markers.values()
            if marker and marker.get("avatar_public_id")
        }
        if len(avatar_ids) > 1:
            raise AdminSmallDeleteConflict
        avatar_public_id = next(iter(avatar_ids), None)

        if deletion_markers[target_site] is None:
            with get_site_connection(target_site).cursor() as cursor:
                cursor.execute(
                    "SELECT ma_admin, ma_co_so, loai_admin FROM dbo.Admin "
                    "WHERE ma_tai_khoan = %s",
                    [account_id],
                )
                profiles = cursor.fetchall()
            if (
                len(profiles) != 1 or str(profiles[0][1]).upper() != target_site
                or str(profiles[0][2]).lower() != "admin_small"
            ):
                raise AdminSmallTargetNotFound

        from core.media.avatars import AvatarUnavailable, destroy_cloudinary_avatar_asset

        try:
            destroy_cloudinary_avatar_asset(avatar_public_id)
        except AvatarUnavailable as exc:
            raise AuthInfrastructureUnavailable from exc

        ordered_sites = tuple(site for site in sites if site != target_site) + (target_site,)
        for site in ordered_sites:
            alias = get_site_database_alias(site)
            with transaction.atomic(using=alias):
                with connections[alias].cursor() as cursor:
                    marker = _read_admin_small_delete_marker(cursor, site, account_id)
                    cursor.execute(
                        """
                        SELECT TOP (2) ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                               vai_tro, ma_co_so, trang_thai, phien_ban,
                               bat_buoc_doi_mat_khau, avatar_public_id, avatar_secure_url
                        FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK)
                        WHERE ma_tai_khoan = %s
                        """,
                        [account_id],
                    )
                    rows = cursor.fetchall()
                    if len(rows) > 1:
                        raise AdminSmallDeleteConflict
                    local_account = _normalized_admin_small_account(rows[0]) if rows else None
                    if marker is not None:
                        if local_account is not None:
                            raise AdminSmallDeleteConflict
                        continue
                    if local_account is not None and local_account != account:
                        raise AdminSmallDeleteConflict
                    if site in active_sites and local_account is None:
                        raise AdminSmallDeleteConflict

                    cursor.execute(
                        "SELECT COUNT_BIG(*) FROM dbo.HocVien WHERE ma_tai_khoan = %s",
                        [account_id],
                    )
                    student_count = int(cursor.fetchone()[0])
                    cursor.execute(
                        "SELECT COUNT_BIG(*) FROM dbo.GiaoVien WHERE ma_tai_khoan = %s",
                        [account_id],
                    )
                    teacher_count = int(cursor.fetchone()[0])
                    cursor.execute(
                        "SELECT COUNT_BIG(*) FROM dbo.NhanVien WHERE ma_tai_khoan = %s",
                        [account_id],
                    )
                    employee_count = int(cursor.fetchone()[0])
                    if student_count or teacher_count or employee_count:
                        raise AdminSmallDeleteConflict

                    cursor.execute(
                        "SELECT ma_admin, ma_co_so, loai_admin FROM dbo.Admin "
                        "WHERE ma_tai_khoan = %s",
                        [account_id],
                    )
                    profiles = cursor.fetchall()
                    if site == target_site:
                        if (
                            len(profiles) != 1
                            or str(profiles[0][1]).upper() != target_site
                            or str(profiles[0][2]).lower() != "admin_small"
                        ):
                            raise AdminSmallDeleteConflict
                        cursor.execute(
                            "DELETE FROM dbo.Admin WHERE ma_tai_khoan = %s "
                            "AND ma_co_so = %s AND loai_admin = 'admin_small'",
                            [account_id, target_site],
                        )
                        if cursor.rowcount != 1:
                            raise AdminSmallDeleteConflict
                    elif profiles:
                        raise AdminSmallDeleteConflict

                    for table in ("PhienDangNhap", "TokenDatLaiMatKhau", "GiaoDichDatLaiMatKhau"):
                        cursor.execute(f"DELETE FROM dbo.{table} WHERE ma_tai_khoan = %s", [account_id])
                    if local_account is not None:
                        cursor.execute(
                            "DELETE FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s "
                            "AND vai_tro = 'nhan_vien' AND ma_co_so = %s",
                            [account_id, target_site],
                        )
                        if cursor.rowcount != 1:
                            raise AdminSmallDeleteConflict

                    payload = json.dumps(
                        {
                            "account_id": account_id,
                            "target_site": target_site,
                            "avatar_public_id": avatar_public_id,
                        },
                        separators=(",", ":"),
                    )
                    cursor.execute(
                        """
                        INSERT INTO dbo.Logs
                            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong,
                             bang_tac_dong, ma_ban_ghi, du_lieu_cu, ip, ket_qua, site_dich)
                        VALUES (%s, 'system', %s, %s, 'xoa_admin_small', 'TaiKhoan',
                                %s, %s, %s, 'thanh_cong', %s)
                        """,
                        [
                            _admin_small_delete_event_id(site, account_id), site,
                            admin_big_id, account_id, payload, remote_ip[:45], target_site,
                        ],
                    )
    except (AdminSmallDeleteConflict, AdminSmallTargetNotFound, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

    return AdminSmallDeletionResult(account_id=account_id, site_code=target_site)
