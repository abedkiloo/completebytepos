from rest_framework import serializers
from .models import Sale, SaleItem, Invoice, InvoiceItem, Payment, Customer, PaymentPlan, PaymentReminder
from products.serializers import ProductSerializer


class CustomerSerializer(serializers.ModelSerializer):
    total_invoices = serializers.IntegerField(read_only=True)
    total_outstanding = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    wallet_balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = Customer
        fields = [
            'id', 'customer_code', 'name', 'customer_type',
            'email', 'phone', 'address', 'city', 'country',
            'tax_id', 'notes', 'is_active',
            'total_invoices', 'total_outstanding', 'wallet_balance',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['customer_code', 'total_invoices', 'total_outstanding', 'wallet_balance', 'created_at', 'updated_at']


class CustomerListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for customer lists"""
    total_outstanding = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Customer
        fields = [
            'id', 'customer_code', 'name', 'customer_type',
            'email', 'phone', 'city', 'country',
            'is_active', 'total_outstanding'
        ]


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    variant_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    size_name = serializers.CharField(source='size.name', read_only=True)
    color_name = serializers.CharField(source='color.name', read_only=True)
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    
    class Meta:
        model = SaleItem
        fields = [
            'id', 'product_id', 'product', 'product_name', 'product_sku',
            'variant', 'variant_id', 'variant_sku',
            'size', 'size_name', 'color', 'color_name',
            'quantity', 'unit_price', 'subtotal', 'created_at'
        ]
        read_only_fields = ['subtotal', 'created_at']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source='cashier.username', read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Sale
        fields = [
            'id', 'sale_number', 'sale_type', 'cashier', 'cashier_name',
            'subtotal', 'tax_amount', 'discount_amount', 'total',
            'payment_method', 'amount_paid', 'change', 'notes',
            'items', 'item_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['sale_number', 'created_at', 'updated_at']
    
    def get_item_count(self, obj):
        """Get total number of items in sale"""
        return obj.item_count


class SaleCreateSerializer(serializers.Serializer):
    """Serializer for creating a sale with items"""
    items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True
    )
    sale_type = serializers.ChoiceField(choices=Sale.SALE_TYPES, default='pos')
    payment_method = serializers.ChoiceField(choices=Sale.PAYMENT_METHODS, default='cash')
    amount_paid = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False, 
        allow_null=True,
        default=0,
        help_text='Amount paid. Can be null/0 for installments, required for pay_now'
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0, required=False)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0, required=False)
    branch_id = serializers.IntegerField(required=False, allow_null=True, help_text='Branch ID (optional, uses current branch if not provided)')
    # For normal sales, invoice is always created
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True)
    customer_address = serializers.CharField(required=False, allow_blank=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    # Payment plan fields (for installments)
    create_payment_plan = serializers.BooleanField(default=False, required=False)
    number_of_installments = serializers.IntegerField(
        required=False, 
        allow_null=True, 
        min_value=1,
        default=None,
        help_text='Number of installments. Can be null if not using installments.'
    )
    # Use CharField with choices validation instead of ChoiceField to better handle null
    installment_frequency = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
        help_text='Payment frequency for installments. Can be null if not using installments.'
    )
    
    def validate_installment_frequency(self, value):
        """Validate installment_frequency against choices if provided"""
        if value is None or value == '':
            return None
        # Validate against PaymentPlan.FREQUENCY_CHOICES
        valid_choices = [choice[0] for choice in PaymentPlan.FREQUENCY_CHOICES]
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"Invalid choice. Must be one of: {', '.join(valid_choices)}"
            )
        return value
    
    payment_plan_start_date = serializers.DateField(
        required=False, 
        allow_null=True,
        default=None,
        help_text='Payment plan start date. Can be null if not using installments.'
    )
    # Wallet fields
    use_wallet = serializers.BooleanField(
        default=False,
        required=False,
        help_text='Whether to use customer wallet balance for payment'
    )
    wallet_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        default=0,
        help_text='Amount to use from wallet (0 = use all available)'
    )
    
    def validate(self, attrs):
        """Validate payment based on sale type and payment plan"""
        sale_type = attrs.get('sale_type', 'pos')
        amount_paid = attrs.get('amount_paid', 0) or 0
        create_payment_plan = attrs.get('create_payment_plan', False)
        payment_method = attrs.get('payment_method', 'cash')
        customer_id = attrs.get('customer_id', None)
        installment_frequency = attrs.get('installment_frequency', None)
        number_of_installments = attrs.get('number_of_installments', None)
        payment_plan_start_date = attrs.get('payment_plan_start_date', None)
        
        # For POS sales, amount_paid is required
        if sale_type == 'pos':
            if amount_paid is None or amount_paid <= 0:
                raise serializers.ValidationError({
                    'amount_paid': 'Amount paid is required for POS sales'
                })
        
        # For normal sales with cash payment (pay_now), amount_paid should be provided
        # For installments, amount_paid can be 0 or null
        if sale_type == 'normal' and not create_payment_plan:
            # This is a pay_now normal sale - amount_paid should be provided
            if amount_paid is None or amount_paid <= 0:
                raise serializers.ValidationError({
                    'amount_paid': 'Amount paid is required for pay now sales'
                })
        
        # If not creating payment plan, explicitly set payment plan fields to None
        # This ensures they are null and won't cause validation errors
        if not create_payment_plan:
            # Explicitly set to None to avoid any validation issues
            # This is critical - we must set these to None when not using installments
            attrs['installment_frequency'] = None
            attrs['number_of_installments'] = None
            attrs['payment_plan_start_date'] = None
        else:
            # If creating payment plan, validate required fields
            if installment_frequency is None or installment_frequency == '':
                raise serializers.ValidationError({
                    'installment_frequency': 'Installment frequency is required when creating a payment plan'
                })
            if number_of_installments is None or number_of_installments < 1:
                raise serializers.ValidationError({
                    'number_of_installments': 'Number of installments must be at least 1 when creating a payment plan'
                })
            if payment_plan_start_date is None:
                raise serializers.ValidationError({
                    'payment_plan_start_date': 'Payment plan start date is required when creating a payment plan'
                })
        
        # For cash payments, customer can be optional
        # For installments, customer should ideally be provided but we allow flexibility
        if sale_type == 'normal' and create_payment_plan and not customer_id:
            # Warn but don't fail - allow installments without customer for walk-in sales
            pass
        
        return attrs


class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_detail = ProductSerializer(source='product', read_only=True)
    variant_id = serializers.IntegerField(source='variant.id', read_only=True)
    size_name = serializers.CharField(source='size.name', read_only=True)
    color_name = serializers.CharField(source='color.name', read_only=True)
    
    class Meta:
        model = InvoiceItem
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'product_detail',
            'variant', 'variant_id', 'size', 'size_name', 'color', 'color_name',
            'quantity', 'unit_price', 'subtotal', 'description', 'created_at'
        ]
        read_only_fields = ['subtotal', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.username', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'amount', 'payment_method', 'payment_date',
            'reference', 'notes', 'recorded_by', 'recorded_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    sale_number = serializers.CharField(source='sale.sale_number', read_only=True)
    customer_detail = CustomerSerializer(source='customer', read_only=True)
    payment_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_fully_paid = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'sale', 'sale_number',
            'customer', 'customer_detail',
            'customer_name', 'customer_email', 'customer_phone', 'customer_address',
            'subtotal', 'tax_amount', 'discount_amount', 'total',
            'amount_paid', 'balance', 'status',
            'due_date', 'issued_date', 'notes',
            'created_by', 'created_by_name',
            'items', 'payments',
            'payment_percentage', 'is_fully_paid', 'is_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['invoice_number', 'balance', 'payment_percentage', 'is_fully_paid', 'is_overdue', 'created_at', 'updated_at']


class InvoiceCreateSerializer(serializers.Serializer):
    """Serializer for creating an invoice from a sale or manually"""
    sale_id = serializers.IntegerField(required=False, allow_null=True)
    branch_id = serializers.IntegerField(required=False, allow_null=True, help_text='Branch ID (optional, uses current branch if not provided)')
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True)
    customer_address = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0, required=False)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0, required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating a payment against an invoice"""
    invoice_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHODS, default='cash')
    payment_date = serializers.DateField()
    reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class PaymentPlanSerializer(serializers.ModelSerializer):
    """Serializer for payment plans"""
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    invoice_total = serializers.DecimalField(source='invoice.total', max_digits=10, decimal_places=2, read_only=True)
    invoice_balance = serializers.DecimalField(source='invoice.balance', max_digits=10, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    remaining_installments = serializers.IntegerField(read_only=True)
    is_complete = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PaymentPlan
        fields = [
            'id', 'invoice', 'invoice_number', 'invoice_total', 'invoice_balance',
            'total_amount', 'number_of_installments', 'installment_amount',
            'frequency', 'start_date', 'next_payment_date', 'last_payment_date',
            'completed_installments', 'remaining_installments', 'is_active',
            'is_complete', 'notes', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['next_payment_date', 'completed_installments', 'remaining_installments', 'is_complete', 'created_at', 'updated_at']


class PaymentReminderSerializer(serializers.ModelSerializer):
    """Serializer for payment reminders"""
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    customer_name = serializers.CharField(source='invoice.customer_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PaymentReminder
        fields = [
            'id', 'invoice', 'invoice_number', 'customer_name',
            'payment_plan', 'reminder_type', 'reminder_date', 'due_date',
            'amount_due', 'status', 'message', 'sent_at',
            'is_overdue', 'days_until_due',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['is_overdue', 'days_until_due', 'sent_at', 'created_at', 'updated_at']

