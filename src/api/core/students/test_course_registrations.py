"""The staff list of course registrations and who already has a login."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from core.students import course_registrations as registrations
from core.students.course_registration_views import AdminCourseRegistrationListView


def row(email, issued=False, eligible=True):
    return {
        "enrollment_id": "Q7-DK-000001", "enrolled_at": datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc),
        "enrollment_status": "da_dang_ky", "student_id": "Q7-HV-000001", "slug": "hv", "site_code": "Q7",
        "full_name": "N", "email": email, "phone": None, "class_id": "L1", "class_name": "Lớp 1",
        "course_name": "IELTS", "account_issued": issued, "account_issue_eligible": eligible,
    }


class ListTests(SimpleTestCase):
    def run_list(self, rows, holders, **kwargs):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (len(rows),)
        with (
            patch.object(registrations, "active_site_codes", return_value=("Q1", "Q7")),
            patch.object(registrations, "get_site_database_alias", return_value="q7"),
            patch.object(registrations, "connections", {"q7": conn}),
            patch.object(registrations, "_dict_rows", return_value=rows),
            patch.object(registrations, "_website_account_emails", return_value=holders) as lookup,
        ):
            result = registrations.list_course_registrations(
                site_code="Q7", pending_only=kwargs.get("pending_only", True), search=kwargs.get("search"), limit=25, offset=0,
            )
        return result, cursor, lookup

    def test_marks_registrants_whose_email_already_has_a_website_account(self):
        result, _, lookup = self.run_list(
            [row("A@Example.com"), row("b@example.com"), row("c@example.com", issued=True, eligible=False)],
            holders={"a@example.com"},
        )
        flags = [item["has_website_account"] for item in result["results"]]
        self.assertEqual(flags, [True, False, False])
        self.assertEqual(lookup.call_args.args[0], ["a@example.com", "b@example.com"])
        self.assertEqual(result["results"][0]["enrolled_at"].tzinfo.key, "Asia/Ho_Chi_Minh")

    def test_unknown_when_the_authority_cannot_answer(self):
        result, _, _ = self.run_list([row("a@example.com")], holders=None)
        self.assertIsNone(result["results"][0]["has_website_account"])

    def test_invalid_email_is_not_eligible_and_filters_reach_the_query(self):
        result, cursor, _ = self.run_list([row("khong-hop-le")], holders=set(), search="ielts", pending_only=False)
        self.assertFalse(result["results"][0]["account_issue_eligible"])
        count_sql = cursor.execute.call_args_list[0].args[0]
        self.assertNotIn("h.ma_tai_khoan IS NULL", count_sql)
        self.assertIn("LIKE", count_sql)


class ViewTests(SimpleTestCase):
    def call(self, role, query=""):
        request = APIRequestFactory().get(f"/x/{query}")
        force_authenticate(request, user=SimpleNamespace(
            role=role, account_id="A", pk="A", site_code="Q7", is_authenticated=True))
        return AdminCourseRegistrationListView.as_view()(request)

    def test_roles_without_access_are_rejected(self):
        for role in ("ke_toan", "giao_vien", "hoc_vien", "nguoi_dung"):
            self.assertEqual(self.call(role).status_code, 403, role)

    def test_tu_van_reads_only_their_own_site(self):
        with patch("core.students.course_registration_views.list_course_registrations",
                   return_value={"site_code": "Q7", "count": 0, "limit": 25, "offset": 0, "results": []}) as read:
            response = self.call("tu_van")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(read.call_args.kwargs["site_code"], "Q7")
        self.assertTrue(read.call_args.kwargs["pending_only"])
        self.assertEqual(self.call("tu_van", "?site_code=Q1").status_code, 403)

    def test_unknown_query_fields_are_rejected(self):
        self.assertEqual(self.call("admin_small", "?evil=1").status_code, 400)
