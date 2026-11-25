"""Regression checks with mocked writes and disposable in-memory read fixtures."""

import sqlite3
from contextlib import ExitStack, nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core.academics import attendance, tuition
from core.academics.common import AcademicNotFound
from core.academics.serializers import TuitionReceiptSerializer
from core.classes import services as classes


class TuitionReceiptRegressionTests(SimpleTestCase):
    def test_receipt_key_accounts_for_site_prefix(self):
        for site in ("Q1", "Q7", "TD", "SITE123456"):
            maximum = 24 - len(site) - 4
            for length, valid in ((8, True), (maximum, True), (maximum + 1, False)):
                with self.subTest(site=site, length=length):
                    serializer = TuitionReceiptSerializer(
                        data={"idempotency_key": "a" * length, "amount": 200000, "payment_method": "tien_mat"},
                        context={"site_code": site},
                    )
                    self.assertEqual(serializer.is_valid(), valid, serializer.errors)

    def test_api_rejects_oversized_key_before_collecting(self):
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(
            is_authenticated=True, role="ke_toan", site_code="Q1", account_id="TK", profile_id="NV", pk="TK",
        ))
        with patch("core.academics.tuition_views.collect_tuition") as collect:
            response = client.post(
                reverse("core:tuition-receipt-create", kwargs={"tuition_id": "Q1-HP-000001"}),
                {"idempotency_key": "a" * 24, "amount": 200000, "payment_method": "tien_mat"},
                format="json",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("idempotency_key", response.json())
        collect.assert_not_called()

    def test_collecting_with_fitting_key_and_replaying_creates_one_receipt(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.rowcount = 1
        cursor.fetchone.side_effect = [
            (1000000, 0, 0, "chua_dong"), None,
            ("Q1-HV-000001",), None,  # fee owner, no open transfer
            (1000000, 0, 200000, "dong_mot_phan"),
            ("Q1-HP-000001", "thu", 200000, "tien_mat", "NV", None),
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with ExitStack() as stack:
            stack.enter_context(patch.object(tuition, "require_active_site", return_value="fake"))
            stack.enter_context(patch.object(tuition, "connections", {"fake": connection}))
            stack.enter_context(patch.object(tuition.transaction, "atomic", side_effect=lambda **_: nullcontext()))
            for name in ("_verify_cashier", "allocate_payment_to_installments", "append_audit"):
                stack.enter_context(patch.object(tuition, name))
            kwargs = dict(site_code="Q1", tuition_id="Q1-HP-000001", actor_id="TK", employee_id="NV",
                          role="ke_toan", idempotency_key="a" * 18, amount=200000,
                          payment_method="tien_mat", note=None, remote_ip="")
            first = tuition.collect_tuition(**kwargs)
            replay = tuition.collect_tuition(**kwargs)
        self.assertEqual(len(first["receipt_id"]), 24)
        self.assertEqual(first["receipt_id"], replay["receipt_id"])
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(sum("INSERT INTO dbo.PhieuThu" in call.args[0] for call in cursor.execute.call_args_list), 1)

    def test_refund_replay_uses_original_receipt_for_remaining_amount(self):
        for refunded in (200000, 500000, 1000000):
            with self.subTest(refunded=refunded):
                cursor = MagicMock()
                cursor.__enter__.return_value = cursor
                cursor.fetchone.side_effect = [
                    (1000000, 0, 1000000 - refunded, "dong_mot_phan"),
                    ("Q1-PT-000002", "Q1-HP-000001", "Q1-PT-000001", 200000, "tien_mat", "NV", "reason"),
                    (1000000,), (refunded,),
                ]
                connection = MagicMock()
                connection.cursor.return_value = cursor
                with ExitStack() as stack:
                    stack.enter_context(patch.object(tuition, "require_active_site", return_value="fake"))
                    stack.enter_context(patch.object(tuition, "connections", {"fake": connection}))
                    stack.enter_context(patch.object(tuition.transaction, "atomic", return_value=nullcontext()))
                    stack.enter_context(patch.object(tuition, "_verify_cashier"))
                    stack.enter_context(patch.object(tuition, "acquire_record_lock"))
                    result = tuition.refund_tuition(
                        site_code="Q1", tuition_id="Q1-HP-000001", receipt_id="Q1-PT-000001",
                        actor_id="TK", employee_id="NV", role="ke_toan", idempotency_key="key",
                        amount=200000, payment_method="tien_mat", reason="reason", remote_ip="",
                    )
                self.assertEqual(result["refundable_amount"], 1000000 - refunded)
                self.assertTrue(result["replayed"])
                self.assertFalse(any(call.args[0].lstrip().startswith(("INSERT", "UPDATE")) for call in cursor.execute.call_args_list))


class ClassHistoryRegressionTests(SimpleTestCase):
    def test_class_move_without_learning_history_keeps_working(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.rowcount = 1
        cursor.fetchone.side_effect = [
            ("HV", "OLD", "dang_hoc", "dang_hoc"), None,
            ("KH", 1, 20, None, "dang_hoc"),
            ("KH", 0, 20, None, None, "dang_hoc"),
            (1,), (0,), None, None,
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with ExitStack() as stack:
            stack.enter_context(patch.object(classes, "get_site_database_alias", return_value="fake"))
            stack.enter_context(patch.object(classes, "connections", {"fake": connection}))
            stack.enter_context(patch.object(classes.transaction, "atomic", return_value=nullcontext()))
            for name in ("_active_site", "_acquire_named_lock", "_lock_class_rows", "_audit"):
                stack.enter_context(patch.object(classes, name))
            result = classes.assign_enrollment_to_class(site_code="Q1", enrollment_id="DK", target_class_id="NEW", actor_id="TK", remote_ip="")
        self.assertTrue(result["changed"])
        self.assertEqual(result["current_count"], 1)
        self.assertEqual(result["previous_class_current_count"], 0)

    def test_class_move_rejects_existing_learning_history_before_writing(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.side_effect = [("HV", "OLD", "dang_hoc", "dang_hoc"), (1,)]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with ExitStack() as stack:
            stack.enter_context(patch.object(classes, "get_site_database_alias", return_value="fake"))
            stack.enter_context(patch.object(classes, "connections", {"fake": connection}))
            stack.enter_context(patch.object(classes.transaction, "atomic", return_value=nullcontext()))
            stack.enter_context(patch.object(classes, "_active_site"))
            stack.enter_context(patch.object(classes, "_acquire_named_lock"))
            with self.assertRaisesMessage(classes.ClassConflict, "lịch sử"):
                classes.assign_enrollment_to_class(site_code="Q1", enrollment_id="DK", target_class_id="NEW", actor_id="TK", remote_ip="")
        queries = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertIn("dbo.DiemDanh", queries[-1])
        self.assertIn("dbo.Diem ", queries[-1])
        self.assertFalse(any(sql.lstrip().startswith(("INSERT", "UPDATE")) for sql in queries))

    def test_same_class_remains_an_idempotent_noop(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.side_effect = [("HV", "OLD", "dang_hoc", "dang_hoc"), (1, 20)]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with ExitStack() as stack:
            stack.enter_context(patch.object(classes, "get_site_database_alias", return_value="fake"))
            stack.enter_context(patch.object(classes, "connections", {"fake": connection}))
            stack.enter_context(patch.object(classes.transaction, "atomic", return_value=nullcontext()))
            stack.enter_context(patch.object(classes, "_active_site"))
            stack.enter_context(patch.object(classes, "_acquire_named_lock"))
            result = classes.assign_enrollment_to_class(site_code="Q1", enrollment_id="DK", target_class_id="OLD", actor_id="TK", remote_ip="")
        self.assertFalse(result["changed"])


class TeacherHistoryRegressionTests(SimpleTestCase):
    """Execute production read SQL using SQLite; no SQL Server connections."""

    def setUp(self):
        memory = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        self.addCleanup(memory.close)
        memory.execute("ATTACH DATABASE ':memory:' AS dbo")
        memory.executescript("""
            CREATE TABLE dbo.LopHoc(ma_lop, ma_co_so, ma_giao_vien, ten_lop, ma_khoa_hoc,
                si_so_hien_tai, si_so_toi_da, ngay_khai_giang, ngay_ket_thuc, trang_thai);
            CREATE TABLE dbo.KhoaHoc(ma_khoa_hoc, ten_khoa_hoc);
            CREATE TABLE dbo.GiaoVien(ma_giao_vien, ma_co_so, trang_thai);
            CREATE TABLE dbo.BuoiHoc(ma_buoi, ma_lop, ma_co_so, ma_giao_vien,
                so_thu_tu, ngay_hoc DATE, gio_bat_dau, gio_ket_thuc, ma_phong, trang_thai, ghi_chu);
            CREATE TABLE dbo.PhongHoc(ma_phong, ma_co_so, ten_phong);
            CREATE TABLE dbo.DangKy(ma_dang_ky, ma_hoc_vien, ma_co_so, ma_lop, trang_thai);
            CREATE TABLE dbo.HocVien(ma_hoc_vien, ma_co_so, slug, ho_ten);
            CREATE TABLE dbo.DiemDanh(ma_buoi, ma_dang_ky, ma_co_so, trang_thai, ghi_chu);
            INSERT INTO dbo.LopHoc VALUES ('L1','Q1','NEW','Class','K1',1,20,'2026-11-01','2026-12-01','dang_hoc');
            INSERT INTO dbo.KhoaHoc VALUES ('K1','Course');
            INSERT INTO dbo.GiaoVien VALUES ('OLD','Q1','dang_day'), ('NEW','Q1','dang_day'), ('OTHER','Q1','dang_day');
            INSERT INTO dbo.BuoiHoc VALUES ('B1','L1','Q1','OLD',1,'2026-11-01','08:00','09:00','P1','da_hoc',NULL);
            INSERT INTO dbo.BuoiHoc VALUES ('B2','L1','Q1','NEW',2,'2026-11-02','08:00','09:00','P1','da_hoc',NULL);
            INSERT INTO dbo.PhongHoc VALUES ('P1','Q1','Room');
            INSERT INTO dbo.DangKy VALUES ('D1','H1','Q1','L1','dang_hoc');
            INSERT INTO dbo.HocVien VALUES ('H1','Q1','student','Student');
            INSERT INTO dbo.DiemDanh VALUES ('B1','D1','Q1','co_mat',NULL);
        """)

        class MemoryCursor:
            def __init__(self): self.inner = memory.cursor()
            def __enter__(self): return self
            def __exit__(self, *_): self.inner.close()
            def execute(self, sql, params=()):
                return self.inner.execute(sql.replace("%s", "?").replace(" WITH (UPDLOCK, HOLDLOCK)", ""), params)
            def fetchone(self): return self.inner.fetchone()
            def fetchall(self): return self.inner.fetchall()
            @property
            def description(self): return self.inner.description

        self.enterContext(patch.object(attendance, "require_active_site", return_value="memory"))
        self.enterContext(patch.object(attendance, "connections", {"memory": SimpleNamespace(cursor=MemoryCursor)}))

    def test_current_teacher_reads_old_sessions_and_roster_read_only(self):
        self.assertEqual(len(attendance.list_teacher_classes(site_code="Q1", teacher_id="NEW")), 1)
        sessions = attendance.list_teacher_sessions(site_code="Q1", teacher_id="NEW", class_id="L1")
        self.assertEqual([row["can_edit_attendance"] for row in sessions], [False, True])
        roster = attendance.get_attendance_roster(site_code="Q1", teacher_id="NEW", session_id="B1")
        self.assertFalse(roster["can_edit_attendance"])
        self.assertEqual(roster["results"][0]["attendance_status"], "co_mat")
        self.assertTrue(attendance.get_attendance_roster(site_code="Q1", teacher_id="NEW", session_id="B2")["can_edit_attendance"])

    def test_previous_unassigned_and_cross_site_teachers_cannot_read_history(self):
        for site, teacher in (("Q1", "OLD"), ("Q1", "OTHER"), ("Q7", "NEW")):
            with self.subTest(site=site, teacher=teacher):
                self.assertEqual(attendance.list_teacher_sessions(site_code=site, teacher_id=teacher, class_id="L1"), [])
                with self.assertRaises(AcademicNotFound):
                    attendance.get_attendance_roster(site_code=site, teacher_id=teacher, session_id="B1")

    def test_replacement_teacher_cannot_write_attendance_for_old_teacher(self):
        with patch.object(attendance.transaction, "atomic", return_value=nullcontext()), patch.object(attendance, "acquire_record_lock"):
            with self.assertRaises(AcademicNotFound):
                attendance.save_attendance_batch(site_code="Q1", teacher_id="NEW", actor_id="TK", session_id="B1", items=[], remote_ip="")
