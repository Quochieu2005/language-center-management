"""A student edits their own profile: name, birth date, gender, phone, address; never email or status."""

from contextlib import nullcontext
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.students import services
from core.students.serializers import StudentProfileUpdateSerializer


class StudentSelfProfileTests(SimpleTestCase):
    def test_serializer_accepts_the_editable_profile_fields(self):
        serializer = StudentProfileUpdateSerializer(data={
            "full_name": "  Nguyễn Minh  ", "birth_date": "2005-03-04", "gender": "Nữ",
            "phone": "0901234567", "address": "Q7",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["full_name"], "Nguyễn Minh")
        self.assertEqual(serializer.validated_data["birth_date"], date(2005, 3, 4))

    def test_serializer_rejects_identity_fields_and_bad_values(self):
        for payload in (
            {"email": "x@example.com"}, {"status": "dang_hoc"}, {"site_code": "Q7"},
            {"birth_date": (date.today() + timedelta(days=1)).isoformat()},
            {"gender": "khác nữa"}, {"full_name": "   "},
        ):
            self.assertFalse(StudentProfileUpdateSerializer(data=payload).is_valid(), payload)

    def test_update_writes_merged_values_and_keeps_unsent_fields(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = ("0900", "Cũ", "Tên cũ", date(2000, 1, 1), "Nam")
        cursor.rowcount = 1
        user = SimpleNamespace(role="hoc_vien", site_code="Q1", profile_id="Q1-HV-000001", account_id="Q1-TK-000003")
        with (
            patch.object(services, "get_site_database_alias", return_value="site_q1"),
            patch.object(services, "connections", {"site_q1": SimpleNamespace(cursor=lambda: cursor)}),
            patch.object(services.transaction, "atomic", return_value=nullcontext()),
            patch.object(services, "_next_sequence_number", return_value=1),
            patch.object(services, "get_student_profile", return_value={"full_name": "Tên mới"}),
        ):
            result = services.update_student_contact(user=user, changes={"full_name": "Tên mới", "gender": None}, remote_ip="127.0.0.1")
        self.assertEqual(result["full_name"], "Tên mới")
        update = next(call for call in cursor.execute.call_args_list if "UPDATE dbo.HocVien" in call.args[0])
        self.assertEqual(update.args[1][:5], ["0900", "Cũ", "Tên mới", date(2000, 1, 1), None])
