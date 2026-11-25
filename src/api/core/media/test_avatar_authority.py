"""Account avatars are read and written at the authority only; replicas follow via the outbox."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.media import avatars

OLD = {"avatar_public_id": None, "avatar_secure_url": None}
NEW = {"avatar_public_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
       "avatar_secure_url": "https://res.cloudinary.com/demo/image/upload/v1/x.png"}


@override_settings(AUTH_SESSION_SITE_CODE="Q1")
class AvatarAuthorityTests(SimpleTestCase):
    def setUp(self):
        self.teacher = SimpleNamespace(role="giao_vien", account_id="Q1-TK-000002", site_code="Q1", slug="the-sang")
        self.reads = []
        self.enterContext(patch.object(avatars, "_read_account", side_effect=self._read))
        self.enterContext(patch.object(avatars, "_account_lock", side_effect=lambda _id: nullcontext()))
        self.state = dict(OLD)

    def _read(self, site, account_id, role, account_site):
        self.reads.append(site)
        return dict(self.state)

    def test_read_uses_authority_only(self):
        self.state = dict(NEW)
        self.assertEqual(avatars.get_admin_avatar_url("Q1-TK-000002", "giao_vien", "Q1"), NEW["avatar_secure_url"])
        self.assertEqual(self.reads, ["Q1"])

    def test_complete_writes_authority_only(self):
        def apply(site, *_args, **_kwargs):
            self.assertEqual(site, "Q1")
            self.state = dict(NEW)

        with (
            patch.object(avatars, "_load_intent", return_value={"asset_folder": "f", "old_avatar": OLD}),
            patch.object(avatars, "_cloudinary_resource", return_value=dict(NEW)),
            patch.object(avatars, "_apply_site", side_effect=apply) as apply_site,
        ):
            result = avatars.complete_admin_avatar_upload(self.teacher, "token", NEW["avatar_public_id"], "127.0.0.1")
        apply_site.assert_called_once()
        self.assertEqual(result["site_codes"], ["Q1"])
        self.assertEqual(result["avatar_secure_url"], NEW["avatar_secure_url"])
        self.assertEqual(set(self.reads), {"Q1"})


@override_settings(CLOUDINARY_ROOT_FOLDER="language-center-management")
class AvatarPublicIdTests(SimpleTestCase):
    def test_layout_is_root_category_site_and_slug_with_vietnamese_date(self):
        from datetime import date

        from core.media.folders import build_avatar_public_id

        day = date(2026, 11, 25)
        self.assertEqual(
            build_avatar_public_id("teacher", slug="the-sang", on_date=day, site_code="Q1"),
            ("language-center-management/giao-vien/Q1", "language-center-management/giao-vien/Q1/the-sang-25-11-2026"),
        )
        self.assertEqual(
            build_avatar_public_id("account", slug="admin", on_date=day)[1],
            "language-center-management/admin/admin-25-11-2026",
        )
        self.assertEqual(
            build_avatar_public_id("student", slug="minh-duc", on_date=day, site_code="Q1")[1],
            "language-center-management/hoc-vien/Q1/minh-duc-25-11-2026",
        )
        with self.assertRaises(ValueError):
            build_avatar_public_id("teacher", slug="../x", on_date=day, site_code="Q1")
        with self.assertRaises(ValueError):
            build_avatar_public_id("account", slug="admin", on_date=day, site_code="Q1")

    def test_validator_accepts_new_and_legacy_ids_only_under_root(self):
        from core.media.folders import is_avatar_public_id

        self.assertTrue(is_avatar_public_id("language-center-management/giao-vien/Q1/the-sang-25-11-2026"))
        self.assertTrue(is_avatar_public_id("fe691960-ecc6-4683-a920-7346c9374a8a"))
        self.assertFalse(is_avatar_public_id("other-root/giao-vien/Q1/x"))
        self.assertFalse(is_avatar_public_id("language-center-management/../secret"))
        self.assertFalse(is_avatar_public_id("language-center-management/a b"))
