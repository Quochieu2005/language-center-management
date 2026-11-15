from rest_framework import serializers


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
