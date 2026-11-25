"""Global student counts across separate in-memory site databases during a transfer."""

import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase

from core.academics import reports


class _Cursor:
    def __init__(self, db, fail):
        self._db, self._fail, self._cur = db, fail, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        if self._fail():
            raise DatabaseError("site offline")
        sql = sql.replace("%s", "?").replace("COUNT_BIG(", "COUNT(")
        self._cur = self._db.execute(sql, list(params))

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class GlobalStudentCountTransferTests(SimpleTestCase):
    student = "Q1-HV-000009"

    def setUp(self):
        self.sites, self.offline = {}, set()
        for site in ("Q1", "Q7", "TD"):
            db = sqlite3.connect(":memory:")
            self.addCleanup(db.close)
            db.execute("ATTACH DATABASE ':memory:' AS dbo")
            db.executescript("""
                CREATE TABLE dbo.HocVien (ma_hoc_vien, ma_co_so, trang_thai);
                CREATE TABLE dbo.GiaoDichChuyenCoSo (ma_chuyen, ma_hoc_vien, co_so_nguon,
                    co_so_dich, trang_thai, buoc_cuoi);
            """)
            self.sites[site] = db
        self.sites["Q7"].execute("INSERT INTO dbo.HocVien VALUES ('Q7-HV-000001', 'Q7', 'dang_hoc')")
        self.enterContext(patch.object(reports, "active_site_state", return_value=(("Q1", "Q7", "TD"), ())))
        self.enterContext(patch.object(reports, "get_site_database_alias", side_effect=lambda site: site))
        self.enterContext(patch.object(reports, "connections", {
            site: SimpleNamespace(cursor=lambda site=site: _Cursor(self.sites[site], lambda: site in self.offline))
            for site in self.sites
        }))
        self.enterContext(patch.object(reports, "read_sites_concurrently", side_effect=self._sequential))

    @staticmethod
    def _sequential(sites, reader):
        results, errors = {}, {}
        for site in sites:
            try:
                results[site] = reader(site)
            except Exception as exc:  # mirror fan-out: keep per-site errors
                errors[site] = exc
        return results, errors

    def _set_transfer(self, step, source_status, target_status):
        self.sites["Q1"].execute("DELETE FROM dbo.GiaoDichChuyenCoSo")
        self.sites["Q1"].execute("DELETE FROM dbo.HocVien")
        self.sites["Q7"].execute(f"DELETE FROM dbo.HocVien WHERE ma_hoc_vien = '{self.student}'")
        self.sites["Q1"].execute(
            "INSERT INTO dbo.GiaoDichChuyenCoSo VALUES ('Q1-CC-000001', ?, 'Q1', 'Q7', 'dang_xu_ly', ?)",
            [self.student, step],
        )
        self.sites["Q1"].execute("INSERT INTO dbo.HocVien VALUES (?, 'Q1', ?)", [self.student, source_status])
        if target_status:
            self.sites["Q7"].execute("INSERT INTO dbo.HocVien VALUES (?, 'Q7', ?)", [self.student, target_status])

    def _by_site(self):
        result = reports.student_counts_by_site()
        return result, {row["site_code"]: row["active_students"] for row in result["results"]}

    def test_before_source_update_counts_source_only(self):
        self._set_transfer("da_tao_ho_so_dich", "dang_hoc", "bao_luu")
        result, counts = self._by_site()
        self.assertEqual(counts, {"Q1": 1, "Q7": 1, "TD": 0})
        self.assertEqual(result["total_active_students"], 2)

    def test_after_source_update_counts_staged_destination_once(self):
        self._set_transfer("da_cap_nhat_nguon", "da_chuyen_di", "bao_luu")
        result, counts = self._by_site()
        self.assertEqual(counts, {"Q1": 0, "Q7": 2, "TD": 0})
        self.assertEqual(result["total_active_students"], 2)
        q7 = next(row for row in result["results"] if row["site_code"] == "Q7")
        self.assertEqual(q7["in_transit_students"], 1)
        self.assertTrue(result["complete"])

    def test_activated_destination_before_final_checkpoint_is_not_double_counted(self):
        self._set_transfer("da_cap_nhat_nguon", "da_chuyen_di", "dang_hoc")
        result, counts = self._by_site()
        self.assertEqual(counts, {"Q1": 0, "Q7": 2, "TD": 0})
        self.assertEqual(result["total_active_students"], 2)

    def test_offline_destination_is_reported_missing_not_counted(self):
        self._set_transfer("da_cap_nhat_nguon", "da_chuyen_di", "bao_luu")
        self.offline.add("Q7")
        result, counts = self._by_site()
        self.assertEqual(counts, {"Q1": 0, "TD": 0})
        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_sites"], ["Q7"])
