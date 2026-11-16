"""Site-local tuition balance reads and idempotent in-person receipt posting."""

from typing import Any

from django.db import connections, transaction

from core.academics.common import (
    AcademicConflict,
    AcademicForbidden,
    AcademicInvalid,
    AcademicNotFound,
    acquire_record_lock,
    append_audit,
    next_id,
    require_active_site,
    translate_database_errors,
)
from core.academics.tuition_installments import (
    allocate_payment_to_installments,
    reverse_payment_from_installments,
)


def _dict_rows(cursor) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _verify_cashier(cursor, site_code: str, actor_id: str, employee_id: str, role: str) -> None:
    if role != "ke_toan" or not employee_id:
        raise AcademicForbidden
    cursor.execute(
        """
        SELECT TOP (2) ma_nhan_vien
        FROM dbo.NhanVien
        WHERE ma_nhan_vien = %s AND ma_co_so = %s AND ma_tai_khoan = %s
          AND chuc_vu = 'ke_toan' AND trang_thai = 'dang_lam'
        """,
        [employee_id, site_code, actor_id],
    )
    rows = cursor.fetchall()
    if len(rows) != 1:
        raise AcademicForbidden


@translate_database_errors
def list_tuition(
    *, site_code: str, status_filter: str | None, student_slug: str | None,
    limit: int, offset: int,
) -> dict[str, Any]:
    alias = require_active_site(site_code)
    where: list[str] = ["hp.ma_co_so = %s"]
    params: list[Any] = [site_code]
    if status_filter:
        where.append("hp.trang_thai = %s")
        params.append(status_filter)
    if student_slug:
        where.append("hv.slug = %s")
        params.append(student_slug)
    clause = " AND ".join(where)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COUNT_BIG(*)
            FROM dbo.HocPhi AS hp
            INNER JOIN dbo.DangKy AS dk
                ON dk.ma_dang_ky = hp.ma_dang_ky AND dk.ma_co_so = hp.ma_co_so
            INNER JOIN dbo.HocVien AS hv
                ON hv.ma_hoc_vien = dk.ma_hoc_vien AND hv.ma_co_so = dk.ma_co_so
            INNER JOIN dbo.LopHoc AS lh
                ON lh.ma_lop = dk.ma_lop AND lh.ma_co_so = dk.ma_co_so
            WHERE {clause}
            """,
            params,
        )
        count = int(cursor.fetchone()[0])
        cursor.execute(
            f"""
            SELECT hp.ma_hoc_phi AS tuition_id, hp.ma_dang_ky AS enrollment_id,
                   hv.ma_hoc_vien AS student_id, hv.slug AS student_slug,
                   hv.ho_ten AS student_name, lh.ma_lop AS class_id, lh.ten_lop AS class_name,
                   hp.so_tien_phai_dong AS amount_due, hp.giam_gia AS discount,
                   hp.so_tien_da_dong AS amount_paid,
                   hp.so_tien_phai_dong - hp.giam_gia - hp.so_tien_da_dong AS balance,
                   hp.trang_thai AS status
            FROM dbo.HocPhi AS hp
            INNER JOIN dbo.DangKy AS dk
                ON dk.ma_dang_ky = hp.ma_dang_ky AND dk.ma_co_so = hp.ma_co_so
            INNER JOIN dbo.HocVien AS hv
                ON hv.ma_hoc_vien = dk.ma_hoc_vien AND hv.ma_co_so = dk.ma_co_so
            INNER JOIN dbo.LopHoc AS lh
                ON lh.ma_lop = dk.ma_lop AND lh.ma_co_so = dk.ma_co_so
            WHERE {clause}
            ORDER BY hp.ma_hoc_phi
            OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """,
            [*params, offset, limit],
        )
        results = _dict_rows(cursor)
        for row in results:
            row["site_code"] = site_code
        return {
            "site_code": site_code, "count": count, "limit": limit,
            "offset": offset, "results": results,
        }


@translate_database_errors
def collect_tuition(
    *, site_code: str, tuition_id: str, actor_id: str, employee_id: str,
    role: str, idempotency_key: str, amount: int, payment_method: str,
    note: str | None, remote_ip: str,
) -> dict[str, Any]:
    site_code = str(site_code).strip().upper()
    receipt_id = f"{site_code}-PT-{idempotency_key}"
    if len(receipt_id) > 24:
        raise AcademicInvalid("Idempotency key quá dài đối với mã phiếu thu của site.")
    if amount <= 0 or payment_method not in {"tien_mat", "chuyen_khoan", "the"}:
        raise AcademicInvalid("Số tiền hoặc phương thức thu không hợp lệ.")
    alias = require_active_site(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _verify_cashier(cursor, site_code, actor_id, employee_id, role)
            cursor.execute(
                """
                SELECT so_tien_phai_dong, giam_gia, so_tien_da_dong, trang_thai
                FROM dbo.HocPhi WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_hoc_phi = %s
                """,
                [site_code, tuition_id],
            )
            fee = cursor.fetchone()
            if fee is None:
                raise AcademicNotFound

            cursor.execute(
                """
                SELECT ma_hoc_phi, loai, so_tien, hinh_thuc, ma_nhan_vien, ghi_chu
                FROM dbo.PhieuThu WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_phieu = %s AND ma_co_so = %s
                """,
                [receipt_id, site_code],
            )
            prior = cursor.fetchone()
            if prior is not None:
                same_request = (
                    str(prior[0]) == tuition_id and str(prior[1]) == "thu"
                    and int(prior[2]) == int(amount) and str(prior[3]) == payment_method
                    and str(prior[4]) == employee_id and (prior[5] or None) == note
                )
                if not same_request:
                    raise AcademicConflict("Idempotency key đã được dùng cho nội dung khác.")
                return {
                    "receipt_id": receipt_id, "tuition_id": tuition_id,
                    "amount": int(prior[2]), "payment_method": str(prior[3]),
                    "amount_paid": int(fee[2]),
                    "balance": int(fee[0]) - int(fee[1]) - int(fee[2]),
                    "tuition_status": str(fee[3]), "site_code": site_code,
                    "replayed": True,
                }

            balance = int(fee[0]) - int(fee[1]) - int(fee[2])
            if balance <= 0:
                raise AcademicConflict("Khoản học phí đã được thanh toán đủ hoặc không còn số dư.")
            if amount > balance:
                raise AcademicConflict("Số tiền thu vượt số dư học phí.")

            cursor.execute(
                """
                INSERT INTO dbo.PhieuThu
                    (ma_phieu, ma_co_so, ma_hoc_phi, loai, so_tien, hinh_thuc, ma_nhan_vien, ghi_chu)
                VALUES (%s, %s, %s, 'thu', %s, %s, %s, %s)
                """,
                [receipt_id, site_code, tuition_id, amount, payment_method, employee_id, note],
            )
            new_paid = int(fee[2]) + int(amount)
            new_balance = balance - int(amount)
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
                raise AcademicConflict("Số dư vừa thay đổi; tải lại khoản học phí trước khi thu.")
            allocate_payment_to_installments(
                cursor, site_code=site_code, tuition_id=tuition_id,
                amount=int(amount), expected_balance=balance,
            )
            append_audit(
                cursor, site_code=site_code, actor_id=actor_id,
                action="thu_hoc_phi", table_name="PhieuThu", record_id=receipt_id,
                remote_ip=remote_ip,
                after={"tuition_id": tuition_id, "amount": amount,
                       "payment_method": payment_method, "balance": new_balance},
            )
    return {
        "receipt_id": receipt_id, "tuition_id": tuition_id, "amount": amount,
        "payment_method": payment_method, "amount_paid": new_paid,
        "balance": new_balance, "tuition_status": new_status,
        "site_code": site_code, "replayed": False,
    }


@translate_database_errors
def list_tuition_receipts(
    *, site_code: str, tuition_id: str, actor_id: str, employee_id: str, role: str,
) -> dict[str, Any]:
    site_code = str(site_code).strip().upper()
    alias = require_active_site(site_code)
    with connections[alias].cursor() as cursor:
        _verify_cashier(cursor, site_code, actor_id, employee_id, role)
        cursor.execute(
            "SELECT 1 FROM dbo.HocPhi WHERE ma_co_so = %s AND ma_hoc_phi = %s",
            [site_code, tuition_id],
        )
        if cursor.fetchone() is None:
            raise AcademicNotFound
        cursor.execute(
            """
            SELECT p.ma_phieu, p.loai, p.so_tien, p.hinh_thuc, p.ngay_thu,
                   p.ma_phieu_goc, p.ghi_chu,
                   COALESCE((
                       SELECT SUM(r.so_tien)
                       FROM dbo.PhieuThu AS r
                       WHERE r.ma_co_so = p.ma_co_so AND r.ma_phieu_goc = p.ma_phieu
                   ), 0) AS refunded_amount
            FROM dbo.PhieuThu AS p
            WHERE p.ma_co_so = %s AND p.ma_hoc_phi = %s
            ORDER BY p.ngay_thu DESC, p.ma_phieu DESC
            """,
            [site_code, tuition_id],
        )
        rows = _dict_rows(cursor)
        for row in rows:
            row["receipt_id"] = str(row.pop("ma_phieu"))
            row["type"] = str(row.pop("loai"))
            row["amount"] = int(row.pop("so_tien"))
            row["payment_method"] = str(row.pop("hinh_thuc"))
            row["paid_at"] = row.pop("ngay_thu").isoformat()
            row["original_receipt_id"] = row.pop("ma_phieu_goc")
            row["note"] = row.pop("ghi_chu")
            row["refunded_amount"] = int(row["refunded_amount"])
            row["refundable_amount"] = (
                max(0, row["amount"] - row["refunded_amount"])
                if row["type"] == "thu" else 0
            )
        return {"site_code": site_code, "tuition_id": tuition_id, "count": len(rows), "results": rows}


@translate_database_errors
def refund_tuition(
    *, site_code: str, tuition_id: str, receipt_id: str, actor_id: str,
    employee_id: str, role: str, idempotency_key: str, amount: int,
    payment_method: str, reason: str, remote_ip: str,
) -> dict[str, Any]:
    site_code = str(site_code).strip().upper()
    if amount <= 0 or payment_method not in {"tien_mat", "chuyen_khoan", "the"}:
        raise AcademicInvalid("Số tiền hoặc phương thức hoàn không hợp lệ.")
    alias = require_active_site(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            _verify_cashier(cursor, site_code, actor_id, employee_id, role)
            acquire_record_lock(cursor, f"tuition-refund-idempotency:{site_code}:{idempotency_key}")
            cursor.execute(
                """
                SELECT so_tien_phai_dong, giam_gia, so_tien_da_dong, trang_thai
                FROM dbo.HocPhi WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_hoc_phi = %s
                """,
                [site_code, tuition_id],
            )
            fee = cursor.fetchone()
            if fee is None:
                raise AcademicNotFound

            cursor.execute(
                """
                SELECT ma_phieu, ma_hoc_phi, ma_phieu_goc, so_tien, hinh_thuc, ma_nhan_vien, ghi_chu
                FROM dbo.PhieuThu WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND khoa_idempotency = %s
                """,
                [site_code, idempotency_key],
            )
            prior = cursor.fetchone()
            if prior is not None:
                same_request = (
                    str(prior[1]) == tuition_id and str(prior[2]) == receipt_id
                    and int(prior[3]) == amount and str(prior[4]) == payment_method
                    and str(prior[5]) == employee_id and (prior[6] or None) == reason
                )
                if not same_request:
                    raise AcademicConflict("Idempotency key đã được dùng cho nội dung khác.")
                cursor.execute(
                    "SELECT COALESCE(SUM(so_tien), 0) FROM dbo.PhieuThu WHERE ma_co_so = %s AND ma_phieu_goc = %s",
                    [site_code, receipt_id],
                )
                refunded = int(cursor.fetchone()[0])
                amount_paid = int(fee[2])
                balance = int(fee[0]) - int(fee[1]) - amount_paid
                return {
                    "receipt_id": str(prior[0]), "original_receipt_id": receipt_id,
                    "tuition_id": tuition_id, "amount": amount,
                    "refunded_amount": refunded, "refundable_amount": max(0, int(prior[3]) - refunded),
                    "amount_paid": amount_paid, "balance": balance,
                    "tuition_status": str(fee[3]), "site_code": site_code, "replayed": True,
                }

            cursor.execute(
                """
                SELECT so_tien, hinh_thuc
                FROM dbo.PhieuThu WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_phieu = %s AND ma_co_so = %s AND ma_hoc_phi = %s AND loai = 'thu'
                """,
                [receipt_id, site_code, tuition_id],
            )
            original = cursor.fetchone()
            if original is None:
                raise AcademicNotFound
            cursor.execute(
                """
                SELECT TOP (1) ma_phieu
                FROM dbo.PhieuThu WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_hoc_phi = %s
                  AND loai = 'hoan' AND ma_phieu_goc IS NULL
                """,
                [site_code, tuition_id],
            )
            if cursor.fetchone() is not None:
                raise AcademicConflict("Khoản học phí có phiếu hoàn cũ chưa gắn phiếu gốc; cần đối soát trước khi hoàn tiếp.")
            cursor.execute(
                """
                SELECT COALESCE(SUM(so_tien), 0)
                FROM dbo.PhieuThu WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_co_so = %s AND ma_phieu_goc = %s
                """,
                [site_code, receipt_id],
            )
            refunded = int(cursor.fetchone()[0])
            refundable = min(int(original[0]) - refunded, int(fee[2]))
            if amount > refundable:
                raise AcademicConflict("Số tiền hoàn vượt khoản còn có thể hoàn.")

            new_paid = int(fee[2]) - amount
            new_balance = int(fee[0]) - int(fee[1]) - new_paid
            new_status = "hoan_tien" if new_paid == 0 else "da_dong" if new_balance == 0 else "dong_mot_phan"
            refund_id = next_id(cursor, site_code, "receipt")
            cursor.execute(
                """
                INSERT INTO dbo.PhieuThu
                    (ma_phieu, ma_co_so, ma_hoc_phi, ma_phieu_goc, khoa_idempotency,
                     loai, so_tien, hinh_thuc, ma_nhan_vien, ghi_chu)
                VALUES (%s, %s, %s, %s, %s, 'hoan', %s, %s, %s, %s)
                """,
                [refund_id, site_code, tuition_id, receipt_id, idempotency_key,
                 amount, payment_method, employee_id, reason],
            )
            cursor.execute(
                """
                UPDATE dbo.HocPhi
                SET so_tien_da_dong = %s, trang_thai = %s
                WHERE ma_co_so = %s AND ma_hoc_phi = %s AND so_tien_da_dong >= %s
                """,
                [new_paid, new_status, site_code, tuition_id, amount],
            )
            if cursor.rowcount != 1:
                raise AcademicConflict("Số đã thu vừa thay đổi; tải lại khoản học phí trước khi hoàn.")
            reverse_payment_from_installments(
                cursor, site_code=site_code, tuition_id=tuition_id,
                amount=amount, expected_paid=int(fee[2]),
            )
            append_audit(
                cursor, site_code=site_code, actor_id=actor_id,
                action="hoan_hoc_phi", table_name="PhieuThu", record_id=refund_id,
                remote_ip=remote_ip,
                before={"original_receipt_id": receipt_id, "amount_paid": int(fee[2])},
                after={"amount": amount, "payment_method": payment_method,
                       "amount_paid": new_paid, "balance": new_balance},
                note=reason,
            )
    return {
        "receipt_id": refund_id, "original_receipt_id": receipt_id,
        "tuition_id": tuition_id, "amount": amount,
        "refunded_amount": refunded + amount,
        "refundable_amount": int(original[0]) - refunded - amount,
        "amount_paid": new_paid, "balance": new_balance,
        "tuition_status": new_status, "site_code": site_code, "replayed": False,
    }
