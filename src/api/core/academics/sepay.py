"""Site-local SePay tuition QR requests and idempotent webhook settlement."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import connections, transaction
from django.utils import timezone

from core.academics.common import (
    AcademicConflict,
    AcademicInvalid,
    AcademicNotFound,
    acquire_record_lock,
    append_audit,
    next_id,
    require_active_site,
    translate_database_errors,
)
from core.academics.tuition_invoices import send_tuition_invoice_email
from core.academics.tuition_installments import allocate_payment_to_installments
from core.sites.connections import get_site_database_alias

_VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_REFERENCE_SUFFIX_LENGTH = 12


def _payment_enabled() -> bool:
    if not settings.SEPAY_ENABLED:
        raise AcademicInvalid("Thanh toán SePay chưa được bật hoặc chưa cấu hình.")


def _site_token(site_code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", site_code.upper())


def _site_from_reference(reference: str) -> str | None:
    prefix = settings.SEPAY_PAYMENT_CODE_PREFIX
    if not reference.startswith(prefix):
        return None
    matches = []
    for site in settings.SITE_DATABASE_ALIASES:
        token = _site_token(site)
        suffix = reference[len(prefix) + len(token):]
        if token and reference.startswith(prefix + token) and re.fullmatch(
            rf"[A-Z0-9]{{{_REFERENCE_SUFFIX_LENGTH}}}", suffix
        ):
            matches.append(site)
    return matches[0] if len(matches) == 1 else None


def _payment_reference(payload: dict) -> str:
    reference = str(payload.get("code") or "").strip().upper()
    if _site_from_reference(reference):
        return reference

    content = str(payload.get("content") or "").upper()
    candidates = set()
    for site in settings.SITE_DATABASE_ALIASES:
        code_prefix = f"{settings.SEPAY_PAYMENT_CODE_PREFIX}{_site_token(site)}"
        if not code_prefix:
            continue
        pattern = rf"(?<![A-Z0-9]){re.escape(code_prefix)}[A-Z0-9]{{{_REFERENCE_SUFFIX_LENGTH}}}(?![A-Z0-9])"
        candidates.update(re.findall(pattern, content))
    return next(iter(candidates)) if len(candidates) == 1 else ""


def _new_payment_reference(site_code: str) -> str:
    token = _site_token(site_code)
    if not token:
        raise AcademicInvalid("Mã cơ sở không thể mã hóa vào nội dung thanh toán.")
    reference = f"{settings.SEPAY_PAYMENT_CODE_PREFIX}{token}{secrets.token_hex(6).upper()}"
    if len(reference) > 40 or _site_from_reference(reference) != site_code:
        raise AcademicInvalid("Mã cơ sở trùng hoặc không thể định tuyến mã thanh toán an toàn.")
    return reference


def _qr_url(reference: str, amount: int) -> str:
    query = urlencode({
        "acc": settings.SEPAY_BANK_ACCOUNT,
        "bank": settings.SEPAY_BANK_CODE,
        "amount": amount,
        "des": reference,
    })
    return f"https://vietqr.app/img?{query}"


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime_timezone.utc).replace(tzinfo=None)
    return value.astimezone(datetime_timezone.utc).replace(tzinfo=None)


def _response(site_code: str, row) -> dict:
    attempt_id, installment_id, amount, reference, state, expires = row
    expires_aware = expires.replace(tzinfo=datetime_timezone.utc)
    if state == "cho_thanh_toan" and expires_aware <= timezone.now():
        state = "het_han"
    return {
        "site_code": site_code,
        "attempt_id": str(attempt_id),
        "installment_id": str(installment_id),
        "amount": int(amount),
        "payment_code": str(reference),
        "bank_code": settings.SEPAY_BANK_CODE,
        "bank_account": settings.SEPAY_BANK_ACCOUNT,
        "qr_url": _qr_url(str(reference), int(amount)),
        "status": str(state),
        "expires_at": expires_aware,
    }


def _attempt_row(cursor, *, site_code: str, attempt_id: str, account_id: str):
    cursor.execute(
        """
        SELECT ma_yeu_cau, ma_dot_hoc_phi, so_tien, ma_tham_chieu,
               trang_thai, het_han_utc
        FROM dbo.YeuCauThanhToan
        WHERE ma_co_so = %s AND ma_yeu_cau = %s AND ma_tai_khoan = %s
        """,
        [site_code, attempt_id, account_id],
    )
    return cursor.fetchone()


@translate_database_errors
def create_student_payment(
    *, user, tuition_id: str, installment_id: str, amount: int, idempotency_key: str,
) -> dict:
    _payment_enabled()
    site_code = str(user.site_code or "").upper()
    alias = require_active_site(site_code)
    now = timezone.now()
    expires = now + timedelta(seconds=settings.SEPAY_PAYMENT_TTL_SECONDS)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT hp.so_tien_phai_dong, hp.giam_gia, hp.so_tien_da_dong
                FROM dbo.HocPhi AS hp WITH (UPDLOCK, HOLDLOCK)
                INNER JOIN dbo.DangKy AS dk
                    ON dk.ma_dang_ky = hp.ma_dang_ky AND dk.ma_co_so = hp.ma_co_so
                WHERE hp.ma_co_so = %s AND hp.ma_hoc_phi = %s AND dk.ma_hoc_vien = %s
                """,
                [site_code, tuition_id, user.profile_id],
            )
            fee = cursor.fetchone()
            if fee is None:
                raise AcademicNotFound("Không tìm thấy khoản học phí của tài khoản này.")

            cursor.execute(
                """
                SELECT ma_yeu_cau, ma_dot_hoc_phi, so_tien, ma_tham_chieu,
                       trang_thai, het_han_utc, ma_tai_khoan, ma_hoc_phi
                FROM dbo.YeuCauThanhToan WITH (UPDLOCK, HOLDLOCK)
                WHERE khoa_idempotency = %s
                """,
                [idempotency_key],
            )
            prior = cursor.fetchone()
            if prior is not None:
                if (str(prior[6]) != user.account_id or str(prior[7]) != tuition_id
                        or str(prior[1]) != installment_id or int(prior[2]) != amount):
                    raise AcademicConflict("Idempotency-Key đã được dùng cho yêu cầu khác.")
                return _response(site_code, prior[:6])

            cursor.execute(
                """
                UPDATE dbo.YeuCauThanhToan
                SET trang_thai = 'het_han', cap_nhat_luc_utc = SYSUTCDATETIME()
                WHERE ma_hoc_phi = %s AND ma_co_so = %s AND trang_thai = 'cho_thanh_toan'
                  AND het_han_utc <= SYSUTCDATETIME()
                """,
                [tuition_id, site_code],
            )
            cursor.execute(
                """
                SELECT ma_yeu_cau, ma_dot_hoc_phi, so_tien, ma_tham_chieu,
                       trang_thai, het_han_utc, ma_tai_khoan
                FROM dbo.YeuCauThanhToan WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_hoc_phi = %s AND ma_co_so = %s AND trang_thai = 'cho_thanh_toan'
                """,
                [tuition_id, site_code],
            )
            active = cursor.fetchone()
            if active is not None:
                if (str(active[6]) != user.account_id or str(active[1]) != installment_id
                        or int(active[2]) != amount):
                    raise AcademicConflict("Khoản học phí đã có một yêu cầu thanh toán đang mở.")
                return _response(site_code, active[:6])

            balance = int(fee[0]) - int(fee[1]) - int(fee[2])
            cursor.execute(
                """
                SELECT d.ma_dot_hoc_phi, d.so_tien_phai_dong, d.so_tien_da_dong
                FROM dbo.DotHocPhi AS d WITH (UPDLOCK, HOLDLOCK)
                WHERE d.ma_co_so = %s AND d.ma_hoc_phi = %s
                ORDER BY d.so_thu_tu
                """,
                [site_code, tuition_id],
            )
            installments = cursor.fetchall()
            first_unpaid = next(
                ((str(row[0]), int(row[1]) - int(row[2]))
                 for row in installments if int(row[1]) > int(row[2])),
                None,
            )
            selected = next((row for row in installments if str(row[0]) == installment_id), None)
            if balance <= 0 or selected is None or first_unpaid is None:
                raise AcademicConflict("Khoản học phí hoặc kỳ đóng đã được thanh toán đủ.")
            installment_balance = int(selected[1]) - int(selected[2])
            if first_unpaid[0] != installment_id:
                raise AcademicConflict("Chỉ được thanh toán kỳ chưa đóng đầu tiên.")
            if amount <= 0 or amount > min(balance, installment_balance):
                raise AcademicInvalid("Số tiền vượt số dư của kỳ đóng hoặc khoản học phí.")

            reference = _new_payment_reference(site_code)
            attempt_id = next_id(cursor, site_code, "sepay")
            cursor.execute(
                """
                INSERT INTO dbo.YeuCauThanhToan
                    (ma_yeu_cau, ma_co_so, ma_hoc_phi, ma_dot_hoc_phi, ma_tai_khoan,
                     so_tien, ma_tham_chieu, khoa_idempotency, trang_thai,
                     tao_luc_utc, het_han_utc, cap_nhat_luc_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'cho_thanh_toan', %s, %s, %s)
                """,
                [attempt_id, site_code, tuition_id, installment_id, user.account_id,
                 amount, reference, idempotency_key, _utc_naive(now), _utc_naive(expires), _utc_naive(now)],
            )
            return _response(
                site_code,
                (attempt_id, installment_id, amount, reference, "cho_thanh_toan", _utc_naive(expires)),
            )


