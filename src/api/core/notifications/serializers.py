from rest_framework import serializers


class NotificationQuerySerializer(serializers.Serializer):
    site_code = serializers.RegexField(regex=r"^[A-Za-z0-9_-]{2,10}$", required=False)
    category = serializers.ChoiceField(
        choices=("system", "tuition", "account", "teacher", "enrollment", "class", "grade", "transfer", "payment", "security"),
        required=False,
    )
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    offset = serializers.IntegerField(min_value=0, max_value=10000, required=False, default=0)


class NotificationItemSerializer(serializers.Serializer):
    slug = serializers.CharField()
    site_code = serializers.CharField()
    category = serializers.CharField()
    severity = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    target_path = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class NotificationListResponseSerializer(serializers.Serializer):
    complete = serializers.BooleanField()
    missing_sites = serializers.ListField(child=serializers.CharField())
    site_codes = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = NotificationItemSerializer(many=True)
