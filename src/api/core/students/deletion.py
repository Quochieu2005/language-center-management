"""Retryable, site-by-site permanent deletion of a student and linked data."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    _acquire_named_lock,
    _digest,
    _read_catalog,
    active_site_codes,
    auth_session_alias,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.students.services import (
    StudentConflict,
    StudentInfrastructureUnavailable,
    StudentNotFound,
    StudentSiteUnavailable,
    _site_code,
    _translate_infrastructure_errors,
    _verify_active_site,
)


class StudentPermissionDenied(Exception):
    """The authenticated role cannot permanently delete this student."""


class StudentDeletionPending(Exception):
    """Some site commits completed; retry the same DELETE to finish the purge."""


@dataclass(frozen=True)
class StudentDeleteResult:
    slug: str
    site_code: str
    deleted_site_count: int
    account_deleted: bool


@dataclass(frozen=True)
class _StudentTarget:
    student_id: str
    account_id: str | None
    profile_slugs: tuple[str, ...]
    identifiers: tuple[str, ...]


@dataclass(frozen=True)
class _PurgeJob:
    job_id: str
    slug: str
    student_id: str
    account_id: str | None
    requested_site: str
    actor_id: str
    actor_role: str
    teacher_id: str | None
    sites: tuple[str, ...]
    completed_sites: tuple[str, ...]
    profile_slugs: tuple[str, ...]
    identifiers: tuple[str, ...]


def _teacher_owns_all_active_enrollments(cursor, student_id: str, site_code: str, teacher_id: str) -> None:
    cursor.execute(
        """
        SELECT
            SUM(CASE WHEN l.ma_giao_vien = %s THEN 1 ELSE 0 END),
            SUM(CASE WHEN l.ma_giao_vien IS NULL OR l.ma_giao_vien <> %s THEN 1 ELSE 0 END)
        FROM dbo.DangKy AS d
        INNER JOIN dbo.LopHoc AS l
            ON l.ma_lop = d.ma_lop AND l.ma_co_so = d.ma_co_so
        WHERE d.ma_hoc_vien = %s AND d.ma_co_so = %s
          AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
        """,
        [teacher_id, teacher_id, student_id, site_code],
    )
    own_classes, other_classes = cursor.fetchone()
    if not own_classes or other_classes:
        raise StudentPermissionDenied


def _configured_sites_for_purge() -> tuple[str, ...]:
    """Validate and return every configured site, including closed sites with retained data."""
    active = active_site_codes()
    configured = tuple(sorted(_site_code(code) for code in settings.SITE_DATABASE_ALIASES))
    registry_site = _site_code(getattr(settings, "AUTH_SESSION_SITE_CODE", ""))
    if not configured or not registry_site or not set(active).issubset(configured):
        raise StudentInfrastructureUnavailable

    try:
        catalog = _read_catalog(registry_site)
        catalog_codes = {code for code, _state in catalog}
        if catalog_codes != set(configured):
            raise StudentInfrastructureUnavailable
        for code in configured:
            if _read_catalog(code) != catalog:
                raise StudentInfrastructureUnavailable
    except StudentInfrastructureUnavailable:
        raise
    except (AuthInfrastructureUnavailable, DatabaseError, KeyError, ImproperlyConfigured, UnknownSiteError) as exc:
        raise StudentInfrastructureUnavailable from exc
    return configured


def _find_profile(site_code: str, *, slug: str | None = None, student_id: str | None = None):
    alias = get_site_database_alias(site_code)
    predicate, value = ("slug", slug) if slug is not None else ("ma_hoc_vien", student_id)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT TOP (2) ma_hoc_vien, slug, ma_co_so, ma_tai_khoan, email
            FROM dbo.HocVien
            WHERE {predicate} = %s
            """,
            [value],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise StudentInfrastructureUnavailable
    if not rows:
        return None
    row = rows[0]
    if _site_code(row[2]) != site_code:
        raise StudentInfrastructureUnavailable
    return tuple(row)


