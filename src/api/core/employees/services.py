"""SQL Server operations for site-local employee profiles and replicated accounts."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from functools import wraps

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.auth.account_state import account_status_bit
from core.academics.common import append_audit, acquire_record_lock, require_active_site
from core.auth.admin_small_lifecycle import _replicate_account
from core.auth.admin_small_email import (
    EMPLOYEE_EMAIL_READY,
    EMPLOYEE_EMAIL_UNKNOWN,
    _EMPLOYEE_EMAIL_ACTIONS,
    credential_email_status,
    record_credential_email_event,
)
from core.auth.service_common import (
    AdminSmallAccountConflict,
    AuthInfrastructureUnavailable,
    _next_sequence_number,
    _replicated_account,
    active_site_codes,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.slug_utils import make_slug

_JOB_TITLES = {"le_tan", "tu_van", "ke_toan"}


class EmployeeConflict(Exception):
    """A duplicate login identity or an existing employee profile was found."""


class EmployeeNotFound(Exception):
    """The requested site-local employee does not exist."""


class EmployeeForbidden(Exception):
    """The user cannot act within the selected site."""


class EmployeeInfrastructureUnavailable(Exception):
    """A site database or required email service is unavailable."""


def _translate_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (EmployeeConflict, EmployeeInfrastructureUnavailable, EmployeeNotFound, ValueError):
            raise
        except AdminSmallAccountConflict as exc:
            raise EmployeeConflict from exc
        except (AuthInfrastructureUnavailable, DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
            raise EmployeeInfrastructureUnavailable from exc
    return wrapped


@dataclass(frozen=True)
class EmployeeProvisioningResult:
    employee_id: str
    account_id: str
    slug: str
    username: str
    email: str
    site_code: str
    job_title: str
    full_name: str
    phone: str | None
    credential_email_status: str
    must_change_password: bool = True


@dataclass(frozen=True)
class EmployeeDeletionResult:
    employee_id: str
    account_id: str
    slug: str
    site_code: str
    profile_retained: bool


def _require_provisioning_configuration() -> str:
    password = str(getattr(settings, "ADMIN_SMALL_TEMP_PASSWORD", "")).strip()
    if not password or len(password) > 128:
        raise EmployeeInfrastructureUnavailable
    return password


def _next_account_id(site_code: str, sites: tuple[str, ...]) -> str:
    for _ in range(1000):
        candidate = f"{site_code}-TK-{_next_sequence_number(site_code, 'Seq_TK'):06d}"
        if not any(_account_id_exists(code, candidate) for code in sites):
            return candidate
    raise EmployeeInfrastructureUnavailable


def _account_id_exists(site_code: str, account_id: str) -> bool:
    with get_site_connection(site_code).cursor() as cursor:
        cursor.execute(
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s) THEN 1 ELSE 0 END",
            [account_id],
        )
        return bool(cursor.fetchone()[0])


def _unique_username(email: str, supplied: str | None, sites: tuple[str, ...]) -> str:
    if supplied:
        if _replicated_account(supplied.strip().lower(), sites) is not None:
            raise EmployeeConflict
        return supplied.strip().lower()
    base = make_slug(email.partition("@")[0], max_length=80)
    for suffix in range(1000):
        candidate = base if suffix == 0 else f"{base[:88]}-{suffix}"
        if _replicated_account(candidate, sites) is None:
            return candidate
    raise EmployeeInfrastructureUnavailable


def _next_employee_id(site_code: str) -> str:
    for _ in range(1000):
        candidate = f"{site_code}-NV-{_next_sequence_number(site_code, 'Seq_NV'):06d}"
        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.NhanVien WHERE ma_nhan_vien = %s) THEN 1 ELSE 0 END",
                [candidate],
            )
            if not cursor.fetchone()[0]:
                return candidate
    raise EmployeeInfrastructureUnavailable


def _unique_account_slug(site_code: str, username: str, sites: tuple[str, ...]) -> str:
    base = make_slug(f"nhan-vien-{site_code.lower()}-{username}", max_length=120)
    for suffix in range(1000):
        candidate = base if suffix == 0 else make_slug(f"{base[:110]}-{suffix}", max_length=120)
        exists = False
        for site in sites:
            with get_site_connection(site).cursor() as cursor:
                cursor.execute("SELECT TOP (1) 1 FROM dbo.TaiKhoan WHERE slug = %s", [candidate])
                if cursor.fetchone() is not None:
                    exists = True
                    break
        if not exists:
            return candidate
    raise EmployeeInfrastructureUnavailable


def _create_profile(
    *, site_code: str, employee_id: str, account_id: str, full_name: str,
    phone: str | None, email: str, job_title: str, actor_id: str, remote_ip: str,
    initial_credential_status: str,
) -> str:
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            acquire_record_lock(cursor, f"employee-create:{site_code}:{account_id}")
            cursor.execute(
                """
                SELECT TOP (2) ma_nhan_vien, ma_co_so, ma_tai_khoan,
                               ho_ten, sdt, email, chuc_vu, trang_thai
                FROM dbo.NhanVien WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_tai_khoan = %s OR ma_nhan_vien = %s
                """,
                [account_id, employee_id],
            )
            rows = cursor.fetchall()
            if len(rows) > 1:
                raise EmployeeConflict
            if rows:
                row = rows[0]
                if (
                    str(row[0]) != employee_id or str(row[1]).upper() != site_code
                    or str(row[2]) != account_id or str(row[3]) != full_name
                    or row[4] != phone or row[5] != email
                    or str(row[6]).lower() != job_title or str(row[7]).lower() != "dang_lam"
                ):
                    raise EmployeeConflict
            else:
                cursor.execute(
                    """
                    INSERT INTO dbo.NhanVien
                        (ma_nhan_vien, ma_co_so, ma_tai_khoan, ho_ten, sdt, email, chuc_vu, trang_thai)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'dang_lam')
                    """,
                    [employee_id, site_code, account_id, full_name, phone, email, job_title],
                )
            append_audit(
                cursor, site_code=site_code, actor_id=actor_id,
                action="tao_nhan_vien", table_name="NhanVien", record_id=employee_id,
                remote_ip=remote_ip,
                after={"job_title": job_title, "site_code": site_code, "account_id": account_id},
            )
            placeholders = ", ".join(["%s"] * len(_EMPLOYEE_EMAIL_ACTIONS))
            cursor.execute(
                f"""
                SELECT TOP (1) hanh_dong
                FROM dbo.Logs
                WHERE loai_log = 'system' AND ma_co_so = %s AND ma_tai_khoan = %s
                  AND bang_tac_dong = 'TaiKhoan' AND ma_ban_ghi = %s
                  AND hanh_dong IN ({placeholders})
                ORDER BY thoi_diem_utc DESC, ma_log DESC
                """,
                [site_code, account_id, account_id, *_EMPLOYEE_EMAIL_ACTIONS],
            )
            latest_email_action = cursor.fetchone()
            latest_email_action = str(latest_email_action[0]) if latest_email_action else None
            if latest_email_action is None:
                latest_email_action = (
                    EMPLOYEE_EMAIL_READY if initial_credential_status == "ready" else EMPLOYEE_EMAIL_UNKNOWN
                )
                record_credential_email_event(
                    cursor, site_code=site_code, account_id=account_id,
                    action=latest_email_action, remote_ip=remote_ip,
                )
            return credential_email_status(latest_email_action)


def _recover_employee_provisioning(
    *, site_code: str, email: str, username: str | None, full_name: str,
    phone: str | None, job_title: str, temporary_password: str,
) -> tuple[tuple, str] | None:
    """Recover a locally committed employee so retries can finish replica fan-out."""
    try:
        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2)
                       t.ma_tai_khoan, t.slug, t.ten_dang_nhap, t.email, t.mat_khau,
                       t.vai_tro, t.ma_co_so, t.trang_thai,
                       t.bat_buoc_doi_mat_khau, t.phien_ban,
                       n.ma_nhan_vien, n.ma_co_so, n.ma_tai_khoan, n.ho_ten,
                       n.sdt, n.email, n.chuc_vu, n.trang_thai
                FROM dbo.TaiKhoan AS t
                LEFT JOIN dbo.NhanVien AS n ON n.ma_tai_khoan = t.ma_tai_khoan
                WHERE LOWER(t.email) = %s
                   OR (%s IS NOT NULL AND LOWER(t.ten_dang_nhap) = %s)
                """,
                [email, username, username],
            )
            rows = cursor.fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise EmployeeConflict
        row = rows[0]
        account_id, slug, stored_username, stored_email = map(str, row[:4])
        password_hash = str(row[4])
        account_site = str(row[6]).upper() if row[6] else None
        if (
            str(row[5]).lower() != "nhan_vien" or account_site != site_code
            or not account_status_bit(row[7]) or not bool(row[8])
            or stored_email.casefold() != email
            or (username is not None and stored_username.lower() != username)
            or not check_password(temporary_password, password_hash)
            or row[10] is None or str(row[11]).upper() != site_code
            or str(row[12]) != account_id or str(row[13]) != full_name
            or row[14] != phone or row[15] != email
            or str(row[16]).lower() != job_title or str(row[17]).lower() != "dang_lam"
        ):
            raise EmployeeConflict
        account = (
            account_id, slug, stored_username, stored_email, password_hash,
            site_code, bool(row[8]), int(row[9]),
        )
        return account, str(row[10])
    except EmployeeConflict:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise EmployeeInfrastructureUnavailable from exc


