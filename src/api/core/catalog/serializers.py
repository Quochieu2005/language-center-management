from rest_framework import serializers


class SharedSubjectPatchSerializer(serializers.Serializer):
    ten_mon = serializers.CharField(max_length=100, required=False, trim_whitespace=True)
    mo_ta = serializers.CharField(
        max_length=500, required=False, allow_blank=True, allow_null=True, trim_whitespace=True
    )

    def validate_ten_mon(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Tên môn học không hợp lệ.")
        return value

    def validate_mo_ta(self, value):
        if value is None:
            return None
        value = value.strip()
        if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
            raise serializers.ValidationError("Mô tả chứa ký tự điều khiển không hợp lệ.")
        return value or None

    def validate(self, attrs):
        unexpected = set(self.initial_data) - set(self.fields)
        if unexpected:
            raise serializers.ValidationError(
                {field: "Trường này không được phép cập nhật." for field in sorted(unexpected)}
            )
        if not attrs:
            raise serializers.ValidationError("Cần cung cấp ít nhất tên hoặc mô tả môn học.")
        return attrs


class SharedSubjectUpdateResponseSerializer(serializers.Serializer):
    ma_mon = serializers.CharField()
    slug = serializers.CharField()
    ten_mon = serializers.CharField()
    mo_ta = serializers.CharField(allow_null=True)
    phien_ban = serializers.IntegerField()
    complete = serializers.BooleanField()
    sites = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    idempotent_replay = serializers.BooleanField()
