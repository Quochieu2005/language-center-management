from rest_framework import serializers
from decimal import Decimal

from core.slug_utils import make_slug


class PublicCourseBranchSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    site_name = serializers.CharField()
    open_class_count = serializers.IntegerField(min_value=1)


class PublicCourseSerializer(serializers.Serializer):
    course_id = serializers.CharField()
    slug = serializers.CharField()
    subject_id = serializers.CharField()
    subject_slug = serializers.CharField()
    subject_name = serializers.CharField()
    name = serializers.CharField()
    level = serializers.CharField()
    session_count = serializers.IntegerField(min_value=1, allow_null=True)
    thoi_luong_so = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"), allow_null=True)
    thoi_luong_don_vi = serializers.ChoiceField(choices=("thang", "ngay"), allow_null=True)
    standard_fee = serializers.IntegerField(min_value=0)
    version = serializers.IntegerField(min_value=1)
    branches = PublicCourseBranchSerializer(many=True)


class PublicCourseListSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("GLOBAL",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    inconsistent_sites = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField(min_value=0)
    results = PublicCourseSerializer(many=True)


class SharedSubjectSerializer(serializers.Serializer):
    ma_mon = serializers.CharField()
    slug = serializers.CharField()
    ten_mon = serializers.CharField()
    mo_ta = serializers.CharField(allow_null=True)
    phien_ban = serializers.IntegerField(min_value=1)


class SharedSubjectListSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("GLOBAL",))
    complete = serializers.BooleanField()
    site_codes = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    inconsistent_sites = serializers.ListField(child=serializers.CharField())
    count = serializers.IntegerField(min_value=0)
    results = SharedSubjectSerializer(many=True)


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


class SharedSubjectCreateSerializer(serializers.Serializer):
    ma_mon = serializers.RegexField(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$", max_length=30)
    ten_mon = serializers.CharField(max_length=100, trim_whitespace=True)
    mo_ta = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True, trim_whitespace=True)

    def validate_ma_mon(self, value):
        value = value.strip().upper()
        if any(ord(character) < 33 for character in value):
            raise serializers.ValidationError("Mã môn học không hợp lệ.")
        return value

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
                {field: "Trường này không được phép tạo." for field in sorted(unexpected)}
            )
        try:
            attrs["slug"] = make_slug(attrs["ten_mon"], max_length=120)
        except ValueError as exc:
            raise serializers.ValidationError({"ten_mon": str(exc)}) from exc
        attrs.setdefault("mo_ta", None)
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


class SharedSubjectDeleteResponseSerializer(serializers.Serializer):
    ma_mon = serializers.CharField()
    slug = serializers.CharField()
    deleted = serializers.BooleanField()
    complete = serializers.BooleanField()
    sites = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    idempotent_replay = serializers.BooleanField()


