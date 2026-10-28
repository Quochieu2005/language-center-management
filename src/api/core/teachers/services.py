"""Site-scoped teacher CRUD with retryable distributed account lifecycle."""

import json
import uuid
from dataclasses import dataclass
from functools import wraps
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, IntegrityError, connections, transaction

from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    _acquire_named_lock,
    _digest,
    _next_sequence_number,
    _replicated_account,
    _replicated_account_by_id,
    active_site_codes,
    auth_session_alias,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.slug_utils import make_slug
from core.notifications.publisher import publish_notification


class TeacherInfrastructureUnavailable(Exception):
    """A required site, coordinator table, or account replica is unavailable."""


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
    status: str = "vo_hieu"
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


def _load_job(job_id: str):
    alias = auth_session_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT ma_giao_dich, hanh_dong, ma_tai_khoan, ma_giao_vien, ma_co_so,
                   ma_nguoi_thuc_hien, phien_ban_ban_dau, site_codes_json,
                   du_lieu_json, trang_thai
            FROM dbo.GiaoDichQuanLyGiaoVien
            WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
            """,
            [job_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise TeacherInfrastructureUnavailable
    return tuple(row)


def _load_job_for_account(account_id: str, action: str):
    alias = auth_session_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT ma_giao_dich, hanh_dong, ma_tai_khoan, ma_giao_vien, ma_co_so,
                   ma_nguoi_thuc_hien, phien_ban_ban_dau, site_codes_json,
                   du_lieu_json, trang_thai
            FROM dbo.GiaoDichQuanLyGiaoVien
            WHERE ma_tai_khoan = %s AND hanh_dong = %s
            """,
            [account_id, action],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise TeacherInfrastructureUnavailable
    return tuple(rows[0]) if rows else None


def _load_pending_create_by_email(email: str):
    alias = auth_session_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT ma_giao_dich, du_lieu_json, ma_co_so
            FROM dbo.GiaoDichQuanLyGiaoVien
            WHERE hanh_dong = 'tao' AND trang_thai = 'dang_xu_ly'
              AND JSON_VALUE(du_lieu_json, '$.email') = %s
            """,
            [email],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise TeacherInfrastructureUnavailable
    return tuple(rows[0]) if rows else None


def _update_job_sites(job_id: str, sites: tuple[str, ...]) -> None:
    alias = auth_session_alias()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                UPDATE dbo.GiaoDichQuanLyGiaoVien
                SET site_codes_json = %s, cap_nhat_luc_utc = SYSUTCDATETIME()
                WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                  AND trang_thai = 'dang_xu_ly'
                """,
                [json.dumps(sites), job_id],
            )


