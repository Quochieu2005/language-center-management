"""Exercise return transfers on separate disposable in-memory site databases."""

import itertools
import re
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.academics import transfers
from core.academics.common import AcademicConflict, AcademicInfrastructureUnavailable


class ReturnTransferTests(SimpleTestCase):
    source = "Q7"
    target = "Q1"
    student = "Q1-HV-000001"
    transfer = "Q7-CC-000002"

    def setUp(self):
        self.sites = {}
        for site in ("Q1", "Q7"):
            db = sqlite3.connect(":memory:", isolation_level=None, detect_types=sqlite3.PARSE_DECLTYPES)
            self.sites[site] = db
            self.addCleanup(db.close)
            db.execute("ATTACH DATABASE ':memory:' AS dbo")
            db.executescript("""
                CREATE TABLE dbo.HocVien (ma_hoc_vien PRIMARY KEY, slug UNIQUE, ma_co_so,
                    co_so_goc, ma_tai_khoan, ho_ten, ngay_sinh DATE, gioi_tinh, sdt, email,
                    dia_chi, ngay_nhap_hoc DATE, avatar_public_id, avatar_secure_url, trang_thai);
                CREATE TABLE dbo.GiaoDichChuyenCoSo (ma_chuyen PRIMARY KEY, ma_hoc_vien,
                    co_so_nguon, co_so_dich, trang_thai, buoc_cuoi, ma_tai_khoan_quyet_dinh,
                    cap_nhat_luc, loi_cuoi);
                CREATE TABLE dbo.LichSuChuyenCoSo (ma_su_kien PRIMARY KEY, ma_chuyen,
                    ma_hoc_vien, co_so_nguon, co_so_dich, site_ghi, su_kien,
                    ma_tai_khoan_thuc_hien, chi_tiet);
                CREATE TABLE dbo.LopHoc (ma_lop PRIMARY KEY, ma_co_so, si_so_hien_tai);
                CREATE TABLE dbo.DangKy (ma_dang_ky PRIMARY KEY, ma_hoc_vien, ma_co_so, ma_lop, trang_thai);
                CREATE TABLE dbo.Diem (ma_diem, ma_dang_ky, diem_so);
                CREATE TABLE dbo.DiemDanh (ma_diem_danh, ma_dang_ky, trang_thai);
                CREATE TABLE dbo.HocPhi (ma_hoc_phi, ma_dang_ky, so_tien_da_dong);
                CREATE TABLE dbo.PhieuThu (ma_phieu, ma_hoc_phi, so_tien);
                CREATE TABLE dbo.ThongBao (slug, event_key UNIQUE, ma_co_so, danh_muc, muc_do,
                    doi_tuong, tieu_de, noi_dung, duong_dan);
            """)
            db.execute("INSERT INTO dbo.HocVien VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                self.student, "original-slug" if site == "Q1" else "current-slug", site, "Q1", "ACCOUNT",
                "Old name" if site == "Q1" else "Current name", None, None, None, "student@example.com",
                "Old address" if site == "Q1" else "Current address", "2026-01-01", None, None,
                "da_chuyen_di" if site == "Q1" else "dang_hoc",
            ))
        self.sites["Q1"].executescript("""
            INSERT INTO dbo.GiaoDichChuyenCoSo VALUES ('Q1-CC-000001','Q1-HV-000001','Q1','Q7','hoan_tat','hoan_tat','TK',NULL,NULL);
            INSERT INTO dbo.LichSuChuyenCoSo VALUES ('OLD-EVENT','Q1-CC-000001','Q1-HV-000001','Q1','Q7','Q1','cap_nhat_ho_so_nguon','TK',NULL);
            INSERT INTO dbo.DangKy VALUES ('OLD-DK','Q1-HV-000001','Q1','OLD-LH','chuyen_di');
            INSERT INTO dbo.Diem VALUES ('OLD-DIEM','OLD-DK',8);
            INSERT INTO dbo.DiemDanh VALUES ('OLD-DD','OLD-DK','co_mat');
            INSERT INTO dbo.HocPhi VALUES ('OLD-HP','OLD-DK',1000000);
            INSERT INTO dbo.PhieuThu VALUES ('OLD-PT','OLD-HP',1000000);
        """)
        self.sites["Q7"].executescript("""
            INSERT INTO dbo.GiaoDichChuyenCoSo VALUES ('Q7-CC-000002','Q1-HV-000001','Q7','Q1','dang_xu_ly','da_tiep_nhan','TK',NULL,NULL);
            INSERT INTO dbo.LopHoc VALUES ('CURRENT-LH','Q7',1);
            INSERT INTO dbo.DangKy VALUES ('CURRENT-DK','Q1-HV-000001','Q7','CURRENT-LH','dang_hoc');
        """)
        sequence = itertools.count(1)
        self.enterContext(patch.object(transfers, "require_active_site", side_effect=lambda site: site))
        self.enterContext(patch.object(transfers, "get_site_database_alias", side_effect=lambda site: site))
        self.enterContext(patch.object(transfers, "connections", {
            site: SimpleNamespace(cursor=lambda site=site: self.cursor(site)) for site in self.sites
        }))
        self.enterContext(patch.object(transfers.transaction, "atomic", side_effect=self.atomic))
        self.enterContext(patch.object(transfers, "acquire_record_lock"))
        self.enterContext(patch.object(transfers, "_active_destination"))
        self.enterContext(patch.object(transfers, "next_id", side_effect=lambda cursor, site, kind: f"{site}-LS-{next(sequence):06d}"))
        self.audit = self.enterContext(patch.object(transfers, "_audit_transfer"))

    @contextmanager
    def atomic(self, *, using):
        db = self.sites[using]
        db.execute("BEGIN")
        try:
            yield
        except Exception:
            db.execute("ROLLBACK")
            raise
        else:
            db.execute("COMMIT")

    def cursor(self, site):
        db = self.sites[site]

        class Cursor:
            def __init__(self): self.inner = db.cursor()
            def __enter__(self): return self
            def __exit__(self, *_): self.inner.close()
            def execute(self, sql, params=()):
                sql = " ".join(sql.split())
                if sql.startswith("IF NOT EXISTS"):
                    # Model the publisher's unique event key; SQL Server locking is tested separately.
                    return self.inner.execute(
                        "INSERT OR IGNORE INTO dbo.ThongBao VALUES (?,?,?,?,?,?,?,?,?)", params[1:],
                    )
                sql = sql.replace(" WITH (UPDLOCK, HOLDLOCK)", "").replace("SYSUTCDATETIME()", "CURRENT_TIMESTAMP").replace("COUNT_BIG(", "COUNT(")
                top = re.search(r"SELECT TOP \((\d+)\)", sql)
                if top:
                    sql = re.sub(r"SELECT TOP \(\d+\)", "SELECT", sql, count=1) + f" LIMIT {top[1]}"
                return self.inner.execute(sql.replace("%s", "?"), params)
            def fetchone(self): return self.inner.fetchone()
            def fetchall(self): return self.inner.fetchall()
            @property
            def rowcount(self): return self.inner.rowcount

        return Cursor()

    def snapshot(self):
        return transfers._transfer_snapshot("Q7", self.transfer)

    def history(self):
        db = self.sites["Q1"]
        return {name: db.execute(f"SELECT * FROM dbo.{name}").fetchall()
                for name in ("DangKy", "Diem", "DiemDanh", "HocPhi", "PhieuThu")}

    def test_return_reuses_profile_and_preserves_history_slug_and_account(self):
        before = self.history()
        result = transfers.execute_approved_transfer(source_site="Q7", transfer_id=self.transfer, actor_id="TK")
        self.assertTrue(result["complete"])
        self.assertEqual(self.history(), before)
        row = self.sites["Q1"].execute("SELECT slug, ma_tai_khoan, ho_ten, dia_chi, trang_thai FROM dbo.HocVien").fetchone()
        self.assertEqual(row, ("original-slug", "ACCOUNT", "Current name", "Current address", "dang_hoc"))
        self.assertEqual(self.sites["Q7"].execute("SELECT trang_thai FROM dbo.HocVien").fetchone()[0], "da_chuyen_di")
        self.assertEqual(self.sites["Q7"].execute("SELECT si_so_hien_tai FROM dbo.LopHoc").fetchone()[0], 0)
        self.assertTrue(any(call.kwargs["action"] == "tiep_nhan_lai_hoc_vien" for call in self.audit.call_args_list))
        events = self.sites["Q1"].execute("SELECT COUNT(*) FROM dbo.LichSuChuyenCoSo").fetchone()[0]
        self.assertTrue(transfers.retry_transfer(source_site="Q7", transfer_id=self.transfer, actor_id="TK")["complete"])
        self.assertEqual(self.sites["Q1"].execute("SELECT COUNT(*) FROM dbo.HocVien").fetchone()[0], 1)
        self.assertEqual(self.sites["Q1"].execute("SELECT COUNT(*) FROM dbo.ThongBao").fetchone()[0], 1)
        self.assertEqual(self.sites["Q1"].execute("SELECT COUNT(*) FROM dbo.LichSuChuyenCoSo").fetchone()[0], events)

    def test_retry_after_destination_commit_completes_without_duplicate_reception(self):
        checkpoint = transfers._checkpoint_source
        failed = False

        def fail_once(snapshot, actor_id, step, status=None):
            nonlocal failed
            if not failed and step == "da_tao_ho_so_dich":
                failed = True
                raise AcademicInfrastructureUnavailable
            return checkpoint(snapshot, actor_id, step, status)

        before = self.history()
        with patch.object(transfers, "_checkpoint_source", side_effect=fail_once):
            with self.assertRaises(AcademicInfrastructureUnavailable):
                transfers.execute_approved_transfer(source_site="Q7", transfer_id=self.transfer, actor_id="TK")
        self.assertEqual(self.sites["Q1"].execute("SELECT trang_thai FROM dbo.HocVien").fetchone()[0], "bao_luu")
        self.assertEqual(self.sites["Q7"].execute("SELECT trang_thai FROM dbo.HocVien").fetchone()[0], "dang_hoc")
        self.assertTrue(transfers.retry_transfer(source_site="Q7", transfer_id=self.transfer, actor_id="TK")["complete"])
        self.assertEqual(self.history(), before)
        self.assertEqual(self.sites["Q1"].execute("SELECT COUNT(*) FROM dbo.LichSuChuyenCoSo WHERE ma_chuyen=? AND su_kien='tao_ho_so_dich'", (self.transfer,)).fetchone()[0], 1)
        self.assertEqual(self.sites["Q1"].execute("SELECT COUNT(*) FROM dbo.ThongBao").fetchone()[0], 1)

    def test_old_profile_without_account_accepts_account_issued_after_departure(self):
        self.sites["Q1"].execute("UPDATE dbo.HocVien SET ma_tai_khoan=NULL")
        transfers._create_destination_profile(self.snapshot(), "TK")
        self.assertEqual(self.sites["Q1"].execute("SELECT ma_tai_khoan, trang_thai FROM dbo.HocVien").fetchone(), ("ACCOUNT", "bao_luu"))

    def test_repeated_round_trips_keep_the_same_profiles_and_old_records(self):
        before = self.history()
        self.assertTrue(transfers.execute_approved_transfer(source_site="Q7", transfer_id=self.transfer, actor_id="TK")["complete"])
        for source, target, transfer_id in (("Q1", "Q7", "Q1-CC-000003"), ("Q7", "Q1", "Q7-CC-000004")):
            self.sites[source].execute(
                "INSERT INTO dbo.GiaoDichChuyenCoSo VALUES (?,?,?,?,?,?,?,?,?)",
                (transfer_id, self.student, source, target, "dang_xu_ly", "da_tiep_nhan", "TK", None, None),
            )
            self.assertTrue(transfers.execute_approved_transfer(source_site=source, transfer_id=transfer_id, actor_id="TK")["complete"])
        self.assertEqual(self.history(), before)
        for site, status in (("Q1", "dang_hoc"), ("Q7", "da_chuyen_di")):
            rows = self.sites[site].execute("SELECT ma_hoc_vien, ma_tai_khoan, trang_thai FROM dbo.HocVien").fetchall()
            self.assertEqual(rows, [(self.student, "ACCOUNT", status)])

    def test_wrong_identity_or_unowned_active_profile_is_not_overwritten(self):
        for column, value in (("ma_tai_khoan", "OTHER"), ("co_so_goc", "TD"), ("trang_thai", "dang_hoc")):
            with self.subTest(column=column):
                self.sites["Q1"].execute("UPDATE dbo.HocVien SET ma_tai_khoan='ACCOUNT', co_so_goc='Q1', trang_thai='da_chuyen_di'")
                self.sites["Q1"].execute(f"UPDATE dbo.HocVien SET {column}=?", (value,))
                before = self.sites["Q1"].execute("SELECT * FROM dbo.HocVien").fetchall()
                with self.assertRaises(AcademicConflict):
                    transfers._create_destination_profile(self.snapshot(), "TK")
                self.assertEqual(self.sites["Q1"].execute("SELECT * FROM dbo.HocVien").fetchall(), before)

    def test_missing_departure_evidence_or_previous_open_transfer_is_rejected(self):
        db = self.sites["Q1"]
        db.execute("DELETE FROM dbo.LichSuChuyenCoSo")
        with self.assertRaises(AcademicConflict):
            transfers._create_destination_profile(self.snapshot(), "TK")
        db.execute("INSERT INTO dbo.LichSuChuyenCoSo VALUES ('OLD','Q1-CC-000001','Q1-HV-000001','Q1','Q7','Q1','cap_nhat_ho_so_nguon','TK',NULL)")
        db.execute("UPDATE dbo.GiaoDichChuyenCoSo SET trang_thai='dang_xu_ly'")
        with self.assertRaises(AcademicConflict):
            transfers._create_destination_profile(self.snapshot(), "TK")
        self.assertEqual(db.execute("SELECT trang_thai FROM dbo.HocVien").fetchone()[0], "da_chuyen_di")

    def test_reception_and_event_are_rolled_back_together_on_event_failure(self):
        db = self.sites["Q1"]
        before = db.execute("SELECT * FROM dbo.HocVien").fetchall()
        db.execute("CREATE TRIGGER dbo.fail_receive BEFORE INSERT ON LichSuChuyenCoSo WHEN NEW.su_kien='tao_ho_so_dich' BEGIN SELECT RAISE(ABORT, 'fixture event failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            transfers._create_destination_profile(self.snapshot(), "TK")
        self.assertEqual(db.execute("SELECT * FROM dbo.HocVien").fetchall(), before)

    def test_first_arrival_still_creates_new_staged_profile(self):
        self.sites["Q1"].execute("DELETE FROM dbo.HocVien")
        transfers._create_destination_profile(self.snapshot(), "TK")
        self.assertEqual(self.sites["Q1"].execute("SELECT ma_hoc_vien, trang_thai FROM dbo.HocVien").fetchone(), (self.student, "bao_luu"))
