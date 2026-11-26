from contextlib import nullcontext
from unittest.mock import MagicMock, patch
from django.contrib.auth.hashers import check_password, make_password

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from core.auth import service_common as common, session_services as sessions
from core.auth.registration import RegistrationResult
from core.auth.serializers import AuthRegisterSerializer
from core.students import identity


def connection():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    return conn, cursor


@override_settings(AUTH_SESSION_SITE_CODE="Q1")
class SiteIsolationTests(SimpleTestCase):
    def test_account_lookup_never_reads_stale_or_offline_replicas(self):
        conn, cursor = connection()
        account = ("ACCOUNT", "name", "slug", "test@example.com", "hash", "admin_big", None, 0, 3, 0)
        cursor.fetchall.return_value = [account]
        with patch.object(common, "get_site_connection", side_effect=lambda site: conn if site == "Q1" else (_ for _ in ()).throw(DatabaseError())) as read:
            self.assertEqual(common._replicated_account("test@example.com", ("Q1", "Q7", "TD")), account)
        read.assert_called_once_with("Q1")
        self.assertIsNone(common._resolve_principal(account, ("Q1", "Q7", "TD")))

    def test_owning_student_profile_resolves_without_opening_unrelated_sites(self):
        conn, cursor = connection()
        cursor.fetchall.return_value = [("STUDENT", "student-slug", "TD", 0)]
        account = ("ACCOUNT", "name", "slug", "test@example.com", "hash", "hoc_vien", "TD", 1, 1, 0)
        with patch.object(common, "get_site_connection", side_effect=lambda site: conn if site == "TD" else (_ for _ in ()).throw(DatabaseError())) as read:
            user = common._resolve_principal(account, ("Q1", "Q7", "TD"))
        self.assertEqual((user.site_code, user.profile_id), ("TD", "STUDENT"))
        read.assert_called_once_with("TD")

    def test_unavailable_actual_profile_returns_service_unavailable(self):
        account = ("ACCOUNT", "name", "slug", "test@example.com", "hash", "hoc_vien", "TD", 1, 1, 0)
        with patch.object(common, "get_site_connection", side_effect=DatabaseError()):
            with self.assertRaises(common.AuthInfrastructureUnavailable):
                common._resolve_principal(account, ("Q1", "Q7", "TD"))

    def test_password_job_check_is_scoped_to_only_the_requested_account(self):
        conn, cursor = connection()
        cursor.fetchone.return_value = None
        with patch.object(sessions, "connections", {"auth": conn}), patch.object(sessions, "auth_session_alias", return_value="auth"):
            sessions.require_settled_password("ACCOUNT")
            self.assertEqual(cursor.execute.call_args.args[1], ["ACCOUNT"])
            cursor.fetchone.return_value = (1,)
            with self.assertRaises(common.AuthInfrastructureUnavailable):
                sessions.require_settled_password("ACCOUNT")

    def test_catalog_reads_only_authority(self):
        with patch.object(common, "_read_catalog", return_value=(("Q1", "hoat_dong"), ("Q7", "hoat_dong"), ("TD", "hoat_dong"))) as read, patch.object(common, "get_site_database_alias"):
            self.assertEqual(common.active_site_codes(), ("Q1", "Q7", "TD"))
        read.assert_called_once_with("Q1")


