from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.academics.common import AcademicForbidden
from core.contacts.services import list_admin_contact_requests


class ContactRoleAccessTests(SimpleTestCase):
    def test_consultant_can_read_inbox_only_at_assigned_site(self):
        consultant = SimpleNamespace(role="tu_van", site_code="Q1")
        site_result = {"count": 0, "limit": 20, "offset": 0, "results": []}

        with patch("core.contacts.services._list_site_contacts", return_value=site_result) as read_site:
            result = list_admin_contact_requests(
                user=consultant, site_code=None, status_filter=None,
                search=None, limit=20, offset=0,
            )

        self.assertEqual(result["scope"], "LOCAL")
        read_site.assert_called_once_with(
            site_code="Q1", status_filter=None, search=None, limit=20, offset=0,
        )
        with self.assertRaises(AcademicForbidden):
            list_admin_contact_requests(
                user=consultant, site_code="Q7", status_filter=None,
                search=None, limit=20, offset=0,
            )
