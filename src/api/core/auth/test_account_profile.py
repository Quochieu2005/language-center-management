"""Website account (nguoi_dung) profile: read/update at the authority and the avatar folder."""

from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.auth import account_profile
from core.auth.views import AuthAccountProfileView
from core.media import avatars
from core.media.folders import build_avatar_public_id

ROW = ("nguoi_dung", None, 1, "nguoi-dung-a", "a@example.com", "nd-a", "Tên cũ", date(2000, 1, 2), "Nam", "0900", "Cũ", None)
USER = SimpleNamespace(role="nguoi_dung", account_id="Q1-TK-000009", pk="Q1-TK-000009", is_authenticated=True)


def cursor_with(*rows):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = list(rows)
    cursor.rowcount = 1
    return conn, cursor


@override_settings(AUTH_SESSION_SITE_CODE="Q1")
class AccountProfileServiceTests(SimpleTestCase):
    def patched(self, conn):
        return (
            patch.object(account_profile, "auth_session_alias", return_value="auth"),
            patch.object(account_profile, "connections", {"auth": conn}),
            patch.object(account_profile.transaction, "atomic", return_value=nullcontext()),
            patch.object(account_profile, "_acquire_named_lock"),
        )

    def test_update_merges_changes_and_does_not_bump_the_session_version(self):
        conn, cursor = cursor_with(ROW, ROW[:6] + ("Tên mới",) + ROW[7:])
        a, b, c, d = self.patched(conn)
        with a, b, c, d:
            result = account_profile.update_account_profile(USER, {"full_name": "Tên mới", "gender": None}, "127.0.0.1")
        self.assertEqual(result["full_name"], "Tên mới")
        update = next(call for call in cursor.execute.call_args_list if "UPDATE dbo.TaiKhoan" in call.args[0])
        self.assertNotIn("phien_ban", update.args[0])
        self.assertEqual(update.args[1][:5], ["Tên mới", date(2000, 1, 2), None, "0900", "Cũ"])

    def test_only_a_website_account_without_a_site_is_allowed(self):
        for row in (("hoc_vien",) + ROW[1:], ROW[:1] + ("Q1",) + ROW[2:], ROW[:2] + (0,) + ROW[3:], None):
            conn, _ = cursor_with(row)
            a, b, c, d = self.patched(conn)
            with a, b, c, d, self.assertRaises(account_profile.AccountProfileNotAllowed):
                account_profile.get_account_profile(USER)


class AccountProfileViewTests(SimpleTestCase):
    def call(self, method, user, data=None):
        request = getattr(APIRequestFactory(), method)("/x/", data, format="json")
        force_authenticate(request, user=user)
        return AuthAccountProfileView.as_view()(request)

    def test_other_roles_are_rejected(self):
        student = SimpleNamespace(role="hoc_vien", account_id="A", pk="A", is_authenticated=True)
        self.assertEqual(self.call("get", student).status_code, 403)
        self.assertEqual(self.call("patch", student, {"phone": "0900123456"}).status_code, 403)

    def test_patch_rejects_identity_fields_and_passes_valid_changes(self):
        self.assertEqual(self.call("patch", USER, {"email": "x@example.com"}).status_code, 400)
        with patch("core.auth.views.update_account_profile", return_value={"slug": "s", "email": "a@example.com", "username": "u", "full_name": "N", "birth_date": None, "gender": None, "phone": None, "address": None, "avatar_secure_url": None}) as update:
            response = self.call("patch", USER, {"full_name": "N"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(update.call_args.args[1], {"full_name": "N"})


@override_settings(CLOUDINARY_ROOT_FOLDER="language-center-management")
class AccountAvatarTests(SimpleTestCase):
    def test_avatar_goes_to_the_nguoi_dung_folder(self):
        folder, public_id = build_avatar_public_id("user", slug="nguoi-dung-a", on_date=date(2026, 11, 26))
        self.assertEqual(public_id, "language-center-management/nguoi-dung/nguoi-dung-a-26-11-2026")
        self.assertEqual(folder, "language-center-management/nguoi-dung")

    def test_avatar_intent_accepts_a_website_account_and_rejects_a_site(self):
        target = SimpleNamespace(role="nguoi_dung", account_id="Q1-TK-000009", site_code=None, slug="nguoi-dung-a")
        with (
            patch.object(avatars, "_cloudinary_config", return_value=("demo", "key", "secret")),
            patch.object(avatars, "_authority_site", return_value="Q1"),
            patch.object(avatars, "_read_account", return_value={"avatar_public_id": None, "avatar_secure_url": None}),
            patch.object(avatars, "_account_lock", return_value=nullcontext()),
        ):
            intent = avatars._create_admin_avatar_upload_intent(target)
            self.assertEqual(intent["fields"]["asset_folder"], "language-center-management/nguoi-dung")
            with self.assertRaises(avatars.AvatarConflict):
                avatars._create_admin_avatar_upload_intent(SimpleNamespace(**{**target.__dict__, "site_code": "Q1"}))