@_translate_errors
def create_employee(
    *, site_code: str, full_name: str, email: str, username: str | None,
    phone: str | None, job_title: str, actor_id: str, remote_ip: str,
) -> EmployeeProvisioningResult:
    temporary_password = _require_provisioning_configuration()
    sites = active_site_codes()
    site = str(site_code).strip().upper()
    if site not in sites:
        raise ValueError("Cơ sở không tồn tại hoặc đang không hoạt động.")
    if job_title not in _JOB_TITLES:
        raise ValueError("Chức vụ nhân viên không hợp lệ.")
    normalized_email = email.strip().casefold()
    normalized_name = full_name.strip()
    if not normalized_email or not normalized_name or not remote_ip:
        raise ValueError("Thiếu thông tin nhân viên.")
    normalized_phone = phone.strip() if phone else None
    normalized_username = (username or make_slug(normalized_email.partition("@")[0], max_length=100)).strip().lower()
    recovered = _recover_employee_provisioning(
        site_code=site, email=normalized_email,
        username=username.strip().lower() if username else None,
        full_name=normalized_name, phone=normalized_phone, job_title=job_title,
        temporary_password=temporary_password,
    )
    if recovered is not None:
        account, employee_id = recovered
        account_id, account_slug, normalized_username, normalized_email = account[:4]
    else:
        if _replicated_account(normalized_email, sites) is not None:
            raise EmployeeConflict
        normalized_username = _unique_username(normalized_email, username, sites)
        account_id = _next_account_id(site, sites)
        account_slug = _unique_account_slug(site, normalized_username, sites)
        employee_id = _next_employee_id(site)
        password_hash = make_password(temporary_password)
        account = (
            account_id, account_slug, normalized_username, normalized_email,
            password_hash, site, True, 1,
        )
    target_alias = get_site_database_alias(site)
    credential_status = "unknown"
    try:
        # Persist the site-local employee and its login account in one commit first.
        with transaction.atomic(using=target_alias):
            _replicate_account(site, account, "them")
            credential_status = _create_profile(
                site_code=site, employee_id=employee_id, account_id=account_id,
                full_name=normalized_name, phone=normalized_phone, email=normalized_email,
                job_title=job_title, actor_id=actor_id, remote_ip=remote_ip,
                initial_credential_status="ready" if recovered is None else "unknown",
            )
        for active_site in sites:
            if active_site != site:
                _replicate_account(active_site, account, "them")
    except (EmployeeConflict, AdminSmallAccountConflict):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise EmployeeInfrastructureUnavailable from exc
    return EmployeeProvisioningResult(
        employee_id=employee_id, account_id=account_id, slug=account_slug,
        username=normalized_username, email=normalized_email, site_code=site,
        job_title=job_title, full_name=normalized_name, phone=normalized_phone,
        credential_email_status=credential_status,
    )


