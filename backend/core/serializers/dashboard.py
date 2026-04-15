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
