from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from core.employees.services import EmployeeDeactivationResult


class EmployeeDeleteApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_big = SimpleNamespace(
            is_authenticated=True, role="admin_big", account_id="Q1-TK-000001",
            pk="Q1-TK-000001",
        )
        self.admin_small = SimpleNamespace(
            is_authenticated=True, role="admin_small", account_id="Q7-TK-000002",
            site_code="Q7", pk="Q7-TK-000002",
        )
        self.employee = SimpleNamespace(
            is_authenticated=True, role="tu_van", account_id="Q7-TK-000003",
            site_code="Q7", pk="Q7-TK-000003",
        )
        self.result = EmployeeDeactivationResult(
            employee_id="Q7-NV-000001", account_id="Q7-TK-000010",
            slug="nhan-vien-q7-tu-van", site_code="Q7",
        )

    def test_openapi_has_employee_delete_by_slug(self):
        response = self.client.get("/api/schema/", {"format": "json"})

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("get", paths["/api/v1/admin/employees/"])
        self.assertIn("post", paths["/api/v1/admin/employees/"])
        self.assertIn("delete", paths["/api/v1/admin/employees/{slug}/"])

    def test_admin_big_deletes_employee_in_selected_site(self):
        self.client.force_authenticate(user=self.admin_big)

        with patch("core.employees.views.deactivate_employee", return_value=self.result) as delete:
            response = self.client.delete(
                "/api/v1/admin/employees/nhan-vien-q7-tu-van/?site_code=Q7"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["employee_status"], "nghi_viec")
        self.assertEqual(response.json()["status"], "inactive")
        delete.assert_called_once_with(
            slug="nhan-vien-q7-tu-van", site_code="Q7",
            actor_id="Q1-TK-000001", remote_ip="127.0.0.1",
        )

    def test_admin_small_can_delete_only_within_own_site(self):
        self.client.force_authenticate(user=self.admin_small)

        with patch("core.employees.views.deactivate_employee", return_value=self.result) as delete:
            allowed = self.client.delete("/api/v1/admin/employees/nhan-vien-q7-tu-van/")
            forbidden = self.client.delete(
                "/api/v1/admin/employees/nhan-vien-q7-tu-van/?site_code=Q1"
            )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(delete.call_count, 1)
        self.assertEqual(delete.call_args.kwargs["site_code"], "Q7")

    def test_admin_big_must_select_site_and_other_roles_cannot_delete(self):
        self.client.force_authenticate(user=self.admin_big)
        with patch("core.employees.views.deactivate_employee") as delete:
            missing_site = self.client.delete(
                "/api/v1/admin/employees/nhan-vien-q7-tu-van/"
            )
        self.assertEqual(missing_site.status_code, 400)
        delete.assert_not_called()

        self.client.force_authenticate(user=self.employee)
        with patch("core.employees.views.deactivate_employee") as delete:
            forbidden = self.client.delete(
                "/api/v1/admin/employees/nhan-vien-q7-tu-van/?site_code=Q7"
            )
        self.assertEqual(forbidden.status_code, 403)
        delete.assert_not_called()
