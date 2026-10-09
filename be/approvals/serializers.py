from rest_framework import serializers

from approvals.models import PendingChange


class PendingChangeListSerializer(serializers.ListSerializer):
    """Batch-hydrate approval details once for the whole page (no N+1)."""

    def to_representation(self, data):
        from approvals.details_cache import build_details_cache

        changes = list(data)
        self.child.context['details_cache'] = build_details_cache(changes)
        return super().to_representation(changes)


class PendingChangeSerializer(serializers.ModelSerializer):
    made_by_username = serializers.CharField(source='made_by.username', read_only=True)
    checked_by_username = serializers.CharField(
        source='checked_by.username',
        read_only=True,
        allow_null=True,
    )
    business_date = serializers.SerializerMethodField()
    past_dated = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()

    def _details_cache(self):
        return self.context.get('details_cache')

    def _sales_by_id(self):
        cache = self._details_cache()
        return cache.sales if cache is not None else None

    def get_details(self, obj):
        import logging

        from approvals.details import pending_change_details

        try:
            return pending_change_details(obj, cache=self._details_cache())
        except Exception:
            logging.getLogger(__name__).exception(
                'Could not build approval details for change %s', obj.pk,
            )
            return None

    def get_business_date(self, obj):
        from approvals.permissions import change_business_dates, earliest_business_day

        day = earliest_business_day(
            *change_business_dates(obj, sales_by_id=self._sales_by_id())
        )
        return day.isoformat() if day else None

    def get_past_dated(self, obj):
        from approvals.permissions import change_is_past_dated

        return obj.status == PendingChange.STATUS_PENDING and change_is_past_dated(
            obj, sales_by_id=self._sales_by_id(),
        )

    class Meta:
        model = PendingChange
        list_serializer_class = PendingChangeListSerializer
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
            'details',
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
