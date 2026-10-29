"""Site-scoped teacher profiles and replicated login accounts."""

import json
from dataclasses import dataclass
from functools import wraps
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.auth.account_state import account_is_active, account_status_bit, account_status_label
from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    _next_sequence_number,
    _replicated_account,
    _replicated_account_by_id,
    active_site_codes,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.slug_utils import make_slug
from core.notifications.publisher import publish_notification


class TeacherInfrastructureUnavailable(Exception):
    """A required site database or account replica is unavailable."""


class TeacherNotFound(Exception):
    """The teacher does not exist within the authorized site."""


class TeacherConflict(Exception):
    """An identity is duplicated or a lifecycle transition conflicts with data."""


class TeacherSiteUnavailable(Exception):
    """The requested site is not active or not part of the configured cluster."""


def _translate_infrastructure_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except TeacherInfrastructureUnavailable:
            raise
        except (
            AuthInfrastructureUnavailable,
            DatabaseError,
            ImproperlyConfigured,
            KeyError,
            UnknownSiteError,
        ) as exc:
            raise TeacherInfrastructureUnavailable from exc

    return wrapped


@dataclass(frozen=True)
class TeacherProvisioningResult:
    teacher_id: str
    account_id: str
    site_code: str
    full_name: str
    phone: str | None
    email: str
    username: str
    slug: str
    specialty: str
    status: str = "dang_day"
    must_change_password: bool = True


@dataclass(frozen=True)
class TeacherDeactivationResult:
    teacher_id: str
    account_id: str
    site_code: str
    status: str = "inactive"
    teacher_status: str = "nghi_viec"


def _normalize_site(site_code: str | None) -> str:
    return str(site_code or "").strip().upper()


def _ensure_site(site_code: str, sites: tuple[str, ...]) -> None:
    if site_code not in sites:
        raise TeacherSiteUnavailable


def _next_teacher_account_id(site_code: str, sites: tuple[str, ...]) -> str:
    for _ in range(1000):
        candidate = f"{site_code}-TK-{_next_sequence_number(site_code, 'Seq_TK'):06d}"
        exists = False
        for code in sites:
            with get_site_connection(code).cursor() as cursor:
                cursor.execute(
                    "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s) "
                    "THEN 1 ELSE 0 END",
                    [candidate],
                )
                if int(cursor.fetchone()[0]):
                    exists = True
                    break
        if not exists:
            return candidate
    raise TeacherInfrastructureUnavailable


def _next_teacher_profile_id(site_code: str) -> str:
    for _ in range(1000):
        candidate = f"{site_code}-GV-{_next_sequence_number(site_code, 'Seq_GV'):06d}"
        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.GiaoVien WHERE ma_giao_vien = %s) "
                "THEN 1 ELSE 0 END",
                [candidate],
            )
            if not int(cursor.fetchone()[0]):
                return candidate
    raise TeacherInfrastructureUnavailable


def _append_sync_event(cursor, site_code: str, account_id: str, action: str) -> None:
    cursor.execute(
        """
        SELECT COUNT_BIG(*) FROM dbo.Logs
        WHERE loai_log = 'sync' AND bang_tac_dong = 'TaiKhoan'
          AND ma_ban_ghi = %s AND site_dich = %s
          AND hanh_dong = %s AND ket_qua = 'thanh_cong'
        """,
        [account_id, site_code, action],
    )
    if int(cursor.fetchone()[0]):
        return
    event_id = f"{site_code}-DB-{_next_sequence_number(site_code, 'Seq_DB'):06d}"
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua)
        VALUES (%s, 'sync', 'TaiKhoan', %s, %s, %s, 'thanh_cong')
        """,
        [event_id, account_id, action, site_code],
    )


def _append_audit(
    cursor,
    site_code: str,
    actor_id: str,
    action: str,
    teacher_id: str,
    remote_ip: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    cursor.execute(
        """
        SELECT COUNT_BIG(*) FROM dbo.Logs
        WHERE loai_log = 'system' AND ma_co_so = %s AND ma_tai_khoan = %s AND hanh_dong = %s
          AND bang_tac_dong = 'GiaoVien' AND ma_ban_ghi = %s AND ket_qua = 'thanh_cong'
        """,
        [site_code, actor_id, action, teacher_id],
    )
    if int(cursor.fetchone()[0]):
        return
    audit_id = f"{site_code}-NK-{_next_sequence_number(site_code, 'Seq_NK'):06d}"
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua)
        VALUES (%s, 'system', %s, %s, %s, 'GiaoVien', %s, %s, %s, %s, 'thanh_cong')
        """,
        [
            audit_id,
            site_code,
            actor_id,
            action,
            teacher_id,
            json.dumps(before, ensure_ascii=False) if before is not None else None,
            json.dumps(after, ensure_ascii=False) if after is not None else None,
            remote_ip[:45],
        ],
    )


