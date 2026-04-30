from rest_framework import serializers


class DeclineBreakdownEntrySerializer(serializers.Serializer):
    decline_code = serializers.CharField()
    human_label = serializers.CharField()
    subscriber_count = serializers.IntegerField()
    total_amount_cents = serializers.IntegerField()
    recovery_action = serializers.CharField()


class AttentionItemSerializer(serializers.Serializer):
    type = serializers.CharField()
    subscriber_id = serializers.IntegerField()
    subscriber_name = serializers.CharField()
    label = serializers.CharField()


class DashboardSummarySerializer(serializers.Serializer):
    total_failures = serializers.IntegerField()
    total_subscribers = serializers.IntegerField()
    estimated_recoverable_cents = serializers.IntegerField()
    recovered_this_month_cents = serializers.IntegerField()
    recovered_count = serializers.IntegerField()
    recovery_rate = serializers.FloatField()
    net_benefit_cents = serializers.IntegerField()
    decline_breakdown = DeclineBreakdownEntrySerializer(many=True)
    pending_action_count = serializers.IntegerField()
    attention_items = AttentionItemSerializer(many=True)


class FailedPaymentRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subscriber_id = serializers.IntegerField()
    subscriber_email = serializers.CharField(allow_blank=True, allow_null=True)
    subscriber_stripe_customer_id = serializers.CharField(allow_blank=True)
    subscriber_status = serializers.CharField()
    decline_code = serializers.CharField(allow_blank=True)
    decline_reason = serializers.CharField()
    amount_cents = serializers.IntegerField()
    failure_created_at = serializers.DateTimeField()
    recommended_email_type = serializers.CharField(allow_null=True)
    last_email_sent_at = serializers.DateTimeField(allow_null=True)
    payment_method_country = serializers.CharField(allow_null=True, allow_blank=True)
    excluded_from_automation = serializers.BooleanField()
