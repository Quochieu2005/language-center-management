"""SePay Payment Gateway: signing, amount options, once-only settlement and IPN authentication."""

import base64
import hashlib
import hmac
import io
import json
import re
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from core.academics import sepay, sepay_gateway, sepay_views

SEPAY = dict(
    SEPAY_ENABLED=True, SEPAY_ENV="sandbox", SEPAY_MERCHANT_ID="SP-TEST-1",
    SEPAY_SECRET_KEY="spsk_test_secret", SEPAY_IPN_SECRET_KEY="ipn-secret",
    SEPAY_PAYMENT_CODE_PREFIX="TT", WEB_APP_BASE_URL="http://localhost:3001",
    SITE_DATABASE_ALIASES={"Q1": "site_q1"},
)


@override_settings(**SEPAY)
class GatewaySigningTests(SimpleTestCase):
    def test_signature_matches_sdk_algorithm_and_field_order(self):
        checkout = sepay_gateway.build_checkout(
            invoice="TTQ1ABCDEF123456", amount=1500000, description="Hoc phi Q1-HP-000001",
            return_urls={"success": "http://s", "error": "http://e", "cancel": "http://c"},
        )
        self.assertEqual(checkout["action"], "https://pay-sandbox.sepay.vn/v1/checkout/init")
        fields = checkout["fields"]
        self.assertEqual(list(fields), [
            "merchant", "currency", "order_amount", "operation", "order_description",
            "order_invoice_number", "success_url", "error_url", "cancel_url", "signature",
        ])
        signed = ("merchant=SP-TEST-1,currency=VND,order_amount=1500000,operation=PURCHASE,"
                  "order_description=Hoc phi Q1-HP-000001,order_invoice_number=TTQ1ABCDEF123456,"
                  "success_url=http://s,error_url=http://e,cancel_url=http://c")
        expected = base64.b64encode(hmac.new(b"spsk_test_secret", signed.encode(), hashlib.sha256).digest()).decode()
        self.assertEqual(fields["signature"], expected)

    @override_settings(SEPAY_ENV="production")
    def test_production_host(self):
        checkout = sepay_gateway.build_checkout(invoice="X", amount=1, description="d",
                                                return_urls={"success": "s", "error": "e", "cancel": "c"})
        self.assertEqual(checkout["action"], "https://pay.sepay.vn/v1/checkout/init")

    def test_money_parsing(self):
        self.assertEqual(sepay_gateway.money("100000.00"), 100000)
        self.assertEqual(sepay_gateway.money(250000), 250000)
        for bad in ("10.5", "-1", True, None, "abc"):
            self.assertIsNone(sepay_gateway.money(bad))

    def test_order_lookup_404_means_no_order(self):
        error = HTTPError("u", 404, "Not Found", {}, io.BytesIO(b"{}"))
        with patch.object(sepay_gateway, "urlopen", side_effect=error):
            self.assertIsNone(sepay_gateway.fetch_order("TTQ1ABCDEF123456"))
        with patch.object(sepay_gateway, "urlopen", side_effect=HTTPError("u", 500, "x", {}, io.BytesIO(b""))):
            with self.assertRaises(sepay_gateway.GatewayUnavailable):
                sepay_gateway.fetch_order("TTQ1ABCDEF123456")

    def test_ipn_key_is_compared_exactly(self):
        self.assertTrue(sepay_gateway.ipn_key_valid("ipn-secret"))
        self.assertFalse(sepay_gateway.ipn_key_valid("ipn-secret "))
        self.assertFalse(sepay_gateway.ipn_key_valid(None))


