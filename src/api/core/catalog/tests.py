from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.catalog import services
from core.catalog.serializers import SharedSubjectPatchSerializer
from core.catalog.views import SharedSubjectDetailView


def _subject(version=4, *, name="English", description="General English"):
    return {
        "ma_mon": "MH-ENG",
        "slug": "english",
        "ten_mon": name,
        "mo_ta": description,
        "phien_ban": version,
    }


def _event(before, after, request_hash):
    return {"before": before, "after": after, "request_hash": request_hash}


class SharedCatalogReplicationTests(SimpleTestCase):
    def setUp(self):
        self.patchers = [
            patch.object(services, "active_site_state", return_value=(("Q1", "Q7", "TD"), ())),
            patch.object(services, "get_site_database_alias", side_effect=lambda site: f"site_{site.lower()}"),
            patch.object(services, "connections", {"site_q1": SimpleNamespace(cursor=lambda: nullcontext())}),
            patch.object(services, "acquire_record_lock"),
            patch.object(services.transaction, "atomic", side_effect=lambda using: nullcontext()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_first_update_writes_all_active_sites(self, read_site, apply_site):
        before = _subject()
        read_site.side_effect = lambda site, slug, event_id: (before.copy(), None)

        result = services.update_shared_subject(
            slug="english", patch={"ten_mon": "English A1"},
            idempotency_key="request-0001", actor_id="Q1-TK-000001",
        )

        self.assertTrue(result["complete"])
        self.assertEqual(result["phien_ban"], 5)
        self.assertEqual(result["sites"], ["Q1", "Q7", "TD"])
        self.assertEqual(apply_site.call_count, 3)

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_retry_resumes_only_sites_without_ack(self, read_site, apply_site):
        before = _subject()
        after = _subject(5, name="English A1")
        request_hash = services._fingerprint({"ten_mon": "English A1"})
        states = {
            "Q1": (after.copy(), _event(before, after, request_hash)),
            "Q7": (before.copy(), None),
            "TD": (after.copy(), _event(before, after, request_hash)),
        }
        read_site.side_effect = lambda site, slug, event_id: states[site]

        result = services.update_shared_subject(
            slug="english", patch={"ten_mon": "English A1"},
            idempotency_key="request-0001", actor_id="Q1-TK-000001",
        )

        self.assertTrue(result["complete"])
        self.assertTrue(result["idempotent_replay"])
        apply_site.assert_called_once()
        self.assertEqual(apply_site.call_args.kwargs["site_code"], "Q7")

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_retry_with_same_key_and_different_body_is_conflict(self, read_site, apply_site):
        before = _subject()
        after = _subject(5, name="English A1")
        read_site.side_effect = lambda site, slug, event_id: (
            after.copy(), _event(before, after, services._fingerprint({"ten_mon": "English A1"}))
        )

        with self.assertRaises(services.SharedCatalogConflict):
            services.update_shared_subject(
                slug="english", patch={"ten_mon": "English A2"},
                idempotency_key="request-0001", actor_id="Q1-TK-000001",
            )
        apply_site.assert_not_called()

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_remote_write_error_returns_incomplete_retryable_result(self, read_site, apply_site):
        before = _subject()
        read_site.side_effect = lambda site, slug, event_id: (before.copy(), None)

        def fail_q7(**kwargs):
            if kwargs["site_code"] == "Q7":
                raise DatabaseError("injected site write failure")

        apply_site.side_effect = fail_q7
        result = services.update_shared_subject(
            slug="english", patch={"ten_mon": "English A1"},
            idempotency_key="request-0001", actor_id="Q1-TK-000001",
        )

        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_sites"], ["Q7"])
        self.assertIn("Q1", result["sites"])
        self.assertIn("TD", result["sites"])

    def test_patch_rejects_fields_outside_subject_contract(self):
        serializer = SharedSubjectPatchSerializer(
            data={"ten_mon": "English A1", "ma_co_so": "TD", "phien_ban": 99}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"ma_co_so", "phien_ban"})

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_missing_active_site_blocks_all_replication_writes(self, read_site, apply_site):
        with patch.object(services, "active_site_state", return_value=(("Q1", "Q7"), ("TD",))):
            with self.assertRaises(services.SharedCatalogUnavailable) as raised:
                services.update_shared_subject(
                    slug="english", patch={"ten_mon": "English A1"},
                    idempotency_key="request-0001", actor_id="Q1-TK-000001",
                )

        self.assertEqual(raised.exception.missing_sites, ("TD",))
        read_site.assert_not_called()
        apply_site.assert_not_called()


class SharedCatalogPermissionTests(SimpleTestCase):
    def test_only_admin_big_can_write_shared_subjects(self):
        request = APIRequestFactory().patch(
            "/api/v1/admin/shared/subjects/english/",
            {"ten_mon": "English A1"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="request-0001",
        )
        force_authenticate(
            request,
            user=SimpleNamespace(
                is_authenticated=True, pk="Q1-TK-1", role="admin_small", account_id="Q1-TK-1"
            ),
        )
        with patch("core.catalog.views.update_shared_subject") as update:
            response = SharedSubjectDetailView.as_view()(request, slug="english")

        self.assertEqual(response.status_code, 403)
        update.assert_not_called()
