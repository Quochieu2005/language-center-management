"""Strict request and response serializers for academic workflows."""

import re

from rest_framework import serializers


_SITE = r"^[A-Za-z0-9_-]{1,10}$"
_RECORD = r"^[A-Za-z0-9_-]{1,24}$"
_SLUG = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$"
_KEY = r"^[A-Za-z0-9_-]{8,24}$"


class StrictSerializer(serializers.Serializer):
    allowed_fields: set[str] = set()

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) - self.allowed_fields:
            raise serializers.ValidationError({"detail": "Yêu cầu chứa trường không được phép."})
        return super().to_internal_value(data)


class SiteQuerySerializer(StrictSerializer):
    site_code = serializers.RegexField(regex=_SITE, max_length=10, required=False)
    allowed_fields = {"site_code"}

    def validate_site_code(self, value):
        return value.strip().upper()


class PaginationQuerySerializer(SiteQuerySerializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)
    offset = serializers.IntegerField(min_value=0, max_value=100000, required=False, default=0)
    allowed_fields = {"site_code", "limit", "offset"}


class AttendanceItemSerializer(StrictSerializer):
    enrollment_id = serializers.RegexField(regex=_RECORD, max_length=24)
    status = serializers.ChoiceField(
        choices=("co_mat", "tre", "vang_co_phep", "vang_khong_phep")
    )
    note = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    allowed_fields = {"enrollment_id", "status", "note"}

    def validate_note(self, value):
        if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
            raise serializers.ValidationError("Ghi chú chứa ký tự điều khiển không hợp lệ.")
        return value.strip() or None


class AttendanceBatchSerializer(StrictSerializer):
    items = AttendanceItemSerializer(many=True, allow_empty=False)
    allowed_fields = {"items"}

    def validate_items(self, items):
        ids = [item["enrollment_id"] for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Không được gửi trùng đăng ký trong một buổi học.")
        if len(items) > 300:
            raise serializers.ValidationError("Mỗi lần lưu tối đa 300 học viên.")
        return items


class GradeWriteSerializer(StrictSerializer):
    score = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10)
    allowed_fields = {"score"}


class TuitionQuerySerializer(PaginationQuerySerializer):
    status = serializers.ChoiceField(
        choices=("chua_dong", "dong_mot_phan", "da_dong", "hoan_tien"), required=False
    )
    student_slug = serializers.RegexField(regex=_SLUG, max_length=160, required=False)
    allowed_fields = {"site_code", "limit", "offset", "status", "student_slug"}


class TuitionReceiptSerializer(StrictSerializer):
    idempotency_key = serializers.RegexField(regex=_KEY, max_length=24)
    amount = serializers.IntegerField(min_value=1, max_value=999999999999999999)
    payment_method = serializers.ChoiceField(choices=("tien_mat", "chuyen_khoan", "the"))
    note = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    allowed_fields = {"idempotency_key", "amount", "payment_method", "note"}

    def validate_note(self, value):
        if re.search(r"(?:\d[ -]?){13,19}", value):
            raise serializers.ValidationError("Không nhập dữ liệu thẻ hoặc thông tin thanh toán nhạy cảm vào ghi chú.")
        if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
            raise serializers.ValidationError("Ghi chú chứa ký tự điều khiển không hợp lệ.")
        return value.strip() or None


class TransferRequestSerializer(StrictSerializer):
    student_slug = serializers.RegexField(regex=_SLUG, max_length=160)
    target_site = serializers.RegexField(regex=_SITE, max_length=10)
    reason = serializers.CharField(max_length=500, trim_whitespace=True)
    allowed_fields = {"student_slug", "target_site", "reason"}

    def validate_target_site(self, value):
        return value.strip().upper()

    def validate_reason(self, value):
        if not value or any(ord(char) < 32 and char not in "\t\n\r" for char in value):
            raise serializers.ValidationError("Lý do chuyển cơ sở không hợp lệ.")
        return value.strip()


class TransferListQuerySerializer(PaginationQuerySerializer):
    status = serializers.ChoiceField(
        choices=("cho_duyet", "dang_xu_ly", "tu_choi", "hoan_tat", "that_bai"), required=False
    )
    allowed_fields = {"site_code", "limit", "offset", "status"}


class TransferDecisionSerializer(StrictSerializer):
    decision = serializers.ChoiceField(choices=("approve", "reject"))
    reason = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    allowed_fields = {"decision", "reason"}

    def validate(self, attrs):
        reason = attrs["reason"].strip()
        if attrs["decision"] == "reject" and not reason:
            raise serializers.ValidationError({"reason": "Cần nêu lý do từ chối."})
        attrs["reason"] = reason or None
        return attrs


class TransferScopeSerializer(StrictSerializer):
    source_site = serializers.RegexField(regex=_SITE, max_length=10)
    allowed_fields = {"source_site"}

    def validate_source_site(self, value):
        return value.strip().upper()


class StudentReportQuerySerializer(SiteQuerySerializer):
    allowed_fields = {"site_code"}
