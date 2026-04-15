from rest_framework import serializers


class SubscriberCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    stripe_customer_id = serializers.CharField()
    email = serializers.EmailField()
    status = serializers.CharField()
    decline_code = serializers.CharField(allow_null=True)
    decline_reason = serializers.CharField(allow_null=True)
    amount_cents = serializers.IntegerField(allow_null=True)
    needs_attention = serializers.BooleanField()
    excluded_from_automation = serializers.BooleanField()
