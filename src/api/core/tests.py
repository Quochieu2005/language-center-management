import json

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from core.sites.connections import UnknownSiteError, get_site_database_alias


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
