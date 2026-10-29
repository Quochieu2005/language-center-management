from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core.auth.service_common import AuthenticatedUser
from core.notifications.publisher import publish_notification
from core.notifications import services as notification_services


class NotificationApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_big = AuthenticatedUser(
            account_id="Q1-TK-000001", email="big@example.test", username="big",
            slug="admin-big", role="admin_big",
        )
        self.admin_small = AuthenticatedUser(
            account_id="Q7-TK-000002", email="small@example.test", username="small",
            slug="admin-small", role="admin_small", site_code="Q7",
        )

    @patch("core.notifications.views.list_notifications")
    def test_admin_big_lists_global_notifications(self, list_service):
        list_service.return_value = {
            "complete": True, "missing_sites": [], "site_codes": ["Q1", "Q7", "TD"],
            "count": 0, "limit": 20, "offset": 0, "results": [],
        }
        self.client.force_authenticate(user=self.admin_big)

        response = self.client.get(reverse("core:admin-notification-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["site_codes"], ["Q1", "Q7", "TD"])
        list_service.assert_called_once_with(
            role="admin_big",
            user_site_code=None,
            site_code=None,
            category=None,
            limit=20,
            offset=0,
        )

    @patch("core.notifications.views.list_notifications")
    def test_admin_small_is_limited_to_assigned_site(self, list_service):
        list_service.return_value = {
            "complete": True, "missing_sites": [], "site_codes": ["Q7"],
            "count": 1, "limit": 20, "offset": 0, "results": [],
        }
        self.client.force_authenticate(user=self.admin_small)

        response = self.client.get(reverse("core:admin-notification-list"))

        self.assertEqual(response.status_code, 200)
        list_service.assert_called_once()
        self.assertEqual(list_service.call_args.kwargs["user_site_code"], "Q7")

    @patch("core.notifications.views.list_notifications")
    def test_admin_small_cannot_select_another_site(self, list_service):
        self.client.force_authenticate(user=self.admin_small)

        response = self.client.get(reverse("core:admin-notification-list"), {"site_code": "Q1"})

        self.assertEqual(response.status_code, 403)
        list_service.assert_not_called()

    @patch("core.notifications.views.list_notifications")
    def test_partial_global_result_is_not_reported_as_complete(self, list_service):
        list_service.return_value = {
            "complete": False, "missing_sites": ["TD"], "site_codes": ["Q1", "Q7"],
            "count": 0, "limit": 20, "offset": 0, "results": [],
        }
        self.client.force_authenticate(user=self.admin_big)

        response = self.client.get(reverse("core:admin-notification-list"))

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["complete"])
        self.assertEqual(response.json()["missing_sites"], ["TD"])

    def test_teacher_cannot_read_admin_notifications(self):
        teacher = AuthenticatedUser(
            account_id="Q7-TK-000003", email="teacher@example.test", username="teacher",
            slug="teacher", role="giao_vien", site_code="Q7",
        )
        self.client.force_authenticate(user=teacher)

        response = self.client.get(reverse("core:admin-notification-list"))

        self.assertEqual(response.status_code, 403)

    def test_swagger_schema_exposes_notification_list_without_read_tracking_routes(self):
        response = self.client.get(reverse("schema"), {"format": "json"})

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("get", paths["/api/v1/admin/notifications/"])
        self.assertNotIn("/api/v1/admin/notifications/unread-count/", paths)
        self.assertNotIn("/api/v1/admin/notifications/read-all/", paths)
        self.assertNotIn("/api/v1/admin/notifications/{site_code}/{slug}/read/", paths)


class NotificationPublisherTests(SimpleTestCase):
    def test_publish_uses_parameterized_sql_and_deterministic_slug(self):
        cursor = Mock()
        first = publish_notification(
            cursor,
            site_code="Q7",
            event_key="teacher-created:Q7-GV-000001",
            category="teacher",
            severity="success",
            title="Giáo viên mới được tạo",
            message="Hồ sơ giáo viên được tạo.",
            target_path="/admin/teachers?site_code=Q7",
        )
        second = publish_notification(
            cursor,
            site_code="Q7",
            event_key="teacher-created:Q7-GV-000001",
            category="teacher",
            severity="success",
            title="Giáo viên mới được tạo",
            message="Hồ sơ giáo viên được tạo.",
            target_path="/admin/teachers?site_code=Q7",
        )

        self.assertEqual(first, second)
        sql, params = cursor.execute.call_args.args
        self.assertIn("IF NOT EXISTS", sql)
        self.assertNotIn("teacher-created:Q7-GV-000001", sql)
        self.assertIn("teacher-created:Q7-GV-000001", params)

    def test_publish_rejects_external_notification_target(self):
        with self.assertRaises(ValueError):
            publish_notification(
                Mock(), site_code="Q1", event_key="bad-target", category="system",
                title="Hệ thống", message="Thông tin", target_path="https://example.test",
            )


class NotificationReadOnlySummaryTests(SimpleTestCase):
    def test_tuition_summary_query_is_read_only(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (2, 250000, "Q1-HP-000002")
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        connection_handler = MagicMock()
        connection_handler.__getitem__.return_value = connection

        with (
            patch("core.notifications.services.get_site_database_alias", return_value="Q1"),
            patch("core.notifications.services.connections", connection_handler),
        ):
            item = notification_services._live_tuition_summary("Q1")

        self.assertIsNotNone(item)
        self.assertEqual(item["category"], "tuition")
        sql = cursor.execute.call_args.args[0].upper()
        self.assertTrue(sql.lstrip().startswith("SELECT"))
        self.assertNotRegex(sql, r"\b(INSERT|UPDATE|DELETE|MERGE)\b")

    @patch("core.notifications.services._live_tuition_summary")
    @patch("core.notifications.services._site_items", return_value=[])
    @patch("core.notifications.services._site_counts", return_value=3)
    @patch("core.notifications.services._global_sites", return_value=(("Q1",), ()))
    def test_list_adds_live_summary_without_persisting_it(
        self, _global_sites, _site_counts, _site_items, live_summary,
    ):
        live_summary.return_value = {
            "slug": "live-q1-tuition-123", "site_code": "Q1", "category": "tuition",
            "severity": "warning", "title": "Học phí còn thiếu", "message": "Có khoản cần thu.",
            "target_path": "/admin/tuition?site_code=Q1", "created_at": datetime.now(timezone.utc),
        }

        result = notification_services.list_notifications(role="admin_big")

        self.assertEqual(result["count"], 4)
        self.assertEqual([item["slug"] for item in result["results"]], ["live-q1-tuition-123"])
        live_summary.assert_called_once_with("Q1")