@_translate_errors
def list_employees(
    *, site_code: str, job_title: str | None, status: str | None,
    search: str | None, limit: int, offset: int,
) -> dict:
    site = str(site_code).strip().upper()
    alias = require_active_site(site)
    clauses = [
        "n.ma_co_so = %s", "n.ma_tai_khoan IS NOT NULL",
        "n.chuc_vu IN ('le_tan', 'tu_van', 'ke_toan')",
    ]
    params: list[object] = [site]
    if job_title:
        clauses.append("n.chuc_vu = %s")
        params.append(job_title)
    if status:
        clauses.append("n.trang_thai = %s")
        params.append(status)
    if search:
        clauses.append("(n.ho_ten LIKE %s OR n.email LIKE %s OR t.ten_dang_nhap LIKE %s)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern])
    where = " AND ".join(clauses)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT COUNT_BIG(*) FROM dbo.NhanVien AS n LEFT JOIN dbo.TaiKhoan AS t "
            f"ON t.ma_tai_khoan = n.ma_tai_khoan AND t.ma_co_so = n.ma_co_so WHERE {where}",
            params,
        )
        count = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT n.ma_nhan_vien, n.ma_tai_khoan, t.slug, n.ho_ten, n.sdt, n.email,
                   n.chuc_vu, n.trang_thai, t.trang_thai, t.ten_dang_nhap, t.avatar_secure_url,
                   credential_email.hanh_dong
            FROM dbo.NhanVien AS n
            LEFT JOIN dbo.TaiKhoan AS t
              ON t.ma_tai_khoan = n.ma_tai_khoan AND t.ma_co_so = n.ma_co_so
            OUTER APPLY (
                SELECT TOP (1) l.hanh_dong
                FROM dbo.Logs AS l
                WHERE l.loai_log = 'system' AND l.ma_co_so = n.ma_co_so
                  AND l.ma_tai_khoan = n.ma_tai_khoan
                  AND l.bang_tac_dong = 'TaiKhoan' AND l.ma_ban_ghi = n.ma_tai_khoan
                  AND l.hanh_dong IN (%s, %s, %s, %s, %s, %s)
                ORDER BY l.thoi_diem_utc DESC, l.ma_log DESC
            ) AS credential_email
            WHERE """ + where + " ORDER BY n.ho_ten, n.ma_nhan_vien "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            [*_EMPLOYEE_EMAIL_ACTIONS, *params, offset, limit],
        )
        rows = cursor.fetchall()
    return {
        "site_code": site, "count": count, "limit": limit, "offset": offset,
        "results": [
            {
                "employee_id": str(row[0]), "account_id": str(row[1]) if row[1] else None,
                "slug": str(row[2]) if row[2] else None, "full_name": str(row[3]),
                "phone": row[4], "email": row[5], "site_code": site,
                "job_title": str(row[6]).lower(),
                "employee_status": str(row[7]).lower(),
                "account_status": "active" if row[8] in (True, 1, "1") else "inactive" if row[8] is not None else None,
                "username": str(row[9]) if row[9] else None,
                "avatar_secure_url": str(row[10]) if row[10] else None,
                "credential_email_status": credential_email_status(str(row[11]) if row[11] else None),
            }
            for row in rows
        ],
    }


def _employee_response(site_code: str, row) -> dict:
    account_status = account_status_bit(row[10])
    if account_status not in (0, 1):
        raise EmployeeConflict
    employee_status = str(row[6]).lower()
    if employee_status not in {"dang_lam", "nghi_viec"}:
        raise EmployeeConflict
    return {
        "employee_id": str(row[0]), "account_id": str(row[1]), "full_name": str(row[2]),
        "phone": row[3], "email": str(row[4]), "job_title": str(row[5]).lower(),
        "employee_status": employee_status, "slug": str(row[7]),
        "account_status": "active" if account_status else "inactive",
        "username": str(row[11]), "site_code": site_code,
        "avatar_secure_url": str(row[12]) if row[12] else None,
    }


def _employee_by_slug(cursor, site_code: str, slug: str, *, lock: bool = False):
    if lock:
        cursor.execute(
            """
            SELECT TOP (2) ma_tai_khoan, slug, vai_tro, ma_co_so, trang_thai, ten_dang_nhap,
                           avatar_secure_url
            FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK)
            WHERE ma_co_so = %s AND slug = %s AND vai_tro = 'nhan_vien'
            """,
            [site_code, slug],
        )
        accounts = cursor.fetchall()
        if len(accounts) > 1:
            raise EmployeeConflict
        if not accounts:
            raise EmployeeNotFound
        account = accounts[0]
        cursor.execute(
            """
            SELECT TOP (2) ma_nhan_vien, ma_tai_khoan, ho_ten, sdt, email,
                           chuc_vu, trang_thai
            FROM dbo.NhanVien WITH (UPDLOCK, HOLDLOCK)
            WHERE ma_tai_khoan = %s AND ma_co_so = %s
              AND chuc_vu IN ('le_tan', 'tu_van', 'ke_toan')
            """,
            [account[0], site_code],
        )
        profiles = cursor.fetchall()
        if len(profiles) > 1:
            raise EmployeeConflict
        if not profiles:
            raise EmployeeNotFound
        profile = profiles[0]
        return (
            profile[0], profile[1], profile[2], profile[3], profile[4], profile[5],
            profile[6], account[1], account[2], account[3], account[4], account[5], account[6],
        )

    cursor.execute(
        """
        SELECT TOP (2) n.ma_nhan_vien, n.ma_tai_khoan, n.ho_ten, n.sdt, n.email,
                       n.chuc_vu, n.trang_thai, t.slug, t.vai_tro, t.ma_co_so,
                       t.trang_thai, t.ten_dang_nhap, t.avatar_secure_url
        FROM dbo.TaiKhoan AS t
        INNER JOIN dbo.NhanVien AS n
          ON n.ma_tai_khoan = t.ma_tai_khoan AND n.ma_co_so = t.ma_co_so
        WHERE n.ma_co_so = %s AND t.slug = %s AND t.vai_tro = 'nhan_vien'
          AND n.chuc_vu IN ('le_tan', 'tu_van', 'ke_toan')
        """,
        [site_code, slug],
    )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise EmployeeConflict
    if not rows:
        raise EmployeeNotFound
    row = rows[0]
    if str(row[8]).lower() != "nhan_vien" or str(row[9]).upper() != site_code:
        raise EmployeeConflict
    return row


@_translate_errors
def get_employee(*, slug: str, site_code: str) -> dict:
    site = str(site_code).strip().upper()
    clean_slug = str(slug).strip()
    if not clean_slug:
        raise EmployeeNotFound
    alias = require_active_site(site)
    with connections[alias].cursor() as cursor:
        row = _employee_by_slug(cursor, site, clean_slug)
    return _employee_response(site, row)


@_translate_errors
def update_employee(
    *, slug: str, site_code: str, fields: dict, actor_id: str, remote_ip: str,
) -> dict:
    columns = {"full_name": "ho_ten", "phone": "sdt", "job_title": "chuc_vu"}
    if not fields or set(fields) - columns.keys() or not actor_id or not remote_ip:
        raise ValueError("Thông tin cập nhật không hợp lệ.")
    site = str(site_code).strip().upper()
    clean_slug = str(slug).strip()
    if not clean_slug:
        raise EmployeeNotFound
    alias = require_active_site(site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            row = _employee_by_slug(cursor, site, clean_slug, lock=True)
            if str(row[6]).lower() != "dang_lam" or account_status_bit(row[10]) != 1:
                raise EmployeeConflict
            current = {"full_name": str(row[2]), "phone": row[3], "job_title": str(row[5]).lower()}
            updated = {key: fields.get(key, value) for key, value in current.items()}
            changed = {key: value for key, value in updated.items() if value != current[key]}
            if changed:
                assignments = ", ".join(f"{columns[key]} = %s" for key in changed)
                cursor.execute(
                    f"UPDATE dbo.NhanVien SET {assignments} "
                    "WHERE ma_nhan_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s "
                    "AND trang_thai = 'dang_lam'",
                    [*changed.values(), row[0], site, row[1]],
                )
                if cursor.rowcount != 1:
                    raise EmployeeConflict
                append_audit(
                    cursor, site_code=site, actor_id=actor_id,
                    action="cap_nhat_nhan_vien", table_name="NhanVien",
                    record_id=str(row[0]), remote_ip=remote_ip,
                    before={key: current[key] for key in changed},
                    after={key: changed[key] for key in changed},
                )
    result = list(row)
    result[2], result[3], result[5] = updated["full_name"], updated["phone"], updated["job_title"]
    return _employee_response(site, tuple(result))


def _employee_delete_marker_id(site_code: str, slug: str) -> str:
    digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()[:32]
    return f"employee-delete:{site_code}:{digest}"


def _read_employee_delete_marker(cursor, site_code: str, slug: str):
    cursor.execute(
        """
        SELECT ma_co_so, hanh_dong, bang_tac_dong, ma_ban_ghi, du_lieu_cu,
               site_dich, ket_qua
        FROM dbo.Logs WHERE ma_log = %s
        """,
        [_employee_delete_marker_id(site_code, slug)],
    )
    row = cursor.fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(str(row[4]))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise EmployeeConflict from exc
    if (
        str(row[0]).upper() != site_code or str(row[1]) != "xoa_nhan_vien"
        or str(row[2]) != "TaiKhoan" or str(row[3]) != payload.get("account_id")
        or str(row[5]).upper() != str(payload.get("target_site", "")).upper()
        or str(row[6]) != "thanh_cong" or payload.get("slug") != slug
        or not payload.get("employee_id")
        or not isinstance(payload.get("profile_retained"), bool)
    ):
        raise EmployeeConflict
    return payload


def _employee_delete_identity(account: tuple) -> tuple:
    return tuple(account[index] for index in (0, 1, 2, 3, 4, 5, 6))


def _employee_account_by_slug(cursor, slug: str, *, lock: bool = False):
    lock_hint = " WITH (UPDLOCK, HOLDLOCK)" if lock else ""
    cursor.execute(
        f"""
        SELECT TOP (2) ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                       vai_tro, ma_co_so, trang_thai, phien_ban,
                       bat_buoc_doi_mat_khau, avatar_public_id
        FROM dbo.TaiKhoan{lock_hint} WHERE slug = %s
        """,
        [slug],
    )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise EmployeeConflict
    return tuple(rows[0]) if rows else None


def _check_employee_delete_references(cursor, account_id: str) -> None:
    for table in ("HocVien", "GiaoVien", "Admin"):
        cursor.execute(f"SELECT COUNT_BIG(*) FROM dbo.{table} WHERE ma_tai_khoan = %s", [account_id])
        if int(cursor.fetchone()[0]):
            raise EmployeeConflict
    cursor.execute(
        "IF OBJECT_ID(N'dbo.YeuCauThanhToan', N'U') IS NOT NULL "
        "SELECT COUNT_BIG(*) FROM dbo.YeuCauThanhToan WHERE ma_tai_khoan = %s "
        "ELSE SELECT CONVERT(bigint, 0)",
        [account_id],
    )
    if int(cursor.fetchone()[0]):
        raise EmployeeConflict
    cursor.execute(
        "SELECT COUNT_BIG(*) FROM dbo.GiaoDichChuyenCoSo "
        "WHERE (ma_tai_khoan_de_nghi = %s OR ma_tai_khoan_quyet_dinh = %s) "
        "AND trang_thai IN ('cho_duyet', 'dang_xu_ly')",
        [account_id, account_id],
    )
    if int(cursor.fetchone()[0]):
        raise EmployeeConflict


@_translate_errors
def delete_employee(
    *, slug: str, site_code: str, actor_id: str, remote_ip: str,
) -> EmployeeDeletionResult:
    site = str(site_code).strip().upper()
    clean_slug = str(slug).strip()
    if not clean_slug or not actor_id or not remote_ip:
        raise EmployeeNotFound
    sites = tuple(sorted(getattr(settings, "SITE_DATABASE_ALIASES", {})))
    active_sites = active_site_codes()
    if not sites or site not in active_sites or not set(active_sites).issubset(sites):
        raise EmployeeInfrastructureUnavailable

    accounts, markers, site_markers, avatar_ids = [], [], {}, set()
    for code in sites:
        with get_site_connection(code).cursor() as cursor:
            marker = _read_employee_delete_marker(cursor, code, clean_slug)
            account = _employee_account_by_slug(cursor, clean_slug)
        site_markers[code] = marker
        if marker is not None:
            if account is not None:
                raise EmployeeConflict
            markers.append(marker)
            if marker.get("avatar_public_id"):
                avatar_ids.add(str(marker["avatar_public_id"]))
        elif account is not None:
            accounts.append(account)
            if account[10]:
                avatar_ids.add(str(account[10]))
        elif code in active_sites:
            raise EmployeeInfrastructureUnavailable

    if not accounts and not markers:
        raise EmployeeNotFound
    if any(_employee_delete_identity(row) != _employee_delete_identity(accounts[0]) for row in accounts[1:]):
        raise EmployeeInfrastructureUnavailable
    account_id = str(accounts[0][0]) if accounts else str(markers[0]["account_id"])
    target_site = str(accounts[0][6]).upper() if accounts else str(markers[0]["target_site"]).upper()
    employee_ids = {str(marker["employee_id"]) for marker in markers}
    if accounts:
        if (
            str(accounts[0][1]) != clean_slug or str(accounts[0][5]).lower() != "nhan_vien"
            or str(accounts[0][6]).upper() != target_site
        ):
            raise EmployeeNotFound
        for row in accounts:
            if (
                str(row[0]) != account_id or str(row[6]).upper() != target_site
                or account_status_bit(row[7]) not in (0, 1) or int(row[8]) < 1
            ):
                raise EmployeeInfrastructureUnavailable
    if any(
        str(marker["account_id"]) != account_id
        or str(marker["target_site"]).upper() != target_site
        or marker["slug"] != clean_slug
        for marker in markers
    ) or len(employee_ids) > 1:
        raise EmployeeConflict
    if target_site != site or target_site not in sites:
        raise EmployeeNotFound

    target_marker = site_markers[target_site]
    employee_id = str(target_marker["employee_id"]) if target_marker else next(iter(employee_ids), "")
    profile_retained = bool(target_marker["profile_retained"]) if target_marker else False
    if target_marker is None:
        with get_site_connection(target_site).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2) ma_nhan_vien, ma_co_so, ma_tai_khoan, chuc_vu, trang_thai
                FROM dbo.NhanVien WHERE ma_tai_khoan = %s AND ma_co_so = %s
                  AND chuc_vu IN ('le_tan', 'tu_van', 'ke_toan')
                """,
                [account_id, target_site],
            )
            profiles = cursor.fetchall()
        if len(profiles) != 1 or str(profiles[0][1]).upper() != target_site:
            raise EmployeeConflict
        employee_id = str(profiles[0][0])
        if employee_ids and employee_id not in employee_ids:
            raise EmployeeConflict
        if str(profiles[0][4]).lower() not in {"dang_lam", "nghi_viec"}:
            raise EmployeeConflict
        with get_site_connection(target_site).cursor() as cursor:
            cursor.execute(
                "SELECT COUNT_BIG(*) FROM dbo.PhieuThu WHERE ma_nhan_vien = %s AND ma_co_so = %s",
                [employee_id, target_site],
            )
            profile_retained = int(cursor.fetchone()[0]) > 0
    if not employee_id:
        raise EmployeeConflict

    for code in sites:
        with get_site_connection(code).cursor() as cursor:
            _check_employee_delete_references(cursor, account_id)
            if code != target_site:
                cursor.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.NhanVien WHERE ma_tai_khoan = %s",
                    [account_id],
                )
                if int(cursor.fetchone()[0]):
                    raise EmployeeConflict
            elif code in active_sites:
                cursor.execute(
                    "SELECT TOP (2) ma_nhan_vien, ma_tai_khoan, trang_thai "
                    "FROM dbo.NhanVien WHERE ma_nhan_vien = %s AND ma_co_so = %s",
                    [employee_id, target_site],
                )
                profile = cursor.fetchall()
                if site_markers[target_site] is not None:
                    if profile_retained and (
                        len(profile) != 1 or profile[0][1] is not None
                        or str(profile[0][2]).lower() != "nghi_viec"
                    ):
                        raise EmployeeConflict
                    if not profile_retained and profile:
                        raise EmployeeConflict
                elif len(profile) != 1 or str(profile[0][1]) != account_id:
                    raise EmployeeConflict

    from core.media.avatars import AvatarUnavailable, destroy_cloudinary_avatar_asset

    ordered_sites = tuple(code for code in sites if code != target_site) + (target_site,)
    for code in ordered_sites:
        alias = get_site_database_alias(code)
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                marker = _read_employee_delete_marker(cursor, code, clean_slug)
                local_account = _employee_account_by_slug(cursor, clean_slug, lock=True)
                if marker is not None:
                    if local_account is not None:
                        raise EmployeeConflict
                    continue
                if code in active_sites and local_account is None:
                    raise EmployeeInfrastructureUnavailable
                if local_account is not None:
                    if accounts and _employee_delete_identity(local_account) != _employee_delete_identity(accounts[0]):
                        raise EmployeeConflict
                    if not accounts and str(local_account[0]) != account_id:
                        raise EmployeeConflict
                if local_account is not None and local_account[10]:
                    avatar_ids.add(str(local_account[10]))
                _check_employee_delete_references(cursor, account_id)
                if code == target_site and local_account is not None:
                    cursor.execute(
                        "SELECT TOP (2) ma_nhan_vien FROM dbo.NhanVien WITH (UPDLOCK, HOLDLOCK) "
                        "WHERE ma_nhan_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s "
                        "AND chuc_vu IN ('le_tan', 'tu_van', 'ke_toan')",
                        [employee_id, target_site, account_id],
                    )
                    profile = cursor.fetchall()
                    if len(profile) != 1:
                        raise EmployeeConflict
                    cursor.execute(
                        "SELECT COUNT_BIG(*) FROM dbo.PhieuThu WITH (UPDLOCK, HOLDLOCK) "
                        "WHERE ma_nhan_vien = %s AND ma_co_so = %s",
                        [employee_id, target_site],
                    )
                    has_receipts = int(cursor.fetchone()[0]) > 0
                    if has_receipts != profile_retained:
                        raise EmployeeConflict
                    if profile_retained:
                        cursor.execute(
                            "UPDATE dbo.NhanVien SET ma_tai_khoan = NULL, trang_thai = 'nghi_viec' "
                            "WHERE ma_nhan_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s",
                            [employee_id, target_site, account_id],
                        )
                    else:
                        cursor.execute(
                            "DELETE FROM dbo.NhanVien WHERE ma_nhan_vien = %s "
                            "AND ma_co_so = %s AND ma_tai_khoan = %s",
                            [employee_id, target_site, account_id],
                        )
                    if cursor.rowcount != 1:
                        raise EmployeeConflict
                if local_account is not None:
                    for table in (
                        "PhienDangNhap", "TokenDatLaiMatKhau",
                        "GiaoDichDatLaiMatKhau", "TrangThaiDocThongBao",
                    ):
                        cursor.execute(
                            f"IF OBJECT_ID(N'dbo.{table}', N'U') IS NOT NULL "
                            f"DELETE FROM dbo.{table} WHERE ma_tai_khoan = %s",
                            [account_id],
                        )
                    cursor.execute(
                        "DELETE FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s "
                        "AND vai_tro = 'nhan_vien' AND ma_co_so = %s",
                        [account_id, target_site],
                    )
                    if cursor.rowcount != 1:
                        raise EmployeeConflict
                payload = json.dumps(
                    {
                        "account_id": account_id, "employee_id": employee_id,
                        "slug": clean_slug, "target_site": target_site,
                        "profile_retained": profile_retained,
                        "avatar_public_id": str(local_account[10]) if local_account and local_account[10] else None,
                    },
                    separators=(",", ":"),
                )
                cursor.execute(
                    """
                    INSERT INTO dbo.Logs
                        (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong,
                         bang_tac_dong, ma_ban_ghi, du_lieu_cu, ip, ket_qua, site_dich)
                    VALUES (%s, 'system', %s, %s, 'xoa_nhan_vien', 'TaiKhoan',
                            %s, %s, %s, 'thanh_cong', %s)
                    """,
                    [
                        _employee_delete_marker_id(code, clean_slug), code, actor_id,
                        account_id, payload, remote_ip[:45], target_site,
                    ],
                )

    try:
        for avatar_id in avatar_ids:
            destroy_cloudinary_avatar_asset(avatar_id)
    except AvatarUnavailable as exc:
        raise EmployeeInfrastructureUnavailable from exc
    return EmployeeDeletionResult(employee_id, account_id, clean_slug, target_site, profile_retained)
