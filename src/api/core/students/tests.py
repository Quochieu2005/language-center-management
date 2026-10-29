from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core.auth.service_common import AuthInfrastructureUnavailable, AuthenticatedUser, _resolve_principal
from core.students.serializers import StudentProfileUpdateSerializer
from core.students.deletion import (
    StudentDeletionPending,
    StudentDeleteResult,
    _PurgeJob,
    _StudentTarget,
    _delete_site_data,
    StudentPermissionDenied,
    delete_student,
)
from core.students.services import StudentAccountResult


class _PurgeCursor:
    def __init__(self):
        self.statements = []
        self.last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.statements.append((sql, params))

    def fetchall(self):
        return []

    def fetchone(self):
        return (0,)


class _PurgeConnection:
    def __init__(self, cursor):
        self.purge_cursor = cursor

    def cursor(self):
        return self.purge_cursor


class StudentPermanentDeletionTests(SimpleTestCase):
    def _job(self, completed=(), account_id="Q7-TK-000100"):
        return _PurgeJob(
            job_id="job-1", slug="q7-hv-000001", student_id="Q7-HV-000001",
            account_id=account_id, requested_site="Q7", actor_id="Q1-TK-000001",
            actor_role="admin_big", teacher_id=None, sites=("Q1", "Q7"),
            completed_sites=tuple(completed), profile_slugs=("q7-hv-000001",),
            identifiers=("student@example.com", "student-q7"),
        )

    def test_delete_purges_each_site_and_only_finishes_after_all_sites(self):
        first = self._job(("Q1",))
        completed = self._job(("Q1", "Q7"))
        with (
            patch("core.students.deletion._configured_sites_for_purge", return_value=("Q1", "Q7")),
            patch("core.students.deletion.active_site_codes", return_value=("Q1", "Q7")),
            patch("core.students.deletion._load_job", return_value=None),
            patch("core.students.deletion._discover_target", return_value=_StudentTarget(
                "Q7-HV-000001", "Q7-TK-000100", ("q7-hv-000001",),
                ("student@example.com", "student-q7"),
            )),
            patch("core.students.deletion._reserve_job", return_value=self._job()),
            patch("core.students.deletion._delete_site_data") as delete_site,
            patch("core.students.deletion._mark_site_completed", side_effect=[first, completed]) as mark_done,
            patch("core.students.deletion._finish_job") as finish,
        ):
            result = delete_student(
                site_code="Q7", student_slug="q7-hv-000001", actor_id="Q1-TK-000001",
                actor_role="admin_big", teacher_id=None,
            )

        self.assertEqual(result, StudentDeleteResult("q7-hv-000001", "Q7", 2, True))
        self.assertEqual([call.args[1] for call in delete_site.call_args_list], ["Q1", "Q7"])
        self.assertEqual(mark_done.call_count, 2)
        finish.assert_called_once_with(completed)

    def test_partial_site_failure_keeps_the_delete_pending_for_retry(self):
        with (
            patch("core.students.deletion._configured_sites_for_purge", return_value=("Q1", "Q7")),
            patch("core.students.deletion.active_site_codes", return_value=("Q1", "Q7")),
            patch("core.students.deletion._load_job", return_value=self._job()),
            patch("core.students.deletion._authorize_resume"),
            patch("core.students.deletion._refresh_job_sites", return_value=self._job()),
            patch("core.students.deletion._delete_site_data", side_effect=RuntimeError("site offline")),
            patch("core.students.deletion._mark_site_completed") as mark_done,
            patch("core.students.deletion._finish_job") as finish,
        ):
            with self.assertRaises(StudentDeletionPending):
                delete_student(
                    site_code="Q7", student_slug="q7-hv-000001", actor_id="Q1-TK-000001",
                    actor_role="admin_big", teacher_id=None,
                )
        mark_done.assert_not_called()
        finish.assert_not_called()

    def test_site_purge_deletes_child_records_before_profile_and_account(self):
        cursor = _PurgeCursor()
        connection = _PurgeConnection(cursor)
        with (
            patch("core.students.deletion.get_site_database_alias", return_value="site_q7"),
            patch("core.students.deletion.connections", {"site_q7": connection}),
            patch("core.students.deletion.transaction.atomic", side_effect=lambda using: nullcontext()),
        ):
            _delete_site_data(self._job(), "Q7")

        sql = [statement.upper() for statement, _params in cursor.statements]
        ordered_tables = [
            "DELETE PT FROM DBO.PHIEUTHU",
            "DELETE FROM DBO.HOCPHI",
            "DELETE FROM DBO.DANGKY",
            "DELETE FROM DBO.HOCVIEN",
            "DELETE FROM DBO.TAIKHOAN",
        ]
        positions = [next(i for i, statement in enumerate(sql) if token in statement) for token in ordered_tables]
        self.assertEqual(positions, sorted(positions))
        self.assertTrue(any("DELETE FROM DBO.DIEM" in statement for statement in sql))
        self.assertTrue(any("DELETE FROM DBO.DIEMDANH" in statement for statement in sql))
        self.assertTrue(any("DELETE FROM DBO.LICHSUCHUYENCOSO" in statement for statement in sql))
        self.assertFalse(any("TAIKHOANLIENKETOAUTH" in statement for statement in sql))
        self.assertFalse(any(" LIKE " in statement for statement in sql))


class StudentPortalApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = AuthenticatedUser(
            account_id="Q7-TK-000100", username="hv-q7-student",
            slug="q7-hv-000001", email="student@example.com", role="hoc_vien",
            site_code="Q7", profile_id="Q7-HV-000001", must_change_password=True,
        )
        self.admin_big = SimpleNamespace(
            is_authenticated=True, role="admin_big", account_id="Q1-TK-000001",
            pk="Q1-TK-000001",
        )
        self.admin_small = SimpleNamespace(
            is_authenticated=True, role="admin_small", account_id="Q7-TK-000002",
            site_code="Q7", pk="Q7-TK-000002",
        )
        self.teacher = SimpleNamespace(
            is_authenticated=True, role="giao_vien", account_id="Q7-TK-000003",
            site_code="Q7", profile_id="Q7-GV-000003", pk="Q7-TK-000003",
        )

    def test_student_routes_are_in_openapi_and_use_profile_slugs(self):
        response = self.client.get(reverse("schema"), {"format": "json"})
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("/api/v1/admin/students/{slug}/account/", paths)
        self.assertIn("delete", paths["/api/v1/admin/students/{slug}/"])
        self.assertIn("/api/v1/students/profile/{slug}/", paths)
        self.assertIn("/api/v1/students/profile/{slug}/enrollments/", paths)
        self.assertIn("/api/v1/students/profile/{slug}/schedule/", paths)
        self.assertIn("/api/v1/students/profile/{slug}/tuition/", paths)
        self.assertIn("/api/v1/students/profile/{slug}/grades/", paths)
        self.assertNotIn("/api/v1/students/me/", paths)

    def test_shared_login_accepts_a_provisioned_student_role(self):
        self.client = APIClient()
        with patch("core.auth.views.login_user", return_value=(self.student, "s" * 64, None)):
            response = self.client.post(
                reverse("core:auth-login"),
                {"identifier": self.student.email, "password": "temporary"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "hoc_vien")
        self.assertEqual(response.json()["user"]["slug"], self.student.slug)
        self.assertTrue(response.json()["user"]["must_change_password"])

    def test_admin_small_cannot_choose_another_site_for_student_list(self):
        self.client.force_authenticate(user=self.admin_small)
        with patch("core.students.views.list_students") as list_service:
            response = self.client.get(reverse("core:student-admin-list"), {"site_code": "Q1"})
        self.assertEqual(response.status_code, 403)
        list_service.assert_not_called()

    def test_admin_big_must_choose_site_to_list_students(self):
        self.client.force_authenticate(user=self.admin_big)
        with patch("core.students.views.list_students") as list_service:
            response = self.client.get(reverse("core:student-admin-list"))
        self.assertEqual(response.status_code, 400)
        list_service.assert_not_called()

    def test_admin_big_permanently_deletes_student_at_selected_site(self):
        self.client.force_authenticate(user=self.admin_big)
        result = StudentDeleteResult(
            slug="q7-hv-000001", site_code="Q7", deleted_site_count=3,
            account_deleted=True,
        )
        with patch("core.students.views.delete_student", return_value=result) as delete:
            response = self.client.delete(
                reverse("core:student-admin-delete", kwargs={"slug": result.slug}) + "?site_code=Q7",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        self.assertEqual(response.json()["deleted_site_count"], 3)
        self.assertTrue(response.json()["account_deleted"])
        self.assertEqual(delete.call_args.kwargs["site_code"], "Q7")

    def test_admin_small_cannot_delete_student_at_another_site(self):
        self.client.force_authenticate(user=self.admin_small)
        with patch("core.students.views.delete_student") as delete:
            response = self.client.delete(
                reverse("core:student-admin-delete", kwargs={"slug": "q1-hv-000001"}) + "?site_code=Q1",
            )
        self.assertEqual(response.status_code, 403)
        delete.assert_not_called()

    def test_teacher_deletes_only_with_session_site_and_teacher_profile(self):
        self.client.force_authenticate(user=self.teacher)
        result = StudentDeleteResult(
            slug="q7-hv-000001", site_code="Q7", deleted_site_count=3,
            account_deleted=False,
        )
        with patch("core.students.views.delete_student", return_value=result) as delete:
            response = self.client.delete(
                reverse("core:student-admin-delete", kwargs={"slug": result.slug})
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(delete.call_args.kwargs["site_code"], "Q7")
        self.assertEqual(delete.call_args.kwargs["teacher_id"], "Q7-GV-000003")

    def test_teacher_cannot_select_site_when_deleting_student(self):
        self.client.force_authenticate(user=self.teacher)
        with patch("core.students.views.delete_student") as delete:
            response = self.client.delete(
                reverse("core:student-admin-delete", kwargs={"slug": "q7-hv-000001"}) + "?site_code=Q1",
            )
        self.assertEqual(response.status_code, 403)
        delete.assert_not_called()

    def test_student_role_cannot_delete_another_student(self):
        self.client.force_authenticate(user=self.student)
        with patch("core.students.views.delete_student") as delete:
            response = self.client.delete(
                reverse("core:student-admin-delete", kwargs={"slug": "other-student"})
            )
        self.assertEqual(response.status_code, 403)
        delete.assert_not_called()

    def test_account_issuance_returns_no_password_and_uses_authenticated_site(self):
        self.client.force_authenticate(user=self.admin_small)
        result = StudentAccountResult(
            account_id="Q7-TK-000100", student_id="Q7-HV-000001",
            slug="q7-hv-000001", site_code="Q7", username="hv-q7-student",
            email="student@example.com", email_sent=True,
        )
        with patch("core.students.views.issue_student_account", return_value=result) as issue:
            response = self.client.post(
                reverse("core:student-account-issue", kwargs={"slug": "q7-hv-000001"}),
                {}, format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], "hoc_vien")
        self.assertTrue(response.json()["must_change_password"])
        self.assertTrue(response.json()["email_sent"])
        self.assertNotIn("password", response.json())
        self.assertEqual(issue.call_args.kwargs["site_code"], "Q7")

    def test_student_can_read_own_slug_but_not_another_profile(self):
        self.client.force_authenticate(user=self.student)
        profile = {"student_id": self.student.profile_id, "slug": self.student.slug}
        with patch("core.students.views.get_student_profile", return_value=profile) as get_profile:
            own = self.client.get(reverse("core:student-profile", kwargs={"slug": self.student.slug}))
            other = self.client.get(reverse("core:student-profile", kwargs={"slug": "other-student"}))
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 404)
        get_profile.assert_called_once_with(
            account_id=self.student.account_id, student_id=self.student.profile_id, site_code="Q7"
        )

    def test_profile_update_rejects_identity_and_site_fields(self):
        for payload in ({"email": "other@example.com"}, {"site_code": "Q1"},
                        {"status": "da_chuyen_di"}, {"account_id": "Q1-TK-000001"}):
            serializer = StudentProfileUpdateSerializer(data=payload)
            self.assertFalse(serializer.is_valid(), payload)

    def test_student_login_resolution_requires_exactly_one_active_profile(self):
        account = (
            "Q7-TK-000100", "hv-q7-student", "account-slug", "student@example.com",
            "bcrypt-hash", "hoc_vien", "Q7", "hoat_dong", 1, 1,
        )
        results = [[], [("Q7-HV-000001", "q7-hv-000001", "Q7")], []]

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, *_args):
                return None

            def fetchall(self):
                return results.pop(0)

        class Connection:
            def cursor(self):
                return Cursor()

        with patch("core.auth.service_common.get_site_connection", return_value=Connection()):
            user = _resolve_principal(account, ("Q1", "Q7", "TD"))
        self.assertEqual((user.role, user.site_code, user.profile_id, user.slug),
                         ("hoc_vien", "Q7", "Q7-HV-000001", "q7-hv-000001"))

    def test_student_login_fails_closed_if_profile_claims_a_different_site(self):
        account = (
            "Q7-TK-000100", "hv-q7-student", "account-slug", "student@example.com",
            "bcrypt-hash", "hoc_vien", "Q7", "hoat_dong", 1, 1,
        )
        results = [[("Q7-HV-000001", "q7-hv-000001", "Q1")]]

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, *_args):
                return None

            def fetchall(self):
                return results.pop(0)

        class Connection:
            def cursor(self):
                return Cursor()

        with patch("core.auth.service_common.get_site_connection", return_value=Connection()):
            with self.assertRaises(AuthInfrastructureUnavailable):
                _resolve_principal(account, ("Q7",))