def _load_coordinator_account(account_id: str):
    alias = auth_session_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau,
                   vai_tro, ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban
            FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s
            """,
            [account_id],
        )
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise TeacherInfrastructureUnavailable
    return tuple(rows[0])


def _append_sync_event(cursor, site_code: str, account_id: str, action: str) -> None:
    cursor.execute(
        """
        SELECT COUNT_BIG(*) FROM dbo.NhatKyDongBo
        WHERE bang = 'TaiKhoan' AND ma_ban_ghi = %s AND site_dich = %s
          AND hanh_dong = %s AND trang_thai = 'thanh_cong'
        """,
        [account_id, site_code, action],
    )
    if int(cursor.fetchone()[0]):
        return
    event_id = f"{site_code}-DB-{_next_sequence_number(site_code, 'Seq_DB'):06d}"
    cursor.execute(
        """
        INSERT INTO dbo.NhatKyDongBo
            (ma_dong_bo, bang, ma_ban_ghi, hanh_dong, site_dich, trang_thai)
        VALUES (%s, 'TaiKhoan', %s, %s, %s, 'thanh_cong')
        """,
        [event_id, account_id, action, site_code],
    )


def _append_lifecycle_sync_event(cursor, site_code: str, account_id: str, job_id: str) -> None:
    event_id = f"{site_code}-DB-{uuid.uuid5(uuid.NAMESPACE_URL, f'{job_id}:{site_code}').hex[:10]}"
    cursor.execute(
        """
        SELECT bang, ma_ban_ghi, hanh_dong, site_dich, trang_thai
        FROM dbo.NhatKyDongBo WHERE ma_dong_bo = %s
        """,
        [event_id],
    )
    event = cursor.fetchone()
    expected = ("TaiKhoan", account_id, "sua", site_code, "thanh_cong")
    if event is not None:
        actual = (str(event[0]), str(event[1]), str(event[2]), str(event[3]), str(event[4]))
        if actual != expected:
            raise TeacherInfrastructureUnavailable
        return
    cursor.execute(
        """
        INSERT INTO dbo.NhatKyDongBo
            (ma_dong_bo, bang, ma_ban_ghi, hanh_dong, site_dich, trang_thai)
        VALUES (%s, 'TaiKhoan', %s, 'sua', %s, 'thanh_cong')
        """,
        [event_id, account_id, site_code],
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
        SELECT COUNT_BIG(*) FROM dbo.NhatKyHeThong
        WHERE ma_co_so = %s AND ma_tai_khoan = %s AND hanh_dong = %s
          AND bang_tac_dong = 'GiaoVien' AND ma_ban_ghi = %s AND ket_qua = 'thanh_cong'
        """,
        [site_code, actor_id, action, teacher_id],
    )
    if int(cursor.fetchone()[0]):
        return
    audit_id = f"{site_code}-NK-{_next_sequence_number(site_code, 'Seq_NK'):06d}"
    cursor.execute(
        """
        INSERT INTO dbo.NhatKyHeThong
            (ma_nhat_ky, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua)
        VALUES (%s, %s, %s, %s, 'GiaoVien', %s, %s, %s, %s, 'thanh_cong')
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
                        str(row[7]).lower(), bool(row[8]), int(row[9]),
                    )
                normalized_expected = (
                    str(account_id), str(slug), str(username), str(email), str(password_hash),
                    str(role).lower(), str(account_site).upper(), str(account_status).lower(),
                    bool(forced), int(version),
                )
                if actual is None:
                    cursor.execute(
                        """
                        INSERT INTO dbo.TaiKhoan
                            (ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro,
                             ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban)
                        VALUES (%s, %s, %s, %s, %s, 'giao_vien', %s, 'hoat_dong', 1, %s)
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


def _complete_lifecycle_job(job_id: str) -> None:
    alias = auth_session_alias()
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dbo.GiaoDichQuanLyGiaoVien
                    SET trang_thai = 'hoan_tat', cap_nhat_luc_utc = SYSUTCDATETIME(),
                        hoan_tat_luc_utc = SYSUTCDATETIME()
                    WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                      AND trang_thai = 'dang_xu_ly'
                    """,
                    [job_id],
                )
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc


def _create_result(job, payload: dict[str, Any]) -> TeacherProvisioningResult:
    site_code = _normalize_site(str(job[4]))
    username = str(payload["username"])
    return TeacherProvisioningResult(
        teacher_id=str(job[3]),
        account_id=str(job[2]),
        site_code=site_code,
        full_name=str(payload["full_name"]),
        phone=payload.get("phone"),
        email=str(payload["email"]),
        username=username,
        slug=make_slug(f"giao-vien-{site_code}-{username}", max_length=120),
        specialty=str(payload["specialty"]),
    )


def _resume_teacher_creation(job_id: str, remote_ip: str) -> TeacherProvisioningResult:
    job = _load_job(job_id)
    if str(job[1]).lower() != "tao":
        raise TeacherConflict
    payload = json.loads(str(job[8]))
    if str(job[9]).lower() == "hoan_tat":
        return _create_result(job, payload)
    sites = active_site_codes()
    target_site = _normalize_site(str(job[4]))
    _ensure_site(target_site, sites)
    _update_job_sites(job_id, sites)
    account = _load_coordinator_account(str(job[2]))
    if str(account[5]).lower() != "giao_vien" or _normalize_site(account[6]) != target_site:
        raise TeacherConflict
    for code in sites:
        _ensure_teacher_account_replica(code, account)
        if code == target_site:
            _ensure_teacher_profile(code, payload, remote_ip)
    _complete_lifecycle_job(job_id)
    return _create_result(_load_job(job_id), payload)


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
    normalized_username = (
        username or make_slug(normalized_email.partition("@")[0], max_length=100)
    ).strip().lower()
    if not normalized_email or not full_name.strip() or not specialty.strip() or not remote_ip:
        raise ValueError("Thiếu thông tin giáo viên.")
    sites = active_site_codes()
    _ensure_site(target_site, sites)
    coordinator_alias = auth_session_alias()
    email_lock = f"qlttnn-teacher-email:{_digest('teacher-email', normalized_email)}"
    username_lock = f"qlttnn-teacher-username:{_digest('teacher-username', normalized_username)}"
    normalized_phone = phone.strip() if phone else None
    payload = {
        "full_name": full_name.strip(),
        "email": normalized_email,
        "username": normalized_username,
        "phone": normalized_phone,
        "specialty": specialty.strip(),
        "site_code": target_site,
        "actor_id": actor_id,
    }
    job_id = None
    try:
        with transaction.atomic(using=coordinator_alias):
            with connections[coordinator_alias].cursor() as cursor:
                for resource in sorted((email_lock, username_lock)):
                    _acquire_named_lock(cursor, resource)
                pending = _load_pending_create_by_email(normalized_email)
                if pending is not None:
                    pending_payload = json.loads(str(pending[1]))
                    if (
                        _normalize_site(str(pending[2])) != target_site
                        or any(pending_payload.get(key) != payload.get(key) for key in payload)
                    ):
                        raise TeacherConflict
                    job_id = str(pending[0])
                else:
                    if _replicated_account(normalized_email, sites) is not None:
                        raise TeacherConflict
                    if _replicated_account(normalized_username, sites) is not None:
                        raise TeacherConflict
                    account_id = _next_teacher_account_id(target_site, sites)
                    teacher_id = _next_teacher_profile_id(target_site)
                    payload["teacher_id"] = teacher_id
                    slug = make_slug(f"giao-vien-{target_site}-{normalized_username}", max_length=120)
                    password_hash = make_password(temporary_password)
                    job_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO dbo.TaiKhoan
                            (ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro,
                             ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban)
                        VALUES (%s, %s, %s, %s, %s, 'giao_vien', %s, 'hoat_dong', 1, 1)
                        """,
                        [account_id, slug, normalized_username, normalized_email,
                         password_hash, target_site],
                    )
                    cursor.execute(
                        """
                        INSERT INTO dbo.GiaoDichQuanLyGiaoVien
                            (ma_giao_dich, hanh_dong, ma_tai_khoan, ma_giao_vien,
                             ma_co_so, ma_nguoi_thuc_hien, phien_ban_ban_dau,
                             site_codes_json, du_lieu_json, trang_thai)
                        VALUES (CONVERT(uniqueidentifier, %s), 'tao', %s, %s, %s, %s,
                                1, %s, %s, 'dang_xu_ly')
                        """,
                        [job_id, account_id, teacher_id, target_site, actor_id,
                         json.dumps(sites), json.dumps(payload, ensure_ascii=False)],
                    )
    except (TeacherConflict, TeacherSiteUnavailable, TeacherInfrastructureUnavailable):
        raise
    except IntegrityError as exc:
        raise TeacherConflict from exc
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError, AuthInfrastructureUnavailable) as exc:
        raise TeacherInfrastructureUnavailable from exc
    return _resume_teacher_creation(str(job_id), remote_ip)


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
        "account_status": {
            "hoat_dong": "active",
            "vo_hieu": "inactive",
        }.get(str(row[10]).lower()) if len(row) > 10 and row[10] is not None else None,
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
        INSERT INTO dbo.NhatKyHeThong
            (ma_nhat_ky, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua)
        VALUES (%s, %s, %s, 'sua_giao_vien', 'GiaoVien', %s, %s, %s, %s, 'thanh_cong')
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


