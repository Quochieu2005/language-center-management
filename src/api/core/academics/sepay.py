"""Site-local SePay Payment Gateway attempts, reconciliation and idempotent settlement.

Flow (all writes are LOCAL to the site that owns ``HocPhi``; SePay is an external service):
1. ``create_student_payment`` computes the amount server-side from the chosen option
   (next installment / half / full), stores ``YeuCauThanhToan`` and returns a signed checkout form.
2. SePay confirms through the IPN (``process_gateway_ipn``) or, when the IPN cannot reach this
   server (local runs), through ``GET order/detail`` when the student checks the status.
3. Both paths settle under one event id derived from the invoice number, so a payment is
   recorded at most once: one ``PhieuThu`` allocated oldest-installment-first.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone as datetime_timezone
from urllib.parse import urlencode

from django.conf import settings
from django.db import connections, transaction
from django.utils import timezone

from core.academics.common import (
    AcademicConflict,
    AcademicInfrastructureUnavailable,
    AcademicInvalid,
    AcademicNotFound,
    acquire_record_lock,
    append_audit,
    next_id,
    require_active_site,
    translate_database_errors,
)
from core.academics.sepay_gateway import (
    PAID_ORDER_STATUSES,
    GatewayUnavailable,
    build_checkout,
    fetch_order,
    money,
)
from core.academics.tuition_invoices import send_tuition_invoice_email
from core.academics.tuition_installments import allocate_payment_to_installments
from core.sites.connections import get_site_database_alias

_REFERENCE_SUFFIX_LENGTH = 12
PAYMENT_OPTIONS = ("next_installment", "half", "full")
_OPEN_STATES = ("cho_thanh_toan", "can_doi_soat")
# Attempts that may still be paid on SePay after our own start window closed.
_SETTLEABLE_STATES = ("cho_thanh_toan", "het_han", "can_doi_soat")
_RECHECK_EXPIRED_FOR = timedelta(hours=24)


def _payment_enabled() -> None:
    if not settings.SEPAY_ENABLED:
        raise AcademicInvalid("Thanh toán SePay chưa được bật hoặc chưa cấu hình.")


# ---------------------------------------------------------------- references and amounts
def _site_token(site_code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", site_code.upper())


def site_from_reference(reference: str) -> str | None:
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


def _new_payment_reference(site_code: str) -> str:
    token = _site_token(site_code)
    if not token:
        raise AcademicInvalid("Mã cơ sở không thể mã hóa vào mã thanh toán.")
    reference = f"{settings.SEPAY_PAYMENT_CODE_PREFIX}{token}{secrets.token_hex(6).upper()}"
    if len(reference) > 40 or site_from_reference(reference) != site_code:
        raise AcademicInvalid("Mã cơ sở trùng hoặc không thể định tuyến mã thanh toán an toàn.")
    return reference


def gateway_event_id(reference: str) -> int:
    """Stable negative BIGINT per invoice: IPN and order lookup dedupe on the same row."""
    return -int(hashlib.sha256(f"sepay-pg:{reference}".encode("ascii")).hexdigest()[:15], 16)


def payment_options(balance: int, installments: list[tuple[str, int, int]]) -> dict[str, int]:
    """Amounts allowed for one payment; ``installments`` are (id, due, paid) oldest first."""
    if balance <= 0:
        return {}
    next_installment = next((due - paid for _id, due, paid in installments if due > paid), balance)
    return {
        "next_installment": min(next_installment, balance),
        "half": (balance + 1) // 2,
        "full": balance,
    }


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(datetime_timezone.utc).replace(tzinfo=None)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=datetime_timezone.utc) if value.tzinfo is None else value


def _return_urls(attempt_id: str) -> dict[str, str]:
    base = f"{settings.WEB_APP_BASE_URL}/student"
    return {
        outcome: f"{base}?{urlencode({'payment': attempt_id, 'result': outcome})}"
        for outcome in ("success", "error", "cancel")
    }


# ---------------------------------------------------------------- reads
_ATTEMPT_COLUMNS = (
    "ma_yeu_cau, ma_hoc_phi, ma_dot_hoc_phi, so_tien, ma_tham_chieu, trang_thai, "
    "tao_luc_utc, het_han_utc, ma_tai_khoan"
)


def _attempt(row) -> dict:
    keys = ("attempt_id", "tuition_id", "installment_id", "amount", "reference", "status",
            "created", "expires", "account_id")
    data = dict(zip(keys, row))
    data["amount"] = int(data["amount"])
    for key in ("attempt_id", "tuition_id", "installment_id", "reference", "status", "account_id"):
        data[key] = str(data[key])
    return data


def _response(site_code: str, attempt: dict, option: str | None = None) -> dict:
    status = attempt["status"]
    expires = _aware(attempt["expires"])
    if status == "cho_thanh_toan" and expires <= timezone.now():
        status = "het_han"
    result = {
        "site_code": site_code,
        "attempt_id": attempt["attempt_id"],
        "tuition_id": attempt["tuition_id"],
        "installment_id": attempt["installment_id"],
        "amount": attempt["amount"],
        "payment_code": attempt["reference"],
        "status": status,
        "expires_at": expires,
        "checkout": None,
    }
    if option:
        result["option"] = option
    if status == "cho_thanh_toan":
        result["checkout"] = build_checkout(
            invoice=attempt["reference"], amount=attempt["amount"],
            description=f"Hoc phi {attempt['tuition_id']}",
            return_urls=_return_urls(attempt["attempt_id"]),
        )
    return result


# ---------------------------------------------------------------- settlement
def _insert_event(cursor, *, site_code: str, attempt: dict | None, reference: str, amount: int,
                  provider_ref: str, paid_at: datetime | None, result: str) -> None:
    cursor.execute(
        """
        INSERT INTO dbo.SuKienThanhToan
            (ma_co_so, ma_yeu_cau, ma_giao_dich_sepay, ma_tham_chieu, so_tien,
             tai_khoan_nhan, ma_tham_chieu_ngan_hang, thoi_diem_giao_dich, ket_qua)
        VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s)
        """,
        [site_code, attempt["attempt_id"] if attempt else None, gateway_event_id(reference),
         reference[:40], amount, provider_ref[:100] or None, paid_at, result],
    )


def _settle(cursor, *, site_code: str, attempt: dict, amount: int, provider_ref: str,
            paid_at: datetime | None) -> str | None:
    """Record one confirmed payment; return the receipt id, or None when it needs review."""
    if attempt["status"] not in _SETTLEABLE_STATES or amount != attempt["amount"]:
        return None
    cursor.execute(
        """
        SELECT so_tien_phai_dong, giam_gia, so_tien_da_dong
        FROM dbo.HocPhi WITH (UPDLOCK, HOLDLOCK)
        WHERE ma_co_so = %s AND ma_hoc_phi = %s
        """,
        [site_code, attempt["tuition_id"]],
    )
    fee = cursor.fetchone()
    if fee is None:
        return None
    balance = int(fee[0]) - int(fee[1]) - int(fee[2])
    if amount > balance:
        return None  # e.g. another attempt or the counter already collected; refund manually.

    receipt_id = next_id(cursor, site_code, "receipt")
    cursor.execute(
        """
        INSERT INTO dbo.PhieuThu
            (ma_phieu, ma_co_so, ma_hoc_phi, ma_yeu_cau, loai, so_tien,
             hinh_thuc, ngay_thu, ma_nhan_vien, ghi_chu)
        VALUES (%s, %s, %s, %s, 'thu', %s, 'chuyen_khoan', SYSUTCDATETIME(), NULL, %s)
        """,
        [receipt_id, site_code, attempt["tuition_id"], attempt["attempt_id"], amount,
         f"SePay {attempt['reference']}"[:500]],
    )
    new_balance = balance - amount
    cursor.execute(
        """
        UPDATE dbo.HocPhi SET so_tien_da_dong = so_tien_da_dong + %s, trang_thai = %s
        WHERE ma_co_so = %s AND ma_hoc_phi = %s
          AND so_tien_phai_dong - giam_gia - so_tien_da_dong >= %s
        """,
        [amount, "da_dong" if new_balance == 0 else "dong_mot_phan",
         site_code, attempt["tuition_id"], amount],
    )
    if cursor.rowcount != 1:
        raise AcademicConflict("Số dư vừa thay đổi; giao dịch cần được đối soát.")
    allocate_payment_to_installments(
        cursor, site_code=site_code, tuition_id=attempt["tuition_id"],
        amount=amount, expected_balance=balance,
    )
    cursor.execute(
        "UPDATE dbo.YeuCauThanhToan SET trang_thai = 'da_thanh_toan', "
        "thanh_toan_luc_utc = SYSUTCDATETIME(), cap_nhat_luc_utc = SYSUTCDATETIME() "
        "WHERE ma_yeu_cau = %s AND ma_co_so = %s AND trang_thai IN ('cho_thanh_toan', 'het_han', 'can_doi_soat')",
        [attempt["attempt_id"], site_code],
    )
    if cursor.rowcount != 1:
        raise AcademicConflict("Yêu cầu thanh toán vừa đổi trạng thái; giao dịch cần được đối soát.")
    _insert_event(cursor, site_code=site_code, attempt=attempt, reference=attempt["reference"],
                  amount=amount, provider_ref=provider_ref, paid_at=paid_at, result="da_ghi_nhan")
    append_audit(
        cursor, site_code=site_code, actor_id=attempt["account_id"],
        action="sepay_thanh_toan_hoc_phi", table_name="PhieuThu", record_id=receipt_id,
        after={"tuition_id": attempt["tuition_id"], "amount": amount, "payment_method": "chuyen_khoan",
               "sepay_invoice": attempt["reference"], "balance": new_balance},
    )
    return receipt_id


def _record_paid(site_code: str, reference: str, amount: int, provider_ref: str,
                 paid_at: datetime | None) -> dict:
    """Apply a SePay "paid" signal once (IPN or order lookup); safe to call repeatedly."""
    alias = get_site_database_alias(site_code)
    receipt = None
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            acquire_record_lock(cursor, f"sepay-invoice:{reference}")
            cursor.execute(
                "SELECT ket_qua FROM dbo.SuKienThanhToan WHERE ma_giao_dich_sepay = %s",
                [gateway_event_id(reference)],
            )
            prior = cursor.fetchone()
            if prior is not None:
                return {"status": "duplicate", "result": str(prior[0])}
            cursor.execute(
                f"SELECT {_ATTEMPT_COLUMNS} FROM dbo.YeuCauThanhToan WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND ma_tham_chieu = %s",
                [site_code, reference],
            )
            row = cursor.fetchone()
            attempt = _attempt(row) if row else None
            if attempt:
                receipt = _settle(cursor, site_code=site_code, attempt=attempt, amount=amount,
                                  provider_ref=provider_ref, paid_at=paid_at)
            if receipt is None:
                result = "can_doi_soat" if attempt else "khong_tim_thay"
                if attempt and attempt["status"] in _SETTLEABLE_STATES:
                    cursor.execute(
                        "UPDATE dbo.YeuCauThanhToan SET trang_thai = 'can_doi_soat', "
                        "cap_nhat_luc_utc = SYSUTCDATETIME() WHERE ma_yeu_cau = %s AND ma_co_so = %s",
                        [attempt["attempt_id"], site_code],
                    )
                _insert_event(cursor, site_code=site_code, attempt=attempt, reference=reference,
                              amount=amount, provider_ref=provider_ref, paid_at=paid_at, result=result)
                return {"status": result}
    send_tuition_invoice_email(
        site_code=site_code, tuition_id=attempt["tuition_id"],
        receipt_id=receipt, actor_id=attempt["account_id"],
    )
    return {"status": "da_ghi_nhan", "receipt_id": receipt}


def _mark_expired(site_code: str, attempt_id: str) -> None:
    alias = get_site_database_alias(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "UPDATE dbo.YeuCauThanhToan SET trang_thai = 'het_han', cap_nhat_luc_utc = SYSUTCDATETIME() "
            "WHERE ma_yeu_cau = %s AND ma_co_so = %s AND trang_thai = 'cho_thanh_toan' "
            "AND het_han_utc <= SYSUTCDATETIME()",
            [attempt_id, site_code],
        )


def reconcile_attempt(site_code: str, attempt: dict) -> None:
    """Ask SePay about one attempt (no DB lock held during HTTP) and apply the answer."""
    if attempt["status"] not in _SETTLEABLE_STATES:
        return
    order = fetch_order(attempt["reference"])
    if order is not None and str(order.get("order_status", "")).upper() in PAID_ORDER_STATUSES:
        invoice = str(order.get("order_invoice_number") or attempt["reference"])
        currency = str(order.get("order_currency") or "VND").upper()
        amount = money(order.get("order_amount"))
        if invoice != attempt["reference"] or currency != "VND" or amount is None:
            raise AcademicConflict("Đơn SePay không khớp yêu cầu thanh toán; cần đối soát.")
        _record_paid(site_code, attempt["reference"], amount,
                     provider_ref=str(order.get("order_id") or order.get("id") or ""), paid_at=None)
    elif _aware(attempt["expires"]) <= timezone.now():
        _mark_expired(site_code, attempt["attempt_id"])


# ---------------------------------------------------------------- student API
def _load_attempts(site_code: str, where: str, params: list) -> list[dict]:
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(f"SELECT {_ATTEMPT_COLUMNS} FROM dbo.YeuCauThanhToan WHERE {where}", params)
        return [_attempt(row) for row in cursor.fetchall()]


def _reconcile_open_attempts(site_code: str, tuition_id: str) -> None:
    since = _utc_naive(timezone.now() - _RECHECK_EXPIRED_FOR)
    attempts = _load_attempts(
        site_code,
        "ma_co_so = %s AND ma_hoc_phi = %s AND (trang_thai IN ('cho_thanh_toan', 'can_doi_soat') "
        "OR (trang_thai = 'het_han' AND tao_luc_utc >= %s))",
        [site_code, tuition_id, since],
    )
    for attempt in attempts:
        try:
            reconcile_attempt(site_code, attempt)
        except GatewayUnavailable as exc:
            if attempt["status"] in _OPEN_STATES:
                raise AcademicInfrastructureUnavailable(
                    "Chưa xác nhận được giao dịch trước với SePay; thử lại sau ít phút."
                ) from exc


@translate_database_errors
def create_student_payment(*, user, tuition_id: str, option: str, idempotency_key: str) -> dict:
    _payment_enabled()
    if option not in PAYMENT_OPTIONS:
        raise AcademicInvalid("Lựa chọn thanh toán không hợp lệ.")
    site_code = str(user.site_code or "").upper()
    alias = require_active_site(site_code)
    # Settle or expire earlier attempts first, so a new one never double-charges the student.
    _reconcile_open_attempts(site_code, tuition_id)
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
                f"SELECT {_ATTEMPT_COLUMNS}, khoa_idempotency FROM dbo.YeuCauThanhToan "
                "WITH (UPDLOCK, HOLDLOCK) WHERE khoa_idempotency = %s",
                [idempotency_key],
            )
            prior = cursor.fetchone()
            if prior is not None:
                attempt = _attempt(prior[:9])
                if attempt["account_id"] != user.account_id or attempt["tuition_id"] != tuition_id:
                    raise AcademicConflict("Idempotency-Key đã được dùng cho yêu cầu khác.")
                return _response(site_code, attempt)

            cursor.execute(
                f"SELECT {_ATTEMPT_COLUMNS} FROM dbo.YeuCauThanhToan WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_hoc_phi = %s AND ma_co_so = %s AND trang_thai IN ('cho_thanh_toan', 'can_doi_soat')",
                [tuition_id, site_code],
            )
            for open_row in cursor.fetchall():
                attempt = _attempt(open_row)
                if attempt["status"] == "can_doi_soat":
                    raise AcademicConflict(
                        f"Khoản học phí có giao dịch {attempt['attempt_id']} đang chờ đối soát; liên hệ cơ sở."
                    )
                if _aware(attempt["expires"]) > now:
                    raise AcademicConflict(
                        f"Khoản này đang có yêu cầu thanh toán {attempt['attempt_id']} chưa hết hạn; "
                        "hãy tiếp tục yêu cầu đó thay vì tạo yêu cầu mới."
                    )

            cursor.execute(
                "SELECT ma_dot_hoc_phi, so_tien_phai_dong, so_tien_da_dong FROM dbo.DotHocPhi "
                "WITH (UPDLOCK, HOLDLOCK) WHERE ma_co_so = %s AND ma_hoc_phi = %s ORDER BY so_thu_tu",
                [site_code, tuition_id],
            )
            installments = [(str(r[0]), int(r[1]), int(r[2])) for r in cursor.fetchall()]
            balance = int(fee[0]) - int(fee[1]) - int(fee[2])
            if not installments or sum(due - paid for _i, due, paid in installments) != balance:
                raise AcademicConflict("Lịch các kỳ học phí chưa khớp số dư; liên hệ cơ sở để đối soát.")
            amount = payment_options(balance, installments).get(option)
            if not amount:
                raise AcademicConflict("Khoản học phí đã được thanh toán đủ.")
            anchor = next(i for i, due, paid in installments if due > paid)

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
                [attempt_id, site_code, tuition_id, anchor, user.account_id, amount, reference,
                 idempotency_key, _utc_naive(now), _utc_naive(expires), _utc_naive(now)],
            )
            append_audit(
                cursor, site_code=site_code, actor_id=user.account_id,
                action="sepay_tao_yeu_cau_thanh_toan", table_name="YeuCauThanhToan", record_id=attempt_id,
                after={"tuition_id": tuition_id, "amount": amount, "option": option},
            )
    return _response(site_code, {
        "attempt_id": attempt_id, "tuition_id": tuition_id, "installment_id": anchor,
        "amount": amount, "reference": reference, "status": "cho_thanh_toan",
        "created": _utc_naive(now), "expires": _utc_naive(expires), "account_id": user.account_id,
    }, option)


@translate_database_errors
def get_student_payment(*, user, attempt_id: str) -> dict:
    """Status from the site DB; an unsettled attempt is first checked with SePay."""
    _payment_enabled()
    site_code = str(user.site_code or "").upper()
    where = "ma_co_so = %s AND ma_yeu_cau = %s AND ma_tai_khoan = %s"
    params = [site_code, attempt_id, user.account_id]
    attempts = _load_attempts(site_code, where, params)
    if not attempts:
        raise AcademicNotFound("Không tìm thấy yêu cầu thanh toán.")
    try:
        reconcile_attempt(site_code, attempts[0])
    except GatewayUnavailable:
        pass  # keep the stored status; the next check or the IPN settles it
    return _response(site_code, _load_attempts(site_code, where, params)[0])


@translate_database_errors
def process_gateway_ipn(payload: dict) -> dict:
    """Handle a SePay IPN whose X-Secret-Key was already verified by the view."""
    order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
    txn = payload.get("transaction") if isinstance(payload.get("transaction"), dict) else {}
    reference = str(order.get("order_invoice_number") or "").strip().upper()
    site_code = site_from_reference(reference)
    if site_code is None:
        return {"status": "ignored_unmatched_reference"}
    if str(payload.get("notification_type") or "").upper() != "ORDER_PAID":
        return {"status": "ignored_notification_type"}
    amount = money(order.get("order_amount"))
    currency = str(order.get("order_currency") or txn.get("transaction_currency") or "VND").upper()
    txn_status = str(txn.get("transaction_status") or "APPROVED").upper()
    if amount is None or currency != "VND" or txn_status != "APPROVED":
        return {"status": "ignored_not_approved"}
    paid_at = None
    raw_date = txn.get("transaction_date")
    if isinstance(raw_date, str) and raw_date.strip():
        try:
            parsed = datetime.fromisoformat(raw_date.strip().replace("Z", "+00:00").replace(" ", "T"))
            paid_at = _utc_naive(parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.get_current_timezone()))
        except ValueError:
            paid_at = None
    return _record_paid(site_code, reference, amount,
                        provider_ref=str(txn.get("transaction_id") or txn.get("id") or ""), paid_at=paid_at)
