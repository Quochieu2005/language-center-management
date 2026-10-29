"""Validated request and response contracts for staff operations."""

from rest_framework import serializers


_SITE_CODE = r"^[A-Za-z0-9_-]{2,10}$"
_USERNAME = r"^[A-Za-z0-9._-]{3,100}$"
_STAFF_ROLES = ("le_tan", "tu_van", "ke_toan", "xep_lop")


class StrictInputSerializer(serializers.Serializer):
    allowed_fields: set[str] = set()

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) - self.allowed_fields:
            raise serializers.ValidationError({"detail": "Yêu cầu chứa trường không được phép."})
        return super().to_internal_value(data)


class EmployeeCreateSerializer(StrictInputSerializer):
    full_name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    username = serializers.RegexField(regex=_USERNAME, max_length=100, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    job_title = serializers.ChoiceField(choices=_STAFF_ROLES)
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    allowed_fields = {"full_name", "email", "username", "phone", "job_title", "site_code"}

    def validate_full_name(self, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Họ tên không hợp lệ.")
        return value

    def validate_email(self, value):
        return value.strip().casefold()

    def validate_username(self, value):
        value = value.strip().lower()
        if not value or any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Tên đăng nhập không hợp lệ.")
        return value

    def validate_phone(self, value):
        value = (value or "").strip()
        if value and (len(value) < 6 or any(char not in "+0123456789(). -" for char in value)):
            raise serializers.ValidationError("Số điện thoại không hợp lệ.")
        return value or None

    def validate_site_code(self, value):
        return value.strip().upper()


class EmployeeListQuerySerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    job_title = serializers.ChoiceField(choices=_STAFF_ROLES, required=False)
    status = serializers.ChoiceField(choices=("dang_lam", "nghi_viec"), required=False)
    search = serializers.CharField(max_length=100, required=False, trim_whitespace=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)
    offset = serializers.IntegerField(min_value=0, max_value=100000, required=False, default=0)
    allowed_fields = {"site_code", "job_title", "status", "search", "limit", "offset"}

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_search(self, value):
        return value.strip()


class EmployeeSiteQuerySerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    allowed_fields = {"site_code"}

    def validate_site_code(self, value):
        return value.strip().upper()


class EmployeeListResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = serializers.ListField(child=serializers.DictField())
