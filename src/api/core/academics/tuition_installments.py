"""Site-local tuition plans, monthly installments, and receipt allocation."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from django.db import connections, transaction
from django.utils import timezone

from core.academics.common import (
    AcademicConflict,
    AcademicInvalid,
    AcademicNotFound,
    append_audit,
    next_id,
    require_active_site,
    translate_database_errors,
)


ALLOWED_INSTALLMENT_COUNTS = (3, 6, 9, 12)
_MAX_MONEY = 999_999_999_999_999_999


def add_calendar_months(start: date, months: int) -> date:
    """Keep the original day where possible, clamping at a month's last day."""
    month_index = start.year * 12 + (start.month - 1) + months
    year, month_zero_based = divmod(month_index, 12)
    month = month_zero_based + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def build_installment_amounts(total: int, payment_mode: str, installment_count: int | None) -> list[int]:
    if total < 0 or total > _MAX_MONEY:
        raise AcademicInvalid("Tổng học phí sau giảm giá không hợp lệ.")
    if payment_mode == "full":
        if installment_count not in (None, 1):
            raise AcademicInvalid("Thanh toán một lần chỉ có một kỳ đóng.")
        return [total]
    if payment_mode != "monthly":
        raise AcademicInvalid("Hình thức kế hoạch học phí không hợp lệ.")
    if installment_count not in ALLOWED_INSTALLMENT_COUNTS:
        raise AcademicInvalid("Chỉ hỗ trợ chia học phí thành 3, 6, 9 hoặc 12 tháng.")
    if total < installment_count:
        raise AcademicInvalid("Tổng học phí không đủ để chia thành số kỳ đã chọn.")
    regular = total // installment_count
    return [regular] * (installment_count - 1) + [total - regular * (installment_count - 1)]


def build_installment_schedule(
    *, total: int, payment_mode: str, installment_count: int | None, first_due_date: date
) -> list[dict[str, Any]]:
    if first_due_date < timezone.localdate():
        raise AcademicInvalid("Ngày đến hạn đầu tiên không được trước ngày hiện tại.")
    amounts = build_installment_amounts(total, payment_mode, installment_count)
    return [
        {
            "sequence": sequence,
            "due_date": add_calendar_months(first_due_date, sequence - 1),
            "amount_due": amount,
            "amount_paid": 0,
            "balance": amount,
            "status": "da_dong" if amount == 0 else "chua_dong",
        }
        for sequence, amount in enumerate(amounts, start=1)
    ]


def _insert_schedule(
    cursor, *, site_code: str, tuition_id: str, total: int,
    payment_mode: str, installment_count: int | None, first_due_date: date,
) -> list[dict[str, Any]]:
    schedule = build_installment_schedule(
        total=total, payment_mode=payment_mode,
        installment_count=installment_count, first_due_date=first_due_date,
    )
    for item in schedule:
        installment_id = next_id(cursor, site_code, "installment")
        cursor.execute(
            """
            INSERT INTO dbo.DotHocPhi
                (ma_dot_hoc_phi, ma_co_so, ma_hoc_phi, so_thu_tu, ngay_den_han,
                 so_tien_phai_dong, so_tien_da_dong, trang_thai)
            VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
            """,
            [
                installment_id, site_code, tuition_id, item["sequence"],
                item["due_date"], item["amount_due"], item["status"],
            ],
        )
        item["installment_id"] = installment_id
    return schedule


def create_default_tuition_installment(
    cursor, *, site_code: str, tuition_id: str, total: int, first_due_date: date,
) -> None:
    """Create the backward-compatible one-time plan during local enrollment creation."""
    _insert_schedule(
        cursor, site_code=site_code, tuition_id=tuition_id, total=total,
        payment_mode="full", installment_count=None, first_due_date=first_due_date,
    )