def _apply_teacher_deactivation_site(job, site_code: str, remote_ip: str) -> None:
    job_id, _action, account_id, teacher_id, target_site, actor_id, initial_version, _sites, _data, _state = job
    alias = get_site_database_alias(site_code)
    target_site = _normalize_site(target_site)
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT vai_tro, ma_co_so, trang_thai, phien_ban
                    FROM dbo.TaiKhoan WITH (UPDLOCK, ROWLOCK)
                    WHERE ma_tai_khoan = %s
                    """,
                    [account_id],
                )
                account = cursor.fetchone()
                if account is None:
                    raise TeacherInfrastructureUnavailable
                role, account_site, account_status, version = (
                    str(account[0]).lower(), _normalize_site(account[1]) if account[1] else None,
                    str(account[2]).lower(), int(account[3]),
                )
                if role != "giao_vien" or account_site != target_site:
                    raise TeacherConflict
                account_changed = False
                if account_status == "hoat_dong" and version == int(initial_version):
                    cursor.execute(
                        """
                        UPDATE dbo.TaiKhoan
                        SET trang_thai = 'vo_hieu', phien_ban = phien_ban + 1,
                            cap_nhat_luc = SYSUTCDATETIME()
                        WHERE ma_tai_khoan = %s AND vai_tro = 'giao_vien'
                          AND ma_co_so = %s AND trang_thai = 'hoat_dong' AND phien_ban = %s
                        """,
                        [account_id, target_site, initial_version],
                    )
                    if cursor.rowcount != 1:
                        raise TeacherConflict
                    account_changed = True
                elif not (
                    account_status == "vo_hieu"
                    and version in {int(initial_version), int(initial_version) + 1}
                ):
                    raise TeacherConflict
                if account_changed:
                    _append_lifecycle_sync_event(cursor, site_code, account_id, str(job_id))
                if site_code == target_site:
                    cursor.execute(
                        """
                        SELECT TOP (2) trang_thai FROM dbo.GiaoVien WITH (UPDLOCK, ROWLOCK)
                        WHERE ma_giao_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
                        """,
                        [teacher_id, target_site, account_id],
                    )
                    profiles = cursor.fetchall()
                    if len(profiles) != 1:
                        raise TeacherConflict
                    old_status = str(profiles[0][0]).lower()
                    if old_status != "nghi_viec":
                        cursor.execute(
                            """
                            UPDATE dbo.GiaoVien SET trang_thai = 'nghi_viec'
                            WHERE ma_giao_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
                              AND trang_thai IN ('dang_day', 'tam_nghi')
                            """,
                            [teacher_id, target_site, account_id],
                        )
                        if cursor.rowcount != 1:
                            raise TeacherConflict
                    _append_audit(
                        cursor, target_site, actor_id, "xoa_giao_vien", teacher_id, remote_ip,
                        before={"status": old_status}, after={"status": "nghi_viec"},
                    )
                    publish_notification(
                        cursor,
                        site_code=target_site,
                        event_key=f"teacher-deactivated:{account_id}",
                        category="teacher",
                        severity="warning",
                        title="Giáo viên đã nghỉ việc",
                        message=f"Tài khoản giáo viên tại cơ sở {target_site} đã được vô hiệu hóa.",
                        target_path=f"/admin/teachers?site_code={target_site}",
                    )
    except (TeacherInfrastructureUnavailable, TeacherConflict):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc


def _complete_teacher_deactivation(job_id: str, account_id: str) -> None:
    alias = auth_session_alias()
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dbo.PhienDangNhap
                    SET thu_hoi_luc_utc = COALESCE(thu_hoi_luc_utc, SYSUTCDATETIME())
                    WHERE ma_tai_khoan = %s AND thu_hoi_luc_utc IS NULL
                    """,
                    [account_id],
                )
                cursor.execute(
                    """
                    UPDATE dbo.GiaoDichQuanLyGiaoVien
                    SET trang_thai = 'hoan_tat', cap_nhat_luc_utc = SYSUTCDATETIME(),
                        hoan_tat_luc_utc = SYSUTCDATETIME()
                    WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)
                      AND hanh_dong = 'vo_hieu_hoa' AND trang_thai = 'dang_xu_ly'
                    """,
                    [job_id],
                )
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc


