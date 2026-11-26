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


@override_settings(CLOUDINARY_ROOT_FOLDER="language-center-management")
class AvatarCompleteRequestTests(SimpleTestCase):
    """The finalize requests must accept every public id the intents generate (this was a 400)."""

    CASES = (
        ("account", None, "admin"),
        ("account", None, "admin-small-q1"),
        ("teacher", "Q1", "the-sang"),
        ("employee", "TD", "lan-le"),
        ("student", "Q7", "minh-duc"),
    )

    def test_every_generated_public_id_passes_all_finalize_serializers(self):
        from datetime import date

        from core.media.folders import build_avatar_public_id
        from core.media.serializers import (
            AdminAvatarFinalizeRequestSerializer,
            AdminSmallAvatarFinalizeRequestSerializer,
            EmployeeAvatarFinalizeRequestSerializer,
            TeacherAvatarFinalizeRequestSerializer,
        )

        for resource, site, slug in self.CASES:
            _folder, public_id = build_avatar_public_id(resource, slug=slug, on_date=date(2026, 11, 26), site_code=site)
            with self.subTest(public_id=public_id):
                body = {"intent_token": "token", "public_id": public_id}
                for serializer_class in (AdminAvatarFinalizeRequestSerializer,):
                    serializer = serializer_class(data=body)
                    self.assertTrue(serializer.is_valid(), serializer.errors)
                setup_body = {**body, "setup_token": "setup"}
                for serializer_class in (
                    AdminSmallAvatarFinalizeRequestSerializer,
                    TeacherAvatarFinalizeRequestSerializer,
                    EmployeeAvatarFinalizeRequestSerializer,
                ):
                    serializer = serializer_class(data=setup_body)
                    self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_legacy_uuid_still_passes_and_unsafe_ids_do_not(self):
        from core.media.serializers import AdminAvatarFinalizeRequestSerializer

        legacy = "fe691960-ecc6-4683-a920-7346c9374a8a"
        self.assertTrue(AdminAvatarFinalizeRequestSerializer(data={"intent_token": "t", "public_id": legacy}).is_valid())
        for bad in ("../x", "language-center-management/../secret", "other-root/giao-vien/Q1/x", "a b", ""):
            with self.subTest(bad=bad):
                serializer = AdminAvatarFinalizeRequestSerializer(data={"intent_token": "t", "public_id": bad})
                self.assertFalse(serializer.is_valid())

    def test_self_complete_endpoint_accepts_the_new_id_and_calls_the_service(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from core.media import views as media_views

        public_id = "language-center-management/giao-vien/Q1/the-sang-26-11-2026"
        user = SimpleNamespace(is_authenticated=True, role="giao_vien", account_id="Q1-TK-000002", site_code="Q1", slug="the-sang", pk="Q1-TK-000002")
        request = APIRequestFactory().post(
            "/api/v1/auth/profile/the-sang/avatar/complete/",
            {"intent_token": "token", "public_id": public_id}, format="json",
        )
        force_authenticate(request, user=user)
        with patch.object(media_views, "complete_admin_avatar_upload", return_value={
            "account_id": "Q1-TK-000002", "role": "giao_vien", "avatar_secure_url": "https://res.cloudinary.com/x.png",
            "complete": True, "site_codes": ["Q1"],
        }) as complete:
            response = media_views.AdminAvatarCompleteView.as_view()(request, slug="the-sang")
        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(complete.call_args.args[2], public_id)
