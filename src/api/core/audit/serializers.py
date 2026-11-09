from rest_framework import serializers


class AuditLogQuerySerializer(serializers.Serializer):
    ma_co_so = serializers.RegexField(regex=r"^[A-Za-z0-9_-]{2,10}$", required=False)
    ma_tai_khoan = serializers.CharField(max_length=24, required=False, allow_blank=False)
    loai_log = serializers.ChoiceField(choices=("login", "password_reset", "system", "sync"), required=False)
    tu_ngay = serializers.DateField(required=False)
    den_ngay = serializers.DateField(required=False)
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    offset = serializers.IntegerField(min_value=0, max_value=10000, required=False, default=0)

    def validate(self, attrs):
        start, end = attrs.get("tu_ngay"), attrs.get("den_ngay")
        if start and end and end < start:
            raise serializers.ValidationError({"den_ngay": "Ngày kết thúc không được trước ngày bắt đầu."})
        return attrs


class AuditLogItemSerializer(serializers.Serializer):
    log_id = serializers.CharField()
    log_type = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    site_code = serializers.CharField()
    account_id = serializers.CharField(allow_null=True)
    action = serializers.CharField(allow_null=True)
    affected_table = serializers.CharField(allow_null=True)
    record_id = serializers.CharField(allow_null=True)
    result = serializers.CharField(allow_null=True)
    destination_site = serializers.CharField(allow_null=True)


class AuditLogListResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("LOCAL", "GLOBAL"))
    complete = serializers.BooleanField()
    missing_sites = serializers.ListField(child=serializers.CharField())
    site_codes = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = AuditLogItemSerializer(many=True)