def _profile_values(payload: dict[str, Any]) -> tuple[Any, ...]:
    return (
        payload["teacher_id"], payload["site_code"], payload["account_id"],
        payload["full_name"], payload["phone"], payload["email"], payload["specialty"],
    )


def _ensure_teacher_account_replica(site_code: str, expected: tuple[Any, ...]) -> None:
    alias = get_site_database_alias(site_code)
    account_id, slug, username, email, password_hash, role, account_site, account_status, forced, version = expected
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP (2) ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                                   vai_tro, ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban
                    FROM dbo.TaiKhoan WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_tai_khoan = %s OR LOWER(email) = %s OR LOWER(ten_dang_nhap) = %s
                    """,
                    [account_id, email, username],
                )
                rows = cursor.fetchall()
                if len(rows) > 1:
                    raise TeacherConflict
                actual = None
                if rows:
                    row = rows[0]
                    actual = (
                        str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]),
                        str(row[5]).lower(), str(row[6]).upper() if row[6] else None,
                        account_status_bit(row[7]), bool(row[8]), int(row[9]),
                    )
                normalized_expected = (
                    str(account_id), str(slug), str(username), str(email), str(password_hash),
                    str(role).lower(), str(account_site).upper(), account_status_bit(account_status),
                    bool(forced), int(version),
                )
                if actual is None:
                    cursor.execute(
                        """
                        INSERT INTO dbo.TaiKhoan
                            (ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro,
                             ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban)
                        VALUES (%s, %s, %s, %s, %s, 'giao_vien', %s, 1, 1, %s)
                        """,
                        [account_id, slug, username, email, password_hash, account_site, version],
                    )
                elif actual != normalized_expected:
                    raise TeacherConflict
                _append_sync_event(cursor, site_code, account_id, "them")
    except (TeacherInfrastructureUnavailable, TeacherConflict):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc


def _ensure_teacher_profile(site_code: str, payload: dict[str, Any], remote_ip: str) -> None:
    alias = get_site_database_alias(site_code)
    expected = _profile_values(payload)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP (2) ma_giao_vien, ma_co_so, ma_tai_khoan, ho_ten,
                                   sdt, email, chuyen_mon, trang_thai
                    FROM dbo.GiaoVien WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_giao_vien = %s OR ma_tai_khoan = %s
                    """,
                    [payload["teacher_id"], payload["account_id"]],
                )
                rows = cursor.fetchall()
                if not rows:
                    cursor.execute(
                        """
                        INSERT INTO dbo.GiaoVien
                            (ma_giao_vien, ma_co_so, ma_tai_khoan, ho_ten, sdt,
                             email, chuyen_mon, trang_thai)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'dang_day')
                        """,
                        expected,
                    )
                elif len(rows) != 1:
                    raise TeacherConflict
                else:
                    row = rows[0]
                    actual = (
                        str(row[0]), str(row[1]).upper(), str(row[2]), str(row[3]),
                        row[4], row[5], str(row[6]), str(row[7]).lower(),
                    )
                    normalized_expected = (
                        str(expected[0]), str(expected[1]).upper(), str(expected[2]),
                        str(expected[3]), expected[4], expected[5], str(expected[6]), "dang_day",
                    )
                    if actual != normalized_expected:
                        raise TeacherConflict
                _append_audit(
                    cursor,
                    site_code,
                    payload["actor_id"],
                    "tao_giao_vien",
                    payload["teacher_id"],
                    remote_ip,
                    after={"site_code": site_code, "teacher_id": payload["teacher_id"]},
                )
                publish_notification(
                    cursor,
                    site_code=site_code,
                    event_key=f"teacher-created:{payload['teacher_id']}",
                    category="teacher",
                    severity="success",
                    title="Giáo viên mới được tạo",
                    message=f"Một hồ sơ giáo viên mới đã được tạo tại cơ sở {site_code}.",
                    target_path=f"/admin/teachers?site_code={site_code}",
                )
    except (TeacherInfrastructureUnavailable, TeacherConflict):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc


