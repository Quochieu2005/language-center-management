"""SQL Server operations for site-local employee profiles and replicated accounts."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from functools import wraps

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.auth.account_state import account_status_bit
from core.academics.common import append_audit, acquire_record_lock, require_active_site
from core.auth.admin_small_lifecycle import _replicate_account
from core.auth.service_common import (
    AdminSmallAccountConflict,
    AuthInfrastructureUnavailable,
    _next_sequence_number,
    _replicated_account,
    active_site_codes,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.slug_utils import make_slug

logger = logging.getLogger("core.employees")
_JOB_TITLES = {"le_tan", "tu_van", "ke_toan", "xep_lop"}


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
    email_sent: bool
    must_change_password: bool = True


@dataclass(frozen=True)
class EmployeeDeactivationResult:
    employee_id: str
    account_id: str
    slug: str
    site_code: str
    status: str = "inactive"
    employee_status: str = "nghi_viec"


def _require_provisioning_configuration() -> str:
    password = str(getattr(settings, "ADMIN_SMALL_TEMP_PASSWORD", "")).strip()
    smtp_ready = (
        str(getattr(settings, "EMAIL_BACKEND", "")).endswith("smtp.EmailBackend")
        and getattr(settings, "EMAIL_HOST_USER", "")
        and getattr(settings, "EMAIL_HOST_PASSWORD", "")
        and getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )
    if not password or len(password) > 128 or not smtp_ready:
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
) -> None:
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


def _send_credentials(email: str, full_name: str, username: str, password: str) -> bool:
    try:
        return send_mail(
            subject="Tài khoản nhân viên Trung tâm Ngoại ngữ",
            message=(
                f"Chào {full_name},\n\nTài khoản nhân viên của bạn đã được tạo.\n"
                f"Tên đăng nhập: {username}\nMật khẩu tạm thời: {password}\n\n"
                "Hãy đổi mật khẩu ngay lần đăng nhập đầu tiên và không chia sẻ mật khẩu."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        ) == 1
    except Exception as exc:
        logger.warning("Employee credential email failed; error_type=%s", type(exc).__name__)
        return False


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
    try:
        # Persist the site-local employee and its login account in one commit first.
        with transaction.atomic(using=target_alias):
            _replicate_account(site, account, "them")
            _create_profile(
                site_code=site, employee_id=employee_id, account_id=account_id,
                full_name=normalized_name, phone=normalized_phone, email=normalized_email,
                job_title=job_title, actor_id=actor_id, remote_ip=remote_ip,
            )
        for active_site in sites:
            if active_site != site:
                _replicate_account(active_site, account, "them")
    except (EmployeeConflict, AdminSmallAccountConflict):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise EmployeeInfrastructureUnavailable from exc
    email_sent = _send_credentials(normalized_email, normalized_name, normalized_username, temporary_password)
    return EmployeeProvisioningResult(
        employee_id=employee_id, account_id=account_id, slug=account_slug,
        username=normalized_username, email=normalized_email, site_code=site,
        job_title=job_title, full_name=normalized_name, phone=normalized_phone,
        email_sent=email_sent,
    )


@_translate_errors
def list_employees(
    *, site_code: str, job_title: str | None, status: str | None,
    search: str | None, limit: int, offset: int,
) -> dict:
    site = str(site_code).strip().upper()
    alias = require_active_site(site)
    clauses = ["n.ma_co_so = %s", "n.chuc_vu IN ('le_tan', 'tu_van', 'ke_toan', 'xep_lop')"]
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
                   n.chuc_vu, n.trang_thai, t.trang_thai, t.ten_dang_nhap
            FROM dbo.NhanVien AS n
            LEFT JOIN dbo.TaiKhoan AS t
              ON t.ma_tai_khoan = n.ma_tai_khoan AND t.ma_co_so = n.ma_co_so
            WHERE """ + where + " ORDER BY n.ho_ten, n.ma_nhan_vien "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            [*params, offset, limit],
        )
        rows = cursor.fetchall()
    return {
        "site_code": site, "count": count, "limit": limit, "offset": offset,
        "results": [
            {
                "employee_id": str(row[0]), "account_id": str(row[1]) if row[1] else None,
                "slug": str(row[2]) if row[2] else None, "full_name": str(row[3]),
                "phone": row[4], "email": row[5], "job_title": str(row[6]).lower(),
                "employee_status": str(row[7]).lower(),
                "account_status": "active" if row[8] in (True, 1, "1") else "inactive" if row[8] is not None else None,
                "username": str(row[9]) if row[9] else None,
            }
            for row in rows
        ],
    }


def _read_employee_for_deactivation(site_code: str, slug: str):
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT TOP (2) n.ma_nhan_vien, n.ma_tai_khoan, n.trang_thai,
                           t.slug, t.vai_tro, t.ma_co_so
            FROM dbo.NhanVien AS n
            INNER JOIN dbo.TaiKhoan AS t
              ON t.ma_tai_khoan = n.ma_tai_khoan AND t.ma_co_so = n.ma_co_so
            WHERE n.ma_co_so = %s AND t.slug = %s
              AND n.chuc_vu IN ('le_tan', 'tu_van', 'ke_toan', 'xep_lop')
            """,
            [site_code, slug],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise EmployeeConflict
    return tuple(rows[0]) if rows else None


def _read_employee_account_copies(account_id: str, sites: tuple[str, ...]):
    copies = []
    for site in sites:
        with get_site_connection(site).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2) ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                               vai_tro, ma_co_so, trang_thai, phien_ban,
                               bat_buoc_doi_mat_khau
                FROM dbo.TaiKhoan
                WHERE ma_tai_khoan = %s
                """,
                [account_id],
            )
            rows = cursor.fetchall()
        if len(rows) > 1:
            raise EmployeeInfrastructureUnavailable
        if not rows:
            raise EmployeeInfrastructureUnavailable
        copies.append(tuple(rows[0]))

    # Status/version may differ after an interrupted replicated write; all identity
    # and credential fields must still agree so the same request can safely resume.
    identity = (*copies[0][:7], copies[0][9])
    if any((*row[:7], row[9]) != identity for row in copies[1:]):
        raise EmployeeInfrastructureUnavailable
    if str(copies[0][5]).lower() != "nhan_vien":
        raise EmployeeNotFound
    return copies


