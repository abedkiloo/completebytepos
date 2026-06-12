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
from products.status_rules import get_operational_product, get_operational_variant
from approvals.effective import approved_sellable_stock_quantity
from products.stock_utils import (
    active_variant_stock_sum,
    sellable_unit_price,
    sellable_unit_cost,
    variants_sold_as_simple,
)
from inventory.models import StockMovement
from settings.models import Branch
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
from settings.feature_flags import is_product_variants_enabled
from services.base import BaseService
import logging

logger = logging.getLogger(__name__)


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

        # Status filter — default hides register drafts from sales history / reports.
        status = filters.get('status')
        if status:
            queryset = queryset.filter(status=status)
        elif filters.get('include_holding') not in (True, 'true', '1', 1):
            queryset = queryset.exclude(status='holding')
        
        return queryset
    
    def validate_sale_items(
        self,
        items_data: List[Dict[str, Any]],
        *,
        check_stock: bool = True,
        user=None,
    ) -> List[Dict[str, Any]]:
        """Validate sale items; optionally enforce stock (checkout only)."""
        validated_items = []
        
        for item_data in items_data:
            product_id = item_data.get('product_id')
            variant_id = item_data.get('variant_id')
            quantity = item_data.get('quantity', 1)
            
            if not product_id:
                raise ValidationError("Product ID is required for each item")
            
            try:
                product = get_operational_product(product_id)
            except Product.DoesNotExist:
                raise ValidationError(f"Product with id {product_id} not found")
            
            variant = None
            if variant_id and is_product_variants_enabled():
                try:
                    variant = get_operational_variant(variant_id, product)
                except ProductVariant.DoesNotExist:
                    if int(variant_id) == int(product_id):
                        raise ValidationError(
                            f'Invalid variant_id {variant_id}: it matches product_id. '
                            'Use the ProductVariant id from size/color selection, not the product id.'
                        )
                    raise ValidationError(
                        f'Variant with id {variant_id} not found for product {product_id}'
                    )
            elif variant_id and not is_product_variants_enabled():
                # Ignore stale variant_id from clients when the feature is off.
                variant_id = None
            
            # Stock is enforced at checkout, not while saving holding drafts.
            if check_stock and product.track_stock:
                stock_quantity = approved_sellable_stock_quantity(product, variant)
                if stock_quantity < quantity:
                    stock_info = variant.sku if variant else product.name
                    raise ValidationError(
                        f"Insufficient stock for {stock_info}. Available: {stock_quantity}"
                    )
            
            from accounts.sensitive_edits import validate_sale_unit_price_override

            validate_sale_unit_price_override(
                user,
                product=product,
                variant=variant,
                override=item_data.get('unit_price'),
            )
            unit_price = sellable_unit_price(
                product,
                variant,
                override=item_data.get('unit_price'),
            )
            
            # Get unit cost
            unit_cost = sellable_unit_cost(product, variant)
            
            validated_items.append({
                'product': product,
                'variant': variant,
                'quantity': quantity,
                'unit_price': Decimal(str(unit_price)),
                'unit_cost': unit_cost,
                'subtotal': Decimal(str(quantity)) * Decimal(str(unit_price))
            })
        
        return validated_items

    def _create_sale_stock_movements(
        self,
        *,
        branch,
        user,
        reference: str,
        notes: str,
        product,
        variant,
        quantity: int,
        unit_cost,
    ):
        """Create stock movement(s) for a sale line, FIFO across variants when needed."""
        if not product.track_stock:
            return

        if variant is None and variants_sold_as_simple(product):
            remaining = int(quantity)
            for v in product.variants.filter(is_active=True, stock_quantity__gt=0).order_by('id'):
                if remaining <= 0:
                    break
                take = min(remaining, v.stock_quantity)
                StockMovement.objects.create(
                    branch=branch,
                    product=product,
                    variant=v,
                    movement_type='sale',
                    quantity=take,
                    unit_cost=unit_cost,
                    total_cost=take * unit_cost,
                    reference=reference,
                    user=user,
                    notes=notes,
                )
                remaining -= take
            return

        if (
            variant is not None
            and is_product_variants_enabled()
            and product.has_variants
        ):
            remaining = int(quantity)
            v_qty = int(variant.stock_quantity or 0)
            if v_qty > 0:
                take = min(remaining, v_qty)
                StockMovement.objects.create(
                    branch=branch,
                    product=product,
                    variant=variant,
                    movement_type='sale',
                    quantity=take,
                    unit_cost=unit_cost,
                    total_cost=take * unit_cost,
                    reference=reference,
                    user=user,
                    notes=notes,
                )
                remaining -= take
            if remaining > 0:
                StockMovement.objects.create(
                    branch=branch,
                    product=product,
                    variant=variant,
                    movement_type='sale',
                    quantity=remaining,
                    unit_cost=unit_cost,
                    total_cost=remaining * unit_cost,
                    reference=reference,
                    user=user,
                    notes=notes,
                )
            return

        StockMovement.objects.create(
            branch=branch,
            product=product,
            variant=variant,
            movement_type='sale',
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=quantity * unit_cost,
            reference=reference,
            user=user,
            notes=notes,
        )

    def get_active_holding(self, user, branch: Optional[Branch] = None) -> Optional[Sale]:
        """Return the cashier's open holding invoice for this branch, if any."""
        qs = self.model.objects.filter(
            cashier=user,
            status='holding',
        ).prefetch_related('items__product', 'items__variant')
        if branch:
            qs = qs.filter(branch=branch)
        return qs.order_by('-updated_at').first()

    @transaction.atomic
    def save_holding_sale(
        self,
        user,
        items_data: List[Dict[str, Any]],
        *,
        branch: Optional[Branch] = None,
        customer: Optional[Customer] = None,
        tax_amount: Decimal = Decimal('0'),
        discount_amount: Decimal = Decimal('0'),
        notes: str = '',
        holding_id: Optional[int] = None,
    ) -> Sale:
        """
        Create or update a holding (draft) sale. Does NOT move stock or post
        accounting entries — those happen in ``complete_holding_sale``.
        """
        from accounts.sensitive_edits import clamp_holding_financial_adjustments

        tax_amount, discount_amount = clamp_holding_financial_adjustments(
            user, tax_amount, discount_amount
        )
        validated_items = (
            self.validate_sale_items(items_data, check_stock=False, user=user)
            if items_data
            else []
        )

        subtotal = sum(item['subtotal'] for item in validated_items)
        total = subtotal + tax_amount - discount_amount

        holding = None
        if holding_id:
            holding = self.model.objects.filter(
                id=holding_id, cashier=user, status='holding'
            ).first()
        if not holding:
            holding = self.get_active_holding(user, branch)

        if holding:
            holding.items.all().delete()
            holding.customer = customer
            holding.branch = branch or holding.branch
            holding.subtotal = subtotal
            holding.tax_amount = tax_amount
            holding.discount_amount = discount_amount
            holding.total = max(Decimal('0'), total)
            holding.amount_paid = Decimal('0')
            holding.change = Decimal('0')
            holding.notes = notes or holding.notes
            holding.save()
        else:
            holding = self.model.objects.create(
                sale_type='pos',
                status='holding',
                branch=branch,
                cashier=user,
                customer=customer,
                subtotal=subtotal,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                total=max(Decimal('0'), total),
                payment_method='cash',
                amount_paid=Decimal('0'),
                change=Decimal('0'),
                notes=notes,
            )

        for item_data in validated_items:
            SaleItem.objects.create(
                sale=holding,
                product=item_data['product'],
                variant=item_data['variant'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['subtotal'],
            )

        return holding

    @transaction.atomic
    def complete_holding_sale(
        self,
        holding: Sale,
        *,
        payment_method: str,
        amount_paid: Decimal,
        user,
        branch: Optional[Branch] = None,
        allow_partial: bool = False,
        excess_payment_choice: str = 'change',
        use_wallet: bool = False,
        wallet_amount: Decimal = Decimal('0'),
        payment_reference: str = '',
    ) -> Sale:
        """Finalise a holding sale: stock, journal entry, status=completed."""
        if holding.status != 'holding':
            raise ValidationError('This sale is not a holding invoice.')

        items_data = [
            {
                'product_id': item.product_id,
                'variant_id': item.variant_id,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
            }
            for item in holding.items.select_related('product', 'variant')
        ]
        if not items_data:
            raise ValidationError('Cannot checkout an empty cart.')

        from sales.module_settings import sales_validate_stock_before_sale

        validated_items = self.validate_sale_items(
            items_data,
            check_stock=sales_validate_stock_before_sale(),
            user=user,
        )

        subtotal = sum(item['subtotal'] for item in validated_items)
        tax_amount = holding.tax_amount or Decimal('0')
        discount_amount = holding.discount_amount or Decimal('0')
        delivery_cost = holding.delivery_cost or Decimal('0')
        total = subtotal + tax_amount - discount_amount + delivery_cost

        customer = holding.customer
        self._validate_checkout_payment(
            payment_method, amount_paid, total, customer, allow_partial
        )

        payment_result = self._prepare_sale_payment(
            customer=customer,
            sale_type='pos',
            total=total,
            amount_paid=amount_paid,
            allow_partial=allow_partial,
            excess_payment_choice=excess_payment_choice,
            use_wallet=use_wallet,
            wallet_amount_requested=wallet_amount,
        )

        holding.items.all().delete()
        for item_data in validated_items:
            SaleItem.objects.create(
                sale=holding,
                product=item_data['product'],
                variant=item_data['variant'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['subtotal'],
            )
            if (
                item_data['product'].track_stock
                and sales_validate_stock_before_sale()
            ):
                self._create_sale_stock_movements(
                    branch=branch or holding.branch,
                    user=user,
                    reference=holding.sale_number,
                    notes=f'Sale {holding.sale_number}',
                    product=item_data['product'],
                    variant=item_data['variant'],
                    quantity=item_data['quantity'],
                    unit_cost=item_data['unit_cost'],
                )

        holding.subtotal = subtotal
        holding.total = total
        holding.payment_method = payment_method
        holding.payment_reference = payment_reference
        holding.status = 'completed'
        holding.save()

        self._apply_sale_payment(customer, holding, user, payment_result)

        try:
            from accounting.services import create_sale_journal_entry
            create_sale_journal_entry(holding)
        except Exception as e:
            logger.error('Error creating journal entry for sale: %s', e)

        return holding
    
    @transaction.atomic
    def create_sale(self, sale_data: Dict[str, Any], items_data: List[Dict[str, Any]],
                   user, branch: Optional[Branch] = None,
                   *, validated_items: Optional[List[Dict[str, Any]]] = None) -> Sale:
        """Create a sale with items and update inventory"""
        from sales.module_settings import sales_validate_stock_before_sale

        if validated_items is None:
            validated_items = self.validate_sale_items(
                items_data,
                check_stock=sales_validate_stock_before_sale(),
                user=user,
            )

        from accounts.sensitive_edits import clamp_holding_financial_adjustments, user_may_edit_financial_fields

        tax_amount = sale_data.get('tax_amount', Decimal('0'))
        discount_amount = sale_data.get('discount_amount', Decimal('0'))
        if not user_may_edit_financial_fields(user):
            tax_amount, discount_amount = clamp_holding_financial_adjustments(
                user, tax_amount, discount_amount
            )
            sale_data['tax_amount'] = tax_amount
            sale_data['discount_amount'] = discount_amount
            sale_data['delivery_cost'] = Decimal('0')

        # Calculate totals
        subtotal = sum(item['subtotal'] for item in validated_items)
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
            status='completed',
            branch=branch,
            cashier=user,
            customer=sale_data.get('customer'),
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total=total,
            delivery_method=sale_data.get('delivery_method'),
            delivery_cost=delivery_cost,
            shipping_address=sale_data.get('shipping_address'),
            shipping_location=sale_data.get('shipping_location'),
            payment_method=payment_method,
            payment_reference=sale_data.get('payment_reference', ''),
            amount_paid=amount_paid,
            change=change,
            notes=sale_data.get('notes', ''),
        )
        
        # Create sale items. Stock is mutated exclusively by StockMovement.save()
        # below — see inventory/models.py. Doing both here would double-decrement.
        for item_data in validated_items:
            SaleItem.objects.create(
                sale=sale,
                product=item_data['product'],
                variant=item_data['variant'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['subtotal']
            )

            if (
                item_data['product'].track_stock
                and sales_validate_stock_before_sale()
            ):
                self._create_sale_stock_movements(
                    branch=branch,
                    user=user,
                    reference=sale.sale_number,
                    notes=f'Sale {sale.sale_number}',
                    product=item_data['product'],
                    variant=item_data['variant'],
                    quantity=item_data['quantity'],
                    unit_cost=item_data['unit_cost'],
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
        queryset = self.model.objects.filter(status='completed')
        
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

    def resolve_customer(self, customer_id: Optional[int]) -> Optional[Customer]:
        if not customer_id:
            return None
        try:
            return Customer.objects.get(id=customer_id, is_active=True)
        except Customer.DoesNotExist:
            logger.warning('Customer %s not found for sale', customer_id)
            return None

    def resolve_sale_branch(self, request, branch_id: Optional[int] = None) -> Optional[Branch]:
        if not is_branch_support_enabled():
            return None
        current_branch = get_current_branch(request)
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id, is_active=True)
                tenant = get_current_tenant(request)
                if tenant and branch.tenant != tenant:
                    raise ValidationError('Branch does not belong to current tenant')
                return branch
            except Branch.DoesNotExist:
                return current_branch
        if not current_branch:
            raise ValidationError('No branch selected. Please select a branch first.')
        return current_branch

    def _validate_checkout_payment(
        self,
        payment_method: str,
        amount_paid: Decimal,
        total: Decimal,
        customer: Optional[Customer],
        allow_partial: bool,
    ) -> None:
        if payment_method not in ('cash', 'mpesa', 'card'):
            return
        if amount_paid <= 0:
            raise ValidationError('Enter the amount received from the customer.')
        if amount_paid < total and not allow_partial:
            raise ValidationError(
                f'Amount received ({amount_paid}) is less than total ({total}). '
                'Select a customer and allow partial payment, or collect the full amount.'
            )
        if amount_paid < total and allow_partial and not customer:
            raise ValidationError('Customer required for partial payment.')

    def _prepare_sale_payment(
        self,
        *,
        customer: Optional[Customer],
        sale_type: str,
        total: Decimal,
        amount_paid: Decimal,
        allow_partial: bool,
        excess_payment_choice: str,
        use_wallet: bool,
        wallet_amount_requested: Decimal,
    ) -> Dict[str, Any]:
        wallet_amount_used = Decimal('0')
        wallet_credit_added = Decimal('0')
        change = Decimal('0')
        pending_debt = None

        if customer and use_wallet and customer.wallet_balance > 0:
            if wallet_amount_requested > 0:
                wallet_amount_used = min(wallet_amount_requested, customer.wallet_balance, total)
            else:
                wallet_amount_used = min(customer.wallet_balance, total)

        if sale_type in ('pos', 'normal'):
            total_payment = amount_paid + wallet_amount_used
            change = total_payment - total

            if change < 0:
                if not allow_partial:
                    raise ValidationError(
                        f'Total payment ({total_payment}) is less than total ({total}). '
                        f'Amount paid: {amount_paid}, Wallet used: {wallet_amount_used}. '
                        'Please select a customer and allow partial payment to proceed.'
                    )
                if not customer:
                    raise ValidationError('Customer must be selected to allow partial payment')
                pending_debt = abs(change)
                change = Decimal('0')
            elif change > 0 and excess_payment_choice == 'wallet' and customer:
                wallet_credit_added = change
                change = Decimal('0')

        return {
            'wallet_amount_used': wallet_amount_used,
            'wallet_credit_added': wallet_credit_added,
            'change': max(change, Decimal('0')),
            'pending_debt': pending_debt,
            'amount_paid_recorded': amount_paid + wallet_amount_used,
        }

    def _apply_sale_payment(
        self,
        customer: Optional[Customer],
        sale: Sale,
        user,
        payment_result: Dict[str, Any],
    ) -> None:
        if not customer:
            sale.amount_paid = payment_result['amount_paid_recorded']
            sale.change = payment_result['change']
            sale.save(update_fields=['amount_paid', 'change', 'updated_at'])
            return

        wallet_amount_used = payment_result['wallet_amount_used']
        if wallet_amount_used > 0:
            customer.wallet_balance -= wallet_amount_used
            customer.save(update_fields=['wallet_balance', 'updated_at'])
            CustomerWalletTransaction.objects.create(
                customer=customer,
                transaction_type='debit',
                source_type='payment',
                amount=wallet_amount_used,
                balance_after=customer.wallet_balance,
                sale=sale,
                reference=sale.sale_number,
                notes=f'Used {wallet_amount_used} from wallet for sale',
                created_by=user,
            )

        pending_debt = payment_result.get('pending_debt')
        if pending_debt:
            customer.wallet_balance -= pending_debt
            customer.save(update_fields=['wallet_balance', 'updated_at'])
            CustomerWalletTransaction.objects.create(
                customer=customer,
                transaction_type='debit',
                source_type='debt',
                amount=pending_debt,
                balance_after=customer.wallet_balance,
                sale=sale,
                reference=sale.sale_number,
                notes=(
                    f'Unpaid balance from sale added to customer debt '
                    f'(wallet balance: {customer.wallet_balance})'
                ),
                created_by=user,
            )

        wallet_credit_added = payment_result['wallet_credit_added']
        if wallet_credit_added > 0:
            customer.wallet_balance += wallet_credit_added
            customer.save(update_fields=['wallet_balance', 'updated_at'])
            CustomerWalletTransaction.objects.create(
                customer=customer,
                transaction_type='credit',
                source_type='overpayment',
                amount=wallet_credit_added,
                balance_after=customer.wallet_balance,
                sale=sale,
                reference=sale.sale_number,
                notes='Overpayment from sale added to wallet',
                created_by=user,
            )

        sale.customer = customer
        sale.amount_paid = payment_result['amount_paid_recorded']
        sale.change = payment_result['change']
        sale.save(update_fields=['customer', 'amount_paid', 'change', 'updated_at'])

    def _maybe_create_invoice_for_sale(
        self,
        sale: Sale,
        validated_data: Dict[str, Any],
        customer: Optional[Customer],
        user,
        amount_paid: Decimal,
    ) -> Optional[Invoice]:
        sale_type = validated_data.get('sale_type', 'pos')
        create_invoice = validated_data.get('create_invoice', False)
        if sale_type != 'normal' and not create_invoice:
            return None

        if not sale.items.exists():
            raise ValidationError('Cannot create invoice: Sale must have at least one item')

        payment_method = validated_data.get('payment_method', 'cash')
        customer_name = validated_data.get('customer_name', '') or ''
        customer_email = validated_data.get('customer_email', '') or ''
        customer_phone = validated_data.get('customer_phone', '') or ''
        customer_address = validated_data.get('customer_address', '') or ''
        due_date = validated_data.get('due_date')
        notes = validated_data.get('notes', '') or ''

        if customer:
            customer_name = customer.name or customer_name
            customer_email = customer.email or customer_email
            customer_phone = customer.phone or customer_phone
            customer_address = customer.address or customer_address
        elif not customer_name:
            if payment_method == 'cash':
                customer_name = 'Cash Customer'
            elif validated_data.get('create_payment_plan'):
                customer_name = 'Walk-in Customer'
            else:
                customer_name = 'Customer'

        invoice_service = InvoiceService()
        invoice = invoice_service.create_invoice_from_sale(
            sale,
            customer=customer,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_address=customer_address,
            due_date=due_date,
            notes=notes,
            user=user,
            amount_paid=amount_paid,
        )

        if validated_data.get('create_payment_plan') and invoice.balance > 0:
            number_of_installments = validated_data.get('number_of_installments')
            frequency = validated_data.get('installment_frequency')
            start_date = validated_data.get('payment_plan_start_date')

            if not number_of_installments or number_of_installments < 1:
                raise ValidationError(
                    'Number of installments is required and must be at least 1 for payment plans'
                )
            if not frequency:
                raise ValidationError('Installment frequency is required for payment plans')
            if not start_date:
                raise ValidationError('Payment plan start date is required for payment plans')

            invoice_service.create_payment_plan(
                invoice,
                number_of_installments,
                frequency,
                start_date,
                user=user,
            )

        return invoice

    @transaction.atomic
    def create_sale_from_validated_data(
        self,
        validated_data: Dict[str, Any],
        user,
        request,
    ) -> Dict[str, Any]:
        """Orchestrate sale creation: items, payment, wallet, optional invoice."""
        from sales.module_settings import sales_validate_stock_before_sale

        branch = self.resolve_sale_branch(request, validated_data.get('branch_id'))
        customer = self.resolve_customer(validated_data.get('customer_id'))

        items_data = validated_data['items']
        payment_method = validated_data.get('payment_method', 'cash')
        amount_paid_value = validated_data.get('amount_paid', 0)
        amount_paid = (
            Decimal(str(amount_paid_value)) if amount_paid_value is not None else Decimal('0')
        )
        tax_amount = Decimal(str(validated_data.get('tax_amount', 0)))
        discount_amount = Decimal(str(validated_data.get('discount_amount', 0)))
        delivery_method = validated_data.get('delivery_method', '') or None
        delivery_cost = Decimal(str(validated_data.get('delivery_cost', 0)))
        sale_type = validated_data.get('sale_type', 'pos')

        from accounts.sensitive_edits import (
            clamp_holding_financial_adjustments,
            user_may_edit_financial_fields,
        )

        tax_amount, discount_amount = clamp_holding_financial_adjustments(
            user, tax_amount, discount_amount
        )
        if not user_may_edit_financial_fields(user):
            delivery_cost = Decimal('0')

        validated_items = self.validate_sale_items(
            items_data,
            check_stock=sales_validate_stock_before_sale(),
            user=user,
        )
        subtotal = sum(item['subtotal'] for item in validated_items)
        total = subtotal + tax_amount - discount_amount + delivery_cost

        payment_result = self._prepare_sale_payment(
            customer=customer,
            sale_type=sale_type,
            total=total,
            amount_paid=amount_paid,
            allow_partial=validated_data.get('allow_partial_payment', False),
            excess_payment_choice=validated_data.get('excess_payment_choice', 'change'),
            use_wallet=validated_data.get('use_wallet', False),
            wallet_amount_requested=Decimal(str(validated_data.get('wallet_amount', 0) or 0)),
        )

        sale_data = {
            'sale_type': sale_type,
            'payment_method': payment_method,
            'payment_reference': validated_data.get('payment_reference', ''),
            'amount_paid': amount_paid,
            'notes': validated_data.get('notes', ''),
            'tax_amount': tax_amount,
            'discount_amount': discount_amount,
            'delivery_method': delivery_method,
            'delivery_cost': delivery_cost,
            'customer': customer,
        }

        sale = self.create_sale(
            sale_data,
            items_data,
            user,
            branch,
            validated_items=validated_items,
        )
        self._apply_sale_payment(customer, sale, user, payment_result)

        invoice = self._maybe_create_invoice_for_sale(
            sale,
            validated_data,
            customer,
            user,
            amount_paid,
        )

        result = {
            'sale': sale,
            'invoice': invoice,
            'wallet_amount_used': payment_result['wallet_amount_used'],
            'wallet_credit_added': payment_result['wallet_credit_added'],
        }
        if customer:
            customer.refresh_from_db()
            result['wallet_balance'] = customer.wallet_balance
            if payment_result['wallet_credit_added'] > 0:
                result['message'] = (
                    f'Sale completed. {payment_result["wallet_credit_added"]} KES added to customer wallet.'
                )
        return result

    @transaction.atomic
    def cancel_holding_sale(self, holding: Sale) -> Sale:
        if holding.status != 'holding':
            raise ValidationError('Only holding invoices can be cancelled.')
        holding.status = 'cancelled'
        holding.save(update_fields=['status', 'updated_at'])
        return holding


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
