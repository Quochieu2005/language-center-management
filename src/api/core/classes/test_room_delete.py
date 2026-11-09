from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from core.classes import services
from core.classes.services import ClassConflict
from core.classes.views import RoomDetailView


class RoomDeleteServiceTests(SimpleTestCase):
    def _delete_with_references(self, reference):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.__exit__.return_value = False
        cursor.fetchone.side_effect = [("hoat_dong",), ("Room A",), reference]
        cursor.rowcount = 1
        connection = MagicMock()
        connection.cursor.return_value = cursor
        patches = (
            patch.object(services, "get_site_database_alias", return_value="site_q1"),
            patch.object(services, "connections", {"site_q1": connection}),
            patch.object(services.transaction, "atomic", return_value=nullcontext()),
            patch.object(services, "_audit"),
        )
        return cursor, patches

    def test_delete_rejects_a_room_referenced_by_class_or_session(self):
        cursor, patches = self._delete_with_references(("Q1-LH-000001",))
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(ClassConflict):
                services.delete_room(
                    site_code="Q1", room_id="Q1-PH-000001", actor_id="Q1-TK-1", remote_ip="127.0.0.1"
                )

        self.assertFalse(any(call.args[0].startswith("DELETE FROM dbo.PhongHoc") for call in cursor.execute.call_args_list))

    def test_delete_unreferenced_room_and_audit_in_same_transaction(self):
        cursor, patches = self._delete_with_references(None)
        with patches[0], patches[1], patches[2], patches[3] as audit:
            result = services.delete_room(
                site_code="Q1", room_id="Q1-PH-000001", actor_id="Q1-TK-1", remote_ip="127.0.0.1"
            )

        self.assertEqual(result, {"room_id": "Q1-PH-000001", "site_code": "Q1", "deleted": True})
        self.assertTrue(any(call.args[0].startswith("DELETE FROM dbo.PhongHoc") for call in cursor.execute.call_args_list))
        audit.assert_called_once()


class RoomDeletePermissionTests(SimpleTestCase):
    def _request(self, role, site_code, query=""):
        request = APIRequestFactory().delete(f"/api/v1/admin/rooms/Q1-PH-000001/{query}")
        force_authenticate(request, user=SimpleNamespace(
            is_authenticated=True, pk=f"{site_code}-TK-1", role=role,
            site_code=site_code, account_id=f"{site_code}-TK-1",
        ))
        return request

    @patch("core.classes.views.delete_room", return_value={
        "room_id": "Q7-PH-000001", "site_code": "Q7", "deleted": True,
    })
    def test_admin_small_can_only_delete_within_own_site(self, delete_room):
        response = RoomDetailView.as_view()(self._request("admin_small", "Q7"), room_id="Q7-PH-000001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(delete_room.call_args.kwargs["site_code"], "Q7")

        response = RoomDetailView.as_view()(
            self._request("admin_small", "Q7", "?site_code=Q1"), room_id="Q1-PH-000001"
        )
        self.assertEqual(response.status_code, 403)

    @patch("core.classes.views.delete_room")
    def test_non_admin_cannot_delete_room(self, delete_room):
        response = RoomDetailView.as_view()(self._request("le_tan", "Q1"), room_id="Q1-PH-000001")

        self.assertEqual(response.status_code, 403)
        delete_room.assert_not_called()

    @patch("core.classes.views.delete_room")
    def test_admin_big_must_choose_site(self, delete_room):
        response = RoomDetailView.as_view()(self._request("admin_big", None), room_id="Q1-PH-000001")

        self.assertEqual(response.status_code, 400)
        delete_room.assert_not_called()
