from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from core.auth.account_status import AccountStatusResult
from core.teachers.services import TeacherDeactivationResult, TeacherProvisioningResult


class TeacherManagementApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_big = SimpleNamespace(
            is_authenticated=True,
            role="admin_big",
            account_id="Q1-TK-000001",
            pk="Q1-TK-000001",
        )
        self.admin_small = SimpleNamespace(
            is_authenticated=True,
            role="admin_small",
            account_id="Q7-TK-000002",
            site_code="Q7",
            pk="Q7-TK-000002",
        )
        self.teacher = SimpleNamespace(
            is_authenticated=True,
            role="giao_vien",
            account_id="Q7-TK-000003",
            slug="giao-vien-q7-teacher-q7",
            site_code="Q7",
            pk="Q7-TK-000003",
        )
        self.create_payload = {
            "full_name": "Nguyễn An",
            "email": "teacher.q7@example.com",
            "username": "teacher.q7",
            "phone": "0901234567",
            "specialty": "Tiếng Anh giao tiếp",
        }
        self.created = TeacherProvisioningResult(
            teacher_id="Q7-GV-000001",
            account_id="Q7-TK-000010",
            site_code="Q7",
            full_name="Nguyễn An",
            phone="0901234567",
            email="teacher.q7@example.com",
            username="teacher.q7",
            slug="giao-vien-q7-teacher-q7",
            specialty="Tiếng Anh giao tiếp",
        )

    def test_openapi_lists_teacher_crud_routes(self):
        response = self.client.get("/api/schema/", {"format": "json"})

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("get", paths["/api/v1/admin/teachers/"])
        self.assertIn("post", paths["/api/v1/admin/teachers/"])
        self.assertIn("get", paths["/api/v1/admin/teachers/{slug}/"])
        self.assertNotIn("patch", paths["/api/v1/admin/teachers/{slug}/"])
        self.assertIn("delete", paths["/api/v1/admin/teachers/{slug}/"])
        self.assertIn("patch", paths["/api/v1/admin/teachers/{slug}/status/"])
        self.assertIn("get", paths["/api/v1/teachers/profile/{slug}/"])
        self.assertIn("patch", paths["/api/v1/teachers/profile/{slug}/"])

    def test_admin_big_creates_teacher_at_the_selected_site_without_returning_password(self):
        self.client.force_authenticate(user=self.admin_big)
        payload = {**self.create_payload, "site_code": "Q7"}

        with patch("core.teachers.views.create_teacher", return_value=self.created) as create:
            response = self.client.post("/api/v1/admin/teachers/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["site_code"], "Q7")
        self.assertEqual(response.json()["slug"], self.created.slug)
        self.assertTrue(response.json()["must_change_password"])
        self.assertNotIn("password", response.json())
        self.assertNotIn("1234567890", response.content.decode())
        create.assert_called_once_with(
            full_name="Nguyễn An",
            email="teacher.q7@example.com",
            username="teacher.q7",
            phone="0901234567",
            specialty="Tiếng Anh giao tiếp",
            site_code="Q7",
            actor_id="Q1-TK-000001",
            remote_ip="127.0.0.1",
        )

    def test_admin_small_creates_teacher_only_at_its_authenticated_site(self):
        self.client.force_authenticate(user=self.admin_small)

        with patch("core.teachers.views.create_teacher", return_value=self.created) as create:
            response = self.client.post(
                "/api/v1/admin/teachers/", self.create_payload, format="json"
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["site_code"], "Q7")
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["site_code"], "Q7")
        self.assertEqual(create.call_args.kwargs["actor_id"], "Q7-TK-000002")

    def test_admin_small_cannot_choose_another_site_when_creating(self):
        self.client.force_authenticate(user=self.admin_small)

        with patch("core.teachers.views.create_teacher") as create:
            response = self.client.post(
                "/api/v1/admin/teachers/",
                {**self.create_payload, "site_code": "Q1"},
                format="json",
            )

        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_admin_big_must_choose_site_and_other_roles_cannot_create(self):
        self.client.force_authenticate(user=self.admin_big)
        with patch("core.teachers.views.create_teacher") as create:
            missing_site = self.client.post(
                "/api/v1/admin/teachers/", self.create_payload, format="json"
            )
        self.assertEqual(missing_site.status_code, 400)
        create.assert_not_called()

        self.client.force_authenticate(user=self.teacher)
        with patch("core.teachers.views.create_teacher") as create:
            forbidden = self.client.post(
                "/api/v1/admin/teachers/",
                {**self.create_payload, "site_code": "Q7"},
                format="json",
            )
        self.assertEqual(forbidden.status_code, 403)
        create.assert_not_called()

    def test_create_rejects_client_supplied_role_or_password(self):
        self.client.force_authenticate(user=self.admin_big)

        with patch("core.teachers.views.create_teacher") as create:
            response = self.client.post(
                "/api/v1/admin/teachers/",
                {**self.create_payload, "site_code": "Q7", "role": "admin_big", "password": "unsafe"},
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    def test_admin_roles_can_delete_but_cannot_edit_teacher_profile(self):
        for user, query in (
            (self.admin_big, "?site_code=Q7"),
            (self.admin_small, ""),
        ):
            self.client.force_authenticate(user=user)
            with patch("core.teachers.views.update_teacher") as update:
                response = self.client.patch(
                    f"/api/v1/admin/teachers/giao-vien-q7-teacher-q7/{query}",
                    {"full_name": "Tên mới"},
                    format="json",
                )
            self.assertEqual(response.status_code, 405)
            update.assert_not_called()

            with patch(
                "core.teachers.views.deactivate_teacher",
                return_value=TeacherDeactivationResult(
                    teacher_id="Q7-GV-000001", account_id="Q7-TK-000010", site_code="Q7"
                ),
            ) as deactivate:
                response = self.client.delete(
                    f"/api/v1/admin/teachers/giao-vien-q7-teacher-q7/{query}"
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["teacher_status"], "nghi_viec")
            deactivate.assert_called_once()

    def test_admin_big_and_admin_small_can_toggle_teacher_status_in_scope(self):
        expected = AccountStatusResult(
            account_id="Q7-TK-000010", slug=self.created.slug, role="giao_vien",
            site_code="Q7", status="inactive",
        )
        for user, query in ((self.admin_big, "?site_code=Q7"), (self.admin_small, "")):
            self.client.force_authenticate(user=user)
            with patch("core.teachers.views.change_account_status", return_value=expected) as change:
                response = self.client.patch(
                    f"/api/v1/admin/teachers/{self.created.slug}/status/{query}",
                    {"status": "inactive"},
                    format="json",
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "inactive")
            self.assertEqual(change.call_args.kwargs["expected_role"], "giao_vien")
            self.assertEqual(change.call_args.kwargs["site_code"], "Q7")

    def test_teacher_cannot_list_admin_manage_or_read_another_teacher(self):
        self.client.force_authenticate(user=self.teacher)
        with (
            patch("core.teachers.views.list_teachers") as list_service,
            patch("core.teachers.views.get_teacher") as get_service,
            patch("core.teachers.views.change_account_status") as status_service,
        ):
            list_response = self.client.get("/api/v1/admin/teachers/?site_code=Q7")
            detail_response = self.client.get("/api/v1/admin/teachers/another-teacher/?site_code=Q7")
            status_response = self.client.patch(
                f"/api/v1/admin/teachers/{self.teacher.slug}/status/?site_code=Q7",
                {"status": "inactive"},
                format="json",
            )
            other_profile = self.client.get("/api/v1/teachers/profile/another-teacher/")

        self.assertEqual(
            [list_response.status_code, detail_response.status_code, status_response.status_code,
             other_profile.status_code],
            [403, 403, 403, 404],
        )
        list_service.assert_not_called()
        get_service.assert_not_called()
        status_service.assert_not_called()

    def test_teacher_can_read_and_update_only_own_profile_by_slug(self):
        self.client.force_authenticate(user=self.teacher)
        profile = {
            "teacher_id": "Q7-GV-000001", "account_id": self.teacher.account_id,
            "site_code": "Q7", "slug": self.teacher.slug, "account_status": "active",
            "full_name": "Tên mới", "phone": None, "email": "teacher@example.com",
            "username": "teacher.q7", "specialty": "Tiếng Anh", "status": "dang_day",
        }
        with (
            patch("core.teachers.views.get_teacher", return_value=profile) as get_service,
            patch("core.teachers.views.update_teacher", return_value=profile) as update_service,
        ):
            get_response = self.client.get(f"/api/v1/teachers/profile/{self.teacher.slug}/")
            update_response = self.client.patch(
                f"/api/v1/teachers/profile/{self.teacher.slug}/",
                {"full_name": "Tên mới"},
                format="json",
            )

        self.assertEqual((get_response.status_code, update_response.status_code), (200, 200))
        get_service.assert_called_once_with(slug=self.teacher.slug, site_code="Q7")
        update_service.assert_called_once_with(
            slug=self.teacher.slug, site_code="Q7", actor_id=self.teacher.account_id,
            updates={"full_name": "Tên mới"}, remote_ip="127.0.0.1",
        )

    def test_admin_small_cannot_read_edit_or_delete_a_teacher_at_another_site(self):
        self.client.force_authenticate(user=self.admin_small)

        with (
            patch("core.teachers.views.get_teacher") as get_teacher,
            patch("core.teachers.views.update_teacher") as update_teacher,
            patch("core.teachers.views.deactivate_teacher") as deactivate_teacher,
        ):
            responses = (
                self.client.get("/api/v1/admin/teachers/teacher-q1/?site_code=Q1"),
                self.client.patch(
                    "/api/v1/admin/teachers/teacher-q1/?site_code=Q1",
                    {"full_name": "Tên mới"},
                    format="json",
                ),
                self.client.delete("/api/v1/admin/teachers/teacher-q1/?site_code=Q1"),
            )

        self.assertEqual([response.status_code for response in responses], [403, 405, 403])
        get_teacher.assert_not_called()
        update_teacher.assert_not_called()
        deactivate_teacher.assert_not_called()
