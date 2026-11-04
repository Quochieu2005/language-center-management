"""Request and response schemas for student SePay tuition payments."""

from rest_framework import serializers

from core.academics.serializers import StrictSerializer


class StudentSePayPaymentCreateSerializer(StrictSerializer):
    installment_id = serializers.RegexField(r"^[A-Za-z0-9_-]{1,24}$", max_length=24)
    amount = serializers.IntegerField(min_value=1, max_value=999999999999999999)
    allowed_fields = {"installment_id", "amount"}


class StudentSePayPaymentResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    attempt_id = serializers.CharField()
    installment_id = serializers.CharField()
    amount = serializers.IntegerField(min_value=1)
    payment_code = serializers.CharField()
    bank_code = serializers.CharField()
    bank_account = serializers.CharField()
    qr_url = serializers.URLField()
    status = serializers.ChoiceField(
        choices=("cho_thanh_toan", "da_thanh_toan", "het_han", "can_doi_soat", "da_huy")
    )
    expires_at = serializers.DateTimeField()


class SePayWebhookAckSerializer(serializers.Serializer):
    success = serializers.BooleanField()