def _resume_teacher_deactivation(job, remote_ip: str) -> TeacherDeactivationResult:
    job_id, action, account_id, teacher_id, site_code, _actor, _version, _sites, _data, state = job
    if str(action).lower() != "vo_hieu_hoa":
        raise TeacherConflict
    if str(state).lower() == "hoan_tat":
        return TeacherDeactivationResult(str(teacher_id), str(account_id), _normalize_site(site_code))
    sites = active_site_codes()
    _ensure_site(_normalize_site(site_code), sites)
    _update_job_sites(str(job_id), sites)
    for code in sites:
        _apply_teacher_deactivation_site(job, code, remote_ip)
    _complete_teacher_deactivation(str(job_id), str(account_id))
    return TeacherDeactivationResult(str(teacher_id), str(account_id), _normalize_site(site_code))


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

    existing_job = _load_job_for_account(account_id, "vo_hieu_hoa")
    if existing_job is not None:
        return _resume_teacher_deactivation(existing_job, remote_ip)

    sites = active_site_codes()
    _ensure_site(site, sites)
    try:
        account = _replicated_account_by_id(account_id, sites)
        if account is None or str(account[5]).lower() != "giao_vien" or _normalize_site(account[6]) != site:
            raise TeacherNotFound
        if str(account[7]).lower() not in ("hoat_dong", "vo_hieu") or str(profile[2]).lower() not in ("dang_day", "tam_nghi"):
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

    coordinator_alias = auth_session_alias()
    job_id = str(uuid.uuid4())
    try:
        with transaction.atomic(using=coordinator_alias):
            with connections[coordinator_alias].cursor() as cursor:
                _acquire_named_lock(cursor, f"qlttnn-teacher-deactivate:{account_id}")
                cursor.execute(
                    """
                    SELECT ma_giao_dich FROM dbo.GiaoDichQuanLyGiaoVien WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_tai_khoan = %s AND hanh_dong = 'vo_hieu_hoa'
                    """,
                    [account_id],
                )
                prior = cursor.fetchone()
                if prior is not None:
                    job_id = str(prior[0])
                else:
                    cursor.execute(
                        """
                        INSERT INTO dbo.GiaoDichQuanLyGiaoVien
                            (ma_giao_dich, hanh_dong, ma_tai_khoan, ma_giao_vien,
                             ma_co_so, ma_nguoi_thuc_hien, phien_ban_ban_dau,
                             site_codes_json, du_lieu_json, trang_thai)
                        VALUES (CONVERT(uniqueidentifier, %s), 'vo_hieu_hoa', %s, %s,
                                %s, %s, %s, %s, %s, 'dang_xu_ly')
                        """,
                        [job_id, account_id, teacher_id, site, actor_id, int(account[8]),
                         json.dumps(sites), json.dumps({"teacher_id": teacher_id})],
                    )
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise TeacherInfrastructureUnavailable from exc
    return _resume_teacher_deactivation(_load_job(job_id), remote_ip)