def _pending_provision_account(student_id: str, site_code: str) -> str | None:
    alias = get_site_database_alias(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT TOP (2) ma_tai_khoan
            FROM dbo.HocVien
            WHERE ma_hoc_vien = %s AND ma_co_so = %s
            """,
            [student_id, site_code],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise StudentInfrastructureUnavailable
    return str(rows[0][0]) if rows else None


def _discover_target(
    *, site_code: str, slug: str, actor_role: str, teacher_id: str | None,
    sites: tuple[str, ...],
) -> _StudentTarget:
    selected_profile = _find_profile(site_code, slug=slug)
    if selected_profile is None:
        raise StudentNotFound
    student_id = str(selected_profile[0])

    if actor_role == "giao_vien":
        alias = get_site_database_alias(site_code)
        with connections[alias].cursor() as cursor:
            _teacher_owns_all_active_enrollments(cursor, student_id, site_code, str(teacher_id))

    profile_slugs: set[str] = {slug}
    identifiers: set[str] = set()
    account_ids: set[str] = set()
    for code in sites:
        profile = _find_profile(code, student_id=student_id)
        if profile is None:
            continue
        profile_slugs.add(str(profile[1]))
        if profile[3] is not None:
            account_ids.add(str(profile[3]))
        if profile[4]:
            identifiers.add(str(profile[4]).strip().casefold())

    pending_account = _pending_provision_account(student_id, site_code)
    if pending_account:
        account_ids.add(pending_account)
    if len(account_ids) > 1:
        raise StudentInfrastructureUnavailable
    account_id = next(iter(account_ids), None)

    if account_id:
        account_rows = []
        for code in sites:
            alias = get_site_database_alias(code)
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP (2) ten_dang_nhap, email, vai_tro
                    FROM dbo.TaiKhoan
                    WHERE ma_tai_khoan = %s
                    """,
                    [account_id],
                )
                rows = cursor.fetchall()
            if len(rows) > 1:
                raise StudentInfrastructureUnavailable
            if rows:
                account_rows.append(tuple(rows[0]))
        if not account_rows:
            raise StudentInfrastructureUnavailable
        if any(str(row[2]).lower() != "hoc_vien" for row in account_rows):
            raise StudentConflict
        canonical = account_rows[0]
        if any(row != canonical for row in account_rows[1:]):
            raise StudentInfrastructureUnavailable
        if canonical[0]:
            identifiers.add(str(canonical[0]).strip().casefold())
        if canonical[1]:
            identifiers.add(str(canonical[1]).strip().casefold())

    return _StudentTarget(
        student_id=student_id,
        account_id=account_id,
        profile_slugs=tuple(sorted(profile_slugs)),
        identifiers=tuple(sorted(item for item in identifiers if item)),
    )


def _job_from_row(row) -> _PurgeJob:
    return _PurgeJob(
        job_id=str(row[0]),
        slug=str(row[1]),
        student_id=str(row[2]),
        account_id=str(row[3]) if row[3] is not None else None,
        requested_site=_site_code(row[4]),
        actor_id=str(row[5]),
        actor_role=str(row[6]).lower(),
        teacher_id=str(row[7]) if row[7] is not None else None,
        sites=tuple(sorted(_site_code(code) for code in json.loads(row[8]))),
        completed_sites=tuple(sorted(_site_code(code) for code in json.loads(row[9]))),
        profile_slugs=tuple(sorted(str(value) for value in json.loads(row[10]))),
        identifiers=tuple(sorted(str(value).casefold() for value in json.loads(row[11]))),
    )


_JOB_SELECT = """
    SELECT ma_giao_dich, slug_hoc_vien, ma_hoc_vien, ma_tai_khoan,
           ma_co_so_yeu_cau, ma_tai_khoan_thuc_hien, vai_tro_thuc_hien,
           ma_giao_vien_thuc_hien, site_codes_json, site_completed_json,
           profile_slugs_json, identifiers_json
    FROM dbo.GiaoDichXoaHocVien
"""


def _load_job(slug: str) -> _PurgeJob | None:
    alias = auth_session_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(_JOB_SELECT + " WHERE slug_hoc_vien = %s", [slug])
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise StudentInfrastructureUnavailable
    return _job_from_row(rows[0]) if rows else None


def _authorize_resume(job: _PurgeJob, *, site_code: str, actor_id: str, actor_role: str, teacher_id: str | None) -> None:
    same_actor = job.actor_id == actor_id and job.actor_role == actor_role and job.teacher_id == teacher_id
    supervisor_resume = actor_role == "admin_big"
    if job.requested_site != site_code or not (same_actor or supervisor_resume):
        raise StudentPermissionDenied


def _refresh_job_sites(job: _PurgeJob, configured_sites: tuple[str, ...]) -> _PurgeJob:
    if not set(job.sites).issubset(configured_sites):
        raise StudentInfrastructureUnavailable
    expanded_sites = tuple(sorted(set(job.sites).union(configured_sites)))
    if expanded_sites == job.sites:
        return job
    alias = auth_session_alias()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _acquire_named_lock(cursor, f"qlttnn-student-delete:{job.slug}")
            cursor.execute(
                "UPDATE dbo.GiaoDichXoaHocVien SET site_codes_json = %s, cap_nhat_luc_utc = SYSUTCDATETIME() "
                "WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)",
                [json.dumps(expanded_sites), job.job_id],
            )
    return _PurgeJob(**{**job.__dict__, "sites": expanded_sites})


