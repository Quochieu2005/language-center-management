import json
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import resolve, reverse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient, APIRequestFactory

from core.sites.connections import UnknownSiteError, get_site_database_alias
from core.media.folders import build_asset_folder
from core.auth.authentication import AuthCookieAuthentication
from core.auth.services import (
    AdminSmallProvisioningResult,
    AuthenticatedSession,
    AuthenticatedUser,
)


class HealthCheckTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_is_public_and_does_not_require_a_database(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "qlttnn-api"})

    def test_swagger_ui_is_the_generated_dr_spectacular_interface(self):
        response = self.client.get(reverse("swagger-ui"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"swagger-ui", response.content.lower())
        self.assertIn(b"/api/schema/", response.content)

    def test_openapi_schema_contains_the_real_health_route(self):
        response = self.client.get(reverse("schema"), {"format": "json"})

        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        self.assertIn("/api/v1/health/", schema["paths"])
        self.assertIn("get", schema["paths"]["/api/v1/health/"])
        self.assertIn("/api/v1/admin/admin-smalls/", schema["paths"])

    def test_site_database_resolves_only_a_configured_site_code(self):
        with override_settings(SITE_DATABASE_ALIASES={"Q7": "site_q7"}):
            self.assertEqual(get_site_database_alias("Q7"), "site_q7")
            with self.assertRaises(UnknownSiteError):
                get_site_database_alias("untrusted-alias")

    def test_default_database_cannot_store_application_data(self):
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.dummy")


class CloudinaryAssetFolderTests(SimpleTestCase):
    @override_settings(CLOUDINARY_ROOT_FOLDER="language-center-management")
    def test_student_image_gets_its_own_site_and_record_folder(self):
        folder = build_asset_folder(
            "student",
            site_code="Q1",
            record_code="Q1-HV-000001",
            asset_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        )

        self.assertEqual(
            folder,
            "language-center-management/hoc-vien/Q1/Q1-HV-000001/anh/"
            "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        )

    @override_settings(CLOUDINARY_ROOT_FOLDER="language-center-management")
    def test_shared_course_image_does_not_include_site(self):
        folder = build_asset_folder(
            "course",
            record_code="KH-IELTS-65",
            asset_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        )

        self.assertEqual(
            folder,
            "language-center-management/khoa-hoc/dung-chung/KH-IELTS-65/anh/"
            "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        )

    @override_settings(CLOUDINARY_ROOT_FOLDER="language-center-management")
    def test_site_specific_image_rejects_missing_site(self):
        with self.assertRaisesRegex(ValueError, "mã site"):
            build_asset_folder(
                "teacher",
                record_code="Q7-GV-000001",
                asset_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            )

    @override_settings(CLOUDINARY_ROOT_FOLDER="language-center-management")
    def test_untrusted_path_segments_and_unknown_resources_are_rejected(self):
        with self.assertRaises(ValueError):
            build_asset_folder(
                "student",
                site_code="Q1/../Q7",
                record_code="Q1-HV-000001",
                asset_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            )
        with self.assertRaises(ValueError):
            build_asset_folder(
                "unknown",
                record_code="Q1-HV-000001",
                asset_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            )


class AdminSmallProvisioningApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "full_name": "Nguyễn Văn Quản Lý",
            "email": "manager.q7@example.com",
            "site_code": "Q7",
        }

    def test_only_admin_big_can_create_admin_small(self):
        self.client.force_authenticate(
            user=SimpleNamespace(
                is_authenticated=True, role="admin_small", account_id="Q1-TK-000001", pk="Q1-TK-000001"
            )
        )

        with patch("core.auth.views.create_admin_small") as create_account:
            response = self.client.post("/api/v1/admin/admin-smalls/", self.payload, format="json")

        self.assertEqual(response.status_code, 403)
        create_account.assert_not_called()

    def test_admin_big_creates_account_and_response_never_contains_password(self):
        self.client.force_authenticate(
            user=SimpleNamespace(
                is_authenticated=True, role="admin_big", account_id="Q1-TK-000001", pk="Q1-TK-000001"
            )
        )
        result = AdminSmallProvisioningResult(
            account_id="Q7-TK-000123",
            employee_id="Q7-NV-000045",
            username="manager.q7",
            email="manager.q7@example.com",
            site_code="Q7",
        )

        with patch("core.auth.views.create_admin_small", return_value=(result, True)) as create_account:
            response = self.client.post("/api/v1/admin/admin-smalls/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], "admin_small")
        self.assertTrue(response.json()["must_change_password"])
        self.assertTrue(response.json()["email_sent"])
        self.assertNotIn("password", response.json())
        self.assertNotIn("1234567890", response.content.decode())
        create_account.assert_called_once()


class TemporaryPasswordAccessTests(SimpleTestCase):
    def setUp(self):
        self.user = AuthenticatedUser(
            account_id="Q7-TK-000123",
            email="manager.q7@example.com",
            username="manager.q7",
            slug="admin-small-q7-manager-q7",
            role="admin_small",
            site_code="Q7",
            profile_id="Q7-NV-000045",
            must_change_password=True,
        )
        self.session = AuthenticatedSession(token_digest="a" * 64, session_id="session", expires_at=None)

    def test_temporary_password_blocks_business_endpoints(self):
        request = APIRequestFactory().get("/api/v1/admin/admin-smalls/")
        request.COOKIES[settings.AUTH_COOKIE_NAME] = "a" * 64
        request.resolver_match = resolve("/api/v1/admin/admin-smalls/")

        with patch(
            "core.auth.authentication.load_user_session", return_value=(self.user, self.session)
        ):
            with self.assertRaises(AuthenticationFailed) as caught:
                AuthCookieAuthentication().authenticate(request)

        self.assertEqual(caught.exception.get_codes(), "password_change_required")

    def test_temporary_password_allows_account_profile_check(self):
        request = APIRequestFactory().get("/api/v1/auth/me/")
        request.COOKIES[settings.AUTH_COOKIE_NAME] = "a" * 64
        request.resolver_match = resolve("/api/v1/auth/me/")

        with patch(
            "core.auth.authentication.load_user_session", return_value=(self.user, self.session)
        ):
            authenticated = AuthCookieAuthentication().authenticate(request)

        self.assertEqual(authenticated[0], self.user)
