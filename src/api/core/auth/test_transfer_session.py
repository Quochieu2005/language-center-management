from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.auth.service_common import AuthInfrastructureUnavailable, _resolve_principal


class TransferSessionTests(SimpleTestCase):
    def resolve(self, source, target):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = [source, target]
        account = ("TK-1", "student", "student", "student@example.com", None, "hoc_vien", "Q1", 1, 1, False)
        with patch("core.auth.service_common.get_site_connection", return_value=connection):
            return _resolve_principal(account, ("Q1", "Q7"))

    def test_staged_destination_does_not_invalidate_source_session(self):
        user = self.resolve([("HV-1", "student", "Q1", 0)], [("HV-1", "student", "Q7", 1)])
        self.assertEqual(user.site_code, "Q1")

    def test_gap_before_destination_activation_is_unavailable_not_unauthorized(self):
        with self.assertRaises(AuthInfrastructureUnavailable):
            self.resolve([], [("HV-1", "student", "Q7", 1)])

    def test_completed_destination_becomes_current_profile(self):
        user = self.resolve([], [("HV-1", "student", "Q7", 0)])
        self.assertEqual(user.site_code, "Q7")