@_translate_infrastructure_errors
def create_teacher(
    *, full_name: str, email: str, username: str | None, phone: str | None,
    specialty: str, site_code: str, actor_id: str, remote_ip: str,
) -> TeacherProvisioningResult:
    temporary_password = str(getattr(settings, "TEACHER_INITIAL_PASSWORD", "")).strip()
    if not temporary_password:
        raise TeacherInfrastructureUnavailable
    normalized_email = email.strip().casefold()
    target_site = _normalize_site(site_code)
    normalized_username = (username or make_slug(normalized_email.partition("@")[0], max_length=100)).strip().lower()
    normalized_name = full_name.strip()
    normalized_phone = phone.strip() if phone else None
    normalized_specialty = specialty.strip()
    if not normalized_email or not normalized_name or not normalized_specialty or not remote_ip:
        raise ValueError("Thiếu thông tin giáo viên.")
    sites = active_site_codes()
    _ensure_site(target_site, sites)
    if _replicated_account(normalized_email, sites) is not None:
        raise TeacherConflict
    if _replicated_account(normalized_username, sites) is not None:
        raise TeacherConflict

    account_id = _next_teacher_account_id(target_site, sites)
    teacher_id = _next_teacher_profile_id(target_site)
    slug = make_slug(f"giao-vien-{target_site}-{normalized_username}", max_length=120)
    password_hash = make_password(temporary_password)
    account = (
        account_id, slug, normalized_username, normalized_email, password_hash,
        "giao_vien", target_site, 1, True, 1,
    )
    payload = {
        "teacher_id": teacher_id,
        "account_id": account_id,
        "site_code": target_site,
        "full_name": normalized_name,
        "phone": normalized_phone,
        "email": normalized_email,
        "specialty": normalized_specialty,
        "actor_id": actor_id,
    }
    for code in sites:
        _ensure_teacher_account_replica(code, account)
    _ensure_teacher_profile(target_site, payload, remote_ip)
    return TeacherProvisioningResult(
        teacher_id=teacher_id,
        account_id=account_id,
        site_code=target_site,
        full_name=normalized_name,
        phone=normalized_phone,
        email=normalized_email,
        username=normalized_username,
        slug=slug,
        specialty=normalized_specialty,
    )


_TEACHER_SELECT = """
    SELECT g.ma_giao_vien, g.ma_tai_khoan, g.ma_co_so, g.ho_ten, g.sdt,
           COALESCE(g.email, t.email), t.ten_dang_nhap, t.slug,
           g.chuyen_mon, g.trang_thai, t.trang_thai
    FROM dbo.GiaoVien AS g
    LEFT JOIN dbo.TaiKhoan AS t ON t.ma_tai_khoan = g.ma_tai_khoan
    WHERE g.ma_co_so = %s
"""


def _teacher_dict(row) -> dict[str, Any]:
    return {
        "teacher_id": str(row[0]),
        "account_id": str(row[1]) if row[1] is not None else None,
        "site_code": _normalize_site(row[2]),
        "full_name": str(row[3]),
        "phone": str(row[4]) if row[4] is not None else None,
        "email": str(row[5]) if row[5] is not None else None,
        "username": str(row[6]) if row[6] is not None else None,
        "slug": str(row[7]) if row[7] is not None else None,
        "specialty": str(row[8]),
        "status": str(row[9]).lower(),
        "account_status": account_status_label(row[10]) if len(row) > 10 else None,
    }


@_translate_infrastructure_errors
def list_teachers(
    *, site_code: str, status_filter: str | None = None, search: str | None = None,
    limit: int = 25, offset: int = 0,
) -> dict[str, Any]:
    site = _normalize_site(site_code)
    sites = active_site_codes()
    _ensure_site(site, sites)
    alias = get_site_database_alias(site)
    conditions = ["g.ma_co_so = %s"]
    params: list[Any] = [site]
    if status_filter:
        conditions.append("g.trang_thai = %s")
        params.append(status_filter)
    if search:
        conditions.append(
            "(g.ho_ten LIKE %s OR COALESCE(g.email, t.email) LIKE %s "
            "OR t.ten_dang_nhap LIKE %s OR g.ma_giao_vien LIKE %s OR t.slug LIKE %s)"
        )
        term = f"%{search.strip()}%"
        params.extend((term, term, term, term, term))
    where = " AND ".join(conditions)
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT COUNT_BIG(*) FROM dbo.GiaoVien AS g "
                "LEFT JOIN dbo.TaiKhoan AS t ON t.ma_tai_khoan = g.ma_tai_khoan WHERE " + where,
                params,
            )
            count = int(cursor.fetchone()[0])
            statement = _TEACHER_SELECT.replace("WHERE g.ma_co_so = %s", f"WHERE {where}")
            cursor.execute(
                statement + " ORDER BY g.ho_ten, g.ma_giao_vien OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
                [*params, offset, limit],
            )
            results = [_teacher_dict(row) for row in cursor.fetchall()]
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc
    return {"site_code": site, "count": count, "limit": limit, "offset": offset, "results": results}


