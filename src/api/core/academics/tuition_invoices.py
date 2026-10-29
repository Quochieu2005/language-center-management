"""Site-local receipt invoice lookup and email delivery using existing Logs."""

from __future__ import annotations

import logging
from datetime import timezone as datetime_timezone
from html import escape
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import connections, transaction

from core.academics.common import (
    AcademicNotFound,
    acquire_record_lock,
    next_id,
    require_active_site,
    translate_database_errors,
)

logger = logging.getLogger("core.academics.invoices")
_VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_PAYMENT_LABELS = {
    "tien_mat": "Tiền mặt",
    "chuyen_khoan": "Chuyển khoản",
    "the": "Thẻ",
}
_EMAIL_ACTION = "gui_hoa_don_hoc_phi"


def _vietnam_time(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime_timezone.utc)
    return value.astimezone(_VIETNAM_TZ)


@translate_database_errors
def get_tuition_invoice(*, site_code: str, tuition_id: str, receipt_id: str) -> dict:
    """Read receipt and related student/course details from exactly one site DB."""
    site = str(site_code).strip().upper()
    alias = require_active_site(site)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT p.ma_phieu, p.ma_co_so, cs.ten_co_so, cs.dia_chi, cs.sdt,
                   p.ma_hoc_phi, hv.ma_hoc_vien, hv.ho_ten, hv.email,
                   kh.ten_khoa_hoc, lh.ten_lop,
                   hp.so_tien_phai_dong, hp.giam_gia, p.so_tien,
                   p.hinh_thuc, p.ngay_thu, nv.ho_ten, p.ghi_chu
            FROM dbo.PhieuThu AS p
            INNER JOIN dbo.HocPhi AS hp
                ON hp.ma_hoc_phi = p.ma_hoc_phi AND hp.ma_co_so = p.ma_co_so
            INNER JOIN dbo.DangKy AS dk
                ON dk.ma_dang_ky = hp.ma_dang_ky AND dk.ma_co_so = hp.ma_co_so
            INNER JOIN dbo.HocVien AS hv
                ON hv.ma_hoc_vien = dk.ma_hoc_vien AND hv.ma_co_so = dk.ma_co_so
            INNER JOIN dbo.LopHoc AS lh
                ON lh.ma_lop = dk.ma_lop AND lh.ma_co_so = dk.ma_co_so
            INNER JOIN dbo.KhoaHoc AS kh
                ON kh.ma_khoa_hoc = lh.ma_khoa_hoc
            INNER JOIN dbo.CoSo AS cs ON cs.ma_co_so = p.ma_co_so
            LEFT JOIN dbo.NhanVien AS nv
                ON nv.ma_nhan_vien = p.ma_nhan_vien AND nv.ma_co_so = p.ma_co_so
            WHERE p.ma_co_so = %s AND p.ma_hoc_phi = %s
              AND p.ma_phieu = %s AND p.loai = 'thu'
            """,
            [site, tuition_id, receipt_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise AcademicNotFound

    paid_at = _vietnam_time(row[15])
    gross, discount = int(row[11]), int(row[12])
    payment_method = str(row[14])
    return {
        "document_type": "bien_nhan_hoc_phi_noi_bo",
        "invoice_number": str(row[0]),
        "site_code": str(row[1]),
        "branch_name": str(row[2]),
        "branch_address": row[3],
        "branch_phone": row[4],
        "tuition_id": str(row[5]),
        "student_id": str(row[6]),
        "student_name": str(row[7]),
        "student_email": str(row[8]).strip() if row[8] else None,
        "course_name": str(row[9]),
        "class_name": str(row[10]),
        "total_due": gross,
        "discount": discount,
        "net_total": gross - discount,
        "amount_received": int(row[13]),
        "currency": "VND",
        "payment_method": payment_method,
        "payment_method_label": _PAYMENT_LABELS[payment_method],
        "paid_at": paid_at,
        "paid_at_display": paid_at.strftime("%d/%m/%Y %H:%M:%S"),
        "cashier_name": str(row[16] or ""),
        "note": row[17],
    }


def _format_vnd(amount: int) -> str:
    return f"{int(amount):,}".replace(",", ".") + " ₫"


def render_invoice_email(invoice: dict) -> tuple[str, str]:
    """Build plain-text and escaped HTML versions of the internal receipt email."""
    rows = (
        ("Mã phiếu thu", invoice["invoice_number"]),
        ("Cơ sở", invoice["branch_name"]),
        ("Học viên", invoice["student_name"]),
        ("Khóa học", invoice["course_name"]),
        ("Lớp", invoice["class_name"]),
        ("Thời gian thu", invoice["paid_at_display"]),
        ("Hình thức", invoice["payment_method_label"]),
        ("Số tiền thu lần này", _format_vnd(invoice["amount_received"])),
        ("Tổng học phí sau giảm giá", _format_vnd(invoice["net_total"])),
    )
    if invoice.get("note"):
        rows += (("Ghi chú", invoice["note"]),)

    text_body = "Biên nhận học phí\n\n" + "\n".join(
        f"{label}: {value}" for label, value in rows
    ) + "\n\nĐây là biên nhận nội bộ của trung tâm, không phải hóa đơn điện tử thuế."
    html_rows = "".join(
        "<tr><th style=\"text-align:left;padding:8px;border-bottom:1px solid #e5e7eb\">"
        f"{escape(str(label))}</th><td style=\"padding:8px;border-bottom:1px solid #e5e7eb\">"
        f"{escape(str(value))}</td></tr>"
        for label, value in rows
    )
    html_body = (
        "<!doctype html><html lang=\"vi\"><body style=\"margin:0;background:#f5f7fa;"
        "font-family:Arial,sans-serif;color:#172033;padding:24px\"><main style=\"max-width:640px;"
        "margin:auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:24px\">"
        "<h1 style=\"font-size:22px;margin:0 0 6px\">Biên nhận học phí</h1>"
        "<p style=\"color:#667085;margin:0 0 20px\">Trung tâm ngoại ngữ · "
        f"{escape(str(invoice['branch_name']))}</p><table style=\"width:100%;border-collapse:collapse\">"
        f"{html_rows}</table><p style=\"font-size:12px;color:#667085;margin-top:20px\">"
        "Đây là biên nhận nội bộ của trung tâm, không phải hóa đơn điện tử thuế.</p>"
        "</main></body></html>"
    )
    return text_body, html_body


def send_tuition_invoice_email(
    *, site_code: str, tuition_id: str, receipt_id: str, actor_id: str,
) -> dict[str, str]:
    """Email one site-local receipt; mail failure never reverses a committed payment."""
    if not (
        str(getattr(settings, "EMAIL_BACKEND", "")).endswith("smtp.EmailBackend")
        and getattr(settings, "EMAIL_HOST_USER", "")
        and getattr(settings, "EMAIL_HOST_PASSWORD", "")
        and getattr(settings, "DEFAULT_FROM_EMAIL", "")
    ):
        return {"status": "not_configured"}

    try:
        invoice = get_tuition_invoice(
            site_code=site_code, tuition_id=tuition_id, receipt_id=receipt_id,
        )
        recipient = invoice.get("student_email")
        if not recipient:
            return {"status": "missing_email"}
        text_body, html_body = render_invoice_email(invoice)
        alias = require_active_site(site_code)
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                acquire_record_lock(cursor, f"tuition-invoice-email:{site_code}:{receipt_id}")
                cursor.execute(
                    """
                    SELECT TOP (1) ma_log FROM dbo.Logs
                    WHERE loai_log = 'system' AND hanh_dong = %s
                      AND bang_tac_dong = 'PhieuThu' AND ma_ban_ghi = %s
                      AND ket_qua = 'thanh_cong'
                    """,
                    [_EMAIL_ACTION, receipt_id],
                )
                if cursor.fetchone() is not None:
                    return {"status": "already_sent"}

                email = EmailMultiAlternatives(
                    subject=f"Biên nhận học phí {receipt_id}",
                    body=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient],
                )
                email.attach_alternative(html_body, "text/html")
                try:
                    result = "thanh_cong" if email.send(fail_silently=False) == 1 else "that_bai"
                except Exception as exc:
                    logger.warning("Tuition invoice email failed; error_type=%s", type(exc).__name__)
                    result = "that_bai"

                cursor.execute(
                    """
                    INSERT INTO dbo.Logs
                        (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong,
                         bang_tac_dong, ma_ban_ghi, ket_qua)
                    VALUES (%s, 'system', %s, %s, %s, 'PhieuThu', %s, %s)
                    """,
                    [next_id(cursor, site_code, "audit"), site_code, actor_id,
                     _EMAIL_ACTION, receipt_id, result],
                )
        return {"status": "sent" if result == "thanh_cong" else "failed"}
    except Exception as exc:
        logger.warning("Tuition invoice processing failed; error_type=%s", type(exc).__name__)
        return {"status": "failed"}
