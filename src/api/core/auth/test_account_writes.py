"""Authority-only identity writes: version bump, session continuity, no replica writes."""

import re
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import SimpleTestCase

from core.auth import admin_big_profile, oauth_services
from core.auth.account_writes import AccountVersionConflict, update_authority_account
from core.auth.admin_big_profile import AdminBigProfileConflict
from core.auth.oauth_services import OAuthAccountConflict


class _Cursor:
    def __init__(self, db):
        self.db, self.cur = db, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        sql = " ".join(sql.split())
        sql = sql.replace(" WITH (UPDLOCK, HOLDLOCK)", "").replace("SYSUTCDATETIME()", "CURRENT_TIMESTAMP")
        sql = sql.replace("CONVERT(NVARCHAR(120), NEWID())", "lower(hex(randomblob(8)))").replace(" N'", " '")
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


class AuthorityAccountWriteTests(SimpleTestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(self.db.close)
        self.db.execute("ATTACH DATABASE ':memory:' AS dbo")
        self.db.executescript("""
            CREATE TABLE dbo.TaiKhoan (ma_tai_khoan PRIMARY KEY, ten_dang_nhap, slug, email, mat_khau,
                vai_tro, ma_co_so, trang_thai, phien_ban, bat_buoc_doi_mat_khau,
                google_subject UNIQUE, facebook_subject UNIQUE, cap_nhat_luc);
            CREATE TABLE dbo.PhienDangNhap (ma_phien, ma_tai_khoan, phien_ban_tai_khoan, thu_hoi_luc_utc);
            CREATE TABLE dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong,
                ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua, ghi_chu);
        """)
        self.password = make_password("current-password")
        self.db.executemany("INSERT INTO dbo.TaiKhoan VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL)", [
            ("Q1-TK-000001", "admin", "admin", "admin@example.com", self.password, "admin_big", None, 1, 4, 0, None, None),
            ("Q1-TK-000003", "hv", "hv", "hv@example.com", self.password, "hoc_vien", "Q1", 1, 1, 0, None, None),
            ("Q1-TK-000009", "other", "other", "other@example.com", self.password, "hoc_vien", "Q1", 1, 1, 0, None, None),
        ])
        self.db.executemany("INSERT INTO dbo.PhienDangNhap VALUES (?,?,?,?)", [
            ("S1", "Q1-TK-000003", 1, None), ("S2", "Q1-TK-000003", 1, "2026-01-01"),
            ("S3", "Q1-TK-000001", 4, None),
        ])
        conn = SimpleNamespace(cursor=lambda: _Cursor(self.db))
        replica = SimpleNamespace(cursor=lambda: self.fail("replica must not be written"))
        for module in (oauth_services, admin_big_profile):
            self.enterContext(patch.object(module, "connections", {"authority": conn, "replica": replica}))
            self.enterContext(patch.object(module, "auth_session_alias", return_value="authority"))
            self.enterContext(patch.object(module.transaction, "atomic", side_effect=self._atomic))
            self.enterContext(patch.object(module, "_acquire_named_lock"))
        self.enterContext(patch.object(oauth_services, "active_site_codes", return_value=("Q1", "Q7", "TD")))
        self.enterContext(patch.object(admin_big_profile, "auth_session_site_code", return_value="Q1"))
        self.student = SimpleNamespace(account_id="Q1-TK-000003", role="hoc_vien", profile_id="Q1-HV-000001", slug="hv")
        self.enterContext(patch.object(oauth_services, "_resolve_principal", return_value=self.student))

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

    def _row(self, account_id, columns):
        return self.db.execute(f"SELECT {columns} FROM dbo.TaiKhoan WHERE ma_tai_khoan = ?", [account_id]).fetchone()

    def test_helper_bumps_version_keeps_live_sessions_and_rejects_stale_version(self):
        cursor = _Cursor(self.db)
        self.assertEqual(update_authority_account(cursor, "Q1-TK-000003", 1, {"email": "new@example.com"}), 2)
        sessions = dict(self.db.execute("SELECT ma_phien, phien_ban_tai_khoan FROM dbo.PhienDangNhap").fetchall())
        self.assertEqual(sessions, {"S1": 2, "S2": 1, "S3": 4})  # revoked session is not revived
        with self.assertRaises(AccountVersionConflict):
            update_authority_account(cursor, "Q1-TK-000003", 1, {"email": "again@example.com"})
        with self.assertRaises(ValueError):
            update_authority_account(cursor, "Q1-TK-000003", 2, {"mat_khau": "x"})

    def test_oauth_link_writes_authority_only_with_new_version_and_is_idempotent(self):
        oauth_services.link_oauth_provider(self.student, "google", "sub-123", "127.0.0.1")
        self.assertEqual(self._row("Q1-TK-000003", "google_subject, phien_ban"), ("sub-123", 2))
        oauth_services.link_oauth_provider(self.student, "google", "sub-123", "127.0.0.1")
        self.assertEqual(self._row("Q1-TK-000003", "phien_ban"), (2,))
        self.assertEqual(oauth_services.get_oauth_connections(self.student, "hv"), {"google": True, "facebook": False})

    def test_oauth_subject_owned_by_another_account_is_rejected_without_changes(self):
        self.db.execute("UPDATE dbo.TaiKhoan SET google_subject = 'sub-123' WHERE ma_tai_khoan = 'Q1-TK-000009'")
        with self.assertRaises(OAuthAccountConflict):
            oauth_services.link_oauth_provider(self.student, "google", "sub-123", "127.0.0.1")
        self.assertEqual(self._row("Q1-TK-000003", "google_subject, phien_ban"), (None, 1))

    def test_admin_big_profile_updates_authority_and_bumps_version(self):
        admin = SimpleNamespace(account_id="Q1-TK-000001", role="admin_big", slug="admin")
        result = admin_big_profile.update_admin_big_self_profile(
            admin, "admin", {"email": "boss@example.com"}, "current-password", "127.0.0.1",
        )
        self.assertEqual(result["email"], "boss@example.com")
        self.assertEqual(self._row("Q1-TK-000001", "email, phien_ban"), ("boss@example.com", 5))
        self.assertEqual(self.db.execute("SELECT phien_ban_tai_khoan FROM dbo.PhienDangNhap WHERE ma_phien='S3'").fetchone(), (5,))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM dbo.Logs").fetchone(), (1,))

    def test_admin_big_profile_rejects_identity_used_by_another_account(self):
        admin = SimpleNamespace(account_id="Q1-TK-000001", role="admin_big", slug="admin")
        with self.assertRaises(AdminBigProfileConflict):
            admin_big_profile.update_admin_big_self_profile(
                admin, "admin", {"email": "OTHER@example.com"}, "current-password", "127.0.0.1",
            )
        self.assertEqual(self._row("Q1-TK-000001", "email, phien_ban"), ("admin@example.com", 4))
