from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Sale, SaleItem, Invoice, InvoiceItem, Payment, Customer, PaymentPlan, PaymentReminder, CustomerWalletTransaction
from .serializers import (
    SaleSerializer, SaleCreateSerializer,
    InvoiceSerializer, InvoiceCreateSerializer,
    PaymentSerializer, PaymentCreateSerializer,
    CustomerSerializer, CustomerListSerializer
)
from products.models import Product, ProductVariant
from inventory.models import StockMovement
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
import logging

logger = logging.getLogger(__name__)


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().select_related('cashier').prefetch_related('items__product')
    serializer_class = SaleSerializer
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Sale.objects.all().select_related('cashier', 'branch').prefetch_related(
            'items__product', 'items__variant', 'items__size', 'items__color'
        )
        
        # Filter by branch only if branch support is enabled
        if is_branch_support_enabled():
            # Filter by branch if specified (skip if show_all is true)
            show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
            branch_id = self.request.query_params.get('branch_id', None)
            
            if not show_all:
                if not branch_id:
                    # Try to get from current branch
                    current_branch = get_current_branch(self.request)
                    if current_branch:
                        branch_id = current_branch.id
                
                if branch_id:
                    queryset = queryset.filter(branch_id=branch_id)
        
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        payment_method = self.request.query_params.get('payment_method', None)
        search = self.request.query_params.get('search', None)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if search:
            queryset = queryset.filter(
                Q(sale_number__icontains=search) |
                Q(cashier__username__icontains=search) |
                Q(notes__icontains=search)
            )
        
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a sale with items and update inventory"""
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        items_data = serializer.validated_data['items']
        payment_method = serializer.validated_data.get('payment_method', 'cash')
        amount_paid_value = serializer.validated_data.get('amount_paid', 0)
        amount_paid = Decimal(str(amount_paid_value)) if amount_paid_value is not None else Decimal('0')
        notes = serializer.validated_data.get('notes', '')
        tax_amount = Decimal(str(serializer.validated_data.get('tax_amount', 0)))
        discount_amount = Decimal(str(serializer.validated_data.get('discount_amount', 0)))
        
        # Calculate totals
        subtotal = Decimal('0')
        sale_items = []
        
        for item_data in items_data:
            product_id = item_data['product_id']
            quantity = item_data['quantity']
            unit_price = item_data.get('unit_price', None)
            variant_id = item_data.get('variant_id', None)
            
            try:
                product = Product.objects.get(id=product_id, is_active=True)
            except Product.DoesNotExist:
                return Response(
                    {'error': f'Product with id {product_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            variant = None
            if variant_id:
                try:
                    variant = ProductVariant.objects.get(id=variant_id, product=product, is_active=True)
                except ProductVariant.DoesNotExist:
                    return Response(
                        {'error': f'Variant with id {variant_id} not found for this product'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # Check stock - use variant stock if variant exists, otherwise product stock
            stock_quantity = variant.stock_quantity if variant else product.stock_quantity
            if stock_quantity < quantity:
                stock_info = f"Variant {variant}" if variant else product.name
                return Response(
                    {'error': f'Insufficient stock for {stock_info}. Available: {stock_quantity}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Use variant price if variant exists and has price, otherwise product price
            if unit_price is None:
                if variant and variant.price is not None:
                    unit_price = variant.price
                else:
                    unit_price = product.price
            else:
                unit_price = Decimal(str(unit_price))
            
            # Get cost for stock movement
            if variant and variant.cost is not None:
                unit_cost = variant.cost
            else:
                unit_cost = product.cost
            
            item_subtotal = Decimal(quantity) * unit_price
            subtotal += item_subtotal
            
            sale_items.append({
                'product': product,
                'variant': variant,
                'quantity': quantity,
                'unit_price': unit_price,
                'unit_cost': unit_cost,
                'subtotal': item_subtotal
            })
        
        # Calculate total
        total = subtotal + tax_amount - discount_amount
        
        # Get sale type (default to 'pos' for backward compatibility)
        sale_type = serializer.validated_data.get('sale_type', 'pos')
        
        # Handle wallet usage if customer is selected
        customer_id = serializer.validated_data.get('customer_id', None)
        customer = None
        wallet_amount_used = Decimal('0')
        wallet_credit_added = Decimal('0')
        
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id, is_active=True)
            except Customer.DoesNotExist:
                logger.warning(f"Customer {customer_id} not found for wallet transaction")
        
        # Check if wallet should be used
        use_wallet = serializer.validated_data.get('use_wallet', False)
        wallet_amount_requested = serializer.validated_data.get('wallet_amount', 0) or Decimal('0')
        
        if customer and use_wallet and customer.wallet_balance > 0:
            # Determine how much to use from wallet
            if wallet_amount_requested > 0:
                wallet_amount_used = min(wallet_amount_requested, customer.wallet_balance, total)
            else:
                # Use all available wallet balance (up to total)
                wallet_amount_used = min(customer.wallet_balance, total)
            
            # Deduct from wallet
            customer.wallet_balance -= wallet_amount_used
            customer.save()
            
            # Create wallet transaction record
            CustomerWalletTransaction.objects.create(
                customer=customer,
                transaction_type='debit',
                source_type='payment',
                amount=wallet_amount_used,
                balance_after=customer.wallet_balance,
                reference=f"Sale payment",
                notes=f"Used {wallet_amount_used} from wallet for sale",
                created_by=request.user
            )
            
            logger.info(f"Used {wallet_amount_used} from customer {customer.id} wallet. Remaining balance: {customer.wallet_balance}")
        
        # Adjust amount_paid to account for wallet usage
        # If wallet was used, reduce the amount needed from other payment methods
        amount_paid_after_wallet = amount_paid
        if wallet_amount_used > 0:
            # The amount_paid should be the remaining amount after wallet
            # But we keep amount_paid as is and track wallet separately
            # The effective payment is amount_paid + wallet_amount_used
            pass
        
        # For POS sales, validate payment amount. Normal sales can have partial/no payment (invoice created)
        if sale_type == 'pos':
            # Total payment = amount_paid + wallet_amount_used
            total_payment = amount_paid + wallet_amount_used
            change = total_payment - total
            
            if change < 0:
                return Response(
                    {'error': f'Total payment ({total_payment}) is less than total ({total}). Amount paid: {amount_paid}, Wallet used: {wallet_amount_used}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # If customer overpays (change > 0), add excess to wallet
            if customer and change > 0:
                customer.wallet_balance += change
                customer.save()
                wallet_credit_added = change
                
                # Create wallet transaction record for credit (sale will be updated later)
                CustomerWalletTransaction.objects.create(
                    customer=customer,
                    transaction_type='credit',
                    source_type='overpayment',
                    amount=change,
                    balance_after=customer.wallet_balance,
                    reference='Sale pending',
                    notes=f"Overpayment from sale added to wallet",
                    created_by=request.user
                )
                
                logger.info(f"Added {change} to customer {customer.id} wallet from overpayment. New balance: {customer.wallet_balance}")
                # Set change to 0 since it's now in wallet
                change = Decimal('0')
        else:
            # For normal sales, change is 0 (no immediate payment)
            change = Decimal('0')
        
        # Get current branch (will be filtered by tenant automatically)
        # Only require branch if branch support is enabled
        branch = None
        if is_branch_support_enabled():
            current_branch = get_current_branch(request)
            if not current_branch:
                logger.warning(f"Sale creation attempted without branch - user: {request.user.username}")
                return Response(
                    {'error': 'No branch selected. Please select a branch first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            branch_id = serializer.validated_data.get('branch_id', None)
            if branch_id:
                from settings.models import Branch
                try:
                    branch = Branch.objects.get(id=branch_id, is_active=True)
                    # Verify branch belongs to current tenant
                    tenant = get_current_tenant(request)
                    if tenant and branch.tenant != tenant:
                        logger.warning(f"Branch {branch_id} does not belong to tenant {tenant.id}")
                        return Response(
                            {'error': 'Branch does not belong to current tenant'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except Branch.DoesNotExist:
                    branch = current_branch
            else:
                branch = current_branch
            
            logger.info(f"Creating sale in branch: {branch.name} by user: {request.user.username}")
        else:
            logger.info(f"Creating sale without branch (branch support disabled) by user: {request.user.username}")
        
        # Create sale
        sale = Sale.objects.create(
            cashier=request.user,
            branch=branch,
            sale_type=sale_type,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total=total,
            payment_method=payment_method,
            amount_paid=amount_paid + wallet_amount_used,  # Include wallet amount in amount_paid
            change=max(change, 0),  # Change can't be negative for normal sales
            notes=notes
        )
        
        # Update wallet transaction sale references (created before sale existed)
        if customer and wallet_amount_used > 0:
            wallet_debit = CustomerWalletTransaction.objects.filter(
                customer=customer,
                sale__isnull=True,
                transaction_type='debit',
                source_type='payment'
            ).order_by('-created_at').first()
            if wallet_debit:
                wallet_debit.sale = sale
                wallet_debit.save()
        
        if customer and wallet_credit_added > 0:
            wallet_credit = CustomerWalletTransaction.objects.filter(
                customer=customer,
                sale__isnull=True,
                transaction_type='credit',
                source_type='overpayment'
            ).order_by('-created_at').first()
            if wallet_credit:
                wallet_credit.sale = sale
                wallet_credit.reference = sale.sale_number
                wallet_credit.save()
        
        # Create sale items and update stock
        for item_data in sale_items:
            SaleItem.objects.create(
                sale=sale,
                product=item_data['product'],
                variant=item_data.get('variant'),
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['subtotal']
            )
            
            # Update stock - variant stock if variant exists, otherwise product stock
            if item_data.get('variant'):
                variant = item_data['variant']
                variant.stock_quantity -= item_data['quantity']
                variant.save()
            else:
                product = item_data['product']
                product.stock_quantity -= item_data['quantity']
                product.save()
            
            # Create stock movement (this will automatically update product/variant stock)
            StockMovement.objects.create(
                branch=branch,  # Use same branch as sale
                product=item_data['product'],
                variant=item_data.get('variant'),
                movement_type='sale',
                quantity=item_data['quantity'],
                reference=sale.sale_number,
                user=request.user,
                unit_cost=item_data['unit_cost'],
                total_cost=item_data['quantity'] * item_data['unit_cost']
            )
        
        # Create journal entry for sale
        try:
            from accounting.views import create_sale_journal_entry
            create_sale_journal_entry(sale)
        except Exception as e:
            # Log error but don't fail the sale creation
            logger.error(f"Error creating journal entry for sale: {e}")
        
        # Create invoice for normal sales (always), optionally for POS sales
        invoice = None
        create_invoice = serializer.validated_data.get('create_invoice', False)
        # Normal sales always create invoice
        if sale_type == 'normal' or create_invoice:
            customer_id = serializer.validated_data.get('customer_id', None)
            customer = None
            if customer_id:
                try:
                    customer = Customer.objects.get(id=customer_id, is_active=True)
                except Customer.DoesNotExist:
                    logger.warning(f"Customer {customer_id} not found, creating invoice without customer")
            
            # For cash payments (pay_now), customer can be optional
            # For installments, customer should be provided but we'll allow null for flexibility
            customer_name = serializer.validated_data.get('customer_name', '')
            customer_email = serializer.validated_data.get('customer_email', '')
            customer_phone = serializer.validated_data.get('customer_phone', '')
            customer_address = serializer.validated_data.get('customer_address', '')
            due_date = serializer.validated_data.get('due_date', None)
            
            # Use customer details if customer is provided
            if customer:
                customer_name = customer.name or customer_name
                customer_email = customer.email or customer_email
                customer_phone = customer.phone or customer_phone
                customer_address = customer.address or customer_address
            
            # For cash sales without customer, use a default name if not provided
            if not customer and not customer_name:
                if payment_method == 'cash':
                    customer_name = 'Cash Customer'
                elif create_payment_plan:
                    customer_name = 'Walk-in Customer'
                else:
                    customer_name = 'Customer'
            
            # Ensure sale has items before creating invoice
            sale_items = sale.items.all()
            if not sale_items.exists():
                return Response(
                    {'error': 'Cannot create invoice: Sale must have at least one item'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create invoice from sale
            invoice = Invoice.objects.create(
                sale=sale,
                branch=sale.branch,  # Use same branch as sale
                customer=customer,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                customer_address=customer_address,
                subtotal=subtotal,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                total=total,
                due_date=due_date,
                issued_date=timezone.now().date(),
                status='sent' if amount_paid < total else 'paid',
                created_by=request.user,
                notes=notes
            )
            
            # Create invoice items from sale items - ensure all items are copied
            for sale_item in sale_items:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=sale_item.product,
                    variant=sale_item.variant,
                    size=sale_item.size,
                    color=sale_item.color,
                    quantity=sale_item.quantity,
                    unit_price=sale_item.unit_price,
                    subtotal=sale_item.subtotal
                )
            
            # If payment was made, create payment record
            if amount_paid > 0:
                Payment.objects.create(
                    invoice=invoice,
                    amount=amount_paid,
                    payment_method=payment_method,
                    payment_date=timezone.now().date(),
                    recorded_by=request.user,
                    notes=f"Initial payment from sale {sale.sale_number}"
                )
            
            # Create payment plan if requested (for normal sales with installments)
            create_payment_plan = serializer.validated_data.get('create_payment_plan', False)
            if create_payment_plan and invoice and invoice.balance > 0:
                number_of_installments = serializer.validated_data.get('number_of_installments')
                frequency = serializer.validated_data.get('installment_frequency')
                start_date = serializer.validated_data.get('payment_plan_start_date')
                
                # Validate that all required fields are present
                if not number_of_installments or number_of_installments < 1:
                    logger.error("Payment plan creation attempted without valid number_of_installments")
                    return Response(
                        {'error': 'Number of installments is required and must be at least 1 for payment plans'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if not frequency:
                    logger.error("Payment plan creation attempted without installment_frequency")
                    return Response(
                        {'error': 'Installment frequency is required for payment plans'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if not start_date:
                    logger.error("Payment plan creation attempted without payment_plan_start_date")
                    return Response(
                        {'error': 'Payment plan start date is required for payment plans'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if not start_date:
                    start_date = timezone.now().date()
                else:
                    from datetime import datetime
                    if isinstance(start_date, str):
                        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                
                # Calculate installment amount
                installment_amount = invoice.balance / number_of_installments
                
                PaymentPlan.objects.create(
                    invoice=invoice,
                    total_amount=invoice.balance,
                    number_of_installments=number_of_installments,
                    installment_amount=installment_amount,
                    frequency=frequency,
                    start_date=start_date,
                    next_payment_date=start_date,
                    is_active=True,
                    created_by=request.user,
                    notes=f"Payment plan created from sale {sale.sale_number}"
                )
        
        response_data = SaleSerializer(sale).data
        if invoice:
            response_data['invoice'] = InvoiceSerializer(invoice).data
        
        # Add wallet information to response
        if customer:
            response_data['wallet_balance'] = str(customer.wallet_balance)
            response_data['wallet_amount_used'] = str(wallet_amount_used)
            if wallet_credit_added > 0:
                response_data['wallet_credit_added'] = str(wallet_credit_added)
                response_data['message'] = f"Sale completed. {wallet_credit_added} KES added to customer wallet."
        
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        """Get receipt data for a sale"""
        sale = self.get_object()
        serializer = self.get_serializer(sale)
        return Response(serializer.data)


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerListSerializer
        return CustomerSerializer
    
    def get_queryset(self):
        queryset = Customer.objects.all().select_related('branch')
        
        # Filter by branch if specified (customers can be shared, so this is optional)
        branch_id = self.request.query_params.get('branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        is_active = self.request.query_params.get('is_active', None)
        customer_type = self.request.query_params.get('customer_type', None)
        search = self.request.query_params.get('search', None)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(customer_code__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(tax_id__icontains=search)
            )
        
        return queryset


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().select_related('sale', 'created_by').prefetch_related(
        'items__product', 'items__variant', 'payments'
    )
    serializer_class = InvoiceSerializer
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Invoice.objects.all().select_related('sale', 'created_by', 'branch').prefetch_related(
            'items__product', 'items__variant', 'payments__recorded_by'
        )
        
        # Filter by branch if specified (skip if show_all is true)
        show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
        branch_id = self.request.query_params.get('branch_id', None)
        
        if not show_all:
            if not branch_id:
                # Try to get from current branch
                current_branch = get_current_branch(self.request)
                if current_branch:
                    branch_id = current_branch.id
            
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)
        
        status_filter = self.request.query_params.get('status', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        search = self.request.query_params.get('search', None)
        overdue = self.request.query_params.get('overdue', None)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        if overdue == 'true':
            queryset = queryset.filter(status='overdue')
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(customer_name__icontains=search) |
                Q(customer_email__icontains=search) |
                Q(customer_phone__icontains=search)
            )
        
        return queryset
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create an invoice from a sale or manually"""
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        sale_id = serializer.validated_data.get('sale_id', None)
        
        if sale_id:
            # Create invoice from sale
            try:
                sale = Sale.objects.get(id=sale_id)
            except Sale.DoesNotExist:
                return Response(
                    {'error': 'Sale not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if invoice already exists for this sale
            if Invoice.objects.filter(sale=sale).exists():
                return Response(
                    {'error': 'Invoice already exists for this sale'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            customer_id = serializer.validated_data.get('customer_id', None)
            customer = None
            if customer_id:
                try:
                    customer = Customer.objects.get(id=customer_id, is_active=True)
                except Customer.DoesNotExist:
                    return Response(
                        {'error': 'Customer not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            customer_name = serializer.validated_data.get('customer_name', '')
            customer_email = serializer.validated_data.get('customer_email', '')
            customer_phone = serializer.validated_data.get('customer_phone', '')
            customer_address = serializer.validated_data.get('customer_address', '')
            due_date = serializer.validated_data.get('due_date', None)
            notes = serializer.validated_data.get('notes', '')
            
            # Use customer details if customer is provided
            if customer:
                customer_name = customer.name
                customer_email = customer.email
                customer_phone = customer.phone
                customer_address = customer.address
            
            # Get sale items before creating invoice to ensure they exist
            sale_items = sale.items.all()
            if not sale_items.exists():
                return Response(
                    {'error': 'Cannot create invoice from a sale with no items'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get branch from sale or current branch
            branch = sale.branch if sale.branch else get_current_branch(request)
            
            invoice = Invoice.objects.create(
                sale=sale,
                branch=branch,
                customer=customer,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                customer_address=customer_address,
                subtotal=sale.subtotal,
                tax_amount=sale.tax_amount,
                discount_amount=sale.discount_amount,
                total=sale.total,
                due_date=due_date,
                issued_date=timezone.now().date(),
                status='sent',
                created_by=request.user,
                notes=notes
            )
            
            # Create invoice items from sale items - ensure all items are copied
            for sale_item in sale_items:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=sale_item.product,
                    variant=sale_item.variant,
                    size=sale_item.size,
                    color=sale_item.color,
                    quantity=sale_item.quantity,
                    unit_price=sale_item.unit_price,
                    subtotal=sale_item.subtotal
                )
        else:
            # Create invoice manually
            customer_id = serializer.validated_data.get('customer_id', None)
            customer = None
            if customer_id:
                try:
                    customer = Customer.objects.get(id=customer_id, is_active=True)
                except Customer.DoesNotExist:
                    return Response(
                        {'error': 'Customer not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            items_data = serializer.validated_data.get('items', [])
            
            # Validate that invoice has at least one item
            if not items_data or len(items_data) == 0:
                return Response(
                    {'error': 'An invoice must have at least one item'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            subtotal = Decimal(str(serializer.validated_data['subtotal']))
            tax_amount = Decimal(str(serializer.validated_data.get('tax_amount', 0)))
            discount_amount = Decimal(str(serializer.validated_data.get('discount_amount', 0)))
            total = subtotal + tax_amount - discount_amount
            
            # Use customer details if customer is provided
            customer_name = serializer.validated_data.get('customer_name', '')
            customer_email = serializer.validated_data.get('customer_email', '')
            customer_phone = serializer.validated_data.get('customer_phone', '')
            customer_address = serializer.validated_data.get('customer_address', '')
            
            if customer:
                customer_name = customer.name
                customer_email = customer.email
                customer_phone = customer.phone
                customer_address = customer.address
            
            # Get current branch
            current_branch = get_current_branch(request)
            branch_id = serializer.validated_data.get('branch_id', None)
            if branch_id:
                from settings.models import Branch
                try:
                    branch = Branch.objects.get(id=branch_id, is_active=True)
                except Branch.DoesNotExist:
                    branch = current_branch
            else:
                branch = current_branch
            
            invoice = Invoice.objects.create(
                branch=branch,
                customer=customer,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                customer_address=customer_address,
                subtotal=subtotal,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                total=total,
                due_date=serializer.validated_data.get('due_date', None),
                issued_date=timezone.now().date(),
                status='draft',
                created_by=request.user,
                notes=serializer.validated_data.get('notes', '')
            )
            
            # Create invoice items - validate each item
            created_items = []
            for item_data in items_data:
                product_id = item_data.get('product_id')
                if not product_id:
                    return Response(
                        {'error': 'Each invoice item must have a product_id'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                variant_id = item_data.get('variant_id', None)
                quantity = item_data.get('quantity', 1)
                if quantity <= 0:
                    return Response(
                        {'error': 'Invoice item quantity must be greater than 0'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                unit_price = Decimal(str(item_data.get('unit_price', 0)))
                if unit_price < 0:
                    return Response(
                        {'error': 'Invoice item unit price cannot be negative'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                description = item_data.get('description', '')
                
                try:
                    product = Product.objects.get(id=product_id, is_active=True)
                except Product.DoesNotExist:
                    return Response(
                        {'error': f'Product with id {product_id} not found or is inactive'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                variant = None
                if variant_id:
                    try:
                        variant = ProductVariant.objects.get(id=variant_id, product=product, is_active=True)
                    except ProductVariant.DoesNotExist:
                        return Response(
                            {'error': f'Variant with id {variant_id} not found or is inactive for product {product.name}'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                
                invoice_item = InvoiceItem.objects.create(
                    invoice=invoice,
                    product=product,
                    variant=variant,
                    size=variant.size if variant else None,
                    color=variant.color if variant else None,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=quantity * unit_price,
                    description=description
                )
                created_items.append(invoice_item)
            
            # Verify that at least one item was created
            if not created_items:
                invoice.delete()  # Rollback invoice creation
                return Response(
                    {'error': 'Failed to create invoice items. Please check your items data.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create journal entry for manually created invoices (not from sale)
        if not invoice.sale:
            try:
                from accounting.views import create_invoice_journal_entry
                create_invoice_journal_entry(invoice)
            except Exception as e:
                logger.error(f"Error creating journal entry for invoice: {e}")
        
        response_serializer = InvoiceSerializer(invoice)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Mark invoice as sent"""
        invoice = self.get_object()
        if invoice.status == 'draft':
            invoice.status = 'sent'
            invoice.save()
        return Response(InvoiceSerializer(invoice).data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get invoice statistics"""
        invoice = self.get_object()
        return Response({
            'total': float(invoice.total),
            'amount_paid': float(invoice.amount_paid),
            'balance': float(invoice.balance),
            'payment_percentage': float(invoice.payment_percentage),
            'is_fully_paid': invoice.is_fully_paid,
            'is_overdue': invoice.is_overdue,
            'payments_count': invoice.payments.count()
        })
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Download invoice as PDF"""
        invoice = self.get_object()
        pdf_buffer = create_invoice_pdf(invoice)
        
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
        return response


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related('invoice', 'recorded_by')
    serializer_class = PaymentSerializer
    ordering = ['-payment_date', '-created_at']
    
    def get_queryset(self):
        queryset = Payment.objects.all().select_related('invoice', 'recorded_by')
        invoice_id = self.request.query_params.get('invoice', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
        if date_from:
            queryset = queryset.filter(payment_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(payment_date__lte=date_to)
        
        return queryset
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a payment against an invoice"""
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        invoice_id = serializer.validated_data['invoice_id']
        amount = Decimal(str(serializer.validated_data['amount']))
        
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if payment exceeds balance
        if amount > invoice.balance:
            return Response(
                {'error': f'Payment amount ({amount}) exceeds invoice balance ({invoice.balance})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create payment
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_method=serializer.validated_data.get('payment_method', 'cash'),
            payment_date=serializer.validated_data.get('payment_date', timezone.now().date()),
            reference=serializer.validated_data.get('reference', ''),
            notes=serializer.validated_data.get('notes', ''),
            recorded_by=request.user
        )
        
        # Invoice amount_paid and status will be updated automatically via save() method
        
        # Create journal entry for payment
        try:
            from accounting.views import create_payment_journal_entry
            create_payment_journal_entry(payment)
        except Exception as e:
            logger.error(f"Error creating journal entry for payment: {e}")
        
        response_serializer = PaymentSerializer(payment)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
