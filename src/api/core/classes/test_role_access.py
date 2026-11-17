from types import SimpleNamespace

from django.test import SimpleTestCase

from core.classes.views import _CLASS_READ_ROLES, _ENROLLMENT_ROLES, _site_scope
from core.students.views import _resolve_student_list_site


class AccountantClassAccessTests(SimpleTestCase):
    def test_accountant_can_read_and_register_only_at_assigned_site(self):
        accountant = SimpleNamespace(role="ke_toan", site_code="Q1")

        self.assertIn("ke_toan", _CLASS_READ_ROLES)
        self.assertIn("ke_toan", _ENROLLMENT_ROLES)
        self.assertEqual(_site_scope(accountant, None, allowed_roles=_CLASS_READ_ROLES), ("Q1", None))
        self.assertEqual(_site_scope(accountant, None, allowed_roles=_ENROLLMENT_ROLES), ("Q1", None))
        self.assertEqual(_resolve_student_list_site(accountant, None), ("Q1", None))
        self.assertEqual(_site_scope(accountant, None)[1].status_code, 403)

        self.assertEqual(_site_scope(accountant, "Q7", allowed_roles=_CLASS_READ_ROLES)[1].status_code, 403)
        self.assertEqual(_site_scope(accountant, "Q7", allowed_roles=_ENROLLMENT_ROLES)[1].status_code, 403)
        self.assertEqual(_resolve_student_list_site(accountant, "Q7")[1].status_code, 403)
