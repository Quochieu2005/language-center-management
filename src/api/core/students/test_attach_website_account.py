"""A sign-up account (nguoi_dung) becomes the student's login when the account is issued."""

from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.students import identity, services


def conn():
    connection = MagicMock()
    return connection, connection.cursor.return_value.__enter__.return_value


class ReplicaUpgradeTests(SimpleTestCase):
    expected = ("Q1-TK-000009", "slug", "user", "a@example.com", "hash", "hoc_vien", "Q7", 1, False, 2)

    def run_replica(self, row):
        connection, cursor = conn()
        cursor.fetchall.return_value = [row] if row else []
        cursor.rowcount = 1
        with (
            patch.object(services, "get_site_database_alias", return_value="q7"),
            patch.object(services, "connections", {"q7": connection}),
            patch.object(services.transaction, "atomic", return_value=nullcontext()),
            patch.object(services, "_append_replication_event"),
        ):
            services._ensure_account_replica("Q7", self.expected)
        return cursor

    def test_replica_still_holding_the_signup_account_is_upgraded(self):
        old = ("Q1-TK-000009", "slug", "user", "a@example.com", "hash", "nguoi_dung", None, 1, False, 1)
        cursor = self.run_replica(old)
        update = next(call for call in cursor.execute.call_args_list if "UPDATE dbo.TaiKhoan" in call.args[0])
        self.assertEqual(update.args[1], ["Q7", False, 2, "Q1-TK-000009"])

    def test_other_differences_are_still_a_conflict(self):
        for old in (
            ("Q1-TK-000009", "slug", "user", "a@example.com", "other-hash", "nguoi_dung", None, 1, False, 1),
            ("Q1-TK-000009", "slug", "user", "a@example.com", "hash", "nguoi_dung", None, 1, False, 2),
            ("Q1-TK-000009", "slug", "user", "a@example.com", "hash", "giao_vien", "Q7", 1, False, 1),
        ):
            with self.assertRaises(services.StudentConflict):
                self.run_replica(old)


class AttachRulesTests(SimpleTestCase):
    def attach(self, found, linked=0):
        _, cursor = conn()
        cursor.fetchone.return_value = (linked,)
        student = ("Q7-HV-000001", "hv", "Q7")
        return services._attach_website_account(cursor, found, student, "Q7", "actor", "127.0.0.1")

    def found(self, role="nguoi_dung", site=None, status=1):
        return ("Q1-TK-000009", "user", "slug", "a@example.com", "hash", role, site, status, 1, 0)

    def test_only_a_website_account_or_an_unlinked_resume_is_accepted(self):
        for found, linked in (
            (self.found(role="giao_vien", site="Q7"), 0),
            (self.found(role="nguoi_dung", site="Q1"), 0),
            (self.found(role="hoc_vien", site="Q1"), 0),
            (self.found(role="hoc_vien", site="Q7"), 1),
            (self.found(status=0), 0),
        ):
            with self.assertRaises(services.StudentConflict, msg=str(found)):
                self.attach(found, linked)


class ReservationMoveTests(SimpleTestCase):
    def reserve(self, existing_reservation, website_holds):
        local, local_cursor = conn()
        local_cursor.fetchone.return_value = ("hoat_dong",)
        registry, registry_cursor = conn()
        registry_cursor.fetchone.side_effect = [(1,), existing_reservation, (1,) if website_holds else None]
        with (
            patch.object(identity, "get_site_connection", return_value=local),
            patch.object(identity, "auth_session_alias", return_value="auth"),
            patch.object(identity, "connections", {"auth": registry}),
            patch.object(identity.transaction, "atomic", return_value=nullcontext()),
            patch.object(identity, "_acquire_named_lock"),
        ):
            identity.reserve_email("a@example.com", "Q7")
        return registry_cursor

    def test_reservation_held_for_a_website_account_moves_to_the_students_site(self):
        cursor = self.reserve(("Q1", None), website_holds=True)
        self.assertTrue(any("UPDATE dbo.DatChoEmailHocVien SET ma_co_so" in call.args[0] for call in cursor.execute.call_args_list))

    def test_reservation_without_a_website_account_stays_a_conflict(self):
        with self.assertRaises(identity.StudentEmailConflict):
            self.reserve(("Q1", None), website_holds=False)
