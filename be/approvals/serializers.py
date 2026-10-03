from rest_framework import serializers

from approvals.models import PendingChange


class PendingChangeSerializer(serializers.ModelSerializer):
    made_by_username = serializers.CharField(source='made_by.username', read_only=True)
    checked_by_username = serializers.CharField(
        source='checked_by.username',
        read_only=True,
        allow_null=True,
    )
    business_date = serializers.SerializerMethodField()
    past_dated = serializers.SerializerMethodField()

    def get_business_date(self, obj):
        from approvals.permissions import change_business_dates, earliest_business_day

        day = earliest_business_day(*change_business_dates(obj))
        return day.isoformat() if day else None

    def get_past_dated(self, obj):
        from approvals.permissions import change_is_past_dated

        return obj.status == PendingChange.STATUS_PENDING and change_is_past_dated(obj)

    class Meta:
        model = PendingChange
        fields = [
            'id',
            'action_type',
            'entity_type',
            'entity_id',
            'entity_repr',
            'original_values',
            'proposed_values',
            'reason',
            'status',
            'batch_id',
            'made_by',
            'made_by_username',
            'made_at',
            'checked_by',
            'checked_by_username',
            'checked_at',
            'rejection_reason',
            'apply_payload',
            'business_date',
            'past_dated',
        ]
        read_only_fields = fields


class SubmitProductChangeSerializer(serializers.Serializer):
    reason = serializers.CharField()


class ApproveChangeSerializer(serializers.Serializer):
    extreme_price_confirmed = serializers.BooleanField(required=False, default=False)


class RejectChangeSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField()


class ResubmitChangeSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')
