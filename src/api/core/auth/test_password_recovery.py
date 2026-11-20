"""Password recovery regressions using isolated database and lock fixtures."""

import copy
import threading
from contextlib import ExitStack, contextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.hashers import check_password
from django.db import DatabaseError
from django.test import SimpleTestCase

from core.auth import password_reset as resets
from core.auth.service_common import AuthInfrastructureUnavailable


class PasswordOtpTests(SimpleTestCase):
    def confirm(self, valid):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = ("token-fixture", "digest-fixture" if valid else "wrong-digest", 0)
        connection = SimpleNamespace(cursor=lambda: cursor)
        with ExitStack() as stack:
            for name in ("_resume_pending_password_resets", "_acquire_named_lock", "_record_password_reset_event"):
                stack.enter_context(patch.object(resets, name))
            stack.enter_context(patch.object(resets, "auth_session_alias", return_value="fixture"))
            stack.enter_context(patch.object(resets, "active_site_codes", return_value=("Q1", "Q7")))
            stack.enter_context(patch.object(resets, "_digest", return_value="digest-fixture"))
            stack.enter_context(patch.object(resets, "_password_reset_verify_retry_after", return_value=None))
            stack.enter_context(patch.object(resets, "_eligible_admin_from_email", return_value=(
                ("account-fixture",), SimpleNamespace(account_id="account-fixture"),
            )))
            stack.enter_context(patch.object(resets, "connections", {"fixture": connection}))
            stack.enter_context(patch.object(resets.transaction, "atomic", return_value=nullcontext()))
            apply = stack.enter_context(patch.object(resets, "_apply_password_reset_transaction"))
            result = resets.reset_admin_password("admin@example.com", "000000", "Only-a-test-password", "127.0.0.1")
        return result, cursor, apply

    def test_valid_otp_hashes_password_creates_job_and_consumes_token(self):
        result, cursor, apply = self.confirm(True)
        self.assertTrue(result)
        insert = next(call for call in cursor.execute.call_args_list if "INSERT INTO dbo.GiaoDichDatLaiMatKhau" in call.args[0])
        job_id, account_id, encoded = insert.args[1]
        self.assertEqual(account_id, "account-fixture")
        self.assertNotEqual(encoded, "Only-a-test-password")
        self.assertTrue(check_password("Only-a-test-password", encoded))
        self.assertTrue(any("SET da_dung = 1 WHERE ma_token" in call.args[0] for call in cursor.execute.call_args_list))
        apply.assert_called_once_with(job_id, ("Q1", "Q7"))

    def test_wrong_otp_does_not_create_or_apply_password_job(self):
        result, cursor, apply = self.confirm(False)
        self.assertFalse(result)
        self.assertFalse(any("INSERT INTO dbo.GiaoDichDatLaiMatKhau" in call.args[0] for call in cursor.execute.call_args_list))
        apply.assert_not_called()


