"""Request and response serializers for tuition installment schedules."""

from django.utils import timezone
from rest_framework import serializers

from core.academics.serializers import StrictSerializer
from core.academics.tuition_installments import ALLOWED_INSTALLMENT_COUNTS


class TuitionInstallmentPlanWriteSerializer(StrictSerializer):
    payment_mode = serializers.ChoiceField(choices=("full", "monthly"))
    installment_count = serializers.ChoiceField(choices=ALLOWED_INSTALLMENT_COUNTS, required=False)
    first_due_date = serializers.DateField()
    allowed_fields = {"payment_mode", "installment_count", "first_due_date"}

    def validate(self, attrs):
        if attrs["payment_mode"] == "full" and "installment_count" in attrs:
            raise serializers.ValidationError(
                {"installment_count": "Kế hoạch đóng một lần không nhận số kỳ."}
            )
        if attrs["payment_mode"] == "monthly" and "installment_count" not in attrs:
            raise serializers.ValidationError(
                {"installment_count": "Chọn 3, 6, 9 hoặc 12 tháng."}
            )
        if attrs["first_due_date"] < timezone.localdate():
            raise serializers.ValidationError(
                {"first_due_date": "Ngày đến hạn đầu tiên không được trước ngày hiện tại."}
            )
        return attrs


class TuitionInstallmentItemSerializer(serializers.Serializer):
    installment_id = serializers.CharField()
    sequence = serializers.IntegerField(min_value=1)
    due_date = serializers.DateField()
    amount_due = serializers.IntegerField(min_value=0)
    amount_paid = serializers.IntegerField(min_value=0)
    balance = serializers.IntegerField(min_value=0)
    status = serializers.ChoiceField(choices=("chua_dong", "dong_mot_phan", "da_dong", "qua_han"))


class TuitionInstallmentPlanResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    tuition_id = serializers.CharField()
    payment_mode = serializers.ChoiceField(choices=("full", "monthly"))
    installment_count = serializers.ChoiceField(choices=(1, *ALLOWED_INSTALLMENT_COUNTS))
    total_due = serializers.IntegerField(min_value=0)
    amount_paid = serializers.IntegerField(min_value=0)
    balance = serializers.IntegerField(min_value=0)
    installments = TuitionInstallmentItemSerializer(many=True)