def _reserve_job(
    *, slug: str, target: _StudentTarget, site_code: str, actor_id: str,
    actor_role: str, teacher_id: str | None, sites: tuple[str, ...],
) -> _PurgeJob:
    alias = auth_session_alias()
    job_id = str(uuid.uuid4())
    existing = None
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _acquire_named_lock(cursor, f"qlttnn-student-delete:{slug}")
            cursor.execute(_JOB_SELECT + " WITH (UPDLOCK, HOLDLOCK) WHERE slug_hoc_vien = %s", [slug])
            rows = cursor.fetchall()
            if len(rows) > 1:
                raise StudentInfrastructureUnavailable
            if rows:
                existing = _job_from_row(rows[0])
                _authorize_resume(
                    existing, site_code=site_code, actor_id=actor_id,
                    actor_role=actor_role, teacher_id=teacher_id,
                )
                if existing.student_id != target.student_id or existing.account_id != target.account_id:
                    raise StudentInfrastructureUnavailable
            else:
                cursor.execute(
                    """
                    INSERT INTO dbo.GiaoDichXoaHocVien
                        (ma_giao_dich, slug_hoc_vien, ma_hoc_vien, ma_tai_khoan,
                         ma_co_so_yeu_cau, ma_tai_khoan_thuc_hien, vai_tro_thuc_hien,
                         ma_giao_vien_thuc_hien, site_codes_json, site_completed_json,
                         profile_slugs_json, identifiers_json)
                    VALUES
                        (CONVERT(uniqueidentifier, %s), %s, %s, %s, %s, %s, %s, %s, %s, N'[]', %s, %s)
                    """,
                    [job_id, slug, target.student_id, target.account_id, site_code, actor_id,
                     actor_role, teacher_id, json.dumps(sites), json.dumps(target.profile_slugs),
                     json.dumps(target.identifiers)],
                )
    if existing is not None:
        return _refresh_job_sites(existing, sites)
    job = _load_job(slug)
    if job is None:
        raise StudentInfrastructureUnavailable
    return job


def _mark_site_completed(job: _PurgeJob, site_code: str) -> _PurgeJob:
    alias = auth_session_alias()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _acquire_named_lock(cursor, f"qlttnn-student-delete:{job.slug}")
            cursor.execute(_JOB_SELECT + " WITH (UPDLOCK, HOLDLOCK) WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)", [job.job_id])
            rows = cursor.fetchall()
            if len(rows) != 1:
                raise StudentInfrastructureUnavailable
            current = _job_from_row(rows[0])
            completed = tuple(sorted(set(current.completed_sites).union({site_code})))
            cursor.execute(
                "UPDATE dbo.GiaoDichXoaHocVien SET site_completed_json = %s, "
                "cap_nhat_luc_utc = SYSUTCDATETIME() WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)",
                [json.dumps(completed), job.job_id],
            )
    return _PurgeJob(**{**current.__dict__, "completed_sites": completed})


def _finish_job(job: _PurgeJob) -> None:
    if set(job.completed_sites) != set(job.sites):
        raise StudentDeletionPending
    alias = auth_session_alias()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _acquire_named_lock(cursor, f"qlttnn-student-delete:{job.slug}")
            cursor.execute(
                "DELETE FROM dbo.GiaoDichXoaHocVien "
                "WHERE ma_giao_dich = CONVERT(uniqueidentifier, %s)",
                [job.job_id],
            )


def _related_record_predicate() -> str:
    return """
        ma_ban_ghi IN (
            SELECT ma_hoc_vien FROM dbo.HocVien WHERE ma_hoc_vien = %s
            UNION ALL SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s
            UNION ALL SELECT ma_hoc_phi FROM dbo.HocPhi
                WHERE ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s)
            UNION ALL SELECT ma_phieu FROM dbo.PhieuThu
                WHERE ma_hoc_phi IN (SELECT ma_hoc_phi FROM dbo.HocPhi
                    WHERE ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s))
            UNION ALL SELECT ma_diem FROM dbo.Diem
                WHERE ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s)
            UNION ALL SELECT ma_diem_danh FROM dbo.DiemDanh
                WHERE ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s)
            UNION ALL SELECT ma_chuyen FROM dbo.GiaoDichChuyenCoSo WHERE ma_hoc_vien = %s
        )
    """


