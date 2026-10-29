"""Site-local email reminders backed by the existing append-only Logs table."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import connections, transaction
from django.utils import timezone

from core.academics.common import AcademicNotFound, acquire_record_lock, next_id, require_active_site
from core.sites.connections import get_site_database_alias

logger = logging.getLogger("core.academics.reminders")
ABSENCE_MONTHLY_LIMIT = 3


class ReminderInfrastructureUnavailable(Exception):
    """A site database or the configured SMTP service is unavailable."""


def _smtp_ready() -> bool:
    return bool(
        str(getattr(settings, "EMAIL_BACKEND", "")).endswith("smtp.EmailBackend")
        and getattr(settings, "EMAIL_HOST_USER", "")
        and getattr(settings, "EMAIL_HOST_PASSWORD", "")
        and getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )


def _month_bounds(value: date) -> tuple[date, date]:
    start = date(value.year, value.month, 1)
    end = date(value.year + (value.month == 12), 1 if value.month == 12 else value.month + 1, 1)
    return start, end


def _record_email_event(
    *, site_code: str, actor_id: str | None, event_key: str,
    action: str, recipient: str, subject: str, message: str,
) -> str:
    """Send once per event key; the event log never stores recipient or message text."""
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            acquire_record_lock(cursor, f"email-reminder:{site_code}:{event_key}")
            cursor.execute(
                """
                SELECT TOP (1) ket_qua FROM dbo.Logs
                WHERE loai_log = 'system' AND hanh_dong = %s AND ma_ban_ghi = %s
                  AND ket_qua = 'thanh_cong'
                """,
                [action, event_key],
            )
            if cursor.fetchone() is not None:
                return "already_sent"

            result = "thanh_cong"
            try:
                sent = send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False,
                )
                if sent != 1:
                    result = "that_bai"
            except Exception as exc:  # Do not log addresses, message bodies, or SMTP credentials.
                logger.warning("Reminder email failed; error_type=%s", type(exc).__name__)
                result = "that_bai"

            log_id = next_id(cursor, site_code, "audit")
            cursor.execute(
                """
                INSERT INTO dbo.Logs
                    (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong,
                     bang_tac_dong, ma_ban_ghi, ket_qua)
                VALUES (%s, 'system', %s, %s, %s, 'EmailReminder', %s, %s)
                """,
                [log_id, site_code, actor_id, action, event_key, result],
            )
            return "sent" if result == "thanh_cong" else "failed"


def send_monthly_absence_warnings(
    *, site_code: str, class_id: str, student_ids: list[str], month_date: date,
    actor_id: str,
) -> dict[str, Any]:
    """Email a student once per site/month after more than three unexcused absences."""
    summary = {
        "status": "checked", "monthly_limit": ABSENCE_MONTHLY_LIMIT,
        "sent_count": 0, "already_sent_count": 0, "missing_email_count": 0,
        "below_limit_count": 0, "failed_count": 0,
    }
    if not student_ids:
        return summary
    if not _smtp_ready():
        summary["status"] = "email_not_configured"
        summary["failed_count"] = len(student_ids)
        return summary

    alias = require_active_site(site_code)
    month_start, month_end = _month_bounds(month_date)
    unique_ids = sorted(set(student_ids))[:300]
    placeholders = ", ".join(["%s"] * len(unique_ids))
    with connections[alias].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT h.ma_hoc_vien, h.ho_ten, h.email, COUNT_BIG(*) AS so_buoi_vang
            FROM dbo.HocVien AS h
            INNER JOIN dbo.DangKy AS d
                ON d.ma_hoc_vien = h.ma_hoc_vien AND d.ma_co_so = h.ma_co_so
            INNER JOIN dbo.DiemDanh AS dd
                ON dd.ma_dang_ky = d.ma_dang_ky AND dd.ma_co_so = d.ma_co_so
            INNER JOIN dbo.BuoiHoc AS b
                ON b.ma_buoi = dd.ma_buoi AND b.ma_co_so = dd.ma_co_so
            WHERE h.ma_co_so = %s AND h.ma_hoc_vien IN ({placeholders})
              AND h.trang_thai = 'dang_hoc'
              AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
              AND dd.trang_thai = 'vang_khong_phep'
              AND b.ngay_hoc >= %s AND b.ngay_hoc < %s
            GROUP BY h.ma_hoc_vien, h.ho_ten, h.email
            """,
            [site_code, *unique_ids, month_start, month_end],
        )
        students = cursor.fetchall()

    for student_id, full_name, email, absence_count in students:
        if int(absence_count) <= ABSENCE_MONTHLY_LIMIT:
            summary["below_limit_count"] += 1
            continue
        recipient = str(email or "").strip()
        if not recipient:
            summary["missing_email_count"] += 1
            continue
        event_key = f"absence:{site_code}:{student_id}:{month_date:%Y-%m}"
        result = _record_email_event(
            site_code=site_code, actor_id=actor_id, event_key=event_key,
            action="canh_bao_vang_hoc",
            recipient=recipient,
            subject="Cảnh báo số buổi nghỉ không phép",
            message=(
                f"Chào {full_name},\n\n"
                f"Trong tháng {month_date:%m/%Y}, hệ thống ghi nhận {int(absence_count)} buổi nghỉ không phép "
                f"tại các lớp của cơ sở {site_code}; cảnh báo được kích hoạt khi điểm danh lớp {class_id}. "
                f"Mức nhắc nhở là trên {ABSENCE_MONTHLY_LIMIT} buổi. "
                "Vui lòng liên hệ cơ sở để được hỗ trợ.\n"
            ),
        )
        summary[{"sent": "sent_count", "already_sent": "already_sent_count", "failed": "failed_count"}[result]] += 1

    if summary["failed_count"] and not summary["sent_count"]:
        summary["status"] = "delivery_failed"
    return summary


