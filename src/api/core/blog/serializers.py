from rest_framework import serializers

from core.academics.serializers import StrictSerializer


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
        "reading_time_minutes", "status", "published_at",
    }
    slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160)
    category_slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    excerpt = serializers.CharField(max_length=500, trim_whitespace=True)
    content = serializers.CharField(max_length=20000, trim_whitespace=True)
    reading_time_minutes = serializers.IntegerField(min_value=1, max_value=240)
    status = serializers.ChoiceField(choices=("nhap", "da_xuat_ban", "an"), default="nhap")
    published_at = serializers.DateTimeField(allow_null=True, required=False, default=None)


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

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Cần ít nhất một trường để cập nhật.")
        return attrs


class BlogWriteResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("REPLICATED-WRITE",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    idempotent_replay = serializers.BooleanField()
    result = serializers.DictField()