def _delete_append_only_events(
    cursor, *, student_id: str, profile_slugs: tuple[str, ...], account_id: str | None,
) -> None:
    account_clause = " OR ma_tai_khoan = %s" if account_id else ""
    record_ids = [student_id, *profile_slugs]
    if account_id:
        record_ids.append(account_id)
    record_placeholders = ", ".join("%s" for _ in record_ids)
    cursor.execute(
        f"""
        DELETE FROM dbo.Logs
        WHERE loai_log = 'system'
          AND (ma_ban_ghi IN ({record_placeholders})
               {account_clause}
               OR {_related_record_predicate()})
        """,
        [*record_ids, *([account_id] if account_id else []), *([student_id] * 7)],
    )
    sync_values = [student_id, *profile_slugs]
    if account_id:
        sync_values.append(account_id)
    sync_placeholders = ", ".join("%s" for _ in sync_values)
    cursor.execute(
        f"""
        DELETE FROM dbo.Logs
        WHERE loai_log = 'sync'
          AND (ma_ban_ghi IN ({sync_placeholders}) OR {_related_record_predicate()})
        """,
        [*sync_values, *([student_id] * 7)],
    )
    cursor.execute(
        """
        DELETE FROM dbo.LichSuChuyenCoSo
        WHERE ma_hoc_vien = %s OR ma_tai_khoan_thuc_hien = %s
           OR ma_chuyen IN (SELECT ma_chuyen FROM dbo.GiaoDichChuyenCoSo WHERE ma_hoc_vien = %s)
        """,
        [student_id, account_id, student_id],
    )


def _delete_account_references(cursor, account_id: str, identifiers: tuple[str, ...]) -> None:
    cursor.execute("DELETE FROM dbo.PhienDangNhap WHERE ma_tai_khoan = %s", [account_id])
    cursor.execute("DELETE FROM dbo.TokenDatLaiMatKhau WHERE ma_tai_khoan = %s", [account_id])
    cursor.execute(
        "IF OBJECT_ID(N'dbo.GiaoDichDatLaiMatKhau', N'U') IS NOT NULL "
        "DELETE FROM dbo.GiaoDichDatLaiMatKhau WHERE ma_tai_khoan = %s",
        [account_id],
    )
    for purpose, identifier in (("identity", value) for value in identifiers):
        digest = _digest(purpose, identifier)
        cursor.execute(
            "DELETE FROM dbo.Logs WHERE loai_log = 'login' AND dinh_danh_bam = %s", [digest]
        )
    for identifier in identifiers:
        digest = _digest("password-reset-identity", identifier)
        cursor.execute(
            "DELETE FROM dbo.Logs WHERE loai_log = 'password_reset' AND dinh_danh_bam = %s", [digest]
        )


def _assert_account_has_no_other_references(cursor, account_id: str) -> None:
    cursor.execute(
        """
        SELECT DISTINCT ps.name, pt.name, pc.name
        FROM sys.foreign_key_columns AS fkc
        INNER JOIN sys.tables AS pt ON pt.object_id = fkc.parent_object_id
        INNER JOIN sys.schemas AS ps ON ps.schema_id = pt.schema_id
        INNER JOIN sys.columns AS pc
            ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
        INNER JOIN sys.tables AS rt ON rt.object_id = fkc.referenced_object_id
        INNER JOIN sys.schemas AS rs ON rs.schema_id = rt.schema_id
        INNER JOIN sys.columns AS rc
            ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
        WHERE rs.name = N'dbo' AND rt.name = N'TaiKhoan' AND rc.name = N'ma_tai_khoan'
        """
    )
    for schema_name, table_name, column_name in cursor.fetchall():
        if (schema_name, table_name) in {("dbo", "GiaoVien"), ("dbo", "NhanVien")}:
            continue
        quote = lambda name: "[" + str(name).replace("]", "]]" ) + "]"
        cursor.execute(
            f"SELECT CASE WHEN EXISTS (SELECT 1 FROM {quote(schema_name)}.{quote(table_name)} "
            f"WHERE {quote(column_name)} = %s) THEN 1 ELSE 0 END",
            [account_id],
        )
        if cursor.fetchone()[0]:
            raise StudentConflict


