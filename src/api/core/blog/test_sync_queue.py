"""Blog write queue: intents are replayed oldest first and stop when a site is still unreachable."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.blog import sync_queue
from core.blog.services import PublicBlogConflict, PublicBlogUnavailable
from core.blog.views import AdminBlogSyncView


def operation(n):
    return {"ma_log": f"BLINT-{n:064d}", "actor_id": "Q1-TK-000001", "action": "tao", "entity": "article",
            "slug": f"bai-{n}", "payload": {"title": "T"}, "idempotency_key": f"key-{n}"}


@override_settings(AUTH_SESSION_SITE_CODE="Q1")
class ReconcileTests(SimpleTestCase):
    def run_pass(self, operations, outcomes):
        with (
            patch.object(sync_queue, "_registry_alias", return_value="auth"),
            patch.object(sync_queue, "list_pending", return_value=operations),
            patch.object(sync_queue, "_marker") as marker,
            patch.object(sync_queue, "status", return_value={"pending_count": 0, "review_count": 0}),
            patch("core.blog.write_services.write_blog", side_effect=outcomes) as write,
        ):
            result = sync_queue.reconcile_pending_blog_writes()
        return result, marker, write

    def test_finished_operations_are_marked_done_in_order(self):
        result, marker, write = self.run_pass([operation(1), operation(2)], [{"complete": True}, {"complete": True}])
        self.assertEqual(result["completed"], 2)
        self.assertEqual([call.kwargs["prefix"] for call in marker.call_args_list], ["BLFIN-", "BLFIN-"])
        self.assertEqual([call.kwargs["slug"] for call in write.call_args_list], ["bai-1", "bai-2"])

    def test_pass_stops_at_the_first_operation_that_cannot_finish(self):
        result, marker, write = self.run_pass([operation(1), operation(2)], [{"complete": False}, {"complete": True}])
        self.assertEqual(result["completed"], 0)
        marker.assert_not_called()
        self.assertEqual(write.call_count, 1)
        _, _, write = self.run_pass([operation(1), operation(2)], [PublicBlogUnavailable("x"), {"complete": True}])
        self.assertEqual(write.call_count, 1)

    def test_a_conflict_is_flagged_for_review_and_the_pass_continues(self):
        result, marker, write = self.run_pass([operation(1), operation(2)], [PublicBlogConflict("lệch"), {"complete": True}])
        prefixes = [call.kwargs["prefix"] for call in marker.call_args_list]
        self.assertEqual(prefixes, ["BLREV-", "BLFIN-"])
        self.assertEqual(marker.call_args_list[0].kwargs["detail"], "lệch")
        self.assertEqual(result["completed"], 1)


class EnqueueTests(SimpleTestCase):
    def test_enqueue_stores_the_intent_once_per_idempotency_key(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [None, (7,)]
        with override_settings(AUTH_SESSION_SITE_CODE="Q1"), patch.object(sync_queue, "connections", {"auth": conn}):
            sync_queue.enqueue("auth", entity="article", action="tao", slug="bai", payload={
                "title": "T", "published_at": datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc)},
                idempotency_key="key-1", request_hash="h" * 64, actor_id="Q1-TK-000001")
            insert = next(call for call in cursor.execute.call_args_list if "INSERT INTO dbo.Logs" in call.args[0])
            self.assertIn("2026-11-26T01:00:00Z", insert.args[1][6])
            cursor.fetchone.side_effect = [(1,)]
            cursor.execute.reset_mock()
            sync_queue.enqueue("auth", entity="article", action="tao", slug="bai", payload=None,
                               idempotency_key="key-1", request_hash="h" * 64, actor_id="a")
            self.assertFalse(any("INSERT INTO dbo.Logs" in call.args[0] for call in cursor.execute.call_args_list))

    def test_stored_datetimes_round_trip_to_the_same_value(self):
        stored = datetime.fromisoformat("2026-11-26T01:00:00Z")
        self.assertEqual(stored, datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc))


class SyncViewTests(SimpleTestCase):
    def call(self, method, role):
        request = getattr(APIRequestFactory(), method)("/x/")
        force_authenticate(request, user=SimpleNamespace(role=role, account_id="A", pk="A", is_authenticated=True))
        return AdminBlogSyncView.as_view()(request)

    def test_only_blog_editors_can_read_or_trigger_a_sync(self):
        self.assertEqual(self.call("get", "hoc_vien").status_code, 403)
        self.assertEqual(self.call("post", "giao_vien").status_code, 403)
        with patch("core.blog.views.sync_queue.status", return_value={"pending_count": 2, "review_count": 0}):
            response = self.call("get", "tu_van")
        self.assertEqual((response.status_code, response.data["pending_count"]), (200, 2))