class SharedCourseCreateSerializer(serializers.Serializer):
    ma_khoa_hoc = serializers.RegexField(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$", max_length=30)
    ma_mon = serializers.CharField(max_length=30, trim_whitespace=True)
    ten_khoa_hoc = serializers.CharField(max_length=120, trim_whitespace=True)
    trinh_do = serializers.CharField(max_length=30, trim_whitespace=True)
    so_buoi = serializers.IntegerField(min_value=1, max_value=32767, required=False, allow_null=True)
    thoi_luong_so = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"), max_value=Decimal("99999.99"))
    thoi_luong_don_vi = serializers.ChoiceField(choices=("thang", "ngay"))
    hoc_phi_chuan = serializers.IntegerField(min_value=0, max_value=999999999999999999)

    def validate_ma_mon(self, value):
        value = value.strip().upper()
        if not value or any(ord(character) < 33 for character in value):
            raise serializers.ValidationError("Mã môn học không hợp lệ.")
        return value

    def validate_ten_khoa_hoc(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Tên khóa học không hợp lệ.")
        return value

    def validate_trinh_do(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Trình độ không hợp lệ.")
        return value

    def validate(self, attrs):
        unexpected = set(self.initial_data) - set(self.fields)
        if unexpected:
            raise serializers.ValidationError(
                {field: "Trường này không được phép tạo." for field in sorted(unexpected)}
            )
        if attrs["thoi_luong_don_vi"] == "ngay" and attrs["thoi_luong_so"] % 1:
            raise serializers.ValidationError({"thoi_luong_so": "Thời lượng tính theo ngày phải là số nguyên."})
        try:
            attrs["slug"] = make_slug(attrs["ten_khoa_hoc"], max_length=160)
        except ValueError as exc:
            raise serializers.ValidationError({"ten_khoa_hoc": str(exc)}) from exc
        attrs.setdefault("so_buoi", None)
        return attrs


class SharedCoursePatchSerializer(serializers.Serializer):
    ma_khoa_hoc = serializers.RegexField(
        r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$", max_length=30, required=False
    )
    ma_mon = serializers.CharField(max_length=30, required=False, trim_whitespace=True)
    ten_khoa_hoc = serializers.CharField(max_length=120, required=False, trim_whitespace=True)
    trinh_do = serializers.CharField(max_length=30, required=False, trim_whitespace=True)
    so_buoi = serializers.IntegerField(min_value=1, max_value=32767, required=False, allow_null=True)
    thoi_luong_so = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"), max_value=Decimal("99999.99"), required=False)
    thoi_luong_don_vi = serializers.ChoiceField(choices=("thang", "ngay"), required=False)
    hoc_phi_chuan = serializers.IntegerField(
        min_value=0, max_value=999999999999999999, required=False
    )

    def validate_ma_mon(self, value):
        value = value.strip().upper()
        if not value or any(ord(character) < 33 for character in value):
            raise serializers.ValidationError("Mã môn học không hợp lệ.")
        return value

    def validate_ten_khoa_hoc(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Tên khóa học không hợp lệ.")
        return value

    def validate_trinh_do(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Trình độ không hợp lệ.")
        return value

    def validate(self, attrs):
        unexpected = set(self.initial_data) - set(self.fields)
        if unexpected:
            raise serializers.ValidationError(
                {field: "Trường này không được phép cập nhật." for field in sorted(unexpected)}
            )
        if not attrs:
            raise serializers.ValidationError("Cần cung cấp ít nhất một trường cần cập nhật.")
        if ("thoi_luong_so" in attrs) != ("thoi_luong_don_vi" in attrs):
            raise serializers.ValidationError("Khi đổi thời lượng, cần gửi cả số lượng và đơn vị tháng/ngày.")
        if attrs.get("thoi_luong_don_vi") == "ngay" and attrs["thoi_luong_so"] % 1:
            raise serializers.ValidationError({"thoi_luong_so": "Thời lượng tính theo ngày phải là số nguyên."})
        return attrs


class SharedCourseWriteResponseSerializer(serializers.Serializer):
    ma_khoa_hoc = serializers.CharField()
    slug = serializers.CharField()
    ma_mon = serializers.CharField()
    ten_khoa_hoc = serializers.CharField()
    trinh_do = serializers.CharField()
    so_buoi = serializers.IntegerField(allow_null=True)
    thoi_luong_so = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"), allow_null=True)
    thoi_luong_don_vi = serializers.ChoiceField(choices=("thang", "ngay"), allow_null=True)
    hoc_phi_chuan = serializers.IntegerField()
    phien_ban = serializers.IntegerField()
    complete = serializers.BooleanField()
    sites = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    idempotent_replay = serializers.BooleanField()


class SharedCourseDeleteResponseSerializer(serializers.Serializer):
    ma_khoa_hoc = serializers.CharField()
    slug = serializers.CharField()
    deleted = serializers.BooleanField()
    complete = serializers.BooleanField()
    sites = serializers.ListField(child=serializers.CharField())
    missing_sites = serializers.ListField(child=serializers.CharField())
    idempotent_replay = serializers.BooleanField()
