from decimal import Decimal

from rest_framework import serializers

from .models import (
    DeliveryLineResult,
    DeliveryRoute,
    DeliveryStop,
    ProofOfDelivery,
)
from . import services


class DeliveryLineResultSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)

    class Meta:
        model = DeliveryLineResult
        fields = (
            'id', 'product_id', 'product_name', 'ordered_quantity',
            'delivered_quantity', 'returned_quantity', 'stock_applied',
        )


class ProofOfDeliverySerializer(serializers.ModelSerializer):
    signature_url = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    is_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProofOfDelivery
        fields = (
            'id', 'notes', 'latitude', 'longitude', 'captured_at',
            'signature_url', 'photo_url', 'is_complete',
        )

    def _abs(self, f):
        if not f:
            return None
        request = self.context.get('request')
        url = f.url
        return request.build_absolute_uri(url) if request else url

    def get_signature_url(self, obj):
        return self._abs(obj.signature_image)

    def get_photo_url(self, obj):
        return self._abs(obj.photo)


class DeliveryStopSerializer(serializers.ModelSerializer):
    lines = DeliveryLineResultSerializer(source='line_results', many=True, read_only=True)
    pod = ProofOfDeliverySerializer(read_only=True)
    site = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    next_stop_id = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryStop
        fields = (
            'id', 'sequence', 'status', 'field_order_id',
            'arrived_at', 'completed_at',
            'collection_method', 'collection_amount', 'collection_notes',
            'site', 'customer_name', 'customer_phone',
            'lines', 'pod', 'next_stop_id',
        )

    def get_site(self, obj):
        site = obj.field_order.site
        request = self.context.get('request')
        media = []
        for m in site.media.all():
            url = m.image.url if m.image else None
            if url and request:
                url = request.build_absolute_uri(url)
            media.append({'id': m.id, 'image_url': url, 'caption': m.caption})
        customer = site.customer or obj.field_order.customer
        return {
            'id': site.id,
            'label': site.label,
            'latitude': str(site.latitude) if site.latitude is not None else None,
            'longitude': str(site.longitude) if site.longitude is not None else None,
            'accuracy': site.accuracy,
            'landmark': site.landmark,
            'customer_id': customer.id if customer else None,
            'customer_name': customer.name if customer else None,
            'media': media,
        }

    def get_customer_name(self, obj):
        c = obj.field_order.customer or obj.field_order.site.customer
        return c.name if c else None

    def get_customer_phone(self, obj):
        c = obj.field_order.customer or obj.field_order.site.customer
        return getattr(c, 'phone', None) if c else None

    def get_next_stop_id(self, obj):
        nxt = services.next_open_stop(obj.route)
        if nxt and nxt.pk == obj.pk:
            # After current is still open, find the subsequent open stop.
            nxt = (
                obj.route.stops.exclude(
                    status__in=(
                        DeliveryStop.STATUS_COMPLETED,
                        DeliveryStop.STATUS_FAILED,
                    ),
                )
                .exclude(pk=obj.pk)
                .order_by('sequence', 'id')
                .first()
            )
        return nxt.pk if nxt else None


def _agent_display_name(agent) -> str:
    if agent is None:
        return ''
    full = agent.get_full_name()
    return full or agent.username or ''


class DeliveryRouteListSerializer(serializers.ModelSerializer):
    delivery_agent_name = serializers.SerializerMethodField()
    stop_count = serializers.IntegerField(read_only=True)
    completed_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DeliveryRoute
        fields = (
            'id',
            'route_date',
            'delivery_agent_id',
            'delivery_agent_name',
            'stop_count',
            'completed_count',
        )

    def get_delivery_agent_name(self, obj):
        return _agent_display_name(obj.delivery_agent)


class DeliveryRouteSerializer(serializers.ModelSerializer):
    stops = DeliveryStopSerializer(many=True, read_only=True)
    next_stop_id = serializers.SerializerMethodField()
    delivery_agent_name = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryRoute
        fields = (
            'id',
            'route_date',
            'delivery_agent_id',
            'delivery_agent_name',
            'stops',
            'next_stop_id',
        )

    def get_next_stop_id(self, obj):
        nxt = services.next_open_stop(obj)
        return nxt.pk if nxt else None

    def get_delivery_agent_name(self, obj):
        return _agent_display_name(obj.delivery_agent)


class LineUpdateItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    delivered_quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    returned_quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, required=False, default=Decimal('0'),
    )


class LinesUpdateSerializer(serializers.Serializer):
    lines = LineUpdateItemSerializer(many=True)

    def save(self, **kwargs):
        stop = self.context['stop']
        return services.update_line_results(stop, self.validated_data['lines'])


class CollectSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=['cash', 'debt', 'defer_stk'])
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def save(self, **kwargs):
        stop = self.context['stop']
        return services.collect_money(
            stop,
            method=self.validated_data['method'],
            amount=self.validated_data.get('amount'),
            notes=self.validated_data.get('notes') or '',
        )


class PodSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    signature = serializers.ImageField(required=False)
    photo = serializers.ImageField(required=False)
    signature_b64 = serializers.CharField(required=False, allow_blank=True)
    photo_b64 = serializers.CharField(required=False, allow_blank=True)

    def _file_from_b64(self, raw, name):
        if not raw:
            return None
        import base64
        from django.core.files.uploadedfile import SimpleUploadedFile
        try:
            data = base64.b64decode(raw)
        except Exception as exc:  # noqa: BLE001
            raise serializers.ValidationError({name: 'Invalid base64.'}) from exc
        return SimpleUploadedFile(name, data, content_type='image/png')

    def save(self, **kwargs):
        stop = self.context['stop']
        signature = self.validated_data.get('signature') or self._file_from_b64(
            self.validated_data.get('signature_b64'), 'sig.png',
        )
        photo = self.validated_data.get('photo') or self._file_from_b64(
            self.validated_data.get('photo_b64'), 'pod.png',
        )
        return services.save_pod(
            stop,
            signature_image=signature,
            photo=photo,
            notes=self.validated_data.get('notes') or '',
            latitude=self.validated_data['latitude'],
            longitude=self.validated_data['longitude'],
        )


class ProposePinSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    note = serializers.CharField(required=False, allow_blank=True, default='')

    def save(self, **kwargs):
        stop = self.context['stop']
        request = self.context.get('request')
        return services.propose_pin_correction(
            stop,
            latitude=self.validated_data['latitude'],
            longitude=self.validated_data['longitude'],
            note=self.validated_data.get('note') or '',
            user=getattr(request, 'user', None),
        )
