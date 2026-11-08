from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.classes import public_enrollment
from core.classes.serializers import PublicEnrollmentCreateSerializer
from core.classes.services import ClassConflict
from core.classes.public_views import PublicEnrollmentEmailThrottle


class PublicEnrollmentTests(SimpleTestCase):
    def test_email_throttle_uses_normalized_email_and_client_ip(self):
        throttle = PublicEnrollmentEmailThrottle()

        def key(email):
            request = SimpleNamespace(data={"email": email}, META={"REMOTE_ADDR": "192.0.2.1"})
            return throttle.get_cache_key(request, None)

        self.assertEqual(key("Student@example.com"), key(" student@EXAMPLE.com "))
        self.assertNotEqual(key("student@example.com"), key("other@example.com"))

    def test_serializer_normalizes_email_and_rejects_invalid_phone(self):
        serializer = PublicEnrollmentCreateSerializer(data={
            "site_code": "q1",
            "class_id": "Q1-LH-000001",
            "full_name": " Nguyễn Văn A ",
            "email": " Student@Example.com ",
            "phone": "0912 345 678",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["site_code"], "Q1")
        self.assertEqual(serializer.validated_data["email"], "student@example.com")

        invalid = PublicEnrollmentCreateSerializer(data={
            "site_code": "Q1", "class_id": "Q1-LH-000001",
            "full_name": "Nguyễn Văn A", "email": "student@example.com",
            "phone": "not-a-phone",
        })
        self.assertFalse(invalid.is_valid())
        self.assertIn("phone", invalid.errors)

    def test_registration_creates_local_student_then_calls_existing_enrollment_flow(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.__exit__.return_value = False
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        enrollment_result = {"created": True}

        with (
            patch.object(public_enrollment, "active_site_codes", return_value=("Q1", "Q7")),
            patch.object(public_enrollment, "_sites_with_email", return_value=()),
            patch.object(public_enrollment, "get_site_database_alias", return_value="q1"),
            patch.object(public_enrollment, "connections", {"q1": connection}),
            patch.object(public_enrollment.transaction, "atomic", return_value=nullcontext()),
            patch.object(public_enrollment, "_active_site"),
            patch.object(public_enrollment, "_acquire_named_lock"),
            patch.object(public_enrollment, "_next_identifier", return_value="Q1-HV-000001"),
            patch.object(public_enrollment, "make_slug", return_value="nguyen-van-a"),
            patch.object(public_enrollment, "_audit"),
            patch.object(public_enrollment, "register_student_to_class", return_value=enrollment_result) as register,
        ):
            result = public_enrollment.create_public_enrollment(
                site_code="q1", class_id="Q1-LH-000001", full_name="Nguyễn Văn A",
                email="student@example.com", phone=None, remote_ip="127.0.0.1",
            )

        self.assertTrue(any("INSERT INTO dbo.HocVien" in call.args[0] for call in cursor.execute.call_args_list))
        register.assert_called_once_with(
            site_code="Q1", student_id="Q1-HV-000001", class_id="Q1-LH-000001",
            actor_id=None, remote_ip="127.0.0.1",
        )
        self.assertEqual(result["site_code"], "Q1")
        self.assertTrue(result["accepted"])

    def test_registration_rejects_email_found_at_another_site(self):
        with (
            patch.object(public_enrollment, "active_site_codes", return_value=("Q1", "Q7")),
            patch.object(public_enrollment, "_sites_with_email", return_value=("Q7",)),
        ):
            with self.assertRaises(ClassConflict):
                public_enrollment.create_public_enrollment(
                    site_code="Q1", class_id="Q1-LH-000001", full_name="Nguyễn Văn A",
                    email="student@example.com", phone=None, remote_ip="127.0.0.1",
                )
