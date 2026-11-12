from rest_framework import serializers

from core.slug_utils import make_slug


_SITE_CODE = r"^[A-Za-z0-9_-]{2,10}$"
_USERNAME = r"^[A-Za-z0-9._-]{3,100}$"


class StrictInputSerializer(serializers.Serializer):
    """Reject request fields that this API does not explicitly accept."""

    allowed_fields: set[str] = set()

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) - self.allowed_fields:
            raise serializers.ValidationError({"detail": "Yêu cầu chứa trường không được phép."})
        return super().to_internal_value(data)


class TeacherCreateSerializer(StrictInputSerializer):
    full_name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    username = serializers.RegexField(regex=_USERNAME, max_length=100, required=False)
    slug = serializers.CharField(max_length=120, required=False, allow_blank=True, trim_whitespace=True)
    phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True, trim_whitespace=True
    )
    avatar_requested = serializers.BooleanField(required=False, default=False)
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    allowed_fields = {"full_name", "email", "username", "slug", "phone", "avatar_requested", "site_code"}

    def validate_full_name(self, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise serializers.ValidationError("Họ tên không hợp lệ.")
        return value

    def validate_email(self, value):
        return value.strip().casefold()

    def validate_username(self, value):
        value = value.strip().lower()
        if not value or any(ord(c) < 32 for c in value):
            raise serializers.ValidationError("Tên đăng nhập không hợp lệ.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if value and (len(value) < 6 or any(c not in "+0123456789(). -" for c in value)):
            raise serializers.ValidationError("Số điện thoại không hợp lệ.")
        return value or None

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        try:
            attrs["slug"] = make_slug(attrs["full_name"], attrs.get("slug"), max_length=120)
        except ValueError as exc:
            raise serializers.ValidationError({"slug": str(exc)}) from exc
        return attrs


class TeacherProfileUpdateSerializer(StrictInputSerializer):
    full_name = serializers.CharField(max_length=150, required=False, trim_whitespace=True)
    phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True, trim_whitespace=True
    )
    allowed_fields = {"full_name", "phone"}

    def validate_full_name(self, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise serializers.ValidationError("Họ tên không hợp lệ.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if value and (len(value) < 6 or any(c not in "+0123456789(). -" for c in value)):
            raise serializers.ValidationError("Số điện thoại không hợp lệ.")
        return value or None

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Cần cung cấp ít nhất một trường để cập nhật.")
        return attrs


class TeacherListQuerySerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    status = serializers.ChoiceField(choices=("dang_day", "tam_nghi", "nghi_viec"), required=False)
    search = serializers.CharField(max_length=100, required=False, trim_whitespace=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)
    offset = serializers.IntegerField(min_value=0, max_value=100000, required=False, default=0)
    allowed_fields = {"site_code", "status", "search", "limit", "offset"}

    def validate_site_code(self, value):
        return value.strip().upper()


class TeacherSiteQuerySerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    allowed_fields = {"site_code"}

    def validate_site_code(self, value):
        return value.strip().upper()


class TeacherResponseSerializer(serializers.Serializer):
    teacher_id = serializers.CharField()
    account_id = serializers.CharField(allow_null=True)
    slug = serializers.CharField(allow_null=True)
    site_code = serializers.CharField()
    account_status = serializers.ChoiceField(choices=("active", "inactive"), allow_null=True)
    full_name = serializers.CharField()
    phone = serializers.CharField(allow_null=True)
    email = serializers.EmailField(allow_null=True)
    username = serializers.CharField(allow_null=True)
    specialty = serializers.CharField()
    avatar_secure_url = serializers.URLField(allow_null=True)
    credential_email_status = serializers.ChoiceField(
        choices=("ready", "processing", "sent", "failed", "unknown", "changed")
    )
    status = serializers.ChoiceField(choices=("dang_day", "tam_nghi", "nghi_viec"))


class TeacherListResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = TeacherResponseSerializer(many=True)


class TeacherCreateResponseSerializer(TeacherResponseSerializer):
    must_change_password = serializers.BooleanField()
    avatar_setup_token = serializers.CharField(allow_null=True)


class TeacherDeleteResponseSerializer(serializers.Serializer):
    teacher_id = serializers.CharField()
    account_id = serializers.CharField()
    site_code = serializers.CharField()
    status = serializers.ChoiceField(choices=("inactive",))
    teacher_status = serializers.ChoiceField(choices=("nghi_viec",))
    detail = serializers.CharField()


class TeacherCredentialEmailResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("sent",))
    email = serializers.EmailField()
    detail = serializers.CharField()
