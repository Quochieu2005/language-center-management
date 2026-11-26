"""Blog image folders, serializers and the signed upload intent."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.blog import images
from core.blog.serializers import BlogArticleCreateSerializer, BlogArticlePatchSerializer
from core.media.folders import build_blog_image_public_id, is_blog_public_id

ROOT = "language-center-management"
COVER = f"{ROOT}/blog/bia/bat-dau-26-11-2026"
BASE = {
    "slug": "bat-dau", "category_slug": "bat-dau", "title": "T", "excerpt": "E", "content": "C",
    "reading_time_minutes": 3,
}
URL = "https://res.cloudinary.com/demo/image/upload/v1/x.png"


@override_settings(CLOUDINARY_ROOT_FOLDER=ROOT)
class BlogImageTests(SimpleTestCase):
    def test_folder_layout_follows_the_root_blog_and_date_convention(self):
        self.assertEqual(
            build_blog_image_public_id("cover", slug="bat-dau", on_date=date(2026, 11, 26), stamp="101500"),
            (f"{ROOT}/blog/bia", COVER),
        )
        self.assertEqual(
            build_blog_image_public_id("content", slug="bat-dau", on_date=date(2026, 11, 26), stamp="101500")[1],
            f"{ROOT}/blog/noi-dung/bat-dau-101500-26-11-2026",
        )

    def test_public_id_must_live_under_the_blog_folders(self):
        self.assertTrue(is_blog_public_id(COVER))
        self.assertFalse(is_blog_public_id(f"{ROOT}/admin/someone-26-11-2026"))
        self.assertFalse(is_blog_public_id("other/blog/bia/x-26-11-2026"))

    def test_cover_fields_are_validated_as_a_pair(self):
        ok = BlogArticleCreateSerializer(data={**BASE, "cover_public_id": COVER, "cover_url": URL})
        self.assertTrue(ok.is_valid(), ok.errors)
        half = BlogArticleCreateSerializer(data={**BASE, "cover_public_id": COVER})
        self.assertFalse(half.is_valid())
        foreign = BlogArticlePatchSerializer(data={"cover_public_id": COVER, "cover_url": "https://evil.example/x.png"})
        self.assertFalse(foreign.is_valid())
        clear = BlogArticlePatchSerializer(data={"cover_public_id": None, "cover_url": None})
        self.assertTrue(clear.is_valid(), clear.errors)

    def test_intent_signs_a_cover_upload_with_the_blog_folder(self):
        actor = SimpleNamespace(account_id="Q1-TK-000001")
        with patch.object(images, "_cloudinary_config", return_value=("demo", "key", "secret")):
            intent = images.create_blog_image_intent(actor, "bat-dau", "cover")
        self.assertEqual(intent["fields"]["asset_folder"], f"{ROOT}/blog/bia")
        self.assertRegex(intent["fields"]["public_id"], rf"^{ROOT}/blog/bia/bat-dau-\d{{2}}-\d{{2}}-\d{{4}}$")


class BlogImageViewTests(SimpleTestCase):
    """Go through the serializer and view, as the browser does (a direct service call hid a kwarg mismatch)."""

    def test_complete_view_passes_the_validated_fields_to_the_service(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from core.blog.views import AdminBlogImageCompleteView

        user = SimpleNamespace(role="admin_big", account_id="Q1-TK-000001", pk="Q1-TK-000001", is_authenticated=True)
        request = APIRequestFactory().post(
            "/x/", {"intent_token": "tok", "public_id": COVER}, format="json",
        )
        force_authenticate(request, user=user)
        with (
            override_settings(CLOUDINARY_ROOT_FOLDER=ROOT),
            patch("core.blog.views.complete_blog_image", wraps=images.complete_blog_image) as spy,
            patch.object(images, "_cloudinary_resource", return_value={"avatar_public_id": COVER, "avatar_secure_url": URL}),
            patch.object(images.signing, "loads", return_value={"actor_id": user.account_id, "public_id": COVER, "asset_folder": "f"}),
        ):
            response = AdminBlogImageCompleteView.as_view()(request)
        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response.data["secure_url"], URL)
        spy.assert_called_once()


class BlogAckDecodeTests(SimpleTestCase):
    def test_ack_after_is_read_whether_it_is_a_nested_object_or_a_json_string(self):
        from core.blog.write_services import _decode_event_value

        after = {"slug": "a", "published_at": "2026-11-26T01:00:00+00:00"}
        nested = _decode_event_value("article", after)
        text = _decode_event_value("article", '{"slug":"a","published_at":"2026-11-26T01:00:00+00:00"}')
        self.assertEqual(nested, text)
        self.assertEqual(nested["published_at"].year, 2026)
        self.assertIsNone(_decode_event_value("article", None))
