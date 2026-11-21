"""Exercise delivery through independent SQLite commits, including an ACK crash."""
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings

from core.auth import account_replication as replication


@override_settings(AUTH_SESSION_SITE_CODE="Q1")
class AccountReplicationTests(SimpleTestCase):
    def setUp(self):
        self.databases = {site: sqlite3.connect(":memory:") for site in ("Q1", "TD")}
        self.addCleanup(lambda: [database.close() for database in self.databases.values()])
        self.offline = False
        self.fail_ack = False
        for database in self.databases.values():
            database.execute("CREATE TABLE TaiKhoan(" + ",".join(f"{column} TEXT" for column in replication.ACCOUNT_COLUMNS) + ")")
        source = self.databases["Q1"]
        source.execute("CREATE TABLE GiaoDichDatLaiMatKhau(ma_tai_khoan TEXT,trang_thai TEXT)")
        source.execute("CREATE TABLE DongBoTaiKhoan(ma_su_kien INTEGER PRIMARY KEY,ma_tai_khoan TEXT,site_dich TEXT)")
        source.execute("CREATE TABLE CoSo(ma_co_so TEXT,trang_thai TEXT)")
        source.executemany("INSERT INTO CoSo VALUES (?, 'hoat_dong')", [("Q1",), ("TD",)])
        self.account = ["ACCOUNT", "slug", "name", "student@example.com", "old-hash", "hoc_vien", "TD", "1", "0", "1", None, None, None, None, None]
        source.execute("INSERT INTO TaiKhoan VALUES (" + ",".join("?" for _ in self.account) + ")", self.account)
        source.execute("INSERT INTO DongBoTaiKhoan VALUES (1,'ACCOUNT','TD')")
        source.commit()
        self.enterContext(patch.object(replication, "auth_session_alias", return_value="Q1"))
        self.enterContext(patch.object(replication, "get_site_database_alias", side_effect=lambda site: site))
        self.enterContext(patch.object(replication, "connections", {
            site: SimpleNamespace(cursor=lambda site=site: self.cursor(site)) for site in self.databases
        }))
        self.enterContext(patch.object(replication.transaction, "atomic", side_effect=self.atomic))
        self.enterContext(patch.object(replication, "_acquire_named_lock"))

    @contextmanager
    def atomic(self, *, using):
        database = self.databases[using]
        database.execute("BEGIN")
        try:
            yield
            database.commit()
        except Exception:
            database.rollback()
            raise

    @contextmanager
    def cursor(self, site):
        if site == "TD" and self.offline:
            raise DatabaseError("offline target fixture")
        store = self
        cursor = self.databases[site].cursor()
        class Cursor:
            def execute(self, sql, params):
                sql = " ".join(sql.split())
                if store.fail_ack and sql.startswith("DELETE FROM dbo.DongBoTaiKhoan"):
                    store.fail_ack = False
                    raise DatabaseError("crash after independent target commit")
                sql = sql.replace("dbo.", "").replace(" WITH (UPDLOCK, HOLDLOCK)", "").replace("TOP (1) ", "").replace("%s", "?")
                if sql.startswith("INSERT "):
                    sql = sql.replace("INSERT ", "INSERT INTO ", 1)
                cursor.execute(sql, params)
            def fetchone(self):
                return cursor.fetchone()
        try:
            yield Cursor()
        finally:
            cursor.close()

    def row(self, site):
        return self.databases[site].execute("SELECT * FROM TaiKhoan").fetchone()

    def pending(self):
        return self.databases["Q1"].execute("SELECT COUNT(*) FROM DongBoTaiKhoan").fetchone()[0]

    def test_offline_delivery_stays_queued_then_converges_when_target_returns(self):
        self.offline = True
        with self.assertRaises(DatabaseError):
            replication.deliver_account("ACCOUNT", "TD")
        self.assertEqual(self.pending(), 1)
        self.assertIsNone(self.row("TD"))
        self.offline = False
        replication.deliver_account("ACCOUNT", "TD")
        self.assertEqual(self.row("TD"), tuple(self.account))
        self.assertEqual(self.pending(), 0)

    def test_ack_crash_retry_uses_latest_password_and_does_not_duplicate_account(self):
        self.fail_ack = True
        with self.assertRaises(DatabaseError):
            replication.deliver_account("ACCOUNT", "TD")
        self.assertEqual(self.pending(), 1)
        self.assertEqual(self.row("TD")[4], "old-hash")
        self.databases["Q1"].execute("UPDATE TaiKhoan SET mat_khau='new-hash',phien_ban='2'")
        self.databases["Q1"].execute("INSERT INTO DongBoTaiKhoan VALUES (2,'ACCOUNT','TD')")
        self.databases["Q1"].commit()
        replication.deliver_account("ACCOUNT", "TD")
        self.assertEqual(self.row("TD")[4], "new-hash")
        self.assertEqual(self.databases["TD"].execute("SELECT COUNT(*) FROM TaiKhoan").fetchone()[0], 1)
        self.assertEqual(self.pending(), 0)

    def test_unexplained_newer_replica_is_preserved_for_review(self):
        newer = list(self.account)
        newer[4], newer[9] = "newer-target-hash", "9"
        self.databases["TD"].execute("INSERT INTO TaiKhoan VALUES (" + ",".join("?" for _ in newer) + ")", newer)
        self.databases["TD"].commit()
        with self.assertRaises(replication.AccountReplicaConflict):
            replication.deliver_account("ACCOUNT", "TD")
        self.assertEqual(self.row("TD")[4], "newer-target-hash")
        self.assertEqual(self.pending(), 1)

    def test_incomplete_password_job_blocks_delivery_for_that_account(self):
        self.databases["Q1"].execute("INSERT INTO GiaoDichDatLaiMatKhau VALUES ('ACCOUNT','dang_xu_ly')")
        self.databases["Q1"].commit()
        with self.assertRaises(replication.AuthInfrastructureUnavailable):
            replication.deliver_account("ACCOUNT", "TD")
        self.assertEqual(self.pending(), 1)
        self.assertIsNone(self.row("TD"))

    def test_periodic_reconciliation_repairs_restored_subscriber_after_old_ack(self):
        replication.deliver_account("ACCOUNT", "TD")
        self.assertEqual(self.pending(), 0)
        self.databases["TD"].execute("DELETE FROM TaiKhoan")
        self.databases["TD"].commit()
        replication.queue_account_reconciliation()
        self.databases["Q1"].commit()
        self.assertEqual(self.pending(), 1)
        replication.deliver_account("ACCOUNT", "TD")
        self.assertEqual(self.row("TD"), tuple(self.account))
        self.assertEqual(self.pending(), 0)
