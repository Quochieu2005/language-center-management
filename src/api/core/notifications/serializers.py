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


class NotificationCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=("system", "tuition", "account", "teacher", "enrollment", "class", "grade", "transfer", "payment", "security"),
    )
    severity = serializers.ChoiceField(choices=("info", "success", "warning", "critical"), default="info")
    audience = serializers.ChoiceField(choices=("admin_all", "admin_big", "admin_small"), default="admin_all")
    title = serializers.CharField(max_length=160, trim_whitespace=True)
    message = serializers.CharField(max_length=500, allow_blank=True, trim_whitespace=True)
    target_path = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Tiêu đề không được để trống.")
        return value

    def validate_target_path(self, value):
        if value and not value.startswith("/admin/"):
            raise serializers.ValidationError("Chỉ chấp nhận đường dẫn nội bộ trong khu vực admin.")
        return value or None


class NotificationCreateResultItemSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    slug = serializers.CharField()
    created = serializers.BooleanField()


class NotificationCreateResponseSerializer(serializers.Serializer):
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    results = NotificationCreateResultItemSerializer(many=True)