@translate_database_errors
def get_student_payment(*, user, attempt_id: str) -> dict:
    _payment_enabled()
    site_code = str(user.site_code or "").upper()
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        row = _attempt_row(
            cursor, site_code=site_code, attempt_id=attempt_id, account_id=user.account_id,
        )
    if row is None:
        raise AcademicNotFound("Không tìm thấy yêu cầu thanh toán.")
    return _response(site_code, row)


def _transaction_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_VIETNAM_TZ)
    return parsed.astimezone(datetime_timezone.utc).replace(tzinfo=None)


def _money(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount != amount.to_integral_value() or amount < 0:
        return None
    return int(amount)


def _insert_event(
    cursor, *, site_code: str, request_id: str | None, transaction_id: int,
    reference: str, amount: int, account: str, bank_reference: str,
    transaction_time: datetime | None, result: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO dbo.SuKienThanhToan
            (ma_co_so, ma_yeu_cau, ma_giao_dich_sepay, ma_tham_chieu, so_tien,
             tai_khoan_nhan, ma_tham_chieu_ngan_hang, thoi_diem_giao_dich, ket_qua)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [site_code, request_id, transaction_id, reference[:40] or None, amount,
         account[:34] or None, bank_reference[:100] or None, transaction_time, result],
    )


def _settle_verified_transfer(cursor, *, site_code: str, request: tuple,
                              transaction_id: int, amount: int, transaction_time: datetime,
                              bank_reference: str, account: str, reference: str) -> tuple[str, str, str] | None:
    request_id, tuition_id, installment_id, expected_amount, state, created, expires, account_id = request
    if str(state) != "cho_thanh_toan" or not (_utc_naive(created) <= transaction_time <= _utc_naive(expires)):
        return None
    if amount != int(expected_amount) or account.strip() != settings.SEPAY_BANK_ACCOUNT:
        return None

    cursor.execute(
        """
        SELECT so_tien_phai_dong, giam_gia, so_tien_da_dong
        FROM dbo.HocPhi WITH (UPDLOCK, HOLDLOCK)
        WHERE ma_co_so = %s AND ma_hoc_phi = %s
        """,
        [site_code, tuition_id],
    )
    fee = cursor.fetchone()
    cursor.execute(
        """
        SELECT ma_dot_hoc_phi, so_tien_phai_dong, so_tien_da_dong
        FROM dbo.DotHocPhi WITH (UPDLOCK, HOLDLOCK)
        WHERE ma_co_so = %s AND ma_hoc_phi = %s
        ORDER BY so_thu_tu
        """,
        [site_code, tuition_id],
    )
    installments = cursor.fetchall()
    if fee is None:
        return None
    balance = int(fee[0]) - int(fee[1]) - int(fee[2])
    selected = next((row for row in installments if str(row[0]) == str(installment_id)), None)
    first_unpaid = next(
        ((str(row[0]), int(row[1]) - int(row[2]))
         for row in installments if int(row[1]) > int(row[2])),
        None,
    )
    if (selected is None or first_unpaid is None or first_unpaid[0] != str(installment_id)
            or amount > balance or amount > int(selected[1]) - int(selected[2])):
        return None

    receipt_id = next_id(cursor, site_code, "receipt")
    cursor.execute(
        """
        INSERT INTO dbo.PhieuThu
            (ma_phieu, ma_co_so, ma_hoc_phi, ma_yeu_cau, loai, so_tien,
             hinh_thuc, ngay_thu, ma_nhan_vien, ghi_chu)
        VALUES (%s, %s, %s, %s, 'thu', %s, 'chuyen_khoan', SYSUTCDATETIME(), NULL, %s)
        """,
        [receipt_id, site_code, tuition_id, request_id, amount,
         f"SePay transaction {transaction_id}"],
    )
    new_paid = int(fee[2]) + amount
    new_balance = balance - amount
    new_status = "da_dong" if new_balance == 0 else "dong_mot_phan"
    cursor.execute(
        """
        UPDATE dbo.HocPhi
        SET so_tien_da_dong = %s, trang_thai = %s
        WHERE ma_co_so = %s AND ma_hoc_phi = %s
          AND so_tien_phai_dong - giam_gia - so_tien_da_dong >= %s
        """,
        [new_paid, new_status, site_code, tuition_id, amount],
    )
    if cursor.rowcount != 1:
        raise AcademicConflict("Số dư vừa thay đổi; giao dịch cần được đối soát.")
    allocate_payment_to_installments(
        cursor, site_code=site_code, tuition_id=str(tuition_id),
        amount=amount, expected_balance=balance,
    )
    cursor.execute(
        """
        UPDATE dbo.YeuCauThanhToan
        SET trang_thai = 'da_thanh_toan', thanh_toan_luc_utc = SYSUTCDATETIME(),
            cap_nhat_luc_utc = SYSUTCDATETIME()
        WHERE ma_yeu_cau = %s AND ma_co_so = %s AND trang_thai = 'cho_thanh_toan'
        """,
        [request_id, site_code],
    )
    if cursor.rowcount != 1:
        raise AcademicConflict("Yêu cầu thanh toán vừa đổi trạng thái; giao dịch cần được đối soát.")
    _insert_event(
        cursor, site_code=site_code, request_id=str(request_id), transaction_id=transaction_id,
        reference=reference, amount=amount, account=account, bank_reference=bank_reference,
        transaction_time=transaction_time, result="da_ghi_nhan",
    )
    append_audit(
        cursor, site_code=site_code, actor_id=str(account_id),
        action="sepay_thanh_toan_hoc_phi", table_name="PhieuThu", record_id=receipt_id,
        after={"tuition_id": str(tuition_id), "amount": amount,
               "payment_method": "chuyen_khoan", "sepay_transaction_id": transaction_id,
               "balance": new_balance},
    )
    return str(tuition_id), receipt_id, str(account_id)


@translate_database_errors
def process_sepay_webhook(payload: dict) -> dict[str, str]:
    transaction_id = _money(payload.get("id"))
    if transaction_id is None or transaction_id == 0:
        return {"status": "ignored_test_or_invalid_id"}
    reference = _payment_reference(payload)
    site_code = _site_from_reference(reference)
    if site_code is None:
        return {"status": "ignored_unmatched_reference"}
    alias = get_site_database_alias(site_code)
    transfer_amount = _money(payload.get("transferAmount"))
    amount = transfer_amount if transfer_amount is not None else 0
    account = str(payload.get("accountNumber") or "").strip()
    transfer_type = str(payload.get("transferType") or "").strip().lower()
    bank_reference = str(payload.get("referenceCode") or "").strip()
    transaction_time = _transaction_time(payload.get("transactionDate"))
    receipt_to_email = None

    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            acquire_record_lock(cursor, f"sepay-transaction:{transaction_id}")
            cursor.execute(
                """
                SELECT ma_yeu_cau, ket_qua FROM dbo.SuKienThanhToan
                WHERE ma_giao_dich_sepay = %s
                """,
                [transaction_id],
            )
            prior_event = cursor.fetchone()
            if prior_event is not None:
                if str(prior_event[1]) == "da_ghi_nhan" and prior_event[0] is not None:
                    cursor.execute(
                        """
                        SELECT ma_hoc_phi, ma_phieu
                        FROM dbo.PhieuThu WHERE ma_yeu_cau = %s AND ma_co_so = %s
                        """,
                        [prior_event[0], site_code],
                    )
                    receipt = cursor.fetchone()
                    if receipt:
                        cursor.execute(
                            "SELECT ma_tai_khoan FROM dbo.YeuCauThanhToan WHERE ma_yeu_cau = %s",
                            [prior_event[0]],
                        )
                        account_row = cursor.fetchone()
                        if account_row:
                            receipt_to_email = (str(receipt[0]), str(receipt[1]), str(account_row[0]))
                result = "duplicate"
            else:
                cursor.execute(
                    """
                    SELECT ma_yeu_cau, ma_hoc_phi, ma_dot_hoc_phi, so_tien,
                           trang_thai, tao_luc_utc, het_han_utc, ma_tai_khoan
                    FROM dbo.YeuCauThanhToan WITH (UPDLOCK, HOLDLOCK)
                    WHERE ma_co_so = %s AND ma_tham_chieu = %s
                    """,
                    [site_code, reference],
                )
                request = cursor.fetchone()
                request_id = str(request[0]) if request else None
                if request and transfer_type == "in" and transfer_amount is not None and transaction_time:
                    receipt_to_email = _settle_verified_transfer(
                        cursor, site_code=site_code, request=request,
                        transaction_id=transaction_id, amount=transfer_amount,
                        transaction_time=transaction_time, bank_reference=bank_reference,
                        account=account, reference=reference,
                    )
                result = "da_ghi_nhan" if receipt_to_email else (
                    "can_doi_soat" if request else "khong_tim_thay"
                )
                if request and result == "can_doi_soat" and str(request[4]) == "cho_thanh_toan":
                    cursor.execute(
                        """
                        UPDATE dbo.YeuCauThanhToan
                        SET trang_thai = 'can_doi_soat', cap_nhat_luc_utc = SYSUTCDATETIME()
                        WHERE ma_yeu_cau = %s AND ma_co_so = %s AND trang_thai = 'cho_thanh_toan'
                        """,
                        [request_id, site_code],
                    )
                if not receipt_to_email:
                    _insert_event(
                        cursor, site_code=site_code, request_id=request_id,
                        transaction_id=transaction_id, reference=reference, amount=amount,
                        account=account, bank_reference=bank_reference,
                        transaction_time=transaction_time, result=result,
                    )

    if receipt_to_email:
        tuition_id, receipt_id, account_id = receipt_to_email
        send_tuition_invoice_email(
            site_code=site_code, tuition_id=tuition_id,
            receipt_id=receipt_id, actor_id=account_id,
        )
    return {"status": result}
