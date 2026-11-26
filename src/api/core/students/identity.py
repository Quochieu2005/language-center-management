"""Technical email reservations; student business data remains at its own site."""

from functools import wraps

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.auth.service_common import (
    AuthInfrastructureUnavailable, _acquire_named_lock, _digest, active_site_codes, auth_session_alias,
)
from core.sites.connections import UnknownSiteError, get_site_connection


class StudentEmailConflict(Exception):
    pass


def reserve_email(email, site, *, bootstrap=False):
    with get_site_connection(site).cursor() as local:
        local.execute("SELECT trang_thai FROM dbo.CoSo WHERE ma_co_so = %s", [site])
        state = local.fetchone()
        if state is None or str(state[0]) != "hoat_dong":
            raise StudentEmailConflict("Cơ sở không hoạt động.")
    key = _digest("student-email", str(email).strip().casefold())
    with transaction.atomic(using=auth_session_alias()):
        with connections[auth_session_alias()].cursor() as cursor:
            if not bootstrap:
                cursor.execute("SELECT san_sang FROM dbo.TrangThaiKhoEmail WHERE id = 1")
                ready = cursor.fetchone()
                if not ready or not ready[0]:
                    raise AuthInfrastructureUnavailable
            _acquire_named_lock(cursor, f"qlttnn-student-email:{key}")
            cursor.execute(
                "SELECT ma_co_so, ma_hoc_vien FROM dbo.DatChoEmailHocVien WITH (UPDLOCK, HOLDLOCK) "
                "WHERE email_bam = %s", [key],
            )
            existing = cursor.fetchone()
            if existing is not None and str(existing[0]) != site:
                # A transferred profile retains its ID; move only after verifying the local current row.
                with get_site_connection(site).cursor() as local:
                    local.execute(
                        "SELECT TOP (2) ma_hoc_vien FROM dbo.HocVien WHERE ma_hoc_vien = %s "
                        "AND LOWER(LTRIM(RTRIM(email))) = %s AND trang_thai = 'dang_hoc'",
                        [existing[1], str(email).strip().casefold()],
                    )
                    rows = local.fetchall()
                if len(rows) != 1:
                    raise StudentEmailConflict("Thông tin này đã được giữ chỗ ở cơ sở khác; hãy liên hệ trung tâm.")
                cursor.execute("UPDATE dbo.DatChoEmailHocVien SET ma_co_so = %s WHERE email_bam = %s", [site, key])
            elif existing is None:
                cursor.execute(
                    "INSERT dbo.DatChoEmailHocVien(email_bam, ma_co_so) VALUES (%s, %s)", [key, site],
                )
    return key


def reserve_student_email(conflict_exception):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            email = kwargs.get("email") or kwargs.get("fields", {}).get("email")
            site = str(kwargs["site_code"]).strip().upper()
            if not email:
                return function(*args, **kwargs)
            try:
                # Commit the reservation first. An ambiguous remote commit must never free the email.
                key = reserve_email(email, site)
            except StudentEmailConflict as exc:
                raise conflict_exception(str(exc)) from exc
            result = function(*args, **kwargs)
            with get_site_connection(site).cursor() as cursor:
                cursor.execute(
                    "SELECT TOP (2) ma_hoc_vien FROM dbo.HocVien WHERE LOWER(LTRIM(RTRIM(email))) = %s "
                    "AND trang_thai IN ('dang_hoc', 'bao_luu')", [str(email).strip().casefold()],
                )
                rows = cursor.fetchall()
            if len(rows) == 1:
                with connections[auth_session_alias()].cursor() as cursor:
                    cursor.execute(
                        "UPDATE dbo.DatChoEmailHocVien SET ma_hoc_vien = %s "
                        "WHERE email_bam = %s AND ma_co_so = %s", [rows[0][0], key, site],
                    )
            return result
        return wrapped
    return decorate


def seed_student_emails(allow_missing_sites: bool = False):
    """Bootstrap before cutover while all sites are readable; never infer missing data.

    ``allow_missing_sites`` is an explicit operator opt-in: unreachable sites are skipped, so an email
    held only by a skipped site can later be registered again. Returns ``(reserved, skipped_sites)``.
    """
    rows = []
    skipped = []
    for site in active_site_codes():
        try:
            with get_site_connection(site).cursor() as cursor:
                cursor.execute(
                    "SELECT ma_hoc_vien, email FROM dbo.HocVien WHERE email IS NOT NULL "
                    "AND trang_thai IN ('dang_hoc', 'bao_luu')",
                )
                rows.extend((site, str(student), str(email)) for student, email in cursor.fetchall() if email.strip())
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
            if not allow_missing_sites or site == settings.AUTH_SESSION_SITE_CODE:
                raise
            skipped.append(site)
    seen = {}
    for site, student, email in rows:
        key = email.strip().casefold()
        if key in seen and seen[key] != (site, student):
            raise StudentEmailConflict("Có email trùng giữa các hồ sơ; cần đối soát trước khi bật đăng ký.")
        seen[key] = (site, student)
    with transaction.atomic(using=auth_session_alias()):
        with connections[auth_session_alias()].cursor() as cursor:
            _acquire_named_lock(cursor, "qlttnn-account-creation")
            for site, student, email in rows:
                key = reserve_email(email, site, bootstrap=True)
                cursor.execute("UPDATE dbo.DatChoEmailHocVien SET ma_hoc_vien = %s WHERE email_bam = %s", [student, key])
            cursor.execute("UPDATE dbo.TrangThaiKhoEmail SET san_sang = 1 WHERE id = 1")
    return len(rows), tuple(skipped)
