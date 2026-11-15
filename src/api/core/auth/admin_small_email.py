"""One-time delivery of internal staff temporary credentials."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import DatabaseError, connections, transaction

from core.auth.service_common import (
    AdminSmallCredentialEmailConflict,
    AdminSmallCredentialEmailDeliveryFailed,
    AdminSmallCredentialEmailUncertain,
    AdminSmallTargetNotFound,
    AuthInfrastructureUnavailable,
    _acquire_named_lock,
    _replicated_account_by_id,
    active_site_codes,
    logger,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias

EMAIL_READY = "admin_small_email_ready"
EMAIL_SENDING = "admin_small_email_sending"
EMAIL_SENT = "admin_small_email_sent"
EMAIL_FAILED = "admin_small_email_failed"
EMAIL_UNKNOWN = "admin_small_email_unknown"
EMAIL_CHANGED = "admin_small_email_changed"
EMPLOYEE_EMAIL_READY = "employee_credential_email_ready"
EMPLOYEE_EMAIL_SENDING = "employee_credential_email_sending"
EMPLOYEE_EMAIL_SENT = "employee_credential_email_sent"
EMPLOYEE_EMAIL_FAILED = "employee_credential_email_failed"
EMPLOYEE_EMAIL_UNKNOWN = "employee_credential_email_unknown"
EMPLOYEE_EMAIL_CHANGED = "employee_credential_email_changed"
_ADMIN_SMALL_EMAIL_ACTIONS = (EMAIL_READY, EMAIL_SENDING, EMAIL_SENT, EMAIL_FAILED, EMAIL_UNKNOWN, EMAIL_CHANGED)
_EMPLOYEE_EMAIL_ACTIONS = (
    EMPLOYEE_EMAIL_READY, EMPLOYEE_EMAIL_SENDING, EMPLOYEE_EMAIL_SENT,
    EMPLOYEE_EMAIL_FAILED, EMPLOYEE_EMAIL_UNKNOWN, EMPLOYEE_EMAIL_CHANGED,
)


def credential_email_status(action: str | None) -> str:
    return {
        EMAIL_READY: "ready",
        EMAIL_SENDING: "processing",
        EMAIL_SENT: "sent",
        EMAIL_FAILED: "failed",
        EMAIL_UNKNOWN: "unknown",
        EMAIL_CHANGED: "changed",
        EMPLOYEE_EMAIL_READY: "ready",
        EMPLOYEE_EMAIL_SENDING: "processing",
        EMPLOYEE_EMAIL_SENT: "sent",
        EMPLOYEE_EMAIL_FAILED: "failed",
        EMPLOYEE_EMAIL_UNKNOWN: "unknown",
        EMPLOYEE_EMAIL_CHANGED: "changed",
    }.get(action or "", "unknown")


def record_credential_email_event(
    cursor, *, site_code: str, account_id: str, action: str,
    result: str | None = None, remote_ip: str | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO dbo.Logs
            (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong,
             bang_tac_dong, ma_ban_ghi, ip, ket_qua)
        VALUES (%s, 'system', %s, %s, %s, 'TaiKhoan', %s, %s, %s)
        """,
        [f"{site_code}-EM-{datetime.now(timezone.utc):%Y%m%d%H%M%S%f}-{uuid.uuid4().hex[:8]}", site_code, account_id,
         action, account_id, (remote_ip or "")[:45] or None, result],
    )


def _temporary_password() -> str:
    password = str(getattr(settings, "ADMIN_SMALL_TEMP_PASSWORD", "")).strip()
    if not password or len(password) > 128:
        raise AuthInfrastructureUnavailable
    return password


def _require_smtp_configuration() -> None:
    if "console.EmailBackend" in settings.EMAIL_BACKEND:
        raise AuthInfrastructureUnavailable
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or not settings.DEFAULT_FROM_EMAIL:
        raise AuthInfrastructureUnavailable