class RegistrationBoundaryTests(SimpleTestCase):
    def values(self, **extra):
        return {"full_name": "Người học mới", "email": " New@Example.com ", "site_code": "q1",
                "password": "A!strong-Example-739", "confirm_password": "A!strong-Example-739", **extra}

    def test_normalizes_identity_and_rejects_privilege_injection_and_weak_password(self):
        serializer = AuthRegisterSerializer(data=self.values())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["email"], "new@example.com")
        self.assertEqual(serializer.validated_data["site_code"], "Q1")
        self.assertFalse(AuthRegisterSerializer(data=self.values(role="admin_big")).is_valid())
        self.assertFalse(AuthRegisterSerializer(data=self.values(password="123456789012", confirm_password="123456789012")).is_valid())

    def test_register_requires_csrf(self):
        response = APIClient(enforce_csrf_checks=True).post("/api/v1/auth/register/", self.values(), format="json")
        self.assertEqual(response.status_code, 403)

    def test_success_exposes_pending_status_without_password_or_profile_data(self):
        with patch("core.auth.registration_views.register_student", return_value=RegistrationResult("ACCOUNT", ("Q7",))) as register:
            response = APIClient().post("/api/v1/auth/register/", self.values(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["replication_pending_sites"], ["Q7"])
        self.assertNotIn("password", response.json())
        self.assertEqual(register.call_args.kwargs["site_code"], "Q1")

    def test_existing_guest_profile_is_not_claimed(self):
        from core.auth import registration
        conn, cursor = connection()
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = (1,)
        # Exercise the actual local registration logic, excluding the two tested decorators.
        register = registration.register_student.__wrapped__.__wrapped__
        with patch.object(registration, "provisioning_sites", return_value=("Q1",)), patch.object(registration, "_replicated_account", return_value=None), patch.object(registration, "get_site_database_alias", return_value="local"), patch.object(registration, "connections", {"local": conn}), patch.object(registration.transaction, "atomic", return_value=nullcontext()), patch.object(registration, "_acquire_named_lock"):
            with self.assertRaises(registration.RegistrationConflict):
                register(site_code="Q1", full_name="New", email="old@example.com", password="fixture", remote_ip="127.0.0.1")
        self.assertFalse(any("INSERT" in call.args[0] for call in cursor.execute.call_args_list))

    def test_new_registration_hashes_password_and_does_not_enroll_or_charge(self):
        from core.auth import registration
        conn, cursor = connection()
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None
        register = registration.register_student.__wrapped__.__wrapped__
        with patch.object(registration, "provisioning_sites", return_value=("Q1",)), patch.object(registration, "_replicated_account", return_value=None), patch.object(registration, "get_site_database_alias", return_value="auth"), patch.object(registration, "auth_session_alias", return_value="auth"), patch.object(registration, "connections", {"auth": conn}), patch.object(registration.transaction, "atomic", return_value=nullcontext()), patch.object(registration, "_acquire_named_lock"), patch.object(registration, "_next_student_account_id", return_value="Q1-TK-000001"), patch.object(registration, "_next_sequence_number", return_value=1), patch.object(registration, "available_student_slug", return_value="student"), patch.object(registration, "_username_candidate", return_value="student"), patch.object(registration, "_account_slug_candidate", return_value="student-account"):
            result = register(site_code="Q1", full_name="New", email="new@example.com", password="fixture-password", remote_ip="127.0.0.1")
        self.assertEqual(result.account_id, "Q1-TK-000001")
        insert = next(call for call in cursor.execute.call_args_list if "INSERT dbo.TaiKhoan" in call.args[0])
        self.assertTrue(check_password("fixture-password", insert.args[1][4]))
        self.assertEqual(insert.args[1][5:], ["hoc_vien", "Q1", 1, 0, 1])
        self.assertFalse(any("DangKy" in call.args[0] or "HocPhi" in call.args[0] for call in cursor.execute.call_args_list))

    def test_retry_after_local_commit_requires_original_password(self):
        from core.auth import registration
        conn, cursor = connection()
        cursor.fetchall.return_value = [("ACCOUNT", "slug", "username", "new@example.com", make_password("original"), "hoc_vien", "TD", 1, 0, 1)]
        cursor.fetchone.return_value = (1,)
        register = registration.register_student.__wrapped__.__wrapped__
        with patch.object(registration, "provisioning_sites", return_value=("TD", "Q1")), patch.object(registration, "_replicated_account", return_value=None), patch.object(registration, "get_site_database_alias", return_value="local"), patch.object(registration, "auth_session_alias", return_value="auth"), patch.object(registration, "connections", {"local": conn}), patch.object(registration.transaction, "atomic", return_value=nullcontext()), patch.object(registration, "_acquire_named_lock"), patch.object(registration, "_ensure_account_replica") as promote:
            with self.assertRaises(registration.RegistrationConflict):
                register(site_code="TD", full_name="New", email="new@example.com", password="wrong", remote_ip="127.0.0.1")
            promote.assert_not_called()
            self.assertEqual(register(site_code="TD", full_name="New", email="new@example.com", password="original", remote_ip="127.0.0.1").account_id, "ACCOUNT")
            promote.assert_called_once()

    def test_unknown_offline_emails_cannot_be_treated_as_absent_during_bootstrap(self):
        conn, cursor = connection()
        cursor.fetchall.return_value = [("STUDENT", "test@example.com")]
        def read(site):
            if site == "Q7":
                raise DatabaseError("offline")
            return conn
        with patch.object(identity, "active_site_codes", return_value=("Q1", "Q7", "TD")), patch.object(identity, "get_site_connection", side_effect=read), patch.object(identity, "reserve_email") as reserve:
            with self.assertRaises(DatabaseError):
                identity.seed_student_emails()
        reserve.assert_not_called()

    def test_operator_can_opt_in_to_bootstrap_without_offline_sites(self):
        conn, cursor = connection()
        cursor.fetchall.return_value = [("STUDENT", "test@example.com")]
        registry, _ = connection()
        def read(site):
            if site == "Q7":
                raise DatabaseError("offline")
            return conn
        with (
            patch.object(identity, "active_site_codes", return_value=("Q1", "Q7")),
            patch.object(identity, "get_site_connection", side_effect=read),
            patch.object(identity, "auth_session_alias", return_value="auth"),
            patch.object(identity, "connections", {"auth": registry}),
            patch.object(identity.transaction, "atomic", return_value=nullcontext()),
            patch.object(identity, "_acquire_named_lock"),
            patch.object(identity, "reserve_email", return_value="key") as reserve,
            override_settings(AUTH_SESSION_SITE_CODE="Q1"),
        ):
            reserved, skipped = identity.seed_student_emails(allow_missing_sites=True)
        self.assertEqual((reserved, skipped), (1, ("Q7",)))
        reserve.assert_called_once()

    def test_duplicate_email_is_checked_in_registry_without_querying_other_sites(self):
        local, local_cursor = connection()
        local_cursor.fetchone.return_value = ("hoat_dong",)
        registry, registry_cursor = connection()
        registry_cursor.fetchone.side_effect = [(1,), ("Q7", None), None]  # last: no website account holds the email
        local_cursor.fetchall.return_value = []
        with patch.object(identity, "get_site_connection", return_value=local) as read, patch.object(identity, "auth_session_alias", return_value="auth"), patch.object(identity, "connections", {"auth": registry}), patch.object(identity.transaction, "atomic", return_value=nullcontext()), patch.object(identity, "_acquire_named_lock"):
            with self.assertRaises(identity.StudentEmailConflict):
                identity.reserve_email("same@example.com", "Q1")
        self.assertTrue(all(call.args == ("Q1",) for call in read.call_args_list))


class RegistrationWithoutSiteTests(SimpleTestCase):
    def test_site_is_optional_and_defaults_to_the_authority(self):
        from core.auth.serializers import AuthRegisterSerializer

        data = {"full_name": "Minh", "email": "m@example.com", "password": "x" * 12, "confirm_password": "x" * 12}
        serializer = AuthRegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("site_code", serializer.validated_data)