class _PasswordStore:
    """Model local commits and transaction-owned account locks, not SQL syntax."""

    sites = ("Q1", "Q7", "TD")

    def __init__(self):
        self.jobs = {"old": ["ACCOUNT", "old-hash-fixture", "dang_xu_ly"]}
        self.accounts = {site: ["initial-hash-fixture", 0] for site in self.sites}
        self.local = threading.local()
        self.lock = threading.RLock()
        self.events = []
        self.read = threading.Event()
        self.resume = threading.Event()
        self.pause_stale_reader = False
        self.fail_once_site = None

    @contextmanager
    def atomic(self, *, using):
        depths = getattr(self.local, "depths", None)
        if depths is None:
            depths = self.local.depths = {}
        outer = depths.get(using, 0) == 0
        if outer:
            account_before = copy.deepcopy(self.accounts[using])
            jobs_before = copy.deepcopy(self.jobs) if using == "Q1" else None
        depths[using] = depths.get(using, 0) + 1
        try:
            yield
        except Exception:
            if outer:
                self.accounts[using] = account_before
                if using == "Q1":
                    self.jobs = jobs_before
            raise
        finally:
            depths[using] -= 1
            if outer and using == "Q1" and getattr(self.local, "locked", False):
                self.local.locked = False
                self.lock.release()

    def acquire(self, cursor, resource):
        assert self.local.depths.get("Q1", 0) > 0
        assert resource == "qlttnn-password-account:ACCOUNT"
        assert self.lock.acquire(timeout=5)
        self.local.locked = True
        self.events.append(("lock", threading.current_thread().name))

    def cursor(self, site):
        store = self

        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *_): return False

            def execute(self, sql, params):
                sql = " ".join(sql.split())
                self.pause = False
                if sql.startswith("SELECT ma_tai_khoan") and "GiaoDichDatLaiMatKhau" in sql:
                    job = store.jobs.get(params[0])
                    full = "mat_khau_moi_bam" in sql
                    if full:
                        assert store.local.locked, "Job must be re-read after obtaining the account lock"
                    self.row = tuple(job) if full and job else (job[0],) if job else None
                    if store.pause_stale_reader and threading.current_thread().name == "stale-password-worker":
                        store.pause_stale_reader = False
                        self.pause = True
                elif sql.startswith("UPDATE dbo.TaiKhoan"):
                    assert store.local.locked, "Every replica write must remain under the coordinator account lock"
                    if store.fail_once_site == site:
                        store.fail_once_site = None
                        raise DatabaseError("fixture site unavailable")
                    if store.accounts[site][0] != params[0]:
                        store.accounts[site] = [params[0], store.accounts[site][1] + 1]
                    store.events.append(("write", site))
                elif sql.startswith("SELECT COUNT_BIG(*), MIN(mat_khau)"):
                    self.row = (1, store.accounts[site][0])
                elif sql.startswith("UPDATE dbo.GiaoDichDatLaiMatKhau"):
                    assert store.local.locked
                    job = store.jobs[params[0]]
                    if job[2] == "dang_xu_ly":
                        job[1:] = [None, "hoan_tat"]
                else:
                    raise AssertionError(f"Unexpected fixture query: {sql[:70]}")

            def fetchone(self):
                row = self.row
                if self.pause:
                    store.read.set()
                    assert store.resume.wait(5), "Stale worker was not resumed"
                return row

        return Cursor()


class PasswordRecoveryLockTests(SimpleTestCase):
    def setUp(self):
        self.store = _PasswordStore()
        self.enterContext(patch.object(resets, "auth_session_alias", return_value="Q1"))
        self.enterContext(patch.object(resets, "get_site_database_alias", side_effect=lambda site: site))
        self.enterContext(patch.object(resets, "connections", {
            site: SimpleNamespace(cursor=lambda site=site: self.store.cursor(site)) for site in self.store.sites
        }))
        self.enterContext(patch.object(resets.transaction, "atomic", side_effect=self.store.atomic))
        self.enterContext(patch.object(resets, "_acquire_named_lock", side_effect=self.store.acquire))

    def test_stale_worker_rechecks_completed_job_and_keeps_newer_password(self):
        self.store.pause_stale_reader = True
        errors = []

        def stale_worker():
            try:
                resets._apply_password_reset_transaction("old", self.store.sites)
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=stale_worker, name="stale-password-worker")
        worker.start()
        try:
            self.assertTrue(self.store.read.wait(5))
            resets._apply_password_reset_transaction("old", self.store.sites)
            self.store.jobs["new"] = ["ACCOUNT", "new-hash-fixture", "dang_xu_ly"]
            resets._apply_password_reset_transaction("new", self.store.sites)
        finally:
            self.store.resume.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(all(account[0] == "new-hash-fixture" for account in self.store.accounts.values()))
        self.assertTrue(all(job[2] == "hoan_tat" and job[1] is None for job in self.store.jobs.values()))
        self.assertEqual(sum(event[0] == "write" for event in self.store.events), 6)

    def test_partial_failure_leaves_job_retryable_and_does_not_bump_completed_replica_again(self):
        self.store.fail_once_site = "TD"
        with self.assertRaises(AuthInfrastructureUnavailable):
            resets._apply_password_reset_transaction("old", self.store.sites)
        self.assertEqual(self.store.jobs["old"][2], "dang_xu_ly")
        self.assertEqual(self.store.accounts["Q7"], ["old-hash-fixture", 1])
        self.assertEqual(self.store.accounts["Q1"], ["initial-hash-fixture", 0])
        resets._apply_password_reset_transaction("old", self.store.sites)
        self.assertEqual(self.store.jobs["old"][1:], [None, "hoan_tat"])
        self.assertTrue(all(account == ["old-hash-fixture", 1] for account in self.store.accounts.values()))

    def test_missing_or_completed_job_has_no_replica_writes(self):
        resets._apply_password_reset_transaction("missing", self.store.sites)
        self.store.jobs["old"][1:] = [None, "hoan_tat"]
        resets._apply_password_reset_transaction("old", self.store.sites)
        self.assertFalse(any(event[0] == "write" for event in self.store.events))
