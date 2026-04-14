from rest_framework import serializers

from core.engine.labels import DECLINE_CODE_LABELS


class PendingActionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subscriber_name = serializers.SerializerMethodField()
    decline_reason = serializers.SerializerMethodField()
    recommended_action = serializers.CharField()
    amount_cents = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    failure_id = serializers.IntegerField(source="failure.id")
    subscriber_id = serializers.IntegerField(source="subscriber.id")

    def get_subscriber_name(self, obj):
        return obj.subscriber.email or obj.subscriber.stripe_customer_id

    def get_decline_reason(self, obj):
        code = obj.failure.decline_code
        return DECLINE_CODE_LABELS.get(code, DECLINE_CODE_LABELS["_default"])

    def get_amount_cents(self, obj):
        return obj.failure.amount_cents