def _fetch_schedule(cursor, *, site_code: str, tuition_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT ma_dot_hoc_phi, so_thu_tu, ngay_den_han,
               so_tien_phai_dong, so_tien_da_dong, trang_thai
        FROM dbo.DotHocPhi
        WHERE ma_co_so = %s AND ma_hoc_phi = %s
        ORDER BY so_thu_tu
        """,
        [site_code, tuition_id],
    )
    today = timezone.localdate()
    result: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        due, paid = int(row[3]), int(row[4])
        balance = due - paid
        state = str(row[5])
        if balance > 0 and row[2] < today:
            state = "qua_han"
        result.append(
            {
                "installment_id": str(row[0]),
                "sequence": int(row[1]),
                "due_date": row[2],
                "amount_due": due,
                "amount_paid": paid,
                "balance": balance,
                "status": state,
            }
        )
    return result


def _plan_response(
    *, site_code: str, tuition_id: str, gross: int, discount: int,
    paid: int, installments: list[dict[str, Any]],
) -> dict[str, Any]:
    net_total = gross - discount
    if not installments:
        raise AcademicConflict("Khoản học phí chưa có lịch đóng; hãy chạy migration học phí trên site này.")
    if sum(item["amount_due"] for item in installments) != net_total:
        raise AcademicConflict("Tổng các kỳ không khớp khoản học phí; cần đối soát trước khi thu.")
    balance = net_total - paid
    if sum(item["balance"] for item in installments) != balance:
        raise AcademicConflict("Số đã thu giữa các kỳ và khoản học phí không khớp; cần đối soát.")
    return {
        "site_code": site_code,
        "tuition_id": tuition_id,
        "payment_mode": "full" if len(installments) == 1 else "monthly",
        "installment_count": len(installments),
        "total_due": net_total,
        "amount_paid": paid,
        "balance": balance,
        "installments": installments,
    }


@translate_database_errors
def get_tuition_installment_plan(*, site_code: str, tuition_id: str) -> dict[str, Any]:
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT so_tien_phai_dong, giam_gia, so_tien_da_dong "
            "FROM dbo.HocPhi WHERE ma_co_so = %s AND ma_hoc_phi = %s",
            [site_code, tuition_id],
        )
        tuition = cursor.fetchone()
        if tuition is None:
            raise AcademicNotFound
        return _plan_response(
            site_code=site_code, tuition_id=tuition_id,
            gross=int(tuition[0]), discount=int(tuition[1]), paid=int(tuition[2]),
            installments=_fetch_schedule(cursor, site_code=site_code, tuition_id=tuition_id),
        )


@translate_database_errors
def set_tuition_installment_plan(
    *, site_code: str, tuition_id: str, payment_mode: str,
    installment_count: int | None, first_due_date: date,
    actor_id: str, remote_ip: str,
) -> dict[str, Any]:
    alias = require_active_site(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT so_tien_phai_dong, giam_gia, so_tien_da_dong
                FROM dbo.HocPhi WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_hoc_phi = %s
                """,
                [site_code, tuition_id],
            )
            tuition = cursor.fetchone()
            if tuition is None:
                raise AcademicNotFound
            gross, discount, paid = map(int, tuition)
            total = gross - discount
            desired = build_installment_schedule(
                total=total, payment_mode=payment_mode,
                installment_count=installment_count, first_due_date=first_due_date,
            )

            cursor.execute(
                """
                SELECT TOP (1) ma_phieu
                FROM dbo.PhieuThu WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_hoc_phi = %s
                """,
                [site_code, tuition_id],
            )
            has_receipt = cursor.fetchone() is not None
            current = _fetch_schedule(cursor, site_code=site_code, tuition_id=tuition_id)
            if paid > 0 or has_receipt or any(item["amount_paid"] > 0 for item in current):
                raise AcademicConflict("Không thể đổi kế hoạch sau khi đã phát sinh phiếu thu hoặc đã đóng tiền.")

            same_plan = len(current) == len(desired) and all(
                old["sequence"] == new["sequence"]
                and old["due_date"] == new["due_date"]
                and old["amount_due"] == new["amount_due"]
                for old, new in zip(current, desired)
            )
            if not same_plan:
                cursor.execute(
                    "DELETE FROM dbo.DotHocPhi WHERE ma_co_so = %s AND ma_hoc_phi = %s",
                    [site_code, tuition_id],
                )
                _insert_schedule(
                    cursor, site_code=site_code, tuition_id=tuition_id, total=total,
                    payment_mode=payment_mode, installment_count=installment_count,
                    first_due_date=first_due_date,
                )
                append_audit(
                    cursor, site_code=site_code, actor_id=actor_id,
                    action="cau_hinh_dot_hoc_phi", table_name="DotHocPhi",
                    record_id=tuition_id, remote_ip=remote_ip,
                    after={
                        "payment_mode": payment_mode,
                        "installment_count": len(desired),
                        "first_due_date": first_due_date.isoformat(),
                        "total_due": total,
                    },
                )
            installments = _fetch_schedule(cursor, site_code=site_code, tuition_id=tuition_id)
            return _plan_response(
                site_code=site_code, tuition_id=tuition_id,
                gross=gross, discount=discount, paid=paid, installments=installments,
            )


def allocate_payment_to_installments(
    cursor, *, site_code: str, tuition_id: str, amount: int, expected_balance: int,
) -> None:
    """Apply a received amount to the oldest unpaid installment first."""
    cursor.execute(
        """
        SELECT ma_dot_hoc_phi, so_tien_phai_dong, so_tien_da_dong
        FROM dbo.DotHocPhi WITH (UPDLOCK, HOLDLOCK)
        WHERE ma_co_so = %s AND ma_hoc_phi = %s
        ORDER BY so_thu_tu
        """,
        [site_code, tuition_id],
    )
    rows = cursor.fetchall()
    available = sum(int(row[1]) - int(row[2]) for row in rows)
    if not rows or available != expected_balance:
        raise AcademicConflict("Lịch các kỳ không khớp số dư; không thể ghi nhận khoản thu.")

    unallocated = amount
    for installment_id, due, paid in rows:
        remaining = int(due) - int(paid)
        if remaining <= 0 or unallocated <= 0:
            continue
        allocated = min(remaining, unallocated)
        updated_paid = int(paid) + allocated
        state = "da_dong" if updated_paid == int(due) else "dong_mot_phan"
        cursor.execute(
            """
            UPDATE dbo.DotHocPhi
            SET so_tien_da_dong = %s, trang_thai = %s
            WHERE ma_co_so = %s AND ma_hoc_phi = %s AND ma_dot_hoc_phi = %s
              AND so_tien_da_dong = %s
            """,
            [updated_paid, state, site_code, tuition_id, str(installment_id), int(paid)],
        )
        if cursor.rowcount != 1:
            raise AcademicConflict("Kỳ học phí vừa thay đổi; tải lại lịch trước khi thu.")
        unallocated -= allocated
    if unallocated != 0:
        raise AcademicConflict("Số tiền thu vượt tổng số dư các kỳ học phí.")
