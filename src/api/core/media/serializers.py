from rest_framework import serializers

from core.media.folders import is_avatar_public_id


class AvatarPublicIdField(serializers.CharField):
    """Cloudinary public id: ``<root>/<category>/[<SITE>/]<slug>-dd-mm-yyyy`` or a legacy UUID."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 255)
        kwargs.setdefault("trim_whitespace", False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not is_avatar_public_id(value):
            raise serializers.ValidationError("Mã ảnh tải lên không hợp lệ.")
        return value


class AdminAvatarUploadIntentResponseSerializer(serializers.Serializer):
    intent_token = serializers.CharField()
    upload_url = serializers.URLField()
    cloud_name = serializers.CharField()
    api_key = serializers.CharField()
    fields = serializers.DictField(child=serializers.CharField())
    max_file_bytes = serializers.IntegerField()


class AdminAvatarFinalizeRequestSerializer(serializers.Serializer):
    intent_token = serializers.CharField(max_length=2048, trim_whitespace=False, write_only=True)
    public_id = AvatarPublicIdField()

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) != {"intent_token", "public_id"}:
            raise serializers.ValidationError({"detail": "Chỉ nhận intent_token và public_id."})
        return super().to_internal_value(data)


class AdminSmallAvatarUploadIntentRequestSerializer(serializers.Serializer):
    setup_token = serializers.CharField(max_length=2048, trim_whitespace=False, write_only=True)

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) != {"setup_token"}:
            raise serializers.ValidationError({"detail": "Chỉ nhận setup_token."})
        return super().to_internal_value(data)


class AdminSmallAvatarFinalizeRequestSerializer(serializers.Serializer):
    setup_token = serializers.CharField(max_length=2048, trim_whitespace=False, write_only=True)
    intent_token = serializers.CharField(max_length=2048, trim_whitespace=False, write_only=True)
    public_id = AvatarPublicIdField()

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) != {"setup_token", "intent_token", "public_id"}:
            raise serializers.ValidationError({"detail": "Chỉ nhận setup_token, intent_token và public_id."})
        return super().to_internal_value(data)


class TeacherAvatarUploadIntentRequestSerializer(AdminSmallAvatarUploadIntentRequestSerializer):
    pass


class TeacherAvatarFinalizeRequestSerializer(AdminSmallAvatarFinalizeRequestSerializer):
    pass


class EmployeeAvatarUploadIntentRequestSerializer(TeacherAvatarUploadIntentRequestSerializer):
    pass


class EmployeeAvatarFinalizeRequestSerializer(TeacherAvatarFinalizeRequestSerializer):
    pass


class AdminAvatarResponseSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    role = serializers.ChoiceField(choices=(
        "admin_big", "admin_small", "le_tan", "tu_van", "ke_toan",
        "giao_vien", "hoc_vien",
    ))
    avatar_secure_url = serializers.URLField()
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
