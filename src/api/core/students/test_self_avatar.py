"""A student may manage only their own photo, at their own site; admins keep their rules."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.media.avatars import AvatarConflict
from core.students import avatars

STUDENT = dict(role="hoc_vien", account_id="Q1-TK-000003", site_code="Q1", profile_id="Q1-HV-000001", slug="minh-duc")


def _profile(student_id="Q1-HV-000001", slug="minh-duc", status="dang_hoc"):
    return {"student_id": student_id, "slug": slug, "site_code": "Q1", "status": status,
            "avatar_public_id": None, "avatar_secure_url": None}


@override_settings(CLOUDINARY_ROOT_FOLDER="language-center-management")
class StudentSelfAvatarTests(SimpleTestCase):
    def setUp(self):
        self.student = SimpleNamespace(**STUDENT)
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        self.enterContext(patch.object(avatars, "connections", {"site_q1": SimpleNamespace(cursor=lambda: cursor)}))
        self.enterContext(patch.object(avatars, "get_site_database_alias", return_value="site_q1"))
        self.enterContext(patch.object(avatars, "active_site_codes", return_value=("Q1", "Q7", "TD")))
        self.enterContext(patch.object(avatars, "_cloudinary_config", return_value=("demo", "key", "secret")))

    def test_student_gets_an_intent_for_their_own_profile_with_the_student_folder(self):
        with patch.object(avatars, "_profile", return_value=_profile()):
            intent = avatars.create_student_avatar_upload_intent(self.student, "Q1", "minh-duc")
        self.assertRegex(
            intent["fields"]["public_id"],
            r"^language-center-management/hoc-vien/Q1/minh-duc-\d{2}-\d{2}-\d{4}$",
        )

    def test_student_cannot_use_another_students_profile(self):
        with patch.object(avatars, "_profile", return_value=_profile(student_id="Q1-HV-000002", slug="other")):
            with self.assertRaises(AvatarConflict):
                avatars.create_student_avatar_upload_intent(self.student, "Q1", "other")

    def test_student_cannot_act_on_another_site(self):
        with self.assertRaises(AvatarConflict):
            avatars.create_student_avatar_upload_intent(self.student, "Q7", "minh-duc")

    def test_complete_rejects_a_foreign_profile_before_writing(self):
        intent = {
            "actor_id": "Q1-TK-000003", "actor_role": "hoc_vien", "actor_site": "Q1", "student_id": "Q1-HV-000002",
            "student_slug": "other", "site_code": "Q1", "public_id": "language-center-management/hoc-vien/Q1/other-26-11-2026",
            "asset_folder": "f", "old_avatar": {"avatar_public_id": None, "avatar_secure_url": None},
        }
        new = {"avatar_public_id": intent["public_id"], "avatar_secure_url": "https://res.cloudinary.com/demo/x.png"}
        with (
            patch.object(avatars.signing, "loads", return_value=intent),
            patch.object(avatars, "_cloudinary_resource", return_value=new),
            patch.object(avatars.transaction, "atomic", return_value=nullcontext()),
            patch.object(avatars, "_profile", return_value=_profile(student_id="Q1-HV-000002", slug="other")),
        ):
            with self.assertRaises(AvatarConflict):
                avatars.complete_student_avatar_upload(self.student, "Q1", "other", "token", intent["public_id"], "127.0.0.1")

    def test_other_roles_are_still_rejected(self):
        teacher = SimpleNamespace(role="giao_vien", account_id="Q1-TK-000002", site_code="Q1")
        with self.assertRaises(AvatarConflict):
            avatars.create_student_avatar_upload_intent(teacher, "Q1", "minh-duc")
        admin_small = SimpleNamespace(role="admin_small", account_id="Q1-TK-000009", site_code="Q7")
        with self.assertRaises(AvatarConflict):
            avatars.create_student_avatar_upload_intent(admin_small, "Q1", "minh-duc")