@_translate_infrastructure_errors
def get_teacher(*, slug: str, site_code: str) -> dict[str, Any]:
    site = _normalize_site(site_code)
    sites = active_site_codes()
    _ensure_site(site, sites)
    alias = get_site_database_alias(site)
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(_TEACHER_SELECT + " AND t.slug = %s", [site, slug])
            row = cursor.fetchone()
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc
    if row is None:
        raise TeacherNotFound
    return _teacher_dict(row)


def _append_profile_audit(
    cursor, site_code: str, actor_id: str, teacher_id: str, remote_ip: str,
    old: dict[str, Any], new: dict[str, Any],
) -> None:
    audit_id = f"{site_code}-NK-{_next_sequence_number(site_code, 'Seq_NK'):06d}"
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua)
        VALUES (%s, 'system', %s, %s, 'sua_giao_vien', 'GiaoVien', %s, %s, %s, %s, 'thanh_cong')
        """,
        [audit_id, site_code, actor_id, teacher_id, json.dumps(old, ensure_ascii=False),
         json.dumps(new, ensure_ascii=False), remote_ip[:45]],
    )


@_translate_infrastructure_errors
def update_teacher(
    *, slug: str, site_code: str, actor_id: str, updates: dict[str, Any], remote_ip: str
) -> dict[str, Any]:
    site = _normalize_site(site_code)
    sites = active_site_codes()
    _ensure_site(site, sites)
    alias = get_site_database_alias(site)
    columns = {"full_name": "ho_ten", "phone": "sdt", "specialty": "chuyen_mon"}
    if set(updates) - set(columns) or not updates:
        raise ValueError("Trường cập nhật giáo viên không hợp lệ.")
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT g.ma_giao_vien, g.ma_tai_khoan, g.ho_ten, g.sdt,
                           g.chuyen_mon, g.trang_thai
                    FROM dbo.GiaoVien AS g WITH (UPDLOCK, ROWLOCK)
                    INNER JOIN dbo.TaiKhoan AS t WITH (UPDLOCK, ROWLOCK)
                        ON t.ma_tai_khoan = g.ma_tai_khoan
                    WHERE g.ma_co_so = %s AND t.slug = %s
                    """,
                    [site, slug],
                )
                row = cursor.fetchone()
                if row is None or not row[1]:
                    raise TeacherNotFound
                if str(row[5]).lower() == "nghi_viec":
                    raise TeacherConflict
                teacher_id = str(row[0])
                old = {
                    "full_name": str(row[2]),
                    "phone": str(row[3]) if row[3] is not None else None,
                    "specialty": str(row[4]),
                    "status": str(row[5]).lower(),
                }
                new = dict(old)
                new.update(updates)
                assignments = [f"{columns[key]} = %s" for key in updates]
                cursor.execute(
                    "UPDATE dbo.GiaoVien SET " + ", ".join(assignments)
                    + " WHERE ma_giao_vien = %s AND ma_co_so = %s",
                    [*[updates[key] for key in updates], teacher_id, site],
                )
                if cursor.rowcount != 1:
                    raise TeacherConflict
                _append_profile_audit(cursor, site, actor_id, teacher_id, remote_ip, old, new)
    except (TeacherNotFound, TeacherConflict, TeacherSiteUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc
    return get_teacher(slug=slug, site_code=site)


@_translate_infrastructure_errors
def deactivate_teacher(
    *, slug: str, site_code: str, actor_id: str, remote_ip: str
) -> TeacherDeactivationResult:
    site = _normalize_site(site_code)
    with get_site_connection(site).cursor() as cursor:
        cursor.execute(
            """
            SELECT g.ma_giao_vien, g.ma_tai_khoan, g.trang_thai
            FROM dbo.GiaoVien AS g
            INNER JOIN dbo.TaiKhoan AS t ON t.ma_tai_khoan = g.ma_tai_khoan
            WHERE g.ma_co_so = %s AND t.slug = %s
            """,
            [site, slug],
        )
        profile = cursor.fetchone()
    if profile is None or not profile[1]:
        raise TeacherNotFound
    teacher_id, account_id = str(profile[0]), str(profile[1])

    sites = active_site_codes()
    _ensure_site(site, sites)
    try:
        account = _replicated_account_by_id(account_id, sites)
        if account is None or str(account[5]).lower() != "giao_vien" or _normalize_site(account[6]) != site:
            raise TeacherNotFound
        if account_status_bit(account[7]) not in (0, 1):
            raise TeacherConflict
        if str(profile[2]).lower() == "nghi_viec" and account_status_bit(account[7]) == 0:
            return TeacherDeactivationResult(teacher_id, account_id, site)
        if str(profile[2]).lower() not in ("dang_day", "tam_nghi"):
            raise TeacherConflict
        with get_site_connection(site).cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (1) 1 FROM dbo.LopHoc
                WHERE ma_co_so = %s AND ma_giao_vien = %s
                  AND trang_thai IN ('sap_mo', 'dang_hoc')
                """,
                [site, teacher_id],
            )
            if cursor.fetchone() is not None:
                raise TeacherConflict
    except (TeacherNotFound, TeacherConflict, TeacherSiteUnavailable):
        raise
    except AuthInfrastructureUnavailable as exc:
        raise TeacherInfrastructureUnavailable from exc
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc

    old_status = account_status_bit(account[7])
    version = int(account[8])
    changed_sites: list[str] = []
    try:
        for code in (*[site_code for site_code in sites if site_code != site], site):
            alias = get_site_database_alias(code)
            with transaction.atomic(using=alias):
                with connections[alias].cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE dbo.TaiKhoan
                        SET trang_thai = 0, phien_ban = phien_ban + 1,
                            cap_nhat_luc = SYSUTCDATETIME()
                        WHERE ma_tai_khoan = %s AND vai_tro = 'giao_vien'
                          AND ma_co_so = %s AND trang_thai = 1 AND phien_ban = %s
                        """,
                        [account_id, site, version],
                    )
                    if cursor.rowcount != 1:
                        raise TeacherConflict
                    cursor.execute(
                        """
                        UPDATE dbo.PhienDangNhap
                        SET thu_hoi_luc_utc = COALESCE(thu_hoi_luc_utc, SYSUTCDATETIME())
                        WHERE ma_tai_khoan = %s AND thu_hoi_luc_utc IS NULL
                        """,
                        [account_id],
                    )
                    _append_sync_event(cursor, code, account_id, "sua")
                    if code == site:
                        cursor.execute(
                            """
                            UPDATE dbo.GiaoVien SET trang_thai = 'nghi_viec'
                            WHERE ma_giao_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
                              AND trang_thai IN ('dang_day', 'tam_nghi')
                            """,
                            [teacher_id, site, account_id],
                        )
                        if cursor.rowcount != 1:
                            raise TeacherConflict
                        _append_audit(
                            cursor, site, actor_id, "xoa_giao_vien", teacher_id, remote_ip,
                            before={"status": str(profile[2])}, after={"status": "nghi_viec"},
                        )
                        publish_notification(
                            cursor,
                            site_code=site,
                            event_key=f"teacher-deactivated:{account_id}",
                            category="teacher",
                            severity="warning",
                            title="Giáo viên đã nghỉ việc",
                            message=f"Tài khoản giáo viên tại cơ sở {site} đã được vô hiệu hóa.",
                            target_path=f"/admin/teachers?site_code={site}",
                        )
            changed_sites.append(code)
    except TeacherConflict:
        for changed_site in reversed(changed_sites):
            alias = get_site_database_alias(changed_site)
            try:
                with transaction.atomic(using=alias):
                    with connections[alias].cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE dbo.TaiKhoan
                            SET trang_thai = 1, phien_ban = phien_ban + 1,
                                cap_nhat_luc = SYSUTCDATETIME()
                            WHERE ma_tai_khoan = %s AND trang_thai = 0 AND phien_ban = %s
                            """,
                            [account_id, version + 1],
                        )
            except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
                raise TeacherInfrastructureUnavailable
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        for changed_site in reversed(changed_sites):
            alias = get_site_database_alias(changed_site)
            try:
                with transaction.atomic(using=alias):
                    with connections[alias].cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE dbo.TaiKhoan
                            SET trang_thai = 1, phien_ban = phien_ban + 1,
                                cap_nhat_luc = SYSUTCDATETIME()
                            WHERE ma_tai_khoan = %s AND trang_thai = 0 AND phien_ban = %s
                            """,
                            [account_id, version + 1],
                        )
            except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
                raise TeacherInfrastructureUnavailable from exc
        raise TeacherInfrastructureUnavailable from exc
    return TeacherDeactivationResult(teacher_id, account_id, site)
