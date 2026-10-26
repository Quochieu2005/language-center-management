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
