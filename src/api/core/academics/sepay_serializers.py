"""Request and response schemas for student SePay Payment Gateway tuition payments."""

from rest_framework import serializers

from core.academics.serializers import StrictSerializer


class StudentSePayPaymentCreateSerializer(StrictSerializer):
    # The server computes the amount from this choice; the client never sends a price.
    option = serializers.ChoiceField(choices=("next_installment", "half", "full"))
    allowed_fields = {"option"}


class SePayCheckoutSerializer(serializers.Serializer):
    action = serializers.URLField()
    method = serializers.CharField()
    fields = serializers.DictField(child=serializers.CharField())


class StudentSePayPaymentResponseSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    attempt_id = serializers.CharField()
    tuition_id = serializers.CharField()
    installment_id = serializers.CharField()
    amount = serializers.IntegerField(min_value=1)
    payment_code = serializers.CharField()
    status = serializers.ChoiceField(
        choices=("cho_thanh_toan", "da_thanh_toan", "het_han", "can_doi_soat", "da_huy")
    )
    expires_at = serializers.DateTimeField()
    checkout = SePayCheckoutSerializer(allow_null=True)
    option = serializers.CharField(required=False)


class SePayWebhookAckSerializer(serializers.Serializer):
    success = serializers.BooleanField()
