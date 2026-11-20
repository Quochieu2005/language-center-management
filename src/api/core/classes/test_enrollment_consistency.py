from contextlib import ExitStack, nullcontext
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.classes import services


class EnrollmentConsistencyTests(SimpleTestCase):
    def register(self, *, transferring=False, fee=0):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.rowcount = 1
        cursor.fetchone.side_effect = [
            ("dang_hoc",), (1,) if transferring else None,
            ("KH-1", 0, 20, None, "sap_mo", fee), None, None, (0,), None,
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with ExitStack() as stack:
            for name in ("_active_site", "_acquire_named_lock", "_audit", "create_default_tuition_installment"):
                stack.enter_context(patch.object(services, name))
            stack.enter_context(patch.object(services, "get_site_database_alias", return_value="q1"))
            stack.enter_context(patch.object(services, "connections", {"q1": connection}))
            stack.enter_context(patch.object(services.transaction, "atomic", return_value=nullcontext()))
            stack.enter_context(patch.object(services, "_next_identifier", side_effect=["Q1-DK-1", "Q1-HP-1"]))
            try:
                result = services.register_student_to_class(
                    site_code="Q1", student_id="Q1-HV-1", class_id="Q1-LH-1",
                    actor_id="Q1-TK-1", remote_ip="127.0.0.1",
                )
            finally:
                self.cursor = cursor
        return result

    def test_approved_transfer_blocks_new_enrollment_before_writes(self):
        with self.assertRaisesMessage(services.ClassConflict, "đang chuyển cơ sở"):
            self.register(transferring=True)
        statements = [call.args[0].strip().upper() for call in self.cursor.execute.call_args_list]
        self.assertFalse(any(sql.startswith(("INSERT", "UPDATE")) for sql in statements))

    def test_response_matches_saved_tuition_status_for_free_and_paid_courses(self):
        for fee, expected in ((0, "da_dong"), (500000, "chua_dong")):
            with self.subTest(fee=fee):
                result = self.register(fee=fee)
                inserts = [call for call in self.cursor.execute.call_args_list if "INSERT INTO dbo.HocPhi" in call.args[0]]
                self.assertEqual(inserts[0].args[1][-1], expected)
                self.assertEqual(result["tuition_status"], expected)
