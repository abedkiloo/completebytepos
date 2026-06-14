from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q, Sum
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from django.http import HttpResponse
from .models import Sale, SaleItem, Invoice, InvoiceItem, Payment, Customer, PaymentPlan, PaymentReminder, CustomerWalletTransaction
from .serializers import (
    SaleSerializer, SaleCreateSerializer,
    HoldingSaleSerializer, CheckoutHoldingSerializer,
    SaleRefundCreateSerializer, SaleRefundSerializer,
    InvoiceSerializer, InvoiceCreateSerializer,
    PaymentSerializer, PaymentCreateSerializer,
    CustomerSerializer, CustomerListSerializer
)
from .refunds import SaleRefundService
from products.models import Product, ProductVariant
from products.status_rules import get_operational_product, get_operational_variant
from inventory.models import StockMovement
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
from .services import SaleService, InvoiceService, PaymentService, CustomerService
from .module_settings import sales_validate_stock_before_sale
from accounts.permissions import RequirePermPerAction
from utils.audit_mixin import AuditedModelViewSetMixin
from utils.validation_errors import validation_error_message
from utils.pdf_generator import create_invoice_pdf
import logging

logger = logging.getLogger(__name__)


# RBAC maps. Note: SaleViewSet does NOT include 'destroy' here because we
# disable DELETE on Sales at the http_method_names level for audit-trail
# integrity (refunds/voids should be modelled separately, not DB deletes).
SALES_PERMS = RequirePermPerAction('sales', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'receipt': 'view',
    'dashboard_summary': 'view',
    'active_holding': 'view',
    'save_holding': 'create',
    'checkout': 'create',
    'cancel_holding': 'update',
    'refund': 'refund',
})

CUSTOMERS_PERMS = RequirePermPerAction('customers', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
})

INVOICES_PERMS = RequirePermPerAction('invoicing', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'send': 'update',
    'statistics': 'view',
    'download_pdf': 'view',
    # 'destroy' deliberately omitted - DELETE disabled at http_method_names.
})

PAYMENTS_PERMS = RequirePermPerAction('invoicing', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    # Payments are immutable financial events - no update or destroy.
})


class SaleViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Sale.objects.all().select_related('cashier').prefetch_related('items__product')
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated, SALES_PERMS]
    audit_module = 'sales'
    # Sales are part of the audit trail - never deletable via the API. Use a
    # void/refund flow instead (modelled separately).
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    ordering = ['-created_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sale_service = SaleService()
        self.invoice_service = InvoiceService()
        self.refund_service = SaleRefundService()

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['branch_id', 'show_all', 'date_from', 'date_to', 'payment_method', 'search']:
            if param in query_params:
                filters[param] = query_params.get(param)

        # Draft (holding) sales are hidden from list/history by default, but detail
        # routes such as checkout and cancel-holding must resolve them by pk.
        if getattr(self, 'action', None) in (
            'retrieve',
            'update',
            'partial_update',
            'checkout',
            'cancel_holding',
        ):
            filters['include_holding'] = True
        
        return self.sale_service.build_queryset(filters, request=self.request)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a sale with items and update inventory."""
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = self.sale_service.create_sale_from_validated_data(
                serializer.validated_data,
                request.user,
                request,
            )
        except ValidationError as e:
            return Response(
                {'error': validation_error_message(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sale = result['sale']
        response_data = SaleSerializer(sale).data
        invoice = result.get('invoice')
        if invoice:
            response_data['invoice'] = InvoiceSerializer(invoice).data

        if result.get('wallet_balance') is not None:
            response_data['wallet_balance'] = str(result['wallet_balance'])
            response_data['wallet_amount_used'] = str(result['wallet_amount_used'])
            if result.get('wallet_credit_added', Decimal('0')) > 0:
                response_data['wallet_credit_added'] = str(result['wallet_credit_added'])
                response_data['message'] = result.get('message', '')

        from utils.audit_events import log_sale_completed

        log_sale_completed(request, sale, source='create')

        return Response(response_data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return self._update_sale(request, partial=False, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self._update_sale(request, partial=True, **kwargs)

    def _update_sale(self, request, *, partial, **kwargs):
        """Holding drafts use default update; completed sales are immutable unless optional P3 is on."""
        sale = self.get_object()
        if sale.status == 'completed':
            from approvals.sales_policy import completed_sale_direct_edit_blocked
            from approvals.sales_integration import queue_completed_sale_edit

            if completed_sale_direct_edit_blocked():
                return Response(
                    {'error': 'Completed sales are immutable.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            serializer = self.get_serializer(sale, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            proposed = dict(serializer.validated_data)
            try:
                change = queue_completed_sale_edit(
                    request,
                    sale,
                    proposed,
                    reason=request.data.get('reason') or request.data.get('change_reason') or '',
                )
            except ValidationError as e:
                detail = validation_error_message(e)
                return Response(
                    e.message_dict if hasattr(e, 'message_dict') else {'error': detail},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    'message': 'Change submitted for approval — not yet active.',
                    'pending_change': {
                        'id': change.id,
                        'action_type': change.action_type,
                        'status': change.status,
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )
        kwargs['partial'] = partial
        return super().update(request, **kwargs)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        """Get receipt data for a sale"""
        sale = self.get_object()
        serializer = self.get_serializer(sale)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='dashboard-summary')
    def dashboard_summary(self, request):
        """Lightweight today totals for the home screen; month only with reports.view."""
        from accounts.permissions import _has_permission

        today = timezone.now().date()
        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))

        base = self.sale_service.build_queryset({}, request=request).filter(status='completed')
        today_sales = base.filter(created_at__gte=start_of_day)

        payload = {
            'today': {
                'sales_count': today_sales.count(),
                'total': float(today_sales.aggregate(total=Sum('total'))['total'] or 0),
            },
        }
        if _has_permission(request, 'reports', 'view'):
            month_sales = base.filter(created_at__gte=start_of_month)
            payload['month'] = {
                'total': float(month_sales.aggregate(total=Sum('total'))['total'] or 0),
            }
        return Response(payload)

    def _resolve_branch(self, request, branch_id=None):
        try:
            return self.sale_service.resolve_sale_branch(request, branch_id)
        except ValidationError:
            return None

    @action(detail=False, methods=['get'], url_path='active-holding')
    def active_holding(self, request):
        """Return the cashier's open holding invoice for the current branch."""
        branch = self._resolve_branch(request)
        holding = self.sale_service.get_active_holding(request.user, branch)
        if not holding:
            return Response({'holding': None})
        return Response({'holding': SaleSerializer(holding).data})

    @action(detail=False, methods=['post'], url_path='holding')
    @transaction.atomic
    def save_holding(self, request):
        """Create or update a holding invoice (draft) without moving stock."""
        serializer = HoldingSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        customer = self.sale_service.resolve_customer(data.get('customer_id'))
        if data.get('customer_id') and customer is None:
            return Response(
                {'error': 'Customer not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            branch = self.sale_service.resolve_sale_branch(request, data.get('branch_id'))
        except ValidationError as e:
            return Response(
                {'error': validation_error_message(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        created = not data.get('holding_id')
        try:
            holding = self.sale_service.save_holding_sale(
                request.user,
                data.get('items', []),
                branch=branch,
                customer=customer,
                tax_amount=Decimal(str(data.get('tax_amount', 0))),
                discount_amount=Decimal(str(data.get('discount_amount', 0))),
                notes=data.get('notes', ''),
                holding_id=data.get('holding_id'),
            )
        except ValidationError as e:
            return Response(
                {'error': validation_error_message(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from utils.audit_events import log_holding_saved

        log_holding_saved(request, holding, created=created)

        return Response(SaleSerializer(holding).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def checkout(self, request, pk=None):
        """Complete a holding sale: stock, accounting, receipt."""
        holding = self.get_object()
        serializer = CheckoutHoldingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            branch = holding.branch or self.sale_service.resolve_sale_branch(request)
        except ValidationError as e:
            return Response(
                {'error': validation_error_message(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sale = self.sale_service.complete_holding_sale(
                holding,
                payment_method=serializer.validated_data['payment_method'],
                payment_reference=serializer.validated_data.get('payment_reference', ''),
                amount_paid=Decimal(str(serializer.validated_data.get('amount_paid', 0))),
                user=request.user,
                branch=branch,
                allow_partial=serializer.validated_data.get('allow_partial_payment', False),
                excess_payment_choice=serializer.validated_data.get('excess_payment_choice', 'change'),
                use_wallet=serializer.validated_data.get('use_wallet', False),
                wallet_amount=Decimal(str(serializer.validated_data.get('wallet_amount', 0))),
            )
        except ValidationError as e:
            return Response(
                {'error': validation_error_message(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from utils.audit_events import log_sale_completed

        log_sale_completed(request, sale, source='checkout')

        return Response(SaleSerializer(sale).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def refund(self, request, pk=None):
        """Refund a completed sale (full or partial). Original sale row stays for audit."""
        sale = self.get_object()
        serializer = SaleRefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            refund = self.refund_service.create_refund(
                sale,
                reason=data['reason'],
                user=request.user,
                items=data.get('items'),
                full=data.get('full', False),
            )
        except ValidationError as e:
            payload = getattr(e, 'message_dict', None) or {'error': validation_error_message(e)}
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        from utils.audit_events import log_sale_refunded

        sale.refresh_from_db()
        log_sale_refunded(request, sale, refund)
        return Response(
            SaleRefundSerializer(refund).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='cancel-holding')
    @transaction.atomic
    def cancel_holding(self, request, pk=None):
        """Discard a holding invoice without completing it."""
        holding = self.get_object()
        try:
            self.sale_service.cancel_holding_sale(holding)
        except ValidationError as e:
            return Response(
                {'error': validation_error_message(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from utils.audit_events import log_holding_cancelled

        log_holding_cancelled(request, holding)
        return Response({'message': 'Holding invoice cancelled.', 'sale_number': holding.sale_number})


class CustomerViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, CUSTOMERS_PERMS]
    audit_module = 'customers'
    ordering = ['name']

    @staticmethod
    def _feature_disabled_response(feature_label: str):
        return Response(
            {'error': f'{feature_label} is disabled in store settings.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerListSerializer
        return CustomerSerializer

    def perform_create(self, serializer):
        from utils.audit_helpers import audited_perform_create

        customer = audited_perform_create(self, serializer)
        if self.request.user and self.request.user.is_authenticated:
            customer.created_by = self.request.user
            customer.save(update_fields=['created_by'])

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a customer with proper error handling"""
        from sales.customer_module_settings import customers_enable_create

        if not customers_enable_create():
            return self._feature_disabled_response('Creating customers')
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except serializers.ValidationError:
            # Re-raise validation errors so DRF can handle them properly
            raise
        except Exception as e:
            logger.error(f"Error creating customer: {e}", exc_info=True)
            return Response(
                {'error': f'Failed to create customer: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update a customer with proper error handling"""
        from sales.customer_module_settings import customers_enable_edit

        if not customers_enable_edit():
            return self._feature_disabled_response('Editing customers')
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except serializers.ValidationError:
            # Re-raise validation errors so DRF can handle them properly
            raise
        except Exception as e:
            logger.error(f"Error updating customer: {e}", exc_info=True)
            return Response(
                {'error': f'Failed to update customer: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        from sales.customer_module_settings import customers_enable_delete

        if not customers_enable_delete():
            return self._feature_disabled_response('Deleting customers')
        return super().destroy(request, *args, **kwargs)

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
            try:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')
            except (AttributeError, ValueError):
                pass  # Ignore invalid is_active value
        
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)
        
        if search:
            search = search.strip()
            if search:  # Only search if not empty after stripping
                try:
                    queryset = queryset.filter(
                        Q(name__icontains=search) |
                        Q(customer_code__icontains=search) |
                        Q(email__icontains=search) |
                        Q(phone__icontains=search) |
                        Q(tax_id__icontains=search)
                    )
                except Exception:
                    # If search fails, return empty queryset rather than crashing
                    queryset = queryset.none()
        
        return queryset


class InvoiceViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Invoice.objects.all().select_related('sale', 'created_by').prefetch_related(
        'items__product', 'items__variant', 'payments'
    )
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, INVOICES_PERMS]
    audit_module = 'invoicing'
    # Invoices are part of the audit trail - never deletable via the API.
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
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
        from sales.invoicing_access import invoice_creation_allowed

        if not invoice_creation_allowed():
            return Response(
                {'error': 'Invoice creation is disabled in module settings.'},
                status=status.HTTP_403_FORBIDDEN,
            )

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
            
            from sales.invoice_items import normalize_invoice_items, resolve_product_id

            items_data = normalize_invoice_items(items_data)

            # Create invoice items - validate each item
            created_items = []
            for item_data in items_data:
                product_id = resolve_product_id(item_data)
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
                    product = get_operational_product(product_id)
                except Product.DoesNotExist:
                    return Response(
                        {'error': f'Product with id {product_id} not found or is inactive'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                variant = None
                if variant_id:
                    try:
                        variant = get_operational_variant(variant_id, product)
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
        
        # Accounting: draft invoices do not post until sent (settlement is via payments).
        response_serializer = InvoiceSerializer(invoice)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Mark invoice as sent and recognize receivable in accounting."""
        from sales.invoicing_access import invoice_tracking_allowed

        if not invoice_tracking_allowed():
            return Response(
                {'error': 'Invoice tracking is disabled in module settings.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        invoice = self.get_object()
        if invoice.status == 'draft':
            invoice.status = 'sent'
            invoice.save()
            if not invoice.sale:
                try:
                    from accounting.views import create_invoice_journal_entry

                    create_invoice_journal_entry(invoice)
                except Exception as e:
                    logger.error(f"Error creating journal entry for invoice: {e}")
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
        try:
            pdf_buffer = create_invoice_pdf(invoice)
        except Exception as e:
            logger.exception('Invoice PDF generation failed for %s', invoice.invoice_number)
            return Response(
                {'error': f'Could not generate PDF: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
        )
        return response


class PaymentViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related('invoice', 'recorded_by')
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, PAYMENTS_PERMS]
    audit_module = 'invoicing'
    # Payments are immutable financial events - never mutable via the API.
    http_method_names = ['get', 'post', 'head', 'options']
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
        """Create a payment against an invoice (settlement)."""
        from sales.invoicing_access import payment_tracking_allowed

        if not payment_tracking_allowed():
            return Response(
                {'error': 'Payment tracking is disabled in module settings.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = dict(request.data)
        if 'invoice' in payload and 'invoice_id' not in payload:
            payload['invoice_id'] = payload['invoice']

        serializer = PaymentCreateSerializer(data=payload)
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
        
        if amount <= 0:
            return Response(
                {'error': 'Payment amount must be greater than zero.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if payment exceeds balance (partial payments allowed)
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
