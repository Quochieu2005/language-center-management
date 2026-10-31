from rest_framework import serializers


class AdminAvatarUploadIntentResponseSerializer(serializers.Serializer):
    intent_token = serializers.CharField()
    upload_url = serializers.URLField()
    cloud_name = serializers.CharField()
    api_key = serializers.CharField()
    fields = serializers.DictField(child=serializers.CharField())
    max_file_bytes = serializers.IntegerField()


class AdminAvatarFinalizeRequestSerializer(serializers.Serializer):
    intent_token = serializers.CharField(max_length=2048, trim_whitespace=False, write_only=True)
    public_id = serializers.RegexField(
        regex=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        max_length=36,
        trim_whitespace=False,
    )

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) != {"intent_token", "public_id"}:
            raise serializers.ValidationError({"detail": "Chỉ nhận intent_token và public_id."})
        return super().to_internal_value(data)


class AdminAvatarResponseSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    role = serializers.ChoiceField(choices=("admin_big", "admin_small"))
    avatar_secure_url = serializers.URLField()
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
