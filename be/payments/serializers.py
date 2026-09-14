from rest_framework import serializers

from sales.models import Customer

from .models import PaymentIntent
from . import services


class PaymentIntentSerializer(serializers.ModelSerializer):
    customer_id = serializers.SerializerMethodField()
    sms_sent = serializers.SerializerMethodField()
    invoice_link_token = serializers.CharField(source='public_token', read_only=True)

    class Meta:
        model = PaymentIntent
        fields = (
            'id', 'client_uuid', 'amount', 'phone', 'status', 'purpose',
            'customer_id', 'customer_name', 'invoice_number',
            'invoice_link_token', 'checkout_request_id', 'mpesa_receipt',
            'failure_reason', 'sms_queued', 'sms_sent',
            'created_at', 'prompted_at', 'paid_at',
        )
        read_only_fields = fields

    def get_customer_id(self, obj):
        return obj.customer_id

    def get_sms_sent(self, obj):
        return obj.messages.filter(status='sent').exists()


class CreateIntentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    phone = serializers.CharField(max_length=20)
    purpose = serializers.ChoiceField(
        choices=[c[0] for c in PaymentIntent.PURPOSE_CHOICES],
        required=False,
        default=PaymentIntent.PURPOSE_OTHER,
    )
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True, default='')
    client_uuid = serializers.UUIDField(required=False, allow_null=True)

    def create(self, validated_data):
        request = self.context['request']
        customer = None
        cid = validated_data.get('customer_id')
        if cid:
            try:
                customer = Customer.objects.get(pk=cid)
            except Customer.DoesNotExist as exc:
                raise serializers.ValidationError({
                    'customer_id': 'Customer not found.',
                }) from exc
        return services.create_intent(
            amount=validated_data['amount'],
            phone=validated_data['phone'],
            purpose=validated_data.get('purpose') or PaymentIntent.PURPOSE_OTHER,
            customer=customer,
            customer_name=validated_data.get('customer_name') or '',
            created_by=request.user if request.user.is_authenticated else None,
            client_uuid=validated_data.get('client_uuid'),
        )


class PublicInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentIntent
        fields = (
            'invoice_number', 'amount', 'status', 'customer_name',
            'paid_at', 'mpesa_receipt',
        )
