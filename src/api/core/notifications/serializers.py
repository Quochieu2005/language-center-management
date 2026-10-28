from rest_framework import serializers


class NotificationQuerySerializer(serializers.Serializer):
    site_code = serializers.RegexField(regex=r"^[A-Za-z0-9_-]{2,10}$", required=False)
    category = serializers.ChoiceField(
        choices=("system", "tuition", "account", "teacher", "enrollment", "class", "grade", "transfer", "payment", "security"),
        required=False,
    )
    unread_only = serializers.BooleanField(required=False, default=False)
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    offset = serializers.IntegerField(min_value=0, max_value=10000, required=False, default=0)


class NotificationReadSerializer(serializers.Serializer):
    site_code = serializers.RegexField(regex=r"^[A-Za-z0-9_-]{2,10}$")


class NotificationItemSerializer(serializers.Serializer):
    slug = serializers.CharField()
    site_code = serializers.CharField()
    category = serializers.CharField()
    severity = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    target_path = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()


class NotificationListResponseSerializer(serializers.Serializer):
    complete = serializers.BooleanField()
    missing_sites = serializers.ListField(child=serializers.CharField())
    site_codes = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = NotificationItemSerializer(many=True)


class NotificationUnreadCountResponseSerializer(serializers.Serializer):
    complete = serializers.BooleanField()
    missing_sites = serializers.ListField(child=serializers.CharField())
    site_codes = serializers.ListField(child=serializers.CharField())
    unread_count = serializers.IntegerField()


class NotificationReadAllResponseSerializer(serializers.Serializer):
    complete = serializers.BooleanField()
    marked_sites = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())


class NotificationReadResponseSerializer(serializers.Serializer):
    slug = serializers.CharField()
    site_code = serializers.CharField()
    category = serializers.CharField()
    created_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()
    read_at = serializers.DateTimeField()
