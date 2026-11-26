"""Teacher schedule: one LOCAL query over the teacher's assigned, non-cancelled classes."""

import re
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.academics import attendance


class _Cursor:
    def __init__(self, db):
        self.db, self.cur = db, None
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        sql = " ".join(sql.split())
        top = re.search(r"SELECT TOP \((\d+)\)", sql)
        if top:
            sql = re.sub(r"SELECT TOP \(\d+\)", "SELECT", sql, count=1) + f" LIMIT {top[1]}"
        self.cur = self.db.execute(sql.replace("%s", "?"), list(params))
        self.description = self.cur.description

    def fetchall(self):
        return self.cur.fetchall()


class TeacherScheduleTests(SimpleTestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("ATTACH DATABASE ':memory:' AS dbo")
        db.executescript("""
            CREATE TABLE dbo.KhoaHoc (ma_khoa_hoc, ten_khoa_hoc);
            CREATE TABLE dbo.GiaoVien (ma_giao_vien, ma_co_so, trang_thai);
            CREATE TABLE dbo.PhongHoc (ma_phong, ma_co_so, ten_phong);
            CREATE TABLE dbo.LopHoc (ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ten_lop, trang_thai);
            CREATE TABLE dbo.BuoiHoc (ma_buoi, ma_co_so, ma_lop, so_thu_tu, ngay_hoc, gio_bat_dau,
                gio_ket_thuc, ma_phong, ma_giao_vien, trang_thai, ghi_chu);
            INSERT INTO dbo.KhoaHoc VALUES ('KH', 'IELTS');
            INSERT INTO dbo.GiaoVien VALUES ('GV1', 'Q1', 'dang_day'), ('GV2', 'Q1', 'dang_day');
            INSERT INTO dbo.PhongHoc VALUES ('P1', 'Q1', 'Phòng 1');
            INSERT INTO dbo.LopHoc VALUES
                ('L1', 'Q1', 'KH', 'GV1', 'Lớp sáng', 'dang_hoc'),
                ('L2', 'Q1', 'KH', 'GV1', 'Lớp tối', 'sap_mo'),
                ('L3', 'Q1', 'KH', 'GV1', 'Lớp hủy', 'huy'),
                ('L4', 'Q1', 'KH', 'GV2', 'Lớp người khác', 'dang_hoc');
            INSERT INTO dbo.BuoiHoc VALUES
                ('B2', 'Q1', 'L2', 1, '2026-11-26', '18:30', '20:30', 'P1', 'GV1', 'du_kien', NULL),
                ('B1', 'Q1', 'L1', 2, '2026-11-26', '08:00', '10:00', 'P1', 'GV2', 'du_kien', 'dạy thay'),
                ('B0', 'Q1', 'L1', 1, '2026-11-24', '08:00', '10:00', NULL, 'GV1', 'da_hoc', NULL),
                ('B3', 'Q1', 'L3', 1, '2026-11-27', '08:00', '10:00', 'P1', 'GV1', 'du_kien', NULL),
                ('B4', 'Q1', 'L4', 1, '2026-11-26', '08:00', '10:00', 'P1', 'GV2', 'du_kien', NULL);
        """)
        self.enterContext(patch.object(attendance, "require_active_site", return_value="site_q1"))
        self.enterContext(patch.object(attendance, "connections", {"site_q1": SimpleNamespace(cursor=lambda: _Cursor(db))}))

    def test_returns_own_non_cancelled_sessions_in_time_order(self):
        rows = attendance.list_teacher_schedule(site_code="Q1", teacher_id="GV1")
        self.assertEqual([row["session_id"] for row in rows], ["B0", "B1", "B2"])
        self.assertEqual(rows[1]["class_name"], "Lớp sáng")
        self.assertEqual(rows[1]["course_name"], "IELTS")
        self.assertIsNone(rows[0]["room_name"])
        self.assertNotIn("session_teacher_id", rows[0])

    def test_attendance_flag_follows_session_teacher(self):
        rows = {row["session_id"]: row for row in attendance.list_teacher_schedule(site_code="Q1", teacher_id="GV1")}
        self.assertTrue(rows["B2"]["can_edit_attendance"])
        self.assertFalse(rows["B1"]["can_edit_attendance"])  # substitute teacher recorded on the session

    def test_inactive_teacher_gets_no_schedule(self):
        with patch.object(attendance, "connections") as conns:
            db = sqlite3.connect(":memory:")
            self.addCleanup(db.close)
            db.execute("ATTACH DATABASE ':memory:' AS dbo")
            db.executescript("""
                CREATE TABLE dbo.KhoaHoc (ma_khoa_hoc, ten_khoa_hoc);
                CREATE TABLE dbo.GiaoVien (ma_giao_vien, ma_co_so, trang_thai);
                CREATE TABLE dbo.PhongHoc (ma_phong, ma_co_so, ten_phong);
                CREATE TABLE dbo.LopHoc (ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ten_lop, trang_thai);
                CREATE TABLE dbo.BuoiHoc (ma_buoi, ma_co_so, ma_lop, so_thu_tu, ngay_hoc, gio_bat_dau,
                    gio_ket_thuc, ma_phong, ma_giao_vien, trang_thai, ghi_chu);
                INSERT INTO dbo.KhoaHoc VALUES ('KH', 'IELTS');
                INSERT INTO dbo.GiaoVien VALUES ('GV1', 'Q1', 'nghi_viec');
                INSERT INTO dbo.LopHoc VALUES ('L1', 'Q1', 'KH', 'GV1', 'Lớp', 'dang_hoc');
                INSERT INTO dbo.BuoiHoc VALUES ('B1', 'Q1', 'L1', 1, '2026-11-26', '08:00', '10:00', NULL, 'GV1', 'du_kien', NULL);
            """)
            conns.__getitem__.side_effect = lambda _alias: SimpleNamespace(cursor=lambda: _Cursor(db))
            self.assertEqual(attendance.list_teacher_schedule(site_code="Q1", teacher_id="GV1"), [])
