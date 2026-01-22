"""
Sales service layer - handles all sales business logic
Moved from be/services/sales_service.py to be/sales/services.py
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg, F, QuerySet
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Sale, SaleItem, Invoice, InvoiceItem, Payment, Customer, PaymentPlan, CustomerWalletTransaction
from products.models import Product, ProductVariant
from inventory.models import StockMovement
from settings.models import Branch
from settings.utils import get_current_branch, is_branch_support_enabled
from services.base import BaseService


class SaleService(BaseService):
    """Service for sale operations"""
    
    def __init__(self):
        super().__init__(Sale)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None, request=None) -> QuerySet:
        """
        Build queryset with filters for sale listing.
        Moves query building logic from views to service layer.
        
        Args:
            filters: Dictionary with filter parameters:
                - branch_id: int (branch ID)
                - show_all: bool or str ('true'/'false')
                - date_from: str (date string)
                - date_to: str (date string)
                - payment_method: str
                - search: str (search term)
            request: HttpRequest (optional, for branch detection)
        
        Returns:
            QuerySet of sales with proper select_related/prefetch_related
        """
        queryset = self.model.objects.all().select_related('cashier', 'branch').prefetch_related(
            'items__product', 'items__variant', 'items__size', 'items__color'
        )
        
        if not filters:
            filters = {}
        
        # Handle branch filtering
        if is_branch_support_enabled():
            show_all = filters.get('show_all', 'false')
            if isinstance(show_all, str):
                show_all = show_all.lower() == 'true'
            
            if not show_all:
                branch_id = filters.get('branch_id')
                if not branch_id and request:
                    current_branch = get_current_branch(request)
                    if current_branch:
                        branch_id = current_branch.id
                
                if branch_id:
                    try:
                        queryset = queryset.filter(branch_id=int(branch_id))
                    except (ValueError, TypeError):
                        queryset = queryset.none()
        
        # Date filters
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Payment method filter
        payment_method = filters.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        
        # Search filter
        search = filters.get('search')
        if search:
            queryset = queryset.filter(
                Q(sale_number__icontains=search) |
                Q(cashier__username__icontains=search) |
                Q(notes__icontains=search)
            )
        
        return queryset
    
    def validate_sale_items(self, items_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate sale items and check stock availability"""
        validated_items = []
        
        for item_data in items_data:
            product_id = item_data.get('product_id')
            variant_id = item_data.get('variant_id')
            quantity = item_data.get('quantity', 1)
            
            if not product_id:
                raise ValidationError("Product ID is required for each item")
            
            try:
                product = Product.objects.get(id=product_id, is_active=True)
            except Product.DoesNotExist:
                raise ValidationError(f"Product with id {product_id} not found")
            
            variant = None
            if variant_id:
                try:
                    variant = ProductVariant.objects.get(
                        id=variant_id,
                        product=product,
                        is_active=True
                    )
                except ProductVariant.DoesNotExist:
                    raise ValidationError(
                        f"Variant with id {variant_id} not found for this product"
                    )
            
            # Check stock
            if product.track_stock:
                stock_quantity = variant.stock_quantity if variant else product.stock_quantity
                if stock_quantity < quantity:
                    stock_info = f"Variant {variant}" if variant else product.name
                    raise ValidationError(
                        f"Insufficient stock for {stock_info}. Available: {stock_quantity}"
                    )
            
            # Get unit price
            unit_price = item_data.get('unit_price')
            if unit_price is None:
                if variant and variant.price is not None:
                    unit_price = variant.price
                else:
                    unit_price = product.price
            
            # Get unit cost
            if variant and variant.cost is not None:
                unit_cost = variant.cost
            else:
                unit_cost = product.cost
            
            validated_items.append({
                'product': product,
                'variant': variant,
                'quantity': quantity,
                'unit_price': Decimal(str(unit_price)),
                'unit_cost': unit_cost,
                'subtotal': Decimal(str(quantity)) * Decimal(str(unit_price))
            })
        
        return validated_items
    
    @transaction.atomic
    def create_sale(self, sale_data: Dict[str, Any], items_data: List[Dict[str, Any]],
                   user, branch: Optional[Branch] = None) -> Sale:
        """Create a sale with items and update inventory"""
        # Validate items
        validated_items = self.validate_sale_items(items_data)
        
        # Calculate totals
        subtotal = sum(item['subtotal'] for item in validated_items)
        tax_amount = sale_data.get('tax_amount', Decimal('0'))
        discount_amount = sale_data.get('discount_amount', Decimal('0'))
        delivery_cost = sale_data.get('delivery_cost', Decimal('0'))
        total = subtotal + tax_amount - discount_amount + delivery_cost
        
        # Get sale type
        sale_type = sale_data.get('sale_type', 'pos')
        payment_method = sale_data.get('payment_method', 'cash')
        amount_paid = sale_data.get('amount_paid', Decimal('0')) or Decimal('0')
        
        # Calculate change for POS sales
        change = Decimal('0')
        if sale_type == 'pos':
            change = max(Decimal('0'), amount_paid - total)
        
        # Create sale
        sale = Sale.objects.create(
            sale_type=sale_type,
            branch=branch,
            cashier=user,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total=total,
            delivery_method=sale_data.get('delivery_method'),
            delivery_cost=delivery_cost,
            shipping_address=sale_data.get('shipping_address'),
            shipping_location=sale_data.get('shipping_location'),
            payment_method=payment_method,
            amount_paid=amount_paid,
            change=change,
            notes=sale_data.get('notes', ''),
        )
        
        # Create sale items and update stock
        for item_data in validated_items:
            SaleItem.objects.create(
                sale=sale,
                product=item_data['product'],
                variant=item_data['variant'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['subtotal']
            )
            
            # Update stock
            if item_data['product'].track_stock:
                if item_data['variant']:
                    variant = item_data['variant']
                    variant.stock_quantity -= item_data['quantity']
                    variant.save()
                else:
                    product = item_data['product']
                    product.stock_quantity -= item_data['quantity']
                    product.save()
                
                # Create stock movement
                StockMovement.objects.create(
                    branch=branch,
                    product=item_data['product'],
                    variant=item_data['variant'],
                    movement_type='sale',
                    quantity=item_data['quantity'],
                    unit_cost=item_data['unit_cost'],
                    total_cost=item_data['quantity'] * item_data['unit_cost'],
                    reference=sale.sale_number,
                    user=user,
                    notes=f'Sale {sale.sale_number}'
                )
        
        # Create journal entry
        try:
            from accounting.services import create_sale_journal_entry
            create_sale_journal_entry(sale)
        except Exception as e:
            # Log but don't fail sale creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating journal entry for sale: {e}")
        
        return sale
    
    def get_sale_statistics(self, date_from: Optional[str] = None,
                          date_to: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive sale statistics"""
        queryset = self.model.objects.all()
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        stats = {
            'total_sales': queryset.count(),
            'pos_sales': queryset.filter(sale_type='pos').count(),
            'normal_sales': queryset.filter(sale_type='normal').count(),
            'total_revenue': float(queryset.aggregate(total=Sum('total'))['total'] or 0),
            'total_tax': float(queryset.aggregate(total=Sum('tax_amount'))['total'] or 0),
            'total_discounts': float(queryset.aggregate(total=Sum('discount_amount'))['total'] or 0),
            'total_delivery_cost': float(queryset.aggregate(total=Sum('delivery_cost'))['total'] or 0),
            'average_sale': float(queryset.aggregate(avg=Avg('total'))['avg'] or 0),
        }
        
        return stats
    
    @transaction.atomic
    def handle_wallet_transactions(self, customer: Customer, total: Decimal,
                                  amount_paid: Decimal, use_wallet: bool,
                                  wallet_amount_requested: Decimal, sale: Sale,
                                  user) -> Dict[str, Decimal]:
        """Handle wallet debit and credit transactions for a sale"""
        wallet_amount_used = Decimal('0')
        wallet_credit_added = Decimal('0')
        
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
                sale=sale,
                reference=f"Sale {sale.sale_number}",
                notes=f"Used {wallet_amount_used} from wallet for sale",
                created_by=user
            )
        
        # For POS sales, handle overpayment (add to wallet)
        if customer and sale.sale_type == 'pos':
            total_payment = amount_paid + wallet_amount_used
            change = total_payment - total
            
            if change > 0:
                # Add overpayment to wallet
                customer.wallet_balance += change
                customer.save()
                wallet_credit_added = change
                
                # Create wallet transaction record for credit
                CustomerWalletTransaction.objects.create(
                    customer=customer,
                    transaction_type='credit',
                    source_type='overpayment',
                    amount=change,
                    balance_after=customer.wallet_balance,
                    sale=sale,
                    reference=sale.sale_number,
                    notes=f"Overpayment from sale added to wallet",
                    created_by=user
                )
                change = Decimal('0')  # Set change to 0 since it's now in wallet
            else:
                change = Decimal('0')
        else:
            change = Decimal('0')
        
        return {
            'wallet_amount_used': wallet_amount_used,
            'wallet_credit_added': wallet_credit_added,
            'change': change
        }


class InvoiceService(BaseService):
    """Service for invoice operations"""
    
    def __init__(self):
        super().__init__(Invoice)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for invoice listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - status: str (invoice status)
                - customer_id: int
                - date_from: str
                - date_to: str
                - search: str
        
        Returns:
            QuerySet of invoices
        """
        queryset = self.model.objects.select_related('sale', 'customer', 'branch', 'created_by').prefetch_related('items')
        
        if not filters:
            return queryset
        
        status = filters.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        customer_id = filters.get('customer_id')
        if customer_id:
            try:
                queryset = queryset.filter(customer_id=int(customer_id))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(issued_date__gte=date_from)
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(issued_date__lte=date_to)
        
        search = filters.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(customer_name__icontains=search) |
                Q(customer_email__icontains=search)
            )
        
        return queryset
    
    @transaction.atomic
    def create_invoice_from_sale(self, sale: Sale, customer: Optional[Customer] = None,
                                 customer_name: str = '', customer_email: str = '',
                                 customer_phone: str = '', customer_address: str = '',
                                 due_date: Optional[str] = None, notes: str = '',
                                 user=None, amount_paid: Optional[Decimal] = None) -> Invoice:
        """Create an invoice from a sale with full customer details"""
        # Calculate totals
        subtotal = sale.subtotal
        tax_amount = sale.tax_amount
        discount_amount = sale.discount_amount
        total = sale.total
        
        # Use customer details if customer is provided
        if customer:
            customer_name = customer.name or customer_name
            customer_email = customer.email or customer_email
            customer_phone = customer.phone or customer_phone
            customer_address = customer.address or customer_address
        
        # Default customer name if not provided
        if not customer_name:
            customer_name = 'Walk-in Customer'
        
        # Determine status based on payment
        paid_amount = amount_paid if amount_paid is not None else (sale.amount_paid or Decimal('0'))
        balance = total - paid_amount
        status = 'paid' if balance <= 0 else 'sent'
        
        # Parse due_date if string
        if due_date and isinstance(due_date, str):
            from datetime import datetime
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        elif due_date is None:
            due_date = timezone.now().date()
        
        # Create invoice
        invoice = Invoice.objects.create(
            sale=sale,
            branch=sale.branch,
            customer=customer,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_address=customer_address,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total=total,
            amount_paid=paid_amount,
            balance=balance,
            status=status,
            due_date=due_date,
            issued_date=sale.created_at.date(),
            created_by=user or sale.cashier,
            notes=notes
        )
        
        # Create invoice items
        for sale_item in sale.items.all():
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
        
        # Create payment record if amount_paid > 0
        if paid_amount > 0:
            Payment.objects.create(
                invoice=invoice,
                amount=paid_amount,
                payment_method=sale.payment_method,
                payment_date=timezone.now().date(),
                recorded_by=user or sale.cashier,
                notes=f"Initial payment from sale {sale.sale_number}"
            )
        
        return invoice
    
    @transaction.atomic
    def create_payment_plan(self, invoice: Invoice, number_of_installments: int,
                           frequency: str, start_date: str, user=None) -> PaymentPlan:
        """Create a payment plan for an invoice"""
        if invoice.balance <= 0:
            raise ValidationError("Cannot create payment plan for fully paid invoice")
        
        # Parse start_date if string
        if isinstance(start_date, str):
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Calculate installment amount
        installment_amount = invoice.balance / number_of_installments
        
        payment_plan = PaymentPlan.objects.create(
            invoice=invoice,
            total_amount=invoice.balance,
            number_of_installments=number_of_installments,
            installment_amount=installment_amount,
            frequency=frequency,
            start_date=start_date,
            next_payment_date=start_date,
            is_active=True,
            created_by=user,
            notes=f"Payment plan created from sale {invoice.sale.sale_number if invoice.sale else 'N/A'}"
        )
        
        return payment_plan


class PaymentService(BaseService):
    """Service for payment operations"""
    
    def __init__(self):
        super().__init__(Payment)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for payment listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - invoice_id: int
                - payment_method: str
                - date_from: str
                - date_to: str
        
        Returns:
            QuerySet of payments
        """
        queryset = self.model.objects.select_related('invoice', 'recorded_by')
        
        if not filters:
            return queryset
        
        invoice_id = filters.get('invoice_id')
        if invoice_id:
            try:
                queryset = queryset.filter(invoice_id=int(invoice_id))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        payment_method = filters.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(payment_date__gte=date_from)
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(payment_date__lte=date_to)
        
        return queryset
    
    @transaction.atomic
    def create_payment(self, invoice: Invoice, amount: Decimal,
                      payment_method: str, payment_date: Optional[str] = None,
                      user=None, reference: str = '', notes: str = '') -> Payment:
        """Create a payment against an invoice"""
        if amount > invoice.balance:
            raise ValidationError(
                f'Payment amount ({amount}) exceeds invoice balance ({invoice.balance})'
            )
        
        if payment_date is None:
            payment_date = timezone.now().date()
        else:
            from datetime import datetime
            payment_date = datetime.strptime(payment_date, '%Y-%m-%d').date()
        
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_method=payment_method,
            payment_date=payment_date,
            reference=reference,
            notes=notes,
            recorded_by=user
        )
        
        # Invoice amount_paid and status will be updated automatically via save() method
        
        # Create journal entry
        try:
            from accounting.views import create_payment_journal_entry
            create_payment_journal_entry(payment)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating journal entry for payment: {e}")
        
        return payment


class CustomerService(BaseService):
    """Service for customer operations"""
    
    def __init__(self):
        super().__init__(Customer)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for customer listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
                - search: str (search term)
                - customer_type: str
        
        Returns:
            QuerySet of customers
        """
        queryset = self.model.objects.select_related('branch', 'created_by')
        
        if not filters:
            return queryset
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        search = filters.get('search')
        if search:
            search = str(search).strip()
            if search:  # Only search if not empty after stripping
                try:
                    queryset = queryset.filter(
                        Q(name__icontains=search) |
                        Q(email__icontains=search) |
                        Q(phone__icontains=search) |
                        Q(customer_code__icontains=search)
                    )
                except Exception:
                    # If search fails, return empty queryset rather than crashing
                    queryset = queryset.none()
        
        customer_type = filters.get('customer_type')
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)
        
        return queryset
    
    def search_customers(self, query: str, limit: int = 50) -> List[Customer]:
        """Search customers by name, email, phone, or customer code"""
        try:
            if not query or not query.strip():
                return []
            
            # Validate and sanitize limit
            if limit < 1:
                limit = 50
            elif limit > 1000:
                limit = 1000
            
            queryset = self.model.objects.filter(
                Q(name__icontains=query) |
                Q(email__icontains=query) |
                Q(phone__icontains=query) |
                Q(customer_code__icontains=query)
            ).filter(is_active=True)[:limit]
            
            return list(queryset)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in search_customers: {e}", exc_info=True)
            return []  # Return empty list on error rather than raising
    
    @transaction.atomic
    def update_wallet_balance(self, customer: Customer, amount: Decimal,
                             transaction_type: str, source_type: str = 'other',
                             sale: Optional[Sale] = None, invoice: Optional[Invoice] = None,
                             reference: str = '', notes: str = '', user=None) -> 'CustomerWalletTransaction':
        """Update customer wallet balance and create transaction record"""
        from sales.models import CustomerWalletTransaction
        
        if transaction_type == 'debit':
            if customer.wallet_balance < amount:
                raise ValidationError(
                    f'Insufficient wallet balance. Available: {customer.wallet_balance}, Requested: {amount}'
                )
            customer.wallet_balance -= amount
        elif transaction_type == 'credit':
            customer.wallet_balance += amount
        else:
            raise ValidationError(f'Invalid transaction type: {transaction_type}')
        
        customer.save()
        
        # Create transaction record
        transaction = CustomerWalletTransaction.objects.create(
            customer=customer,
            transaction_type=transaction_type,
            source_type=source_type,
            amount=amount,
            balance_after=customer.wallet_balance,
            sale=sale,
            invoice=invoice,
            reference=reference,
            notes=notes,
            created_by=user
        )
        
        return transaction
    
    def get_customer_statistics(self, customer_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a customer"""
        try:
            customer = self.model.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            raise ValidationError(f"Customer with id {customer_id} not found")
        
        stats = {
            'total_invoices': customer.total_invoices,
            'total_outstanding': float(customer.total_outstanding),
            'wallet_balance': float(customer.wallet_balance),
            'total_sales': customer.invoices.aggregate(
                total=Sum('total')
            )['total'] or Decimal('0'),
        }
        
        return stats
