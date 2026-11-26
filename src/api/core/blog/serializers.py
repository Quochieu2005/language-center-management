from urllib.parse import urlparse

from rest_framework import serializers

from core.media.folders import is_blog_public_id

from core.academics.serializers import StrictSerializer


class BlogImagePublicIdField(serializers.CharField):
    """Cloudinary public id of a Blog image: ``<root>/blog/{bia|noi-dung}/<slug>-...``."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 255)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not is_blog_public_id(value):
            raise serializers.ValidationError("Mã ảnh Blog không hợp lệ.")
        return value


class BlogImageUrlField(serializers.URLField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if urlparse(value).scheme != "https" or urlparse(value).hostname != "res.cloudinary.com":
            raise serializers.ValidationError("Ảnh Blog phải nằm trên Cloudinary.")
        return value


def _check_cover_pair(attrs):
    if ("cover_public_id" in attrs or "cover_url" in attrs) and (
        (attrs.get("cover_public_id") is None) != (attrs.get("cover_url") is None)
    ):
        raise serializers.ValidationError("Ảnh bìa cần cả cover_public_id và cover_url, hoặc cả hai rỗng.")
    return attrs


class BlogImageIntentRequestSerializer(StrictSerializer):
    allowed_fields = {"slug", "kind"}
    slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160)
    kind = serializers.ChoiceField(choices=("cover", "content"))


class BlogImageCompleteRequestSerializer(StrictSerializer):
    allowed_fields = {"intent_token", "public_id"}
    intent_token = serializers.CharField(max_length=2048, trim_whitespace=False)
    public_id = BlogImagePublicIdField()


class BlogImageCompleteResponseSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    secure_url = serializers.URLField()


class PublicBlogCategorySerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True, allow_blank=True)
    post_count = serializers.IntegerField(min_value=0)


class PublicBlogCategoriesResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("GLOBAL",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    inconsistent_sites = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField(min_value=0)
    results = PublicBlogCategorySerializer(many=True)


class PublicBlogCategoryReferenceSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()


class PublicBlogArticleSerializer(serializers.Serializer):
    slug = serializers.CharField()
    title = serializers.CharField()
    excerpt = serializers.CharField()
    content = serializers.CharField()
    reading_time_minutes = serializers.IntegerField(min_value=1)
    published_at = serializers.DateTimeField(allow_null=True)
    category = PublicBlogCategoryReferenceSerializer()
    cover_url = serializers.URLField(allow_null=True, max_length=1024)


class PublicBlogArticleSummarySerializer(serializers.Serializer):
    slug = serializers.CharField()
    title = serializers.CharField()
    excerpt = serializers.CharField()
    reading_time_minutes = serializers.IntegerField(min_value=1)
    published_at = serializers.DateTimeField(allow_null=True)
    category = PublicBlogCategoryReferenceSerializer()
    cover_url = serializers.URLField(allow_null=True, max_length=1024)


class PublicBlogArticlesResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("GLOBAL",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    inconsistent_sites = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField(min_value=0)
    results = PublicBlogArticleSummarySerializer(many=True)


class PublicBlogDetailResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("GLOBAL",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    result = PublicBlogArticleSerializer()


class AdminBlogCategorySerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(choices=("hoat_dong", "ngung"))
    post_count = serializers.IntegerField(min_value=0)


class AdminBlogArticleSerializer(serializers.Serializer):
    slug = serializers.CharField()
    category_slug = serializers.CharField()
    title = serializers.CharField()
    excerpt = serializers.CharField()
    content = serializers.CharField()
    reading_time_minutes = serializers.IntegerField(min_value=1, max_value=240)
    status = serializers.ChoiceField(choices=("nhap", "da_xuat_ban", "an"))
    published_at = serializers.DateTimeField(allow_null=True)
    cover_public_id = serializers.CharField(allow_null=True, required=False)
    cover_url = serializers.URLField(allow_null=True, required=False, max_length=1024)


class AdminBlogCategoryDetailResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("GLOBAL",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    result = AdminBlogCategorySerializer()


class AdminBlogArticleDetailResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("GLOBAL",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    result = AdminBlogArticleSerializer()


class AdminBlogListResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("GLOBAL",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    inconsistent_sites = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField(min_value=0)
    results = serializers.ListField(child=serializers.DictField())


class BlogCategoryCreateSerializer(StrictSerializer):
    allowed_fields = {"slug", "name", "description", "status"}
    slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    name = serializers.CharField(max_length=100, trim_whitespace=True)
    description = serializers.CharField(max_length=500, allow_blank=True, allow_null=True, required=False, default=None)
    status = serializers.ChoiceField(choices=("hoat_dong", "ngung"), default="hoat_dong")


class BlogCategoryPatchSerializer(StrictSerializer):
    allowed_fields = BlogCategoryCreateSerializer.allowed_fields
    slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120, required=False)
    name = serializers.CharField(max_length=100, trim_whitespace=True, required=False)
    description = serializers.CharField(max_length=500, allow_blank=True, allow_null=True, required=False)
    status = serializers.ChoiceField(choices=("hoat_dong", "ngung"), required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Cần ít nhất một trường để cập nhật.")
        return attrs


class BlogArticleCreateSerializer(StrictSerializer):
    allowed_fields = {
        "slug", "category_slug", "title", "excerpt", "content",
        "reading_time_minutes", "status", "published_at", "cover_public_id", "cover_url",
    }
    slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160)
    category_slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    excerpt = serializers.CharField(max_length=500, trim_whitespace=True)
    content = serializers.CharField(max_length=20000, trim_whitespace=True)
    reading_time_minutes = serializers.IntegerField(min_value=1, max_value=240)
    status = serializers.ChoiceField(choices=("nhap", "da_xuat_ban", "an"), default="nhap")
    published_at = serializers.DateTimeField(allow_null=True, required=False, default=None)
    cover_public_id = BlogImagePublicIdField(allow_null=True, required=False, default=None)
    cover_url = BlogImageUrlField(allow_null=True, required=False, default=None)

    def validate(self, attrs):
        return _check_cover_pair(attrs)


class BlogArticlePatchSerializer(StrictSerializer):
    allowed_fields = BlogArticleCreateSerializer.allowed_fields
    slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160, required=False)
    category_slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120, required=False)
    title = serializers.CharField(max_length=200, trim_whitespace=True, required=False)
    excerpt = serializers.CharField(max_length=500, trim_whitespace=True, required=False)
    content = serializers.CharField(max_length=20000, trim_whitespace=True, required=False)
    reading_time_minutes = serializers.IntegerField(min_value=1, max_value=240, required=False)
    status = serializers.ChoiceField(choices=("nhap", "da_xuat_ban", "an"), required=False)
    published_at = serializers.DateTimeField(allow_null=True, required=False)
    cover_public_id = BlogImagePublicIdField(allow_null=True, required=False)
    cover_url = BlogImageUrlField(allow_null=True, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Cần ít nhất một trường để cập nhật.")
        return _check_cover_pair(attrs)


class BlogWriteResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("REPLICATED-WRITE",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    idempotent_replay = serializers.BooleanField()
    result = serializers.DictField()
