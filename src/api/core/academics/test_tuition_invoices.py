from datetime import datetime

from django.test import SimpleTestCase

from core.academics.serializers import TuitionInvoiceSerializer
from core.academics.tuition_invoices import _format_vnd, render_invoice_email


class TuitionInvoiceRenderingTests(SimpleTestCase):
    def setUp(self):
        self.invoice = {
            "document_type": "bien_nhan_hoc_phi_noi_bo",
            "invoice_number": "Q1-PT-000001",
            "site_code": "Q1",
            "branch_name": "Cơ sở Quận 1",
            "branch_address": "Đường A",
            "branch_phone": "0900000000",
            "tuition_id": "Q1-HP-000001",
            "student_id": "Q1-HV-000001",
            "student_name": 'Nguyễn An <script>alert("x")</script>',
            "student_email": "an@example.test",
            "course_name": "Tiếng Anh giao tiếp",
            "class_name": "Giao tiếp A1",
            "total_due": 12000000,
            "discount": 0,
            "net_total": 12000000,
            "amount_received": 4000000,
            "currency": "VND",
            "payment_method": "tien_mat",
            "payment_method_label": "Tiền mặt",
            "paid_at": "2026-10-29T13:00:00+07:00",
            "paid_at_display": "29/10/2026 13:00:00",
            "cashier_name": "Nhân viên thu ngân",
            "note": None,
        }

    def test_invoice_serializer_accepts_internal_receipt_payload(self):
        serializer = TuitionInvoiceSerializer(data=self.invoice)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["payment_method"], "tien_mat")

    def test_invoice_response_serializes_vietnamese_offset(self):
        payload = {**self.invoice, "paid_at": datetime.fromisoformat(self.invoice["paid_at"])}
        serialized = TuitionInvoiceSerializer(instance=payload).data
        self.assertEqual(serialized["paid_at"], "2026-10-29T13:00:00+07:00")

    def test_email_is_vietnamese_html_and_escapes_student_supplied_text(self):
        text_body, html_body = render_invoice_email(self.invoice)
        self.assertIn("Số tiền thu lần này: 4.000.000 ₫", text_body)
        self.assertIn("&lt;script&gt;", html_body)
        self.assertNotIn("<script>", html_body)
        self.assertIn("không phải hóa đơn điện tử thuế", html_body)

    def test_vnd_amount_uses_vietnamese_grouping(self):
        self.assertEqual(_format_vnd(123456789), "123.456.789 ₫")