def _append_employee_replication_event(cursor, site_code: str, account_id: str) -> None:
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, bang_tac_dong, ma_ban_ghi,
             hanh_dong, site_dich, ket_qua)
        VALUES (%s, 'sync', %s, 'TaiKhoan', %s, 'sua', %s, 'thanh_cong')
        """,
        [
            f"{site_code}-DB-{uuid.uuid4().hex[:10]}", site_code,
            account_id, site_code,
        ],
    )


def _deactivate_account_copy(
    *, site_code: str, account_id: str,
    employee_id: str, profile_site: str, actor_id: str, remote_ip: str,
) -> None:
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT trang_thai, phien_ban, vai_tro, ma_co_so
                FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_tai_khoan = %s
                """,
                [account_id],
            )
            current = cursor.fetchone()
            if (
                current is None or str(current[2]).lower() != "nhan_vien"
                or str(current[3]).upper() != profile_site
            ):
                raise EmployeeConflict
            status_bit = account_status_bit(current[0])
            version = int(current[1])
            if status_bit not in (0, 1) or version < 1:
                raise EmployeeConflict
            if status_bit == 1:
                cursor.execute(
                    """
                    UPDATE dbo.TaiKhoan
                    SET trang_thai = 0, phien_ban = phien_ban + 1,
                        cap_nhat_luc = SYSUTCDATETIME()
                    WHERE ma_tai_khoan = %s AND vai_tro = 'nhan_vien'
                      AND ma_co_so = %s AND trang_thai = 1 AND phien_ban = %s
                    """,
                    [account_id, profile_site, version],
                )
                if cursor.rowcount != 1:
                    raise EmployeeConflict
                _append_employee_replication_event(cursor, site_code, account_id)

            cursor.execute(
                """
                UPDATE dbo.PhienDangNhap
                SET thu_hoi_luc_utc = COALESCE(thu_hoi_luc_utc, SYSUTCDATETIME())
                WHERE ma_tai_khoan = %s AND thu_hoi_luc_utc IS NULL
                """,
                [account_id],
            )

            if site_code == profile_site:
                cursor.execute(
                    """
                    SELECT trang_thai FROM dbo.NhanVien WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_nhan_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
                      AND chuc_vu IN ('le_tan', 'tu_van', 'ke_toan', 'xep_lop')
                    """,
                    [employee_id, profile_site, account_id],
                )
                profile = cursor.fetchone()
                if profile is None or str(profile[0]).lower() not in {"dang_lam", "nghi_viec"}:
                    raise EmployeeConflict
                old_status = str(profile[0]).lower()
                if old_status == "dang_lam":
                    cursor.execute(
                        """
                        UPDATE dbo.NhanVien SET trang_thai = 'nghi_viec'
                        WHERE ma_nhan_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
                          AND trang_thai = 'dang_lam'
                        """,
                        [employee_id, profile_site, account_id],
                    )
                    if cursor.rowcount != 1:
                        raise EmployeeConflict
                    append_audit(
                        cursor, site_code=profile_site, actor_id=actor_id,
                        action="xoa_nhan_vien", table_name="NhanVien",
                        record_id=employee_id, remote_ip=remote_ip,
                        before={"status": old_status}, after={"status": "nghi_viec"},
                    )


@_translate_errors
def deactivate_employee(
    *, slug: str, site_code: str, actor_id: str, remote_ip: str,
) -> EmployeeDeactivationResult:
    site = str(site_code).strip().upper()
    clean_slug = str(slug).strip()
    if not clean_slug or not actor_id or not remote_ip:
        raise EmployeeNotFound
    sites = active_site_codes()
    if site not in sites:
        raise EmployeeInfrastructureUnavailable

    profile = _read_employee_for_deactivation(site, clean_slug)
    if profile is None:
        raise EmployeeNotFound
    employee_id, account_id = str(profile[0]), str(profile[1])
    if str(profile[3]) != clean_slug or str(profile[4]).lower() != "nhan_vien":
        raise EmployeeNotFound
    profile_status = str(profile[2]).lower()

    copies = _read_employee_account_copies(account_id, sites)
    account_site = str(copies[0][6]).upper() if copies[0][6] else ""
    if account_site != site:
        raise EmployeeNotFound
    copy_statuses = [account_status_bit(row[7]) for row in copies]
    if any(value not in (0, 1) for value in copy_statuses):
        raise EmployeeConflict
    if profile_status not in {"dang_lam", "nghi_viec"}:
        raise EmployeeConflict

    # Update remote copies first and the profile site last. A partial failure can
    # be retried: the next request accepts already-inactive replicas and continues.
    ordered_sites = tuple(code for code in sites if code != site) + (site,)
    for code in ordered_sites:
        _deactivate_account_copy(
            site_code=code, account_id=account_id, employee_id=employee_id,
            profile_site=site, actor_id=actor_id, remote_ip=remote_ip,
        )
    return EmployeeDeactivationResult(employee_id, account_id, clean_slug, site)
