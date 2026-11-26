"""Account-only self-registration (role nguoi_dung): no site, no student profile."""

from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from django.contrib.auth.hashers import check_password
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from core.auth import account_replication as replication, registration
from core.auth.registration import RegistrationResult


def connection():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    return conn, cursor


def create_account(cursor_rows, *, existing_account=None, email="new@example.com"):
    conn, cursor = connection()
    cursor.fetchone.side_effect = cursor_rows
    create = registration._create_user_account.__wrapped__
    with (
        override_settings(AUTH_SESSION_SITE_CODE="Q1"),
        patch.object(registration, "_replicated_account", return_value=existing_account),
        patch.object(registration, "auth_session_alias", return_value="auth"),
        patch.object(registration, "connections", {"auth": conn}),
        patch.object(registration.transaction, "atomic", return_value=nullcontext()),
        patch.object(registration, "_acquire_named_lock"),
        patch.object(registration, "_next_student_account_id", return_value="Q1-TK-000009"),
        patch.object(registration, "_user_slug", return_value="nguoi-dung-new"),
        patch.object(registration, "_user_username", return_value="nd-new"),
    ):
        try:
            return create(full_name="New", email=email, password="fixture-password", remote_ip="127.0.0.1"), cursor
        except registration.RegistrationConflict:
            return None, cursor


class AccountOnlyRegistrationTests(SimpleTestCase):
    def test_creates_only_an_account_without_site_or_student_profile(self):
        result, cursor = create_account([None])
        self.assertEqual(result.account_id, "Q1-TK-000009")
        sql = [call.args[0] for call in cursor.execute.call_args_list]
        insert = next(call for call in cursor.execute.call_args_list if "INSERT dbo.TaiKhoan" in call.args[0])
        self.assertIn("'nguoi_dung',NULL", insert.args[0])
        self.assertTrue(check_password("fixture-password", insert.args[1][4]))
        self.assertEqual(insert.args[1][-1], "New")
        self.assertFalse(any("INSERT dbo.HocVien" in text for text in sql))

    def test_refuses_an_email_held_by_a_student_profile_or_an_existing_account(self):
        result, cursor = create_account([(1,)])
        self.assertIsNone(result)
        self.assertFalse(any("INSERT dbo.TaiKhoan" in call.args[0] for call in cursor.execute.call_args_list))
        result, _ = create_account([None], existing_account=("A",))
        self.assertIsNone(result)

    def test_register_user_reserves_the_email_at_the_authority_first(self):
        with (
            override_settings(AUTH_SESSION_SITE_CODE="Q1"),
            patch.object(registration, "reserve_email", return_value="key") as reserve,
            patch.object(registration, "_create_user_account", return_value=RegistrationResult("A")) as create,
        ):
            self.assertEqual(registration.register_user(full_name="N", email="n@example.com", password="x" * 12, remote_ip="1").account_id, "A")
        reserve.assert_called_once_with("n@example.com", "Q1")
        create.assert_called_once()

    def test_reservation_conflict_becomes_a_registration_conflict(self):
        with (
            override_settings(AUTH_SESSION_SITE_CODE="Q1"),
            patch.object(registration, "reserve_email", side_effect=registration.StudentEmailConflict("x")),
        ):
            with self.assertRaises(registration.RegistrationConflict):
                registration.register_user(full_name="N", email="n@example.com", password="x" * 12, remote_ip="1")


@override_settings(AUTH_SESSION_SITE_CODE="Q1")
class RegistrationSwitchTests(SimpleTestCase):
    body = {"full_name": "N", "email": "n@example.com", "password": "x" * 12, "confirm_password": "x" * 12}

    def post(self):
        return APIClient().post("/api/v1/auth/register/", self.body, format="json")

    def test_default_keeps_creating_a_student_at_the_authority(self):
        with (
            override_settings(SELF_REGISTRATION_ACCOUNT_ONLY=False),
            patch("core.auth.registration_views.register_student", return_value=RegistrationResult("A")) as student,
            patch("core.auth.registration_views.register_user") as user,
        ):
            self.assertEqual(self.post().status_code, 201)
        self.assertEqual(student.call_args.kwargs["site_code"], "Q1")
        user.assert_not_called()

    def test_flag_switches_to_account_only(self):
        with (
            override_settings(SELF_REGISTRATION_ACCOUNT_ONLY=True),
            patch("core.auth.registration_views.register_student") as student,
            patch("core.auth.registration_views.register_user", return_value=RegistrationResult("A")) as user,
        ):
            self.assertEqual(self.post().status_code, 201)
        student.assert_not_called()
        self.assertNotIn("site_code", user.call_args.kwargs)


@override_settings(AUTH_SESSION_SITE_CODE="Q1")
class ProfileColumnReplicationTests(SimpleTestCase):
    def select_columns(self, role):
        conn, cursor = connection()
        row = tuple(range(len(replication.ACCOUNT_COLUMNS))) + ((None,) * 5 if role == "nguoi_dung" else ())
        cursor.fetchone.side_effect = [(role,), row, None, (1,)]
        with (
            patch.object(replication, "auth_session_alias", return_value="auth"),
            patch.object(replication, "get_site_database_alias", return_value="auth"),
            patch.object(replication, "connections", {"auth": conn}),
            patch.object(replication.transaction, "atomic", return_value=nullcontext()),
            patch.object(replication, "_acquire_named_lock"),
        ):
            replication.deliver_account("A", "Q1")
        return next(call.args[0] for call in cursor.execute.call_args_list if "FROM dbo.TaiKhoan WITH (UPDLOCK" in call.args[0])

    def test_profile_columns_are_replicated_only_for_nguoi_dung(self):
        self.assertIn("ho_ten", self.select_columns("nguoi_dung"))
        self.assertNotIn("ho_ten", self.select_columns("hoc_vien"))


class NguoiDungPrincipalTests(SimpleTestCase):
    def account(self, site=None, status=1):
        return ("Q1-TK-000009", "nd-new", "nguoi-dung-new", "new@example.com", "hash", "nguoi_dung", site, status, 1, 0)

    def test_website_account_resolves_without_site_or_profile(self):
        from core.auth import service_common as common

        user = common._resolve_principal(self.account())
        self.assertEqual((user.role, user.site_code, user.profile_id), ("nguoi_dung", None, None))
        self.assertEqual(user.slug, "nguoi-dung-new")

    def test_website_account_with_a_site_is_rejected_and_inactive_is_rejected(self):
        from core.auth import service_common as common

        self.assertIsNone(common._resolve_principal(self.account(site="Q1")))
        self.assertIsNone(common._resolve_principal(self.account(status=0)))

    def test_password_reset_accepts_website_accounts(self):
        from core.auth import password_reset

        with (
            patch.object(password_reset, "_replicated_account", return_value=self.account()),
            patch.object(password_reset, "_resolve_principal", wraps=password_reset._resolve_principal),
        ):
            account, user = password_reset._eligible_admin_from_email("new@example.com", ("Q1",))
        self.assertEqual(user.role, "nguoi_dung")
        self.assertIsNotNone(account)