def _claim_delivery(
    *, site_code: str, account_id: str, password: str, remote_ip: str,
    profile_kind: str = "admin_small",
) -> tuple[str, str, str]:
    ready_to_send = False
    password_changed = False
    profile_queries = {
        "admin_small": (
            """
            SELECT TOP (2) n.ma_admin
            FROM dbo.Admin AS n
            WHERE n.ma_tai_khoan = %s AND n.ma_co_so = %s
              AND n.loai_admin = 'admin_small' AND n.trang_thai = 1
            """,
            _ADMIN_SMALL_EMAIL_ACTIONS,
            "qlttnn-admin-small-email",
            EMAIL_READY,
            EMAIL_FAILED,
            EMAIL_CHANGED,
            EMAIL_SENDING,
        ),
        "employee": (
            """
            SELECT TOP (2) n.ma_nhan_vien
            FROM dbo.NhanVien AS n
            WHERE n.ma_tai_khoan = %s AND n.ma_co_so = %s
              AND n.chuc_vu IN ('le_tan', 'tu_van', 'ke_toan') AND n.trang_thai = 'dang_lam'
            """,
            _EMPLOYEE_EMAIL_ACTIONS,
            "qlttnn-employee-email",
            EMPLOYEE_EMAIL_READY,
            EMPLOYEE_EMAIL_FAILED,
            EMPLOYEE_EMAIL_CHANGED,
            EMPLOYEE_EMAIL_SENDING,
        ),
    }
    if profile_kind not in profile_queries:
        raise ValueError("Unsupported credential profile.")
    profile_sql, email_actions, lock_prefix, ready_action, failed_action, changed_action, sending_action = profile_queries[profile_kind]
    try:
        alias = get_site_database_alias(site_code)
        account = _replicated_account_by_id(account_id, active_site_codes())
        if account is None or str(account[5]).lower() != "nhan_vien" or str(account[6] or "").upper() != site_code:
            raise AdminSmallTargetNotFound
        if not bool(account[7]):
            raise AdminSmallCredentialEmailConflict

        with get_site_connection(site_code).cursor() as cursor:
            cursor.execute(profile_sql, [account_id, site_code])
            profiles = cursor.fetchall()
        if len(profiles) != 1:
            raise AdminSmallTargetNotFound

        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                _acquire_named_lock(cursor, f"{lock_prefix}:{account_id}")
                placeholders = ", ".join(["%s"] * len(email_actions))
                cursor.execute(
                    f"""
                    SELECT TOP (1) hanh_dong
                    FROM dbo.Logs WITH (UPDLOCK, HOLDLOCK)
                    WHERE loai_log = 'system' AND ma_co_so = %s AND ma_tai_khoan = %s
                      AND bang_tac_dong = 'TaiKhoan' AND ma_ban_ghi = %s
                      AND hanh_dong IN ({placeholders})
                    ORDER BY thoi_diem_utc DESC, ma_log DESC
                    """,
                    [site_code, account_id, account_id, *email_actions],
                )
                latest_action = cursor.fetchone()
                latest_action = str(latest_action[0]) if latest_action else None
                if latest_action not in (ready_action, failed_action):
                    raise AdminSmallCredentialEmailConflict
                if not check_password(password, str(account[4])):
                    record_credential_email_event(
                        cursor, site_code=site_code, account_id=account_id,
                        action=changed_action, result="that_bai", remote_ip=remote_ip,
                    )
                    password_changed = True
                else:
                    record_credential_email_event(
                        cursor, site_code=site_code, account_id=account_id,
                        action=sending_action, remote_ip=remote_ip,
                    )
                    ready_to_send = True
    except (AdminSmallCredentialEmailConflict, AuthInfrastructureUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc

    if password_changed or not ready_to_send:
        raise AdminSmallCredentialEmailConflict
    return str(account[3]), str(account[1]), str(account[4])


def _record_delivery(site_code: str, account_id: str, action: str, result: str, remote_ip: str) -> None:
    try:
        alias = get_site_database_alias(site_code)
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                record_credential_email_event(
                    cursor, site_code=site_code, account_id=account_id,
                    action=action, result=result, remote_ip=remote_ip,
                )
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AuthInfrastructureUnavailable from exc


def send_admin_small_credentials(*, account_id: str, remote_ip: str) -> dict[str, str]:
    return _send_staff_credentials(account_id=account_id, site_code=None, remote_ip=remote_ip, profile_kind="admin_small")


def send_employee_credentials(*, account_id: str, site_code: str, remote_ip: str) -> dict[str, str]:
    return _send_staff_credentials(
        account_id=account_id, site_code=site_code, remote_ip=remote_ip, profile_kind="employee",
    )


def _send_staff_credentials(
    *, account_id: str, site_code: str | None, remote_ip: str, profile_kind: str,
) -> dict[str, str]:
    password = _temporary_password()
    _require_smtp_configuration()
    sites = active_site_codes()
    account = _replicated_account_by_id(account_id.strip(), sites)
    if (account is None or str(account[5]).lower() != "nhan_vien" or not account[6]
            or (profile_kind == "employee" and str(account[6]).upper() != str(site_code or "").upper())):
        raise AdminSmallTargetNotFound
    target_site = str(account[6]).upper()
    if target_site not in sites:
        raise AdminSmallTargetNotFound

    email, _username, _password_hash = _claim_delivery(
        site_code=target_site, account_id=account_id.strip(), password=password,
        remote_ip=remote_ip, profile_kind=profile_kind,
    )
    employee = profile_kind == "employee"
    event_actions = (
        (EMPLOYEE_EMAIL_UNKNOWN, EMPLOYEE_EMAIL_FAILED, EMPLOYEE_EMAIL_SENT)
        if employee else (EMAIL_UNKNOWN, EMAIL_FAILED, EMAIL_SENT)
    )
    try:
        sent = send_mail(
            subject=("Tài khoản nhân viên Trung tâm Ngoại ngữ" if employee else "Tài khoản Admin Small Trung tâm Ngoại ngữ"),
            message=(
                f"Tài khoản {'nhân viên' if employee else 'Admin Small'} của bạn đã được tạo.\n"
                f"Email đăng nhập: {email}\n"
                f"Mật khẩu tạm thời: {password}\n\n"
                "Hãy đăng nhập bằng email này.\n"
                "Hãy đổi mật khẩu ngay lần đăng nhập đầu tiên và không chia sẻ mật khẩu."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.warning("Staff credential email outcome is unknown; error_type=%s.", type(exc).__name__)
        try:
            _record_delivery(target_site, account_id, event_actions[0], "that_bai", remote_ip)
        except AuthInfrastructureUnavailable as log_exc:
            raise AuthInfrastructureUnavailable from log_exc
        raise AdminSmallCredentialEmailUncertain from exc

    if sent != 1:
        try:
            _record_delivery(target_site, account_id, event_actions[1], "that_bai", remote_ip)
        except AuthInfrastructureUnavailable as exc:
            raise AuthInfrastructureUnavailable from exc
        raise AdminSmallCredentialEmailDeliveryFailed

    try:
        _record_delivery(target_site, account_id, event_actions[2], "thanh_cong", remote_ip)
    except AuthInfrastructureUnavailable as exc:
        # The committed sending event blocks retry if the SMTP result cannot be recorded.
        raise AuthInfrastructureUnavailable from exc
    return {"email": email, "status": "sent"}
