"""Site-scoped student account provisioning and self-service reads."""

from __future__ import annotations

from core.auth.account_replication import provisioning_sites, serialize_account_creation
from core.students.identity import reserve_student_email

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone
from functools import wraps
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import DatabaseError, connections, transaction
from django.utils import timezone

from core.auth.account_state import account_is_active, account_status_bit
from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    _next_sequence_number,
    _replicated_account,
    active_site_codes,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.slug_utils import make_slug
from core.students.slugging import available_student_slug


logger = logging.getLogger("core.students")
_CURRENT_STUDENT_STATUSES = ("dang_hoc", "bao_luu")
_ACTIVE_ENROLLMENT_STATUSES = ("da_dang_ky", "dang_hoc")


class StudentInfrastructureUnavailable(Exception):
    """A required database site, coordinator ledger, or email service is unavailable."""


class StudentNotFound(Exception):
    """The student profile does not exist at the authorized site."""


class StudentConflict(Exception):
    """The student account or local profile changed during the operation."""


class StudentNotEligible(Exception):
    """The student is not active or has no valid email for account issuance."""


class StudentSiteUnavailable(Exception):
    """The requested site is not active or configured."""


@dataclass(frozen=True)
class StudentAccountResult:
    account_id: str
    student_id: str
    slug: str
    site_code: str
    username: str
    email: str
    email_sent: bool
    must_change_password: bool = True
    replication_pending_sites: tuple[str, ...] = ()


def _translate_infrastructure_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except StudentInfrastructureUnavailable:
            raise
        except (
            AuthInfrastructureUnavailable,
            DatabaseError,
            ImproperlyConfigured,
            KeyError,
            UnknownSiteError,
        ) as exc:
            raise StudentInfrastructureUnavailable from exc

    return wrapped


def _site_code(value: str | None) -> str:
    return str(value or "").strip().upper()


def _verify_active_site(site_code: str, active_sites: tuple[str, ...]) -> None:
    if site_code not in active_sites:
        raise StudentSiteUnavailable


def _dict_rows(cursor) -> list[dict[str, Any]]:
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _local_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime_timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))