@override_settings(**SEPAY)
class PaymentOptionTests(SimpleTestCase):
    def test_options_next_half_full(self):
        rows = [("D1", 3000000, 3000000), ("D2", 3000000, 1000000), ("D3", 3000000, 0)]
        self.assertEqual(sepay.payment_options(5000000, rows),
                         {"next_installment": 2000000, "half": 2500000, "full": 5000000})
        self.assertEqual(sepay.payment_options(5, [("D1", 5, 0)])["half"], 3)  # rounds up to whole VND
        self.assertEqual(sepay.payment_options(0, rows), {})

    def test_reference_routes_to_site_and_event_id_is_stable(self):
        self.assertEqual(sepay.site_from_reference("TTQ1ABCDEF123456"), "Q1")
        self.assertIsNone(sepay.site_from_reference("TTQ7ABCDEF123456"))
        event = sepay.gateway_event_id("TTQ1ABCDEF123456")
        self.assertLess(event, 0)
        self.assertEqual(event, sepay.gateway_event_id("TTQ1ABCDEF123456"))


class _Cursor:
    def __init__(self, db):
        self.db, self.cur = db, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        sql = " ".join(sql.split()).replace(" WITH (UPDLOCK, HOLDLOCK)", "")
        sql = sql.replace("SYSUTCDATETIME()", "CURRENT_TIMESTAMP")
        top = re.search(r"SELECT TOP \((\d+)\)", sql)
        if top:
            sql = re.sub(r"SELECT TOP \(\d+\)", "SELECT", sql, count=1) + f" LIMIT {top[1]}"
        self.cur = self.db.execute(sql.replace("%s", "?"), list(params))

    @property
    def rowcount(self):
        return self.cur.rowcount

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()


