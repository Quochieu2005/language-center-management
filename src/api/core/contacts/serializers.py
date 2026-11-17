"""Validation and response schemas for contact requests."""

from rest_framework import serializers


class ContactSiteSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    name = serializers.CharField()


class ContactSiteListSerializer(serializers.Serializer):
    complete = serializers.BooleanField()
    missing_sites = serializers.ListField(child=serializers.CharField())
    site_codes = serializers.ListField(child=serializers.CharField())
    results = ContactSiteSerializer(many=True)


class ContactSubmissionSerializer(serializers.Serializer):
    site_code = serializers.RegexField(r"^[A-Za-z0-9_-]{1,10}$", max_length=10)
    full_name = serializers.CharField(max_length=120, trim_whitespace=True)
    email = serializers.EmailField(max_length=254, trim_whitespace=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, trim_whitespace=True)
    subject = serializers.CharField(max_length=160, trim_whitespace=True)
    message = serializers.CharField(max_length=5000, trim_whitespace=True)

    def validate_site_code(self, value):
        return value.upper()

    def validate_email(self, value):
        return value.casefold()

    def validate_subject(self, value):
        if "\r" in value or "\n" in value:
            raise serializers.ValidationError("Tiêu đề không được chứa ký tự xuống dòng.")
        return value

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Vui lòng nhập nội dung cần trao đổi.")
        return value


class ContactSubmissionResponseSerializer(serializers.Serializer):
    request_id = serializers.CharField()
    site_code = serializers.CharField()
    status = serializers.ChoiceField(choices=("cho_xu_ly", "da_phan_hoi"))
    received_at = serializers.DateTimeField()
    replayed = serializers.BooleanField()


class AdminContactQuerySerializer(serializers.Serializer):
    site_code = serializers.RegexField(r"^[A-Za-z0-9_-]{1,10}$", required=False, max_length=10)
    status = serializers.ChoiceField(choices=("cho_xu_ly", "da_phan_hoi"), required=False)
    search = serializers.CharField(required=False, allow_blank=True, max_length=100, trim_whitespace=True)
    limit = serializers.IntegerField(required=False, default=25, min_value=1, max_value=100)
    offset = serializers.IntegerField(required=False, default=0, min_value=0)

    def validate_site_code(self, value):
        return value.upper()


class AdminContactRequestSerializer(serializers.Serializer):
    request_id = serializers.CharField()
    site_code = serializers.CharField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(allow_null=True)
    subject = serializers.CharField()
    message = serializers.CharField()
    status = serializers.ChoiceField(choices=("cho_xu_ly", "da_phan_hoi"))
    received_at = serializers.DateTimeField()
    reply_body = serializers.CharField(allow_null=True)
    replied_at = serializers.DateTimeField(allow_null=True)


class AdminContactListSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("LOCAL", "GLOBAL"))
    complete = serializers.BooleanField()
    missing_sites = serializers.ListField(child=serializers.CharField())
    site_codes = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField(allow_null=True)
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = AdminContactRequestSerializer(many=True)


class ContactReplySerializer(serializers.Serializer):
    reply_body = serializers.CharField(max_length=5000, trim_whitespace=True)

    def validate_reply_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Vui lòng nhập nội dung phản hồi.")
        return value


class ContactReplyResponseSerializer(serializers.Serializer):
    request_id = serializers.CharField()
    site_code = serializers.CharField()
    status = serializers.ChoiceField(choices=("da_phan_hoi",))
    replied_at = serializers.DateTimeField()