def _load_student_by_slug(site_code: str, slug: str):
    with get_site_connection(site_code).cursor() as cursor:
        cursor.execute(
            """
            SELECT TOP (2) h.ma_hoc_vien, h.slug, h.ma_co_so, h.ho_ten, h.sdt,
                   h.email, h.trang_thai, h.ma_tai_khoan,
                   CASE WHEN EXISTS
                   (
                       SELECT 1 FROM dbo.DangKy AS d
                       WHERE d.ma_hoc_vien = h.ma_hoc_vien
                         AND d.ma_co_so = h.ma_co_so
                         AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
                   ) THEN 1 ELSE 0 END AS co_dang_ky_hieu_luc
            FROM dbo.HocVien AS h
            WHERE h.slug = %s
            """,
            [slug],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise StudentInfrastructureUnavailable
    return tuple(rows[0]) if rows else None


@_translate_infrastructure_errors
def list_students(
    *, site_code: str, status_filter: str | None, search: str | None,
    account_issued: bool | None, limit: int, offset: int,
) -> dict[str, Any]:
    sites = active_site_codes()
    site = _site_code(site_code)
    _verify_active_site(site, sites)
    predicates = ["h.ma_co_so = %s"]
    params: list[Any] = [site]
    if status_filter:
        predicates.append("h.trang_thai = %s")
        params.append(status_filter)
    if account_issued is not None:
        predicates.append("h.ma_tai_khoan IS NOT NULL" if account_issued else "h.ma_tai_khoan IS NULL")
    if search:
        pattern = f"%{search.strip()}%"
        predicates.append(
            "(h.ma_hoc_vien LIKE %s OR h.ho_ten LIKE %s OR h.email LIKE %s OR h.sdt LIKE %s)"
        )
        params.extend([pattern] * 4)
    where_sql = " AND ".join(predicates)
    alias = get_site_database_alias(site)
    with connections[alias].cursor() as cursor:
        cursor.execute(f"SELECT COUNT_BIG(*) FROM dbo.HocVien AS h WHERE {where_sql}", params)
        count = int(cursor.fetchone()[0])
        cursor.execute(
            f"""
            SELECT h.ma_hoc_vien AS student_id, h.slug, h.ma_co_so AS site_code,
                   h.ho_ten AS full_name, h.sdt AS phone, h.email,
                   h.avatar_secure_url AS avatar_secure_url,
                   h.trang_thai AS status,
                   CONVERT(bit, CASE WHEN h.ma_tai_khoan IS NULL THEN 0 ELSE 1 END) AS account_issued,
                   CONVERT(bit, CASE WHEN h.ma_tai_khoan IS NULL AND h.trang_thai = 'dang_hoc'
                       AND NULLIF(LTRIM(RTRIM(h.email)), N'') IS NOT NULL
                       THEN 1 ELSE 0 END) AS account_issue_eligible
            FROM dbo.HocVien AS h
            WHERE {where_sql}
            ORDER BY h.ho_ten, h.ma_hoc_vien
            OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """,
            [*params, offset, limit],
        )
        rows = _dict_rows(cursor)
    for row in rows:
        if row["account_issue_eligible"]:
            try:
                validate_email(str(row["email"]).strip())
            except ValidationError:
                row["account_issue_eligible"] = False
    return {
        "site_code": site,
        "count": count,
        "limit": limit,
        "offset": offset,
        "results": rows,
    }


def _next_student_account_id(site_code: str, sites: tuple[str, ...]) -> str:
    for _ in range(1000):
        candidate = f"{site_code}-TK-{_next_sequence_number(site_code, 'Seq_TK'):06d}"
        exists = False
        for code in sites:
            with get_site_connection(code).cursor() as cursor:
                cursor.execute(
                    "SELECT CASE WHEN EXISTS "
                    "(SELECT 1 FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s) THEN 1 ELSE 0 END",
                    [candidate],
                )
                if int(cursor.fetchone()[0]):
                    exists = True
                    break
        if not exists:
            return candidate
    raise StudentInfrastructureUnavailable


def _username_candidate(email: str, site_code: str, sites: tuple[str, ...]) -> str:
    local_part = email.partition("@")[0]
    base = make_slug(f"hv-{site_code.lower()}-{local_part}", max_length=80)
    for suffix in range(0, 1000):
        candidate = base if suffix == 0 else f"{base}-{suffix}"
        if _replicated_account(candidate, sites) is None:
            return candidate
    raise StudentConflict


def _account_slug_candidate(profile_slug: str, sites: tuple[str, ...]) -> str:
    base = make_slug(f"hoc-vien-{profile_slug}", max_length=120)
    for suffix in range(0, 100):
        candidate = base if suffix == 0 else make_slug(f"{base}-{suffix}", max_length=120)
        found = False
        for code in sites:
            with get_site_connection(code).cursor() as cursor:
                cursor.execute(
                    "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.TaiKhoan WHERE slug = %s) "
                    "THEN 1 ELSE 0 END",
                    [candidate],
                )
                found = bool(cursor.fetchone()[0])
            if found:
                break
        if not found:
            return candidate
    raise StudentConflict


def _create_or_load_student_account(
    student, site_code: str, actor_id: str, remote_ip: str, sites: tuple[str, ...]
) -> tuple[Any, ...]:
    if not settings.STUDENT_INITIAL_PASSWORD:
        raise StudentInfrastructureUnavailable
    if (
        not settings.EMAIL_HOST_USER
        or not settings.EMAIL_HOST_PASSWORD
        or not settings.DEFAULT_FROM_EMAIL
        or not settings.EMAIL_BACKEND.endswith("smtp.EmailBackend")
    ):
        raise StudentInfrastructureUnavailable

    student_id = str(student[0])
    email = str(student[5] or "").strip().casefold()
    alias = get_site_database_alias(site_code)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP (2) h.ma_hoc_vien, h.slug, h.ma_co_so, h.ho_ten,
                           h.sdt, h.email, h.trang_thai, h.ma_tai_khoan
                    FROM dbo.HocVien AS h WITH (UPDLOCK, HOLDLOCK)
                    WHERE h.ma_hoc_vien = %s AND h.ma_co_so = %s
                    """,
                    [student_id, site_code],
                )
                rows = cursor.fetchall()
                if len(rows) != 1:
                    raise StudentNotFound
                current = tuple(rows[0])
                if str(current[6]).lower() != "dang_hoc":
                    raise StudentNotEligible
                if str(current[5] or "").strip().casefold() != email:
                    raise StudentConflict
                try:
                    validate_email(email)
                except ValidationError as exc:
                    raise StudentNotEligible from exc

                if current[7] is not None:
                    cursor.execute(
                        """
                        SELECT ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                               vai_tro, ma_co_so, trang_thai,
                               bat_buoc_doi_mat_khau, phien_ban
                        FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s
                        """,
                        [current[7]],
                    )
                    account = cursor.fetchone()
                    if account is None:
                        raise StudentInfrastructureUnavailable
                    return tuple(account)

                if _replicated_account(email, sites) is not None:
                    raise StudentConflict
                username = _username_candidate(email, site_code, sites)
                account_slug = _account_slug_candidate(str(current[1]), sites)
                account_id = _next_student_account_id(site_code, sites)
                password_hash = make_password(settings.STUDENT_INITIAL_PASSWORD)
                cursor.execute(
                    """
                    INSERT INTO dbo.TaiKhoan
                        (ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro,
                         ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban)
                    VALUES (%s, %s, %s, %s, %s, 'hoc_vien', %s, 1, 1, 1)
                    """,
                    [account_id, account_slug, username, email, password_hash, site_code],
                )
                cursor.execute(
                    """
                    UPDATE dbo.HocVien SET ma_tai_khoan = %s
                    WHERE ma_hoc_vien = %s AND ma_co_so = %s AND ma_tai_khoan IS NULL
                    """,
                    [account_id, student_id, site_code],
                )
                if cursor.rowcount != 1:
                    raise StudentConflict
                _append_audit(
                    cursor, site_code, actor_id, "cap_tai_khoan_hoc_vien", "HocVien",
                    student_id, remote_ip, account_id,
                    {"account_id": account_id, "student_id": student_id},
                )
                return (
                    account_id, account_slug, username, email, password_hash,
                    "hoc_vien", site_code, 1, 1, 1,
                )
    except (StudentNotFound, StudentConflict, StudentNotEligible, StudentInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise StudentInfrastructureUnavailable from exc


def _append_replication_event(cursor, site_code: str, account_id: str) -> None:
    event_id = f"{site_code}-DB-{uuid.uuid5(uuid.NAMESPACE_URL, f'{account_id}:{site_code}:replica').hex[:10]}"
    cursor.execute(
        "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua "
        "FROM dbo.Logs WHERE loai_log = 'sync' AND ma_log = %s",
        [event_id],
    )
    event = cursor.fetchone()
    expected = ("TaiKhoan", account_id, "them", site_code, "thanh_cong")
    if event is not None:
        actual = tuple(str(item) for item in event)
        if actual != expected:
            raise StudentInfrastructureUnavailable
        return
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua)
        VALUES (%s, 'sync', 'TaiKhoan', %s, 'them', %s, 'thanh_cong')
        """,
        [event_id, account_id, site_code],
    )


