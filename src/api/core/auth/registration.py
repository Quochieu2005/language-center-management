"""Free student accounts; enrollment and tuition are separate local operations."""

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import connections, transaction
from django.utils import timezone

from core.auth.account_replication import provisioning_sites, serialize_account_creation
from core.auth.service_common import (
    _acquire_named_lock, _next_sequence_number,
    _replicated_account, auth_session_alias,
)
from core.slug_utils import make_slug
from core.sites.connections import get_site_connection, get_site_database_alias
from core.students.identity import StudentEmailConflict, reserve_email, reserve_student_email
from core.students.services import (
    _account_slug_candidate, _ensure_account_replica, _next_student_account_id, _username_candidate,
)
from core.students.slugging import available_student_slug


class RegistrationConflict(Exception):
    pass


@dataclass(frozen=True)
class RegistrationResult:
    account_id: str
    replication_pending_sites: tuple[str, ...] = ()


@reserve_student_email(RegistrationConflict)
@serialize_account_creation
def register_student(*, site_code, full_name, email, password, remote_ip):
    sites = provisioning_sites(site_code)
    if _replicated_account(email, sites) is not None:
        raise RegistrationConflict
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _acquire_named_lock(cursor, "qlttnn-self-registration")
            cursor.execute(
                "SELECT TOP (2) ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, "
                "vai_tro, ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban "
                "FROM dbo.TaiKhoan WHERE LOWER(email) = %s", [email],
            )
            existing = cursor.fetchall()
            if existing:
                # Recover only our own partial local commit, proving knowledge of its password.
                account = tuple(existing[0])
                if (len(existing) != 1 or account[5] != "hoc_vien" or not account[7]
                        or account[8] or not check_password(password, account[4])):
                    raise RegistrationConflict
                cursor.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.HocVien WHERE ma_tai_khoan = %s "
                    "AND ma_co_so = %s AND trang_thai = 'dang_hoc'", [account[0], site_code],
                )
                if cursor.fetchone()[0] != 1:
                    raise RegistrationConflict
            else:
                cursor.execute("SELECT TOP (1) 1 FROM dbo.HocVien WHERE LOWER(LTRIM(RTRIM(email))) = %s", [email])
                if cursor.fetchone() is not None:
                    # Self-registration never claims a previously issued or guest student profile.
                    raise RegistrationConflict
                account_id = _next_student_account_id(site_code, sites)
                student_id = f"{site_code}-HV-{_next_sequence_number(site_code, 'Seq_HV'):06d}"
                slug = available_student_slug(cursor, full_name, None)
                username = _username_candidate(email, site_code, sites)
                account = (account_id, _account_slug_candidate(slug, sites), username,
                           email, make_password(password), "hoc_vien", site_code, 1, 0, 1)
                cursor.execute(
                    "INSERT dbo.TaiKhoan(ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, "
                    "vai_tro, ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", list(account),
                )
                cursor.execute(
                    "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ma_tai_khoan, "
                    "ho_ten, email, ngay_nhap_hoc, trang_thai) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'dang_hoc')",
                    [student_id, slug, site_code, site_code, account_id, full_name, email, timezone.localdate()],
                )
                cursor.execute(
                    "INSERT dbo.Logs(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, "
                    "bang_tac_dong, ma_ban_ghi, ip, ket_qua) "
                    "VALUES (CONVERT(nvarchar(120), NEWID()), 'system', %s, %s, 'tu_dang_ky', "
                    "'TaiKhoan', %s, %s, 'thanh_cong')", [site_code, account_id, account_id, remote_ip[:45]],
                )
    # Local profile/account commit first; a retry can finish the authority write after interruption.
    if alias != auth_session_alias():
        _ensure_account_replica(sites[-1], account)
    return RegistrationResult(str(account[0]))


def _user_slug(full_name, sites):
    base = make_slug(f"nguoi-dung-{full_name}", max_length=110)
    for suffix in range(0, 100):
        candidate = base if suffix == 0 else make_slug(f"{base}-{suffix}", max_length=120)
        with get_site_connection(sites[0]).cursor() as cursor:
            cursor.execute("SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.TaiKhoan WHERE slug = %s) THEN 1 ELSE 0 END", [candidate])
            if not cursor.fetchone()[0]:
                return candidate
    raise RegistrationConflict


def _user_username(email, sites):
    base = make_slug(f"nd-{email.partition('@')[0]}", max_length=80)
    for suffix in range(0, 1000):
        candidate = base if suffix == 0 else f"{base}-{suffix}"
        if _replicated_account(candidate, sites) is None:
            return candidate
    raise RegistrationConflict


@serialize_account_creation
def _create_user_account(*, full_name, email, password, remote_ip):
    authority = settings.AUTH_SESSION_SITE_CODE
    sites = (authority,)
    if _replicated_account(email, sites) is not None:
        raise RegistrationConflict
    alias = auth_session_alias()
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _acquire_named_lock(cursor, "qlttnn-self-registration")
            # Never claim an existing student profile (issued or guest) that holds this email.
            cursor.execute("SELECT TOP (1) 1 FROM dbo.HocVien WHERE LOWER(LTRIM(RTRIM(email))) = %s", [email])
            if cursor.fetchone() is not None:
                raise RegistrationConflict
            account_id = _next_student_account_id(authority, sites)
            cursor.execute(
                "INSERT dbo.TaiKhoan(ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro, ma_co_so, "
                "trang_thai, bat_buoc_doi_mat_khau, phien_ban, ho_ten) "
                "VALUES (%s,%s,%s,%s,%s,'nguoi_dung',NULL,1,0,1,%s)",
                [account_id, _user_slug(full_name, sites), _user_username(email, sites), email,
                 make_password(password), full_name],
            )
            cursor.execute(
                "INSERT dbo.Logs(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, "
                "bang_tac_dong, ma_ban_ghi, ip, ket_qua) "
                "VALUES (CONVERT(nvarchar(120), NEWID()), 'system', %s, %s, 'tu_dang_ky', "
                "'TaiKhoan', %s, %s, 'thanh_cong')", [authority, account_id, account_id, remote_ip[:45]],
            )
    return RegistrationResult(account_id)


def register_user(*, full_name, email, password, remote_ip):
    """Account only: no student profile and no site. The profile is created later when a consultant enrolls them."""
    try:
        # The email stays reserved under the authority site until a student profile exists for it.
        reserve_email(email, settings.AUTH_SESSION_SITE_CODE)
    except StudentEmailConflict as exc:
        raise RegistrationConflict from exc
    return _create_user_account(full_name=full_name, email=email, password=password, remote_ip=remote_ip)
