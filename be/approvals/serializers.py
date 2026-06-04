from rest_framework import serializers

from approvals.models import PendingChange


class PendingChangeSerializer(serializers.ModelSerializer):
    made_by_username = serializers.CharField(source='made_by.username', read_only=True)
    checked_by_username = serializers.CharField(
        source='checked_by.username',
        read_only=True,
        allow_null=True,
    )

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
        ]
        read_only_fields = fields


class SubmitProductChangeSerializer(serializers.Serializer):
    reason = serializers.CharField()


class ApproveChangeSerializer(serializers.Serializer):
    extreme_price_confirmed = serializers.BooleanField(required=False, default=False)


class RejectChangeSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField()