def _append_audit(cursor, site_code: str, actor_id: str, action: str, table: str,
                  record_id: str, remote_ip: str, operation_id: str, details: dict[str, Any]) -> None:
    audit_id = f"{site_code}-NK-{uuid.uuid5(uuid.NAMESPACE_URL, f'{operation_id}:{site_code}:{action}').hex[:10]}"
    cursor.execute(
        "SELECT ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, ma_ban_ghi "
        "FROM dbo.Logs WHERE loai_log = 'system' AND ma_log = %s",
        [audit_id],
    )
    existing = cursor.fetchone()
    expected = (site_code, actor_id, action, table, record_id)
    if existing is not None:
        if tuple(str(item) for item in existing) != expected:
            raise StudentInfrastructureUnavailable
        return
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_moi, ip, ket_qua)
        VALUES (%s, 'system', %s, %s, %s, %s, %s, %s, %s, 'thanh_cong')
        """,
        [audit_id, site_code, actor_id, action, table, record_id,
         json.dumps(details, ensure_ascii=False), remote_ip[:45]],
    )


_STUDENT_PROFILE_COLUMNS = {
    "full_name": "ho_ten",
    "birth_date": "ngay_sinh",
    "gender": "gioi_tinh",
    "phone": "sdt",
    "email": "email",
    "address": "dia_chi",
}


def _student_admin_profile(cursor, site_code: str, slug: str, *, lock: bool = False):
    hint = " WITH (UPDLOCK, HOLDLOCK)" if lock else ""
    cursor.execute(
        """
        SELECT TOP (2) ma_hoc_vien AS student_id, slug, ma_co_so AS site_code,
               ho_ten AS full_name, ngay_sinh AS birth_date, gioi_tinh AS gender,
               sdt AS phone, email, dia_chi AS address, ngay_nhap_hoc AS enrolled_on,
               trang_thai AS status, ma_tai_khoan AS account_id,
               avatar_secure_url
        FROM dbo.HocVien AS h""" + hint + " WHERE slug = %s AND ma_co_so = %s",
        [slug, site_code],
    )
    rows = _dict_rows(cursor)
    if len(rows) > 1:
        raise StudentInfrastructureUnavailable
    if not rows:
        raise StudentNotFound
    return rows[0]


@_translate_infrastructure_errors
def get_admin_student_profile(*, site_code: str, student_slug: str) -> dict[str, Any]:
    site = _site_code(site_code)
    _verify_active_site(site, active_site_codes())
    alias = get_site_database_alias(site)
    with connections[alias].cursor() as cursor:
        profile = _student_admin_profile(cursor, site, student_slug)
    profile.pop("account_id", None)
    return profile


@_translate_infrastructure_errors
@reserve_student_email(StudentConflict)
def create_student_profile(
    *, site_code: str, fields: dict[str, Any], actor_id: str, remote_ip: str,
) -> dict[str, Any]:
    site = _site_code(site_code)
    _verify_active_site(site, active_site_codes())
    alias = get_site_database_alias(site)
    student_id = f"{site}-HV-{_next_sequence_number(site, 'Seq_HV'):06d}"
    values = {name: fields.get(name) for name in _STUDENT_PROFILE_COLUMNS}
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            slug = available_student_slug(cursor, values["full_name"], fields.get("slug"))
            cursor.execute(
                """
                INSERT INTO dbo.HocVien
                    (ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, ngay_sinh,
                     gioi_tinh, sdt, email, dia_chi, ngay_nhap_hoc, trang_thai)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'dang_hoc')
                """,
                [student_id, slug, site, site, values["full_name"], values["birth_date"],
                 values["gender"], values["phone"], values["email"], values["address"],
                 timezone.localdate()],
            )
            _append_audit(
                cursor, site, actor_id, "tao_ho_so_hoc_vien", "HocVien", student_id,
                remote_ip, uuid.uuid4().hex, {"fields": sorted(fields)},
            )
    return get_admin_student_profile(site_code=site, student_slug=slug)


@_translate_infrastructure_errors
@reserve_student_email(StudentConflict)
def update_student_profile(
    *, site_code: str, student_slug: str, fields: dict[str, Any],
    actor_id: str, remote_ip: str,
) -> dict[str, Any]:
    site = _site_code(site_code)
    _verify_active_site(site, active_site_codes())
    alias = get_site_database_alias(site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            profile = _student_admin_profile(cursor, site, student_slug, lock=True)
            if str(profile["status"]).lower() == "da_chuyen_di":
                raise StudentConflict
            cursor.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.GiaoDichChuyenCoSo "
                "WHERE ma_hoc_vien = %s AND co_so_nguon = %s AND trang_thai = 'dang_xu_ly') "
                "THEN 1 ELSE 0 END",
                [profile["student_id"], site],
            )
            if cursor.fetchone()[0]:
                raise StudentConflict
            current_email = (profile["email"] or "").casefold()
            requested_email = fields.get("email", profile["email"])
            if profile["account_id"] is not None and (
                (requested_email or "").casefold() != current_email
            ):
                raise StudentConflict

            changes = {
                name: value for name, value in fields.items()
                if value != profile[name]
            }
            if changes:
                assignments = ", ".join(
                    f"{_STUDENT_PROFILE_COLUMNS[name]} = %s" for name in changes
                )
                cursor.execute(
                    f"UPDATE dbo.HocVien SET {assignments} "
                    "WHERE ma_hoc_vien = %s AND ma_co_so = %s AND slug = %s",
                    [*changes.values(), profile["student_id"], site, student_slug],
                )
                if cursor.rowcount != 1:
                    raise StudentConflict
                _append_audit(
                    cursor, site, actor_id, "sua_ho_so_hoc_vien", "HocVien",
                    profile["student_id"], remote_ip, uuid.uuid4().hex,
                    {"fields": sorted(changes)},
                )
    return get_admin_student_profile(site_code=site, student_slug=student_slug)


@_translate_infrastructure_errors
def delete_student_profile(
    *, site_code: str, student_slug: str, actor_id: str, remote_ip: str,
) -> dict[str, Any]:
    site = _site_code(site_code)
    _verify_active_site(site, active_site_codes())
    alias = get_site_database_alias(site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            profile = _student_admin_profile(cursor, site, student_slug, lock=True)
            if profile["account_id"] is not None or str(profile["status"]).lower() == "da_chuyen_di":
                raise StudentConflict
            cursor.execute(
                """
                SELECT CASE WHEN
                    EXISTS (SELECT 1 FROM dbo.DangKy WHERE ma_hoc_vien = %s AND ma_co_so = %s)
                    OR EXISTS (SELECT 1 FROM dbo.GiaoDichChuyenCoSo WHERE ma_hoc_vien = %s)
                    OR EXISTS (SELECT 1 FROM dbo.LichSuChuyenCoSo WHERE ma_hoc_vien = %s)
                THEN 1 ELSE 0 END
                """,
                [profile["student_id"], site, profile["student_id"], profile["student_id"]],
            )
            if cursor.fetchone()[0]:
                raise StudentConflict
            _append_audit(
                cursor, site, actor_id, "xoa_ho_so_hoc_vien", "HocVien",
                profile["student_id"], remote_ip, uuid.uuid4().hex, {},
            )
            cursor.execute(
                "DELETE FROM dbo.HocVien "
                "WHERE ma_hoc_vien = %s AND ma_co_so = %s AND slug = %s AND ma_tai_khoan IS NULL",
                [profile["student_id"], site, student_slug],
            )
            if cursor.rowcount != 1:
                raise StudentConflict
    return {
        "student_id": profile["student_id"],
        "slug": student_slug,
        "site_code": site,
        "deleted": True,
    }


def _ensure_account_replica(site_code: str, expected: tuple[Any, ...]) -> None:
    alias = get_site_database_alias(site_code)
    account_id, slug, username, email, password_hash, role, account_site, status, forced, version = expected
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
                raise StudentConflict
            actual = None
            if rows:
                row = rows[0]
                actual = (
                    str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]),
                    str(row[5]).lower(), _site_code(row[6]) or None,
                    account_status_bit(row[7]), bool(row[8]), int(row[9]),
                )
            normalized = (
                str(account_id), str(slug), str(username), str(email), str(password_hash),
                str(role).lower(), _site_code(account_site) or None,
                account_status_bit(status), bool(forced), int(version),
            )
            if actual is None:
                cursor.execute(
                    """
                    INSERT INTO dbo.TaiKhoan
                        (ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro,
                         ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban)
                    VALUES (%s, %s, %s, %s, %s, 'hoc_vien', %s, %s, %s, %s)
                    """,
                    [account_id, slug, username, email, password_hash, account_site, status, forced, version],
                )
            elif actual != normalized:
                raise StudentConflict
            _append_replication_event(cursor, site_code, str(account_id))


def _ensure_student_link(site_code: str, student: tuple[Any, ...], account_id: str,
                         actor_id: str, remote_ip: str) -> None:
    alias = get_site_database_alias(site_code)
    student_id, slug, _record_site = str(student[0]), str(student[1]), str(student[2])
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (2) ma_hoc_vien, ma_co_so, ma_tai_khoan,
                       trang_thai, email
                FROM dbo.HocVien AS h WITH (UPDLOCK, HOLDLOCK)
                WHERE slug = %s
                """,
                [slug],
            )
            rows = cursor.fetchall()
            if not rows:
                raise StudentNotFound
            if len(rows) != 1:
                raise StudentInfrastructureUnavailable
            row = rows[0]
            if str(row[0]) != student_id or _site_code(row[1]) != site_code:
                raise StudentConflict
            if str(row[3]).lower() != "dang_hoc":
                raise StudentNotEligible
            if str(row[4] or "").strip().casefold() != str(student[5] or "").strip().casefold():
                raise StudentConflict
            if row[2] is not None and str(row[2]) != account_id:
                raise StudentConflict
            if row[2] is None:
                cursor.execute(
                    "UPDATE dbo.HocVien SET ma_tai_khoan = %s WHERE ma_hoc_vien = %s "
                    "AND ma_co_so = %s AND ma_tai_khoan IS NULL",
                    [account_id, student_id, site_code],
                )
                if cursor.rowcount != 1:
                    raise StudentConflict
            _append_audit(
                cursor, site_code, actor_id, "cap_tai_khoan_hoc_vien", "HocVien",
                student_id, remote_ip, account_id,
                {"account_id": account_id, "student_id": student_id},
            )