@override_settings(**SEPAY)
class SettlementTests(SimpleTestCase):
    reference = "TTQ1ABCDEF123456"

    def setUp(self):
        db = sqlite3.connect(":memory:", isolation_level=None)
        self.db = db
        self.addCleanup(db.close)
        db.execute("ATTACH DATABASE ':memory:' AS dbo")
        db.executescript("""
            CREATE TABLE dbo.HocPhi (ma_hoc_phi, ma_co_so, so_tien_phai_dong, giam_gia, so_tien_da_dong, trang_thai);
            CREATE TABLE dbo.DotHocPhi (ma_dot_hoc_phi, ma_co_so, ma_hoc_phi, so_thu_tu, so_tien_phai_dong, so_tien_da_dong, trang_thai);
            CREATE TABLE dbo.YeuCauThanhToan (ma_yeu_cau, ma_co_so, ma_hoc_phi, ma_dot_hoc_phi, ma_tai_khoan, so_tien,
                ma_tham_chieu, khoa_idempotency, trang_thai, tao_luc_utc, het_han_utc, cap_nhat_luc_utc, thanh_toan_luc_utc);
            CREATE TABLE dbo.PhieuThu (ma_phieu, ma_co_so, ma_hoc_phi, ma_yeu_cau, loai, so_tien, hinh_thuc, ngay_thu, ma_nhan_vien, ghi_chu);
            CREATE TABLE dbo.SuKienThanhToan (ma_co_so, ma_yeu_cau, ma_giao_dich_sepay UNIQUE, ma_tham_chieu, so_tien,
                tai_khoan_nhan, ma_tham_chieu_ngan_hang, thoi_diem_giao_dich, ket_qua);
            INSERT INTO dbo.HocPhi VALUES ('HP1', 'Q1', 6000000, 0, 0, 'chua_dong');
            INSERT INTO dbo.DotHocPhi VALUES ('D1', 'Q1', 'HP1', 1, 3000000, 0, 'chua_dong'),
                                             ('D2', 'Q1', 'HP1', 2, 3000000, 0, 'chua_dong');
        """)
        db.execute(
            "INSERT INTO dbo.YeuCauThanhToan VALUES ('Q1-SP-000001','Q1','HP1','D1','TK1',4500000,?, 'k', "
            "'cho_thanh_toan','2026-11-25 10:00:00','2026-11-25 10:15:00','2026-11-25 10:00:00',NULL)",
            [self.reference],
        )
        conn = SimpleNamespace(cursor=lambda: _Cursor(db))
        self.enterContext(patch.object(sepay, "connections", {"site_q1": conn}))
        self.enterContext(patch.object(sepay, "get_site_database_alias", return_value="site_q1"))
        self.enterContext(patch.object(sepay.transaction, "atomic", side_effect=self._atomic))
        self.enterContext(patch.object(sepay, "acquire_record_lock"))
        self.enterContext(patch.object(sepay, "append_audit"))
        self.enterContext(patch.object(sepay, "next_id", return_value="Q1-PT-000009"))
        self.email = self.enterContext(patch.object(sepay, "send_tuition_invoice_email"))

    @contextmanager
    def _atomic(self, *, using):
        self.db.execute("BEGIN")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def _one(self, sql):
        return self.db.execute(sql).fetchone()

    def test_paid_signal_records_one_receipt_and_spreads_over_installments(self):
        result = sepay._record_paid("Q1", self.reference, 4500000, provider_ref="ORD-1", paid_at=None)
        self.assertEqual(result["status"], "da_ghi_nhan")
        self.assertEqual(self._one("SELECT so_tien_da_dong, trang_thai FROM dbo.HocPhi"), (4500000, "dong_mot_phan"))
        self.assertEqual(self.db.execute("SELECT so_tien_da_dong FROM dbo.DotHocPhi ORDER BY so_thu_tu").fetchall(),
                         [(3000000,), (1500000,)])
        self.assertEqual(self._one("SELECT trang_thai FROM dbo.YeuCauThanhToan"), ("da_thanh_toan",))
        self.email.assert_called_once()

        again = sepay._record_paid("Q1", self.reference, 4500000, provider_ref="ORD-1", paid_at=None)
        self.assertEqual(again["status"], "duplicate")  # IPN after order lookup (or IPN retry)
        self.assertEqual(self._one("SELECT COUNT(*) FROM dbo.PhieuThu"), (1,))

    def test_amount_mismatch_is_held_for_review_without_receipt(self):
        result = sepay._record_paid("Q1", self.reference, 4000000, provider_ref="ORD-1", paid_at=None)
        self.assertEqual(result["status"], "can_doi_soat")
        self.assertEqual(self._one("SELECT COUNT(*) FROM dbo.PhieuThu"), (0,))
        self.assertEqual(self._one("SELECT trang_thai FROM dbo.YeuCauThanhToan"), ("can_doi_soat",))
        self.assertEqual(self._one("SELECT so_tien_da_dong FROM dbo.HocPhi"), (0,))

    def test_late_payment_on_expired_attempt_is_still_recorded(self):
        self.db.execute("UPDATE dbo.YeuCauThanhToan SET trang_thai = 'het_han'")
        self.assertEqual(sepay._record_paid("Q1", self.reference, 4500000, "ORD-1", None)["status"], "da_ghi_nhan")

    def test_ipn_payload_is_parsed_and_settled(self):
        payload = {
            "notification_type": "ORDER_PAID",
            "order": {"order_invoice_number": self.reference, "order_amount": "4500000.00", "order_currency": "VND"},
            "transaction": {"transaction_id": "T-1", "transaction_status": "APPROVED", "transaction_date": "2026-11-25 10:05:00"},
        }
        self.assertEqual(sepay.process_gateway_ipn(payload)["status"], "da_ghi_nhan")
        self.assertEqual(sepay.process_gateway_ipn({**payload, "notification_type": "TRANSACTION_VOID"})["status"],
                         "ignored_notification_type")


@override_settings(**SEPAY)
class IpnViewTests(SimpleTestCase):
    def _post(self, key):
        request = APIRequestFactory().post("/api/v1/webhooks/sepay/", data=json.dumps({"order": {}}),
                                           content_type="application/json", HTTP_X_SECRET_KEY=key)
        return sepay_views.SePayWebhookView.as_view()(request)

    def test_wrong_key_is_rejected_and_right_key_is_processed(self):
        with patch.object(sepay_views, "process_gateway_ipn", return_value={"status": "x"}) as process:
            self.assertEqual(self._post("wrong").status_code, 401)
            process.assert_not_called()
            self.assertEqual(self._post("ipn-secret").status_code, 200)
            process.assert_called_once()
