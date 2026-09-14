from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import serializers

from products.models import Product

from .models import FieldOrder, FieldOrderLine
from .order_services import (
    FieldOrderTransitionError,
    assign_delivery_agent,
    pack_order,
    submit_order,
)
from .push import get_push_notifier
from .serializers import CustomerSiteSerializer, SiteMediaSerializer


class FieldOrderLineSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    product_id = serializers.IntegerField(source='product.id', read_only=True)

    class Meta:
        model = FieldOrderLine
        fields = (
            'id', 'product_id', 'product_name', 'quantity',
            'unit_price', 'line_total',
        )
        read_only_fields = fields


class FieldOrderLineWriteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )


class FieldOrderSerializer(serializers.ModelSerializer):
    lines = FieldOrderLineSerializer(many=True, read_only=True)
    site_detail = CustomerSiteSerializer(source='site', read_only=True)
    site_media = serializers.SerializerMethodField()
    customer_name = serializers.CharField(
        source='customer.name', read_only=True, default=None,
    )
    assigned_delivery_agent_id = serializers.IntegerField(
        read_only=True, allow_null=True,
    )

    class Meta:
        model = FieldOrder
        fields = (
            'id', 'site', 'site_detail', 'site_media', 'customer', 'customer_name',
            'status', 'notes', 'client_uuid', 'lines',
            'assigned_delivery_agent_id', 'stock_allocated',
            'packed_at', 'assigned_at', 'created_by',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'status', 'stock_allocated', 'packed_at', 'assigned_at',
            'created_by', 'created_at', 'updated_at', 'site_detail',
            'site_media', 'customer_name', 'assigned_delivery_agent_id', 'lines',
        )

    def get_site_media(self, obj):
        media = obj.site.media.all() if obj.site_id else []
        return SiteMediaSerializer(media, many=True, context=self.context).data


class FieldOrderCreateSerializer(serializers.Serializer):
    site_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    lines = FieldOrderLineWriteSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError('At least one line is required.')
        return value

    def create(self, validated_data):
        from .models import CustomerSite

        request = self.context['request']
        try:
            site = CustomerSite.objects.select_related('customer').get(
                pk=validated_data['site_id'],
            )
        except CustomerSite.DoesNotExist:
            raise serializers.ValidationError({'site_id': 'Site not found.'})

        lines_data = validated_data['lines']
        order = FieldOrder.objects.create(
            site=site,
            customer=site.customer,
            notes=validated_data.get('notes') or '',
            client_uuid=validated_data.get('client_uuid'),
            created_by=request.user if request.user.is_authenticated else None,
        )
        for row in lines_data:
            try:
                product = Product.objects.get(pk=row['product_id'])
            except Product.DoesNotExist:
                order.delete()
                raise serializers.ValidationError({
                    'lines': f"Product {row['product_id']} not found.",
                })
            unit_price = row.get('unit_price')
            if unit_price is None:
                unit_price = product.selling_price
            FieldOrderLine.objects.create(
                order=order,
                product=product,
                quantity=row['quantity'],
                unit_price=unit_price,
                product_name=product.name,
            )
        return order


class FieldOrderSubmitSerializer(serializers.Serializer):
    def save(self, **kwargs):
        order = self.context['order']
        try:
            order = submit_order(order)
        except FieldOrderTransitionError:
            raise
        get_push_notifier().notify(
            user_id=None,
            title='Field order submitted',
            body=f'Order #{order.id} awaiting pack',
            data={'field_order_id': order.id, 'event': 'submitted'},
        )
        return order


class PackOrderSerializer(serializers.Serializer):
    def save(self, **kwargs):
        order = self.context['order']
        order = pack_order(order)
        get_push_notifier().notify(
            user_id=order.created_by_id,
            title='Order packed',
            body=f'Order #{order.id} is ready',
            data={'field_order_id': order.id, 'event': 'packed'},
        )
        return order


class AssignOrderSerializer(serializers.Serializer):
    delivery_agent_id = serializers.IntegerField()

    def validate_delivery_agent_id(self, value):
        try:
            return User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('Delivery agent not found.')

    def save(self, **kwargs):
        order = self.context['order']
        agent = self.validated_data['delivery_agent_id']
        try:
            order = assign_delivery_agent(order, agent)
        except FieldOrderTransitionError:
            raise
        get_push_notifier().notify(
            user_id=agent.id,
            title='Delivery assigned',
            body=f'Order #{order.id} assigned to you',
            data={'field_order_id': order.id, 'event': 'assigned'},
        )
        return order
