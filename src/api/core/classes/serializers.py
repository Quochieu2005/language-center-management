"""Strict request and response serializers for site-local class management."""

from rest_framework import serializers


_SITE_CODE = r"^[A-Za-z0-9_-]{2,10}$"


class StrictInputSerializer(serializers.Serializer):
    allowed_fields: set[str] = set()

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) - self.allowed_fields:
            raise serializers.ValidationError({"detail": "Yêu cầu chứa trường không được phép."})
        return super().to_internal_value(data)


class ClassListQuerySerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    status = serializers.ChoiceField(
        choices=("sap_mo", "dang_hoc", "ket_thuc", "huy"), required=False
    )
    search = serializers.CharField(max_length=100, required=False, trim_whitespace=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)
    offset = serializers.IntegerField(min_value=0, max_value=100000, required=False, default=0)
    allowed_fields = {"site_code", "status", "search", "limit", "offset"}

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_search(self, value):
        value = value.strip()
        if any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Từ khóa tìm kiếm không hợp lệ.")
        return value


class ClassSiteQuerySerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    allowed_fields = {"site_code"}

    def validate_site_code(self, value):
        return value.strip().upper()


class ClassRosterQuerySerializer(ClassSiteQuerySerializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)
    offset = serializers.IntegerField(min_value=0, max_value=100000, required=False, default=0)
    allowed_fields = {"site_code", "limit", "offset"}


class RoomListQuerySerializer(ClassRosterQuerySerializer):
    status = serializers.ChoiceField(choices=("hoat_dong", "bao_tri"), required=False)
    search = serializers.CharField(max_length=100, required=False, trim_whitespace=True)
    allowed_fields = {"site_code", "limit", "offset", "status", "search"}


class RoomCreateSerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    name = serializers.CharField(max_length=100, trim_whitespace=True)
    capacity = serializers.IntegerField(min_value=1, max_value=300)
    allowed_fields = {"site_code", "name", "capacity"}

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_name(self, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Tên phòng không hợp lệ.")
        return value


class EnrollmentCreateSerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    student_id = serializers.CharField(max_length=24, trim_whitespace=True)
    class_id = serializers.CharField(max_length=24, trim_whitespace=True)
    allowed_fields = {"site_code", "student_id", "class_id"}

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_student_id(self, value):
        return value.strip()

    def validate_class_id(self, value):
        return value.strip()


class ClassCreateSerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    course_id = serializers.CharField(max_length=30, trim_whitespace=True)
    teacher_id = serializers.CharField(max_length=24, trim_whitespace=True)
    room_id = serializers.CharField(max_length=24, trim_whitespace=True)
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    capacity = serializers.IntegerField(
        min_value=1, max_value=300, help_text="Sĩ số tối đa; phải không vượt sức chứa phòng học."
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=2, max_value=6), min_length=1, max_length=5,
        help_text="Ngày học lặp theo tuần: 2=Thứ 2, ..., 6=Thứ 6.",
    )
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    allowed_fields = {
        "site_code", "course_id", "teacher_id", "room_id", "name", "capacity",
        "start_date", "end_date", "weekdays", "start_time", "end_time",
    }

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_course_id(self, value):
        return value.strip()

    def validate_teacher_id(self, value):
        return value.strip()

    def validate_room_id(self, value):
        return value.strip()

    def validate_name(self, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Tên lớp không hợp lệ.")
        return value

    def validate_weekdays(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Không được chọn trùng thứ trong tuần.")
        return sorted(value)

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "Ngày kết thúc không được trước ngày khai giảng."})
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "Giờ kết thúc phải sau giờ bắt đầu."})
        return attrs


class ClassTeacherAssignSerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    teacher_id = serializers.CharField(max_length=24, trim_whitespace=True)
    allowed_fields = {"site_code", "teacher_id"}

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_teacher_id(self, value):
        return value.strip()


class EnrollmentClassAssignSerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    target_class_id = serializers.CharField(max_length=24, trim_whitespace=True)
    allowed_fields = {"site_code", "target_class_id"}

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_target_class_id(self, value):
        return value.strip()


class ClassItemSerializer(serializers.Serializer):
    class_id = serializers.CharField()
    site_code = serializers.CharField()
    course_id = serializers.CharField()
    course_name = serializers.CharField()
    teacher_id = serializers.CharField()
    teacher_name = serializers.CharField()
    room_id = serializers.CharField()
    room_name = serializers.CharField()
    name = serializers.CharField()
    capacity = serializers.IntegerField()
    current_count = serializers.IntegerField()
    registered_count = serializers.IntegerField()
    remaining_seats = serializers.IntegerField()
    capacity_consistent = serializers.BooleanField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(allow_null=True)
    schedule = serializers.CharField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    status = serializers.CharField()


class ClassListResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = ClassItemSerializer(many=True)


class ClassDetailResponseSerializer(ClassItemSerializer):
    session_count = serializers.IntegerField()
    sessions_created = serializers.IntegerField(required=False)


class ClassTeacherAssignResponseSerializer(ClassDetailResponseSerializer):
    changed = serializers.BooleanField()


class ClassRosterItemSerializer(serializers.Serializer):
    enrollment_id = serializers.CharField()
    student_id = serializers.CharField()
    student_slug = serializers.CharField()
    full_name = serializers.CharField()
    enrollment_status = serializers.CharField()
    student_status = serializers.CharField()


class ClassRosterResponseSerializer(serializers.Serializer):
    class_id = serializers.CharField()
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = ClassRosterItemSerializer(many=True)


class ClassSessionItemSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    session_number = serializers.IntegerField()
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    room_id = serializers.CharField()
    room_name = serializers.CharField()
    teacher_id = serializers.CharField()
    teacher_name = serializers.CharField()
    status = serializers.CharField()
    note = serializers.CharField(allow_null=True)


class ClassSessionListResponseSerializer(serializers.Serializer):
    class_id = serializers.CharField()
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = ClassSessionItemSerializer(many=True)


class RoomItemSerializer(serializers.Serializer):
    room_id = serializers.CharField()
    site_code = serializers.CharField()
    name = serializers.CharField()
    capacity = serializers.IntegerField()
    status = serializers.CharField()


class RoomListResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = RoomItemSerializer(many=True)


class RoomCreateResponseSerializer(RoomItemSerializer):
    pass


class EnrollmentCreateResponseSerializer(serializers.Serializer):
    enrollment_id = serializers.CharField()
    student_id = serializers.CharField()
    class_id = serializers.CharField()
    course_id = serializers.CharField()
    tuition_id = serializers.CharField()
    amount_due = serializers.DecimalField(max_digits=18, decimal_places=0)
    enrollment_status = serializers.CharField()
    tuition_status = serializers.CharField()
    site_code = serializers.CharField()
    current_count = serializers.IntegerField()
    remaining_seats = serializers.IntegerField()
    created = serializers.BooleanField()


class EnrollmentClassAssignResponseSerializer(serializers.Serializer):
    enrollment_id = serializers.CharField()
    student_id = serializers.CharField()
    previous_class_id = serializers.CharField(allow_null=True)
    previous_class_current_count = serializers.IntegerField()
    previous_class_remaining_seats = serializers.IntegerField()
    class_id = serializers.CharField()
    site_code = serializers.CharField()
    enrollment_status = serializers.CharField()
    current_count = serializers.IntegerField()
    remaining_seats = serializers.IntegerField()
    changed = serializers.BooleanField()
