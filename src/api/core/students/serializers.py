from rest_framework import serializers


_SITE_CODE = r"^[A-Za-z0-9_-]{2,10}$"


class StrictInputSerializer(serializers.Serializer):
    allowed_fields: set[str] = set()

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) - self.allowed_fields:
            raise serializers.ValidationError({"detail": "Yêu cầu chứa trường không được phép."})
        return super().to_internal_value(data)


class StudentListQuerySerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    status = serializers.ChoiceField(
        choices=("dang_hoc", "bao_luu", "da_chuyen_di", "nghi_hoc"), required=False
    )
    search = serializers.CharField(max_length=100, required=False, trim_whitespace=True)
    account_issued = serializers.BooleanField(required=False)
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)
    offset = serializers.IntegerField(min_value=0, max_value=100000, required=False, default=0)
    allowed_fields = {"site_code", "status", "search", "account_issued", "limit", "offset"}

    def validate_site_code(self, value):
        return value.strip().upper()

    def validate_search(self, value):
        value = value.strip()
        if any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Từ khóa tìm kiếm không hợp lệ.")
        return value


class StudentListItemSerializer(serializers.Serializer):
    student_id = serializers.CharField()
    slug = serializers.CharField()
    site_code = serializers.CharField()
    full_name = serializers.CharField()
    phone = serializers.CharField(allow_null=True)
    email = serializers.EmailField(allow_null=True)
    status = serializers.CharField()
    account_issued = serializers.BooleanField()


class StudentListResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = StudentListItemSerializer(many=True)


class StudentAccountProvisionResponseSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    student_id = serializers.CharField()
    slug = serializers.CharField()
    site_code = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=("hoc_vien",))
    account_status = serializers.ChoiceField(choices=("active",))
    must_change_password = serializers.BooleanField()
    email_sent = serializers.BooleanField()


class StudentDeleteResponseSerializer(serializers.Serializer):
    slug = serializers.CharField()
    site_code = serializers.CharField()
    deleted = serializers.BooleanField()
    deleted_site_count = serializers.IntegerField(min_value=1)
    account_deleted = serializers.BooleanField()


class StudentProfileSerializer(serializers.Serializer):
    student_id = serializers.CharField()
    slug = serializers.CharField()
    site_code = serializers.CharField()
    full_name = serializers.CharField()
    birth_date = serializers.DateField(allow_null=True)
    gender = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    email = serializers.EmailField(allow_null=True)
    address = serializers.CharField(allow_null=True)
    enrolled_on = serializers.DateField()
    status = serializers.CharField()


class StudentProfileUpdateSerializer(StrictInputSerializer):
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)
    allowed_fields = {"phone", "address"}

    def validate_phone(self, value):
        value = value.strip() if value else ""
        if value and (len(value) < 6 or any(char not in "+0123456789(). -" for char in value)):
            raise serializers.ValidationError("Số điện thoại không hợp lệ.")
        return value or None

    def validate_address(self, value):
        value = value.strip() if value else ""
        if any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Địa chỉ không hợp lệ.")
        return value or None

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Cần cung cấp ít nhất một trường để cập nhật.")
        return attrs


class StudentEnrollmentItemSerializer(serializers.Serializer):
    enrollment_id = serializers.CharField()
    enrolled_at = serializers.DateTimeField()
    enrollment_status = serializers.CharField()
    class_id = serializers.CharField()
    class_name = serializers.CharField()
    course_id = serializers.CharField()
    course_name = serializers.CharField()
    subject_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(allow_null=True)
    schedule = serializers.CharField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    class_status = serializers.CharField()


class StudentEnrollmentListResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    results = StudentEnrollmentItemSerializer(many=True)


class StudentScheduleItemSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    class_id = serializers.CharField()
    class_name = serializers.CharField()
    session_number = serializers.IntegerField()
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    room_name = serializers.CharField()
    teacher_name = serializers.CharField()
    status = serializers.CharField()


class StudentScheduleResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    results = StudentScheduleItemSerializer(many=True)


class StudentPaymentItemSerializer(serializers.Serializer):
    receipt_id = serializers.CharField()
    type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=0)
    method = serializers.CharField()
    paid_at = serializers.DateTimeField()


class StudentInstallmentItemSerializer(serializers.Serializer):
    installment_id = serializers.CharField()
    sequence = serializers.IntegerField(min_value=1)
    due_date = serializers.DateField()
    amount_due = serializers.DecimalField(max_digits=18, decimal_places=0)
    amount_paid = serializers.DecimalField(max_digits=18, decimal_places=0)
    balance = serializers.DecimalField(max_digits=18, decimal_places=0)
    status = serializers.ChoiceField(choices=("chua_dong", "dong_mot_phan", "da_dong", "qua_han"))


class StudentTuitionItemSerializer(serializers.Serializer):
    tuition_id = serializers.CharField()
    enrollment_id = serializers.CharField()
    course_name = serializers.CharField()
    amount_due = serializers.DecimalField(max_digits=18, decimal_places=0)
    discount = serializers.DecimalField(max_digits=18, decimal_places=0)
    amount_paid = serializers.DecimalField(max_digits=18, decimal_places=0)
    balance = serializers.DecimalField(max_digits=18, decimal_places=0)
    status = serializers.CharField()
    receipts = StudentPaymentItemSerializer(many=True)
    installments = StudentInstallmentItemSerializer(many=True)


class StudentTuitionResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    results = StudentTuitionItemSerializer(many=True)


class StudentGradeItemSerializer(serializers.Serializer):
    grade_id = serializers.CharField()
    enrollment_id = serializers.CharField()
    class_name = serializers.CharField()
    course_name = serializers.CharField()
    grade_type = serializers.CharField()
    score = serializers.DecimalField(max_digits=4, decimal_places=2)
    entered_at = serializers.DateTimeField()


class StudentGradesResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    count = serializers.IntegerField()
    results = StudentGradeItemSerializer(many=True)
