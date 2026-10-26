import json

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from core.sites.connections import UnknownSiteError, get_site_database_alias
from core.media.folders import build_asset_folder


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