def _send_student_credentials(email: str, student_name: str, password: str) -> None:
    try:
        sent = send_mail(
            subject="Tài khoản học viên Trung tâm Ngoại ngữ",
            message=(
                f"Chào {student_name},\n\n"
                "Tài khoản học viên của bạn đã được cấp.\n"
                f"Email đăng nhập: {email}\n"
                f"Mật khẩu tạm thời: {password}\n\n"
                "Hãy đăng nhập bằng email này trên cổng học viên và đổi mật khẩu ngay lần đầu. "
                "Không chia sẻ mật khẩu này với người khác."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        if sent != 1:
            raise StudentInfrastructureUnavailable
    except StudentInfrastructureUnavailable:
        raise
    except Exception as exc:
        logger.warning("Student credential email delivery failed; error_type=%s.", type(exc).__name__)
        raise StudentInfrastructureUnavailable from exc


def _student_account_result(account: tuple[Any, ...], student, site_code: str,
                            *, email_sent: bool) -> StudentAccountResult:
    return StudentAccountResult(
        account_id=str(account[0]),
        student_id=str(student[0]),
        slug=str(student[1]),
        site_code=site_code,
        username=str(account[2]),
        email=str(account[3]),
        email_sent=email_sent,
        must_change_password=bool(account[8]),
    )


@_translate_infrastructure_errors
@serialize_account_creation
def issue_student_account(
    *, site_code: str, student_slug: str, actor_id: str, remote_ip: str,
) -> StudentAccountResult:
    sites = provisioning_sites(site_code)
    target_site = _site_code(site_code)
    _verify_active_site(target_site, sites)
    student = _load_student_by_slug(target_site, student_slug)
    if student is None:
        raise StudentNotFound
    account = _create_or_load_student_account(
        student, target_site, actor_id, remote_ip, sites
    )
    account_id = str(account[0])
    if (
        str(account[5]).lower() != "hoc_vien"
        or _site_code(account[6]) != target_site
        or not account_is_active(account[7])
        or str(account[3]).strip().casefold() != str(student[5] or "").strip().casefold()
    ):
        raise StudentConflict

    for code in sites:
        _ensure_account_replica(code, account)
    _ensure_student_link(target_site, student, account_id, actor_id, remote_ip)

    email_sent = False
    initial_password = str(settings.STUDENT_INITIAL_PASSWORD or "")
    if bool(account[8]) and initial_password:
        if not check_password(initial_password, str(account[4])):
            raise StudentInfrastructureUnavailable
        _send_student_credentials(
            str(account[3]), str(student[3]), initial_password
        )
        email_sent = True
    return _student_account_result(account, student, target_site, email_sent=email_sent)


@_translate_infrastructure_errors
def get_student_profile(*, account_id: str, student_id: str, site_code: str):
    alias = get_site_database_alias(_site_code(site_code))
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT ma_hoc_vien AS student_id, slug, ma_co_so AS site_code,
                   ho_ten AS full_name, ngay_sinh AS birth_date,
                   gioi_tinh AS gender, sdt AS phone, email,
                   dia_chi AS address, ngay_nhap_hoc AS enrolled_on,
                   trang_thai AS status, avatar_secure_url
            FROM dbo.HocVien
            WHERE ma_hoc_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
              AND trang_thai IN ('dang_hoc', 'bao_luu')
            """,
            [student_id, site_code, account_id],
        )
        rows = _dict_rows(cursor)
    if len(rows) != 1:
        raise StudentNotFound
    return rows[0]


@_translate_infrastructure_errors
def update_student_contact(*, user, changes: dict[str, Any], remote_ip: str):
    if user.role != "hoc_vien" or not user.site_code or not user.profile_id:
        raise StudentNotFound
    site_code = _site_code(user.site_code)
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (1) sdt, dia_chi, ho_ten, ngay_sinh, gioi_tinh
                FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_hoc_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
                  AND trang_thai IN ('dang_hoc', 'bao_luu')
                """,
                [user.profile_id, site_code, user.account_id],
            )
            before = cursor.fetchone()
            if before is None:
                raise StudentNotFound
            new_phone = changes.get("phone", before[0])
            new_address = changes.get("address", before[1])
            new_name = changes.get("full_name", before[2])
            new_birth = changes.get("birth_date", before[3])
            new_gender = changes.get("gender", before[4])
            cursor.execute(
                """
                UPDATE dbo.HocVien SET sdt = %s, dia_chi = %s, ho_ten = %s, ngay_sinh = %s, gioi_tinh = %s
                WHERE ma_hoc_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
                """,
                [new_phone, new_address, new_name, new_birth, new_gender,
                 user.profile_id, site_code, user.account_id],
            )
            if cursor.rowcount != 1:
                raise StudentConflict
            audit_id = f"{site_code}-NK-{_next_sequence_number(site_code, 'Seq_NK'):06d}"
            cursor.execute(
                """
                INSERT INTO dbo.Logs
                    (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
                     ma_ban_ghi, du_lieu_moi, ip, ket_qua)
                VALUES (%s, 'system', %s, %s, 'hoc_vien_cap_nhat_lien_he', 'HocVien', %s, %s, %s, 'thanh_cong')
                """,
                [audit_id, site_code, user.account_id, user.profile_id,
                 json.dumps({"fields": sorted(changes)}), remote_ip[:45]],
            )
    return get_student_profile(
        account_id=user.account_id, student_id=user.profile_id, site_code=site_code
    )


def _student_rows(user, sql: str, params: list[Any]):
    if user.role != "hoc_vien" or not user.site_code or not user.profile_id:
        raise StudentNotFound
    alias = get_site_database_alias(_site_code(user.site_code))
    with connections[alias].cursor() as cursor:
        cursor.execute(sql, params)
        return _dict_rows(cursor)


@_translate_infrastructure_errors
def get_student_enrollments(user):
    rows = _student_rows(
        user,
        """
        SELECT TOP (200) d.ma_dang_ky AS enrollment_id, d.ngay_dang_ky AS enrolled_at,
               d.trang_thai AS enrollment_status, l.ma_lop AS class_id,
               l.ten_lop AS class_name, k.ma_khoa_hoc AS course_id,
               k.ten_khoa_hoc AS course_name, m.ten_mon AS subject_name,
               l.ngay_khai_giang AS start_date, l.ngay_ket_thuc AS end_date,
               l.lich_hoc AS schedule, l.gio_bat_dau AS start_time,
               l.gio_ket_thuc AS end_time, l.trang_thai AS class_status
        FROM dbo.DangKy AS d
        INNER JOIN dbo.LopHoc AS l ON l.ma_lop = d.ma_lop AND l.ma_co_so = d.ma_co_so
        INNER JOIN dbo.KhoaHoc AS k ON k.ma_khoa_hoc = l.ma_khoa_hoc
        INNER JOIN dbo.MonHoc AS m ON m.ma_mon = k.ma_mon
        WHERE d.ma_hoc_vien = %s AND d.ma_co_so = %s
        ORDER BY d.ngay_dang_ky DESC, d.ma_dang_ky DESC
        """,
        [user.profile_id, user.site_code],
    )
    for row in rows:
        row["enrolled_at"] = _local_datetime(row["enrolled_at"])
    return {"site_code": user.site_code, "count": len(rows), "results": rows}


@_translate_infrastructure_errors
def get_student_schedule(user):
    rows = _student_rows(
        user,
        """
        SELECT TOP (200) b.ma_buoi AS session_id, l.ma_lop AS class_id,
               l.ten_lop AS class_name, b.so_thu_tu AS session_number,
               b.ngay_hoc AS date, b.gio_bat_dau AS start_time,
               b.gio_ket_thuc AS end_time, p.ten_phong AS room_name,
               g.ho_ten AS teacher_name, b.trang_thai AS status
        FROM dbo.DangKy AS d
        INNER JOIN dbo.BuoiHoc AS b ON b.ma_lop = d.ma_lop AND b.ma_co_so = d.ma_co_so
        INNER JOIN dbo.LopHoc AS l ON l.ma_lop = d.ma_lop AND l.ma_co_so = d.ma_co_so
        INNER JOIN dbo.PhongHoc AS p ON p.ma_phong = b.ma_phong AND p.ma_co_so = b.ma_co_so
        INNER JOIN dbo.GiaoVien AS g ON g.ma_giao_vien = b.ma_giao_vien AND g.ma_co_so = b.ma_co_so
        WHERE d.ma_hoc_vien = %s AND d.ma_co_so = %s
          AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
        ORDER BY b.ngay_hoc, b.gio_bat_dau, b.ma_buoi
        """,
        [user.profile_id, user.site_code],
    )
    return {"site_code": user.site_code, "count": len(rows), "results": rows}


@_translate_infrastructure_errors
def get_student_tuition(user):
    rows = _student_rows(
        user,
        """
        SELECT TOP (100) hp.ma_hoc_phi AS tuition_id, hp.ma_dang_ky AS enrollment_id,
               k.ten_khoa_hoc AS course_name, hp.so_tien_phai_dong AS amount_due,
               hp.giam_gia AS discount, hp.so_tien_da_dong AS amount_paid,
               hp.so_tien_phai_dong - hp.giam_gia - hp.so_tien_da_dong AS balance,
               hp.trang_thai AS status, pt.ma_phieu AS receipt_id, pt.loai AS receipt_type,
               pt.so_tien AS receipt_amount, pt.hinh_thuc AS receipt_method,
               pt.ngay_thu AS receipt_date, yt.ma_yeu_cau AS active_payment_attempt_id
        FROM dbo.DangKy AS d
        INNER JOIN dbo.HocPhi AS hp ON hp.ma_dang_ky = d.ma_dang_ky AND hp.ma_co_so = d.ma_co_so
        INNER JOIN dbo.LopHoc AS l ON l.ma_lop = d.ma_lop AND l.ma_co_so = d.ma_co_so
        INNER JOIN dbo.KhoaHoc AS k ON k.ma_khoa_hoc = l.ma_khoa_hoc
        LEFT JOIN dbo.PhieuThu AS pt ON pt.ma_hoc_phi = hp.ma_hoc_phi AND pt.ma_co_so = hp.ma_co_so
        LEFT JOIN dbo.YeuCauThanhToan AS yt
          ON yt.ma_hoc_phi = hp.ma_hoc_phi AND yt.ma_co_so = hp.ma_co_so
         AND yt.trang_thai = 'cho_thanh_toan' AND yt.het_han_utc > SYSUTCDATETIME()
        WHERE d.ma_hoc_vien = %s AND d.ma_co_so = %s
        ORDER BY hp.ma_hoc_phi, pt.ngay_thu, pt.ma_phieu
        """,
        [user.profile_id, user.site_code],
    )
    tuition: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = tuition.setdefault(
            str(row["tuition_id"]),
            {
                "tuition_id": str(row["tuition_id"]), "enrollment_id": str(row["enrollment_id"]),
                "course_name": str(row["course_name"]), "amount_due": row["amount_due"],
                "discount": row["discount"], "amount_paid": row["amount_paid"],
                "balance": row["balance"], "status": str(row["status"]), "receipts": [],
                "active_payment": (
                    {"attempt_id": str(row["active_payment_attempt_id"])}
                    if row["active_payment_attempt_id"] is not None else None
                ),
            },
        )
        if row["receipt_id"] is not None:
            item["receipts"].append(
                {
                    "receipt_id": str(row["receipt_id"]), "type": str(row["receipt_type"]),
                    "amount": row["receipt_amount"], "method": str(row["receipt_method"]),
                    "paid_at": _local_datetime(row["receipt_date"]),
                }
            )
    results = list(tuition.values())
    if results:
        tuition_ids = [item["tuition_id"] for item in results]
        placeholders = ", ".join(["%s"] * len(tuition_ids))
        installment_rows = _student_rows(
            user,
            f"""
            SELECT ma_dot_hoc_phi AS installment_id, ma_hoc_phi AS tuition_id,
                   so_thu_tu AS sequence, ngay_den_han AS due_date,
                   so_tien_phai_dong AS amount_due, so_tien_da_dong AS amount_paid,
                   so_tien_phai_dong - so_tien_da_dong AS balance,
                   trang_thai AS status
            FROM dbo.DotHocPhi
            WHERE ma_co_so = %s AND ma_hoc_phi IN ({placeholders})
            ORDER BY ma_hoc_phi, so_thu_tu
            """,
            [user.site_code, *tuition_ids],
        )
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        by_tuition = {item["tuition_id"]: [] for item in results}
        for row in installment_rows:
            item = {
                "installment_id": str(row["installment_id"]),
                "sequence": int(row["sequence"]),
                "due_date": row["due_date"],
                "amount_due": row["amount_due"],
                "amount_paid": row["amount_paid"],
                "balance": row["balance"],
                "status": str(row["status"]),
            }
            if item["balance"] > 0 and item["due_date"] < today:
                item["status"] = "qua_han"
            by_tuition[str(row["tuition_id"])].append(item)
        for item in results:
            item["installments"] = by_tuition[item["tuition_id"]]
    return {"site_code": user.site_code, "count": len(results), "results": results}


@_translate_infrastructure_errors
def get_student_grades(user):
    rows = _student_rows(
        user,
        """
        SELECT TOP (200) d.ma_diem AS grade_id, d.ma_dang_ky AS enrollment_id,
               l.ten_lop AS class_name, k.ten_khoa_hoc AS course_name,
               d.loai_diem AS grade_type, d.diem_so AS score, d.ngay_nhap AS entered_at
        FROM dbo.DangKy AS r
        INNER JOIN dbo.Diem AS d ON d.ma_dang_ky = r.ma_dang_ky AND d.ma_co_so = r.ma_co_so
        INNER JOIN dbo.LopHoc AS l ON l.ma_lop = r.ma_lop AND l.ma_co_so = r.ma_co_so
        INNER JOIN dbo.KhoaHoc AS k ON k.ma_khoa_hoc = l.ma_khoa_hoc
        WHERE r.ma_hoc_vien = %s AND r.ma_co_so = %s
        ORDER BY d.ngay_nhap DESC, d.ma_diem DESC
        """,
        [user.profile_id, user.site_code],
    )
    for row in rows:
        row["entered_at"] = _local_datetime(row["entered_at"])
    return {"site_code": user.site_code, "count": len(rows), "results": rows}
