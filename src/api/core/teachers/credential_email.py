"""One-time delivery of a teacher's configured initial credentials."""

from datetime import datetime, timezone
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import DatabaseError, connections, transaction

from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    _acquire_named_lock,
    active_site_codes,
    logger,
)
from core.auth.account_state import account_status_bit
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias

EMAIL_SENDING = "teacher_credential_email_sending"
EMAIL_SENT = "teacher_credential_email_sent"
EMAIL_FAILED = "teacher_credential_email_failed"
EMAIL_UNKNOWN = "teacher_credential_email_unknown"
EMAIL_CHANGED = "teacher_credential_email_changed"
EMAIL_ACTIONS = (EMAIL_SENDING, EMAIL_SENT, EMAIL_FAILED, EMAIL_UNKNOWN, EMAIL_CHANGED)


class TeacherCredentialEmailError(Exception):
    pass


class TeacherCredentialEmailNotFound(TeacherCredentialEmailError):
    pass


class TeacherCredentialEmailConflict(TeacherCredentialEmailError):
    pass


class TeacherCredentialEmailDeliveryFailed(TeacherCredentialEmailError):
    pass


class TeacherCredentialEmailUncertain(TeacherCredentialEmailError):
    pass


def credential_email_status(action: str | None) -> str:
    return {
        None: "ready",
        EMAIL_SENDING: "processing",
        EMAIL_SENT: "sent",
        EMAIL_FAILED: "failed",
        EMAIL_UNKNOWN: "unknown",
        EMAIL_CHANGED: "changed",
    }.get(action, "unknown")


def _record(cursor, *, site_code: str, account_id: str, action: str, remote_ip: str, result=None) -> None:
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong,
             bang_tac_dong, ma_ban_ghi, ip, ket_qua)
        VALUES (%s, 'system', %s, %s, %s, 'TaiKhoan', %s, %s, %s)
        """,
        [f"{site_code}-EM-{datetime.now(timezone.utc):%Y%m%d%H%M%S%f}-{uuid.uuid4().hex[:8]}",
         site_code, account_id, action, account_id, remote_ip[:45] or None, result],
    )


def _record_after_delivery(site_code: str, account_id: str, action: str, remote_ip: str, result=None) -> None:
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _record(cursor, site_code=site_code, account_id=account_id, action=action,
                    remote_ip=remote_ip, result=result)


def send_teacher_credentials(*, slug: str, site_code: str, remote_ip: str) -> dict[str, str]:
    password = str(getattr(settings, "TEACHER_INITIAL_PASSWORD", "")).strip()
    if (not password or len(password) > 128 or "console.EmailBackend" in settings.EMAIL_BACKEND
            or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or not settings.DEFAULT_FROM_EMAIL):
        raise AuthInfrastructureUnavailable

    site = str(site_code or "").strip().upper()
    if site not in active_site_codes():
        raise AuthInfrastructureUnavailable
    alias = get_site_database_alias(site)
    changed = False
    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                _acquire_named_lock(cursor, f"qlttnn-teacher-credential-email:{site}:{slug}")
                cursor.execute(
                    """
                    SELECT TOP (2) t.ma_tai_khoan, t.email, t.ten_dang_nhap, t.mat_khau,
                                   t.vai_tro, t.ma_co_so, t.trang_thai, g.trang_thai, g.ma_co_so
                    FROM dbo.GiaoVien AS g WITH (UPDLOCK, HOLDLOCK)
                    INNER JOIN dbo.TaiKhoan AS t WITH (UPDLOCK, HOLDLOCK)
                        ON t.ma_tai_khoan = g.ma_tai_khoan
                    WHERE t.slug = %s AND t.vai_tro = 'giao_vien'
                      AND t.ma_co_so = %s AND g.ma_co_so = %s
                    """,
                    [slug, site, site],
                )
                rows = cursor.fetchall()
                if not rows:
                    raise TeacherCredentialEmailNotFound
                if len(rows) != 1:
                    raise TeacherCredentialEmailConflict
                account_id, email, username, password_hash, role, account_site, account_status, teacher_status, profile_site = rows[0]
                if (str(role).lower() != "giao_vien" or str(account_site).upper() != site
                        or str(profile_site).upper() != site or not account_status_bit(account_status)
                        or str(teacher_status).lower() != "dang_day" or not email or not username):
                    raise TeacherCredentialEmailConflict

                cursor.execute(
                    """
                    SELECT TOP (1) hanh_dong
                    FROM dbo.Logs WITH (UPDLOCK, HOLDLOCK)
                    WHERE loai_log = 'system' AND ma_co_so = %s AND ma_tai_khoan = %s
                      AND bang_tac_dong = 'TaiKhoan' AND ma_ban_ghi = %s
                      AND hanh_dong IN (%s, %s, %s, %s, %s)
                    ORDER BY thoi_diem_utc DESC, ma_log DESC
                    """,
                    [site, account_id, account_id, *EMAIL_ACTIONS],
                )
                latest = cursor.fetchone()
                latest_action = str(latest[0]) if latest else None
                if latest_action not in (None, EMAIL_FAILED):
                    raise TeacherCredentialEmailConflict
                if not check_password(password, str(password_hash)):
                    _record(cursor, site_code=site, account_id=str(account_id), action=EMAIL_CHANGED,
                            remote_ip=remote_ip, result="that_bai")
                    changed = True
                else:
                    _record(cursor, site_code=site, account_id=str(account_id), action=EMAIL_SENDING,
                            remote_ip=remote_ip)
    except (TeacherCredentialEmailError, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

    if changed:
        raise TeacherCredentialEmailConflict
    try:
        accepted = send_mail(
            subject="Thông tin tài khoản giáo viên - Trung tâm Ngoại ngữ",
            message=(
                "Tài khoản giáo viên của bạn đã được cấp.\n"
                f"Email đăng nhập: {email}\nMật khẩu: {password}\n\n"
                "Bạn có thể đổi mật khẩu sau khi đăng nhập. Không chia sẻ thông tin này với người khác."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[str(email)],
            fail_silently=False,
        )
    except Exception as exc:
        logger.warning("Teacher credential email outcome is unknown; error_type=%s.", type(exc).__name__)
        try:
            _record_after_delivery(site, str(account_id), EMAIL_UNKNOWN, remote_ip, "that_bai")
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as log_exc:
            raise AuthInfrastructureUnavailable from log_exc
        raise TeacherCredentialEmailUncertain from exc

    if accepted != 1:
        try:
            _record_after_delivery(site, str(account_id), EMAIL_FAILED, remote_ip, "that_bai")
        except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
            raise AuthInfrastructureUnavailable from exc
        raise TeacherCredentialEmailDeliveryFailed
    try:
        _record_after_delivery(site, str(account_id), EMAIL_SENT, remote_ip, "thanh_cong")
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc
    return {"email": str(email), "status": "sent"}