def send_class_unpaid_tuition_reminders(
    *, site_code: str, class_id: str, actor_id: str, actor_role: str,
    employee_id: str | None,
) -> dict[str, Any]:
    """Send one daily reminder to each enrolled student with a positive balance."""
    if not _smtp_ready():
        raise ReminderInfrastructureUnavailable("SMTP chưa được cấu hình.")
    alias = require_active_site(site_code)
    if actor_role == "ke_toan":
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP (1) 1 FROM dbo.NhanVien
                WHERE ma_nhan_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
                  AND chuc_vu = 'ke_toan' AND trang_thai = 'dang_lam'
                """,
                [employee_id, site_code, actor_id],
            )
            if cursor.fetchone() is None:
                raise PermissionError("Tài khoản kế toán không còn hồ sơ đang làm tại site này.")

    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT h.ma_hoc_vien, h.ho_ten, h.email, l.ten_lop,
                   SUM(hp.so_tien_phai_dong - hp.giam_gia - hp.so_tien_da_dong) AS so_con_no
            FROM dbo.LopHoc AS l
            INNER JOIN dbo.DangKy AS d
                ON d.ma_lop = l.ma_lop AND d.ma_co_so = l.ma_co_so
            INNER JOIN dbo.HocVien AS h
                ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
            INNER JOIN dbo.HocPhi AS hp
                ON hp.ma_dang_ky = d.ma_dang_ky AND hp.ma_co_so = d.ma_co_so
            WHERE l.ma_co_so = %s AND l.ma_lop = %s
              AND l.trang_thai IN ('sap_mo', 'dang_hoc')
              AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
              AND h.trang_thai = 'dang_hoc'
            GROUP BY h.ma_hoc_vien, h.ho_ten, h.email, l.ten_lop
            HAVING SUM(hp.so_tien_phai_dong - hp.giam_gia - hp.so_tien_da_dong) > 0
            ORDER BY h.ho_ten, h.ma_hoc_vien
            """,
            [site_code, class_id],
        )
        rows = cursor.fetchall()

    if not rows:
        # Distinguish an empty class from a nonexistent/foreign class.
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT TOP (1) 1 FROM dbo.LopHoc WHERE ma_co_so = %s AND ma_lop = %s",
                [site_code, class_id],
            )
            if cursor.fetchone() is None:
                raise AcademicNotFound

    counts = {"sent_count": 0, "already_sent_count": 0, "missing_email_count": 0, "failed_count": 0}
    today = timezone.localdate()
    for student_id, full_name, email, class_name, balance in rows:
        recipient = str(email or "").strip()
        if not recipient:
            counts["missing_email_count"] += 1
            continue
        event_key = f"tuition:{site_code}:{class_id}:{student_id}:{today:%Y%m%d}"
        result = _record_email_event(
            site_code=site_code, actor_id=actor_id, event_key=event_key,
            action="nhac_hoc_phi",
            recipient=recipient,
            subject=f"Nhắc học phí lớp {class_name}",
            message=(
                f"Chào {full_name},\n\n"
                f"Lớp {class_name} tại cơ sở {site_code} hiện còn học phí chưa thanh toán: "
                f"{int(balance):,} đồng. Vui lòng liên hệ kế toán cơ sở để được hỗ trợ.\n"
            ),
        )
        counts[{"sent": "sent_count", "already_sent": "already_sent_count", "failed": "failed_count"}[result]] += 1
    return {
        "site_code": site_code, "class_id": class_id,
        "unpaid_students": len(rows), **counts,
    }