def _delete_site_data(job: _PurgeJob, site_code: str) -> None:
    alias = get_site_database_alias(site_code)
    connection = connections[alias]
    account_id = job.account_id
    identifiers = job.identifiers
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "EXEC sys.sp_set_session_context @key=N'qlttnn_student_purge', @value=NULL"
            )
            cursor.execute(
                "EXEC sys.sp_set_session_context @key=N'qlttnn_student_purge', @value=1"
            )
        with transaction.atomic(using=alias):
            with connection.cursor() as cursor:
                if account_id:
                    cursor.execute(
                        """
                        SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.GiaoVien WHERE ma_tai_khoan = %s)
                                  OR EXISTS (SELECT 1 FROM dbo.NhanVien WHERE ma_tai_khoan = %s)
                             THEN 1 ELSE 0 END
                        """,
                        [account_id, account_id],
                    )
                    if cursor.fetchone()[0]:
                        raise StudentConflict

                    prefix = f"account-status:{account_id}:"
                    cursor.execute(
                        "DELETE FROM dbo.ThongBao WHERE LEFT(event_key, %s) = %s",
                        [len(prefix), prefix],
                    )

                _delete_append_only_events(
                    cursor, student_id=job.student_id,
                    profile_slugs=job.profile_slugs, account_id=account_id,
                )
                cursor.execute(
                    """
                    DELETE FROM dbo.GiaoDichChuyenCoSo
                    WHERE ma_hoc_vien = %s OR ma_tai_khoan_de_nghi = %s
                       OR ma_tai_khoan_quyet_dinh = %s
                    """,
                    [job.student_id, account_id, account_id],
                )
                cursor.execute(
                    """
                    DELETE FROM dbo.DiemDanh
                    WHERE ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s)
                    """,
                    [job.student_id],
                )
                cursor.execute(
                    "DELETE FROM dbo.Diem WHERE ma_dang_ky IN "
                    "(SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s)",
                    [job.student_id],
                )
                cursor.execute(
                    """
                    DELETE pt FROM dbo.PhieuThu AS pt
                    INNER JOIN dbo.HocPhi AS hp ON hp.ma_hoc_phi = pt.ma_hoc_phi
                                                  AND hp.ma_co_so = pt.ma_co_so
                    WHERE hp.ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s)
                    """,
                    [job.student_id],
                )
                cursor.execute(
                    "DELETE FROM dbo.HocPhi WHERE ma_dang_ky IN "
                    "(SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_hoc_vien = %s)",
                    [job.student_id],
                )
                cursor.execute("DELETE FROM dbo.DangKy WHERE ma_hoc_vien = %s", [job.student_id])
                cursor.execute("DELETE FROM dbo.HocVien WHERE ma_hoc_vien = %s", [job.student_id])

                if account_id:
                    _delete_account_references(cursor, account_id, identifiers)
                    _assert_account_has_no_other_references(cursor, account_id)
                    cursor.execute(
                        "DELETE FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s AND vai_tro = 'hoc_vien'",
                        [account_id],
                    )
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "EXEC sys.sp_set_session_context @key=N'qlttnn_student_purge', @value=NULL"
                )
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
            connection.close()
            raise StudentInfrastructureUnavailable


@_translate_infrastructure_errors
def delete_student(
    *, site_code: str, student_slug: str, actor_id: str, actor_role: str,
    teacher_id: str | None,
) -> StudentDeleteResult:
    """Permanently remove one student and dependent site-local data with retryable recovery."""
    site = _site_code(site_code)
    if actor_role not in {"admin_big", "admin_small", "giao_vien"} or not actor_id:
        raise StudentPermissionDenied
    if actor_role == "giao_vien" and not teacher_id:
        raise StudentPermissionDenied

    sites = _configured_sites_for_purge()
    _verify_active_site(site, active_site_codes())
    job = _load_job(student_slug)
    if job is not None:
        _authorize_resume(
            job, site_code=site, actor_id=actor_id,
            actor_role=actor_role, teacher_id=teacher_id,
        )
        job = _refresh_job_sites(job, sites)
    else:
        target = _discover_target(
            site_code=site, slug=student_slug, actor_role=actor_role,
            teacher_id=teacher_id, sites=sites,
        )
        job = _reserve_job(
            slug=student_slug, target=target, site_code=site, actor_id=actor_id,
            actor_role=actor_role, teacher_id=teacher_id, sites=sites,
        )

    try:
        for code in job.sites:
            if code in job.completed_sites:
                continue
            _delete_site_data(job, code)
            job = _mark_site_completed(job, code)
        _finish_job(job)
    except StudentConflict:
        raise
    except (StudentPermissionDenied, StudentNotFound, StudentSiteUnavailable):
        raise
    except Exception as exc:
        raise StudentDeletionPending from exc

    return StudentDeleteResult(
        slug=student_slug,
        site_code=site,
        deleted_site_count=len(job.sites),
        account_deleted=job.account_id is not None,
    )
