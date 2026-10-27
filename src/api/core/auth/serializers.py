from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class AuthLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    def validate_identifier(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Nhập email hoặc tên đăng nhập hợp lệ.")
        return value


class AdminForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().casefold()


class AdminResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    otp = serializers.RegexField(regex=r"^\d{6}$", trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(
        min_length=12, max_length=128, trim_whitespace=False, write_only=True
    )
    confirm_password = serializers.CharField(
        min_length=12, max_length=128, trim_whitespace=False, write_only=True
    )

    def validate_email(self, value):
        return value.strip().casefold()

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Mật khẩu xác nhận không khớp."})
        return attrs


class AuthChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(
        min_length=12, max_length=128, trim_whitespace=False, write_only=True
    )
    confirm_password = serializers.CharField(
        min_length=12, max_length=128, trim_whitespace=False, write_only=True
    )

    def validate_new_password(self, value):
        request = self.context.get("request")
        try:
            validate_password(value, user=getattr(request, "user", None))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Mật khẩu xác nhận không khớp."})
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError({"new_password": "Mật khẩu mới phải khác mật khẩu hiện tại."})
        return attrs


class AdminSmallCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    site_code = serializers.RegexField(regex=r"^[A-Za-z0-9_-]{2,12}$", max_length=12)
    username = serializers.RegexField(
        regex=r"^[A-Za-z0-9._-]{3,100}$", max_length=100, required=False
    )

    def validate_full_name(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Họ tên không hợp lệ.")
        return value

    def validate_email(self, value):
        return value.strip().casefold()

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_username(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Tên đăng nhập không hợp lệ.")
        return value


class AdminSmallSelfProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=False, trim_whitespace=True)
    phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True, trim_whitespace=True
    )

    def to_internal_value(self, data):
        allowed = {"full_name", "phone"}
        if hasattr(data, "keys") and set(data.keys()) - allowed:
            raise serializers.ValidationError(
                {"detail": "Chỉ được cập nhật họ tên và số điện thoại của chính mình."}
            )
        return super().to_internal_value(data)

    def validate_full_name(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Họ tên không hợp lệ.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not value:
            return None
        if len(value) < 6 or any(character not in "+0123456789(). -" for character in value):
            raise serializers.ValidationError("Số điện thoại không hợp lệ.")
        return value

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Cần cung cấp ít nhất một trường để cập nhật.")
        return attrs


class AdminSmallSelfProfileResponseSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    profile_id = serializers.CharField()
    site_code = serializers.CharField()
    role = serializers.ChoiceField(choices=["admin_small"])
    full_name = serializers.CharField()
    phone = serializers.CharField(allow_null=True)
    username = serializers.CharField()
    email = serializers.EmailField()


class AdminSmallDeleteResponseSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    site_code = serializers.CharField()
    role = serializers.ChoiceField(choices=["admin_small"])
    status = serializers.ChoiceField(choices=["vo_hieu"])
    detail = serializers.CharField()


class AuthPasswordChangeResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class AdminSmallCreateResponseSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    employee_id = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    site_code = serializers.CharField()
    role = serializers.ChoiceField(choices=["admin_small"])
    must_change_password = serializers.BooleanField()
    email_sent = serializers.BooleanField()


class GenericPasswordResetResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PasswordResetCompleteResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class AuthUserSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    slug = serializers.CharField()
    email = serializers.EmailField()
    username = serializers.CharField()
    role = serializers.ChoiceField(
        choices=["admin_big", "admin_small", "le_tan", "ke_toan", "giao_vien"]
    )
    site_code = serializers.CharField(allow_null=True)
    profile_id = serializers.CharField(allow_null=True)
    must_change_password = serializers.BooleanField()


class AuthLoginResponseSerializer(serializers.Serializer):
    user = AuthUserSerializer()
    idle_timeout_seconds = serializers.IntegerField()


class AuthMeResponseSerializer(serializers.Serializer):
    user = AuthUserSerializer()
    expires_at = serializers.DateTimeField()


class CsrfTokenResponseSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()


class EmptyRequestSerializer(serializers.Serializer):
    """Explicit empty JSON body for session activity and logout operations."""
