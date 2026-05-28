from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import datetime, timedelta
from sales.models import Sale, SaleItem, Invoice, Customer, Payment
from products.models import Product
from inventory.models import StockMovement
from expenses.models import Expense
from income.models import Income
from accounts.permissions import RequirePermPerAction
from .services import ReportDashboardService, resolve_period


REPORTS_PERMS = RequirePermPerAction('reports', {
    'dashboard': 'view',
    'sales': 'view',
    'products': 'view',
    'inventory': 'view',
    'purchase': 'view',
    'invoice': 'view',
    'supplier': 'view',
    'customer': 'view',
    'expense': 'view',
    'income': 'view',
    'tax': 'view',
    'profit_loss': 'view',
    'annual': 'view',
    'sales_overview': 'view',
    'top_products': 'view',
    'cash_and_payments': 'view',
    'inventory_health': 'view',
    'customer_outstanding': 'view',
})


class ReportViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, REPORTS_PERMS]
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Dashboard summary data with all metrics"""
        return Response(ReportDashboardService.get_dashboard_summary())

    @action(detail=False, methods=['get'])
    def sales(self, request):
        """Sales report with date filtering"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        queryset = Sale.objects.all()
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        summary = queryset.aggregate(
            total_sales=Count('id'),
            total_revenue=Sum('total'),
            total_items=Sum('items__quantity'),
            total_subtotal=Sum('subtotal'),
            total_tax=Sum('tax_amount'),
            total_discount=Sum('discount_amount'),
        )
        
        # Sales by payment method
        by_payment = queryset.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('total')
        )
        
        # Daily sales breakdown - use TruncDate so this works on SQLite,
        # Postgres and MySQL alike (the previous .extra() with a literal
        # date(...) call was SQLite-only).
        daily_sales = list(
            queryset.annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'), total=Sum('total'))
            .order_by('-day')
        )
        daily_sales = [
            {
                'day': row['day'].isoformat() if row['day'] else None,
                'count': row['count'],
                'total': float(row['total'] or 0),
            }
            for row in daily_sales
        ]

        return Response({
            'summary': summary,
            'by_payment_method': list(by_payment),
            'daily_breakdown': daily_sales,
        })

    @action(detail=False, methods=['get'])
    def products(self, request):
        """Product sales report"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        queryset = SaleItem.objects.all()
        
        if date_from:
            queryset = queryset.filter(sale__created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(sale__created_at__lte=date_to)
        
        product_sales = queryset.values(
            'product__id',
            'product__name', 
            'product__sku',
            'product__category__name'
        ).annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum('subtotal'),
            avg_price=Sum('subtotal') / Sum('quantity')
        ).order_by('-revenue')
        
        return Response({
            'products': list(product_sales),
        })

    @action(detail=False, methods=['get'])
    def inventory(self, request):
        """Inventory report"""
        low_stock = Product.objects.filter(
            stock_quantity__lte=F('low_stock_threshold'),
            is_active=True,
            track_stock=True
        )
        
        out_of_stock = Product.objects.filter(
            stock_quantity=0,
            is_active=True,
            track_stock=True
        )
        
        total_inventory_value = Product.objects.filter(
            track_stock=True
        ).aggregate(
            total_value=Sum(F('stock_quantity') * F('cost'))
        )['total_value'] or 0
        
        total_products_value = Product.objects.filter(
            is_active=True,
            track_stock=True
        ).aggregate(
            total_value=Sum(F('stock_quantity') * F('price'))
        )['total_value'] or 0
        
        # Recent stock movements
        recent_movements = StockMovement.objects.select_related('product', 'user').order_by('-created_at')[:20]
        
        movements_data = []
        for movement in recent_movements:
            movements_data.append({
                'id': movement.id,
                'product_name': movement.product.name,
                'product_sku': movement.product.sku,
                'movement_type': movement.movement_type,
                'quantity': movement.quantity,
                'unit_cost': float(movement.unit_cost or 0),
                'total_cost': float(movement.total_cost or 0),
                'reference': movement.reference,
                'user': movement.user.username if movement.user else None,
                'created_at': movement.created_at.isoformat(),
            })
        
        return Response({
            'low_stock_count': low_stock.count(),
            'out_of_stock_count': out_of_stock.count(),
            'total_inventory_value': float(total_inventory_value),
            'total_products_value': float(total_products_value),
            'recent_movements': movements_data,
        })

    @action(detail=False, methods=['get'])
    def purchase(self, request):
        """Purchase report from stock movements"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        queryset = StockMovement.objects.filter(movement_type='purchase')
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        summary = queryset.aggregate(
            total_purchases=Count('id'),
            total_amount=Sum('total_cost'),
            total_items=Sum('quantity'),
        )
        
        purchases = queryset.select_related('product').order_by('-created_at')[:100]
        purchases_data = []
        for purchase in purchases:
            purchases_data.append({
                'date': purchase.created_at.isoformat(),
                'product_name': purchase.product.name,
                'quantity': purchase.quantity,
                'unit_cost': float(purchase.unit_cost or 0),
                'total_cost': float(purchase.total_cost or 0),
            })
        
        return Response({
            'summary': summary,
            'purchases': purchases_data,
        })

    @action(detail=False, methods=['get'])
    def invoice(self, request):
        """Invoice report"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        queryset = Invoice.objects.all()
        
        if date_from:
            queryset = queryset.filter(issued_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(issued_date__lte=date_to)
        
        # Calculate paid amount from invoice amount_paid field
        summary = queryset.aggregate(
            total_invoices=Count('id'),
            total_amount=Sum('total'),
            paid_amount=Sum('amount_paid'),
        )
        summary['outstanding_amount'] = float(summary['total_amount'] or 0) - float(summary['paid_amount'] or 0)
        
        invoices = queryset.select_related('customer').order_by('-issued_date')[:100]
        invoices_data = []
        for invoice in invoices:
            invoices_data.append({
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'customer_name': invoice.customer_name or (invoice.customer.name if invoice.customer else 'N/A'),
                'issued_date': invoice.issued_date.isoformat(),
                'total': float(invoice.total),
                'status': invoice.status,
            })
        
        return Response({
            'summary': summary,
            'invoices': invoices_data,
        })

    @action(detail=False, methods=['get'])
    def supplier(self, request):
        """Supplier report - based on purchase movements"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        queryset = StockMovement.objects.filter(movement_type='purchase')
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Group by supplier (from reference field or product supplier if available)
        supplier_data = queryset.values('reference').annotate(
            total_purchases=Sum('total_cost'),
            order_count=Count('id'),
        ).order_by('-total_purchases')
        
        suppliers = []
        for item in supplier_data:
            suppliers.append({
                'name': item['reference'] or 'Unknown Supplier',
                'total_purchases': float(item['total_purchases'] or 0),
                'order_count': item['order_count'],
                'avg_order_value': float(item['total_purchases'] or 0) / item['order_count'] if item['order_count'] > 0 else 0,
            })
        
        summary = {
            'total_suppliers': len(suppliers),
            'total_purchases': sum(s['total_purchases'] for s in suppliers),
        }
        
        return Response({
            'summary': summary,
            'suppliers': suppliers,
        })

    @action(detail=False, methods=['get'])
    def customer(self, request):
        """
        Customer report.

        Note: the ``Sale`` model has no direct ``customer`` FK - customer
        linkage flows through ``Invoice``. We aggregate via the Invoice table
        so this report actually returns real data (the previous
        ``sales.values('customer__id')`` query silently returned all-NULL
        groups).
        """
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        invoices_qs = Invoice.objects.exclude(customer__isnull=True)
        if date_from:
            invoices_qs = invoices_qs.filter(created_at__gte=date_from)
        if date_to:
            invoices_qs = invoices_qs.filter(created_at__lte=date_to)

        rows = list(
            invoices_qs.values('customer__id', 'customer__name')
            .annotate(
                total_purchases=Sum('total'),
                outstanding=Sum('balance'),
                order_count=Count('id'),
            )
            .order_by('-total_purchases')
        )

        customers = []
        for item in rows:
            last_invoice = (
                invoices_qs.filter(customer_id=item['customer__id'])
                .order_by('-created_at').first()
            )
            count = item['order_count'] or 0
            total = float(item['total_purchases'] or 0)
            customers.append({
                'id': item['customer__id'],
                'name': item['customer__name'] or 'Unknown',
                'total_purchases': total,
                'outstanding': float(item['outstanding'] or 0),
                'order_count': count,
                'avg_order_value': (total / count) if count else 0,
                'last_purchase': last_invoice.created_at.isoformat() if last_invoice else None,
            })

        summary = {
            'total_customers': len(customers),
            'total_sales': sum(c['total_purchases'] for c in customers),
            'total_outstanding': sum(c['outstanding'] for c in customers),
            'avg_order_value': (
                sum(c['total_purchases'] for c in customers) / len(customers)
                if customers else 0
            ),
        }

        return Response({
            'summary': summary,
            'customers': customers,
        })

    @action(detail=False, methods=['get'])
    def expense(self, request):
        """Expense report"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        queryset = Expense.objects.filter(status='approved')
        
        if date_from:
            queryset = queryset.filter(expense_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(expense_date__lte=date_to)
        
        summary = queryset.aggregate(
            total_expenses=Sum('amount'),
            expense_count=Count('id'),
            category_count=Count('category', distinct=True),
        )
        
        expenses = queryset.select_related('category').order_by('-expense_date')[:100]
        expenses_data = []
        for expense in expenses:
            expenses_data.append({
                'id': expense.id,
                'expense_date': expense.expense_date.isoformat(),
                'category_name': expense.category.name if expense.category else 'Uncategorized',
                'description': expense.description,
                'amount': float(expense.amount),
                'status': expense.status,
            })
        
        return Response({
            'summary': summary,
            'expenses': expenses_data,
        })

    @action(detail=False, methods=['get'])
    def income(self, request):
        """Income report"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        queryset = Income.objects.all()
        
        if date_from:
            queryset = queryset.filter(income_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(income_date__lte=date_to)
        
        summary = queryset.aggregate(
            total_income=Sum('amount'),
            income_count=Count('id'),
        )
        
        income = queryset.select_related('category').order_by('-income_date')[:100]
        income_data = []
        for item in income:
            income_data.append({
                'id': item.id,
                'income_date': item.income_date.isoformat(),
                'category_name': item.category.name if item.category else 'Uncategorized',
                'description': item.description,
                'amount': float(item.amount),
            })
        
        return Response({
            'summary': summary,
            'income': income_data,
        })

    @action(detail=False, methods=['get'])
    def tax(self, request):
        """Tax report"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        sales_queryset = Sale.objects.all()
        
        if date_from:
            sales_queryset = sales_queryset.filter(created_at__gte=date_from)
        if date_to:
            sales_queryset = sales_queryset.filter(created_at__lte=date_to)
        
        summary = sales_queryset.aggregate(
            total_tax=Sum('tax_amount'),
        )
        
        # Calculate average tax rate
        total_subtotal = sales_queryset.aggregate(total=Sum('subtotal'))['total'] or 0
        total_tax = summary['total_tax'] or 0
        tax_rate = (total_tax / total_subtotal * 100) if total_subtotal > 0 else 0
        summary['tax_rate'] = round(tax_rate, 2)
        
        # Tax breakdown by transaction
        tax_breakdown = []
        for sale in sales_queryset.order_by('-created_at')[:100]:
            if sale.tax_amount and sale.tax_amount > 0:
                tax_breakdown.append({
                    'date': sale.created_at.isoformat(),
                    'transaction_type': 'Sale',
                    'taxable_amount': float(sale.subtotal),
                    'tax_amount': float(sale.tax_amount),
                })
        
        return Response({
            'summary': summary,
            'tax_breakdown': tax_breakdown,
        })

    @action(detail=False, methods=['get'])
    def profit_loss(self, request):
        """Profit & Loss report"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        # Sales revenue
        sales_queryset = Sale.objects.all()
        if date_from:
            sales_queryset = sales_queryset.filter(created_at__gte=date_from)
        if date_to:
            sales_queryset = sales_queryset.filter(created_at__lte=date_to)
        
        total_revenue = sales_queryset.aggregate(total=Sum('total'))['total'] or 0
        
        # Expenses
        expenses_queryset = Expense.objects.filter(status='approved')
        if date_from:
            expenses_queryset = expenses_queryset.filter(expense_date__gte=date_from)
        if date_to:
            expenses_queryset = expenses_queryset.filter(expense_date__lte=date_to)
        
        total_expenses = expenses_queryset.aggregate(total=Sum('amount'))['total'] or 0
        
        # Purchases (cost of goods)
        purchases_queryset = StockMovement.objects.filter(movement_type='purchase')
        if date_from:
            purchases_queryset = purchases_queryset.filter(created_at__gte=date_from)
        if date_to:
            purchases_queryset = purchases_queryset.filter(created_at__lte=date_to)
        
        total_purchases = purchases_queryset.aggregate(total=Sum('total_cost'))['total'] or 0
        
        net_profit = float(total_revenue) - float(total_expenses) - float(total_purchases)
        profit_margin = (net_profit / float(total_revenue) * 100) if total_revenue > 0 else 0
        
        summary = {
            'total_revenue': float(total_revenue),
            'total_expenses': float(total_expenses),
            'total_purchases': float(total_purchases),
            'net_profit': float(net_profit),
            'profit_margin': round(profit_margin, 2),
        }
        
        # Monthly breakdown
        monthly_breakdown = []
        # Simplified - in production, you'd want proper month grouping
        for i in range(12):
            month_start = timezone.now().replace(month=i+1, day=1)
            month_end = timezone.now().replace(month=i+1, day=28)
            month_sales = sales_queryset.filter(created_at__gte=month_start, created_at__lte=month_end).aggregate(total=Sum('total'))['total'] or 0
            month_expenses = expenses_queryset.filter(expense_date__gte=month_start.date(), expense_date__lte=month_end.date()).aggregate(total=Sum('amount'))['total'] or 0
            monthly_breakdown.append({
                'month': month_start.strftime('%B %Y'),
                'revenue': float(month_sales),
                'expenses': float(month_expenses),
                'profit': float(month_sales) - float(month_expenses),
            })
        
        return Response({
            'summary': summary,
            'monthly_breakdown': monthly_breakdown,
        })

    @action(detail=False, methods=['get'])
    def annual(self, request):
        """Annual report"""
        year = int(request.query_params.get('year', timezone.now().year))
        
        start_date = timezone.make_aware(datetime(year, 1, 1))
        end_date = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
        
        # Sales
        sales_queryset = Sale.objects.filter(created_at__gte=start_date, created_at__lte=end_date)
        total_sales = sales_queryset.aggregate(total=Sum('total'))['total'] or 0
        
        # Expenses
        expenses_queryset = Expense.objects.filter(status='approved', expense_date__year=year)
        total_expenses = expenses_queryset.aggregate(total=Sum('amount'))['total'] or 0
        
        # Purchases
        purchases_queryset = StockMovement.objects.filter(movement_type='purchase', created_at__gte=start_date, created_at__lte=end_date)
        total_purchases = purchases_queryset.aggregate(total=Sum('total_cost'))['total'] or 0
        
        net_profit = float(total_sales) - float(total_expenses) - float(total_purchases)
        
        # Previous year for growth calculation
        prev_year = year - 1
        prev_start = timezone.make_aware(datetime(prev_year, 1, 1))
        prev_end = timezone.make_aware(datetime(prev_year, 12, 31, 23, 59, 59))
        prev_sales = Sale.objects.filter(created_at__gte=prev_start, created_at__lte=prev_end).aggregate(total=Sum('total'))['total'] or 0
        growth_rate = ((float(total_sales) - float(prev_sales)) / float(prev_sales) * 100) if prev_sales > 0 else 0
        
        summary = {
            'total_sales': float(total_sales),
            'total_expenses': float(total_expenses),
            'total_purchases': float(total_purchases),
            'net_profit': float(net_profit),
            'growth_rate': round(growth_rate, 2),
        }
        
        # Monthly data
        monthly_data = []
        for month in range(1, 13):
            month_start = timezone.make_aware(datetime(year, month, 1))
            if month == 12:
                month_end = timezone.make_aware(datetime(year, month, 31, 23, 59, 59))
            else:
                month_end = timezone.make_aware(datetime(year, month + 1, 1)) - timedelta(days=1)
            
            month_sales = sales_queryset.filter(created_at__gte=month_start, created_at__lte=month_end).aggregate(total=Sum('total'))['total'] or 0
            month_expenses = expenses_queryset.filter(expense_date__month=month).aggregate(total=Sum('amount'))['total'] or 0
            monthly_data.append({
                'month': month_start.strftime('%B'),
                'sales': float(month_sales),
                'expenses': float(month_expenses),
                'profit': float(month_sales) - float(month_expenses),
            })
        
        return Response({
            'summary': summary,
            'monthly_data': monthly_data,
        })

    # ------------------------------------------------------------------
    # New operational reports (Today / Week / Month aware, chart-ready).
    # These supersede the older 13 endpoints for the redesigned Reports
    # screen, but the originals remain for back-compat with existing
    # callers.
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'])
    def sales_overview(self, request):
        """
        Top-line sales metrics + per-day trend, gated by ?period=today|week|month.

        Returns:
          summary:   { sales_count, gross_revenue, items_sold, avg_ticket, tax, discount }
          by_payment_method: [{ method, count, total }]
          trend:     [{ date: 'YYYY-MM-DD', revenue, sales_count }]
        """
        start, end, label = resolve_period(request)
        qs = Sale.objects.all()
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)

        agg = qs.aggregate(
            sales_count=Count('id'),
            gross_revenue=Sum('total'),
            items_sold=Sum('items__quantity'),
            tax=Sum('tax_amount'),
            discount=Sum('discount_amount'),
        )

        gross = float(agg['gross_revenue'] or 0)
        count = agg['sales_count'] or 0
        avg_ticket = (gross / count) if count else 0.0

        by_pm = list(
            qs.values('payment_method')
            .annotate(count=Count('id'), total=Sum('total'))
            .order_by('-total')
        )
        for row in by_pm:
            row['method'] = row.pop('payment_method') or 'unknown'
            row['total'] = float(row['total'] or 0)

        # Daily trend via TruncDate so it works on SQLite, Postgres and MySQL.
        trend = list(
            qs.annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(revenue=Sum('total'), sales_count=Count('id'))
            .order_by('day')
        )
        trend = [
            {
                'date': row['day'].isoformat() if row['day'] else None,
                'revenue': float(row['revenue'] or 0),
                'sales_count': row['sales_count'] or 0,
            }
            for row in trend
        ]

        return Response({
            'period': label,
            'summary': {
                'sales_count': count,
                'gross_revenue': gross,
                'items_sold': int(agg['items_sold'] or 0),
                'avg_ticket': round(avg_ticket, 2),
                'tax': float(agg['tax'] or 0),
                'discount': float(agg['discount'] or 0),
            },
            'by_payment_method': by_pm,
            'trend': trend,
        })

    @action(detail=False, methods=['get'])
    def top_products(self, request):
        """Best-selling products in the chosen period.

        Returns top 10 by quantity + total revenue contribution, ready for a
        horizontal bar chart.
        """
        start, end, label = resolve_period(request)
        qs = SaleItem.objects.select_related('product', 'product__category')
        if start:
            qs = qs.filter(sale__created_at__gte=start)
        if end:
            qs = qs.filter(sale__created_at__lte=end)

        rows = list(
            qs.values('product__id', 'product__name', 'product__sku', 'product__category__name')
            .annotate(
                quantity_sold=Sum('quantity'),
                revenue=Sum('subtotal'),
                line_count=Count('id'),
            )
            .order_by('-quantity_sold')[:10]
        )

        items = [
            {
                'product_id': r['product__id'],
                'name': r['product__name'] or '(unnamed product)',
                'sku': r['product__sku'] or '',
                'category': r['product__category__name'] or 'Uncategorised',
                'quantity_sold': int(r['quantity_sold'] or 0),
                'revenue': float(r['revenue'] or 0),
                'line_count': r['line_count'] or 0,
            }
            for r in rows
        ]

        return Response({
            'period': label,
            'items': items,
        })

    @action(detail=False, methods=['get'])
    def cash_and_payments(self, request):
        """Money-in breakdown: sales tender + invoice payments, by method.

        Drives the cash-reconciliation tile (cash drawer expected, M-Pesa
        expected, etc).
        """
        start, end, label = resolve_period(request)

        sales = Sale.objects.all()
        payments = Payment.objects.all()
        if start:
            sales = sales.filter(created_at__gte=start)
            payments = payments.filter(payment_date__gte=start)
        if end:
            sales = sales.filter(created_at__lte=end)
            payments = payments.filter(payment_date__lte=end)

        sales_by_method = {
            (row['payment_method'] or 'unknown'): float(row['total'] or 0)
            for row in sales.values('payment_method').annotate(total=Sum('total'))
        }
        payments_by_method = {
            (row['payment_method'] or 'unknown'): float(row['total'] or 0)
            for row in payments.values('payment_method').annotate(total=Sum('amount'))
        }

        all_methods = sorted(set(sales_by_method) | set(payments_by_method))
        rows = []
        total_in = 0.0
        for m in all_methods:
            sales_total = sales_by_method.get(m, 0.0)
            payments_total = payments_by_method.get(m, 0.0)
            method_total = sales_total + payments_total
            total_in += method_total
            rows.append({
                'method': m,
                'sales_total': sales_total,
                'payments_total': payments_total,
                'total': method_total,
            })

        return Response({
            'period': label,
            'summary': {
                'total_in': total_in,
                'sales_total': float(sales.aggregate(t=Sum('total'))['t'] or 0),
                'payments_total': float(payments.aggregate(t=Sum('amount'))['t'] or 0),
            },
            'by_method': rows,
        })

    @action(detail=False, methods=['get'])
    def inventory_health(self, request):
        """Stock health snapshot: low / out / value / recent movements.

        Period-aware only in the "recent movements" trend (the absolute stock
        levels are always current — that's how a snapshot works).
        """
        start, end, label = resolve_period(request)

        products = Product.objects.filter(is_active=True)

        low_stock_count = products.filter(
            track_stock=True,
            stock_quantity__gt=0,
            stock_quantity__lte=F('low_stock_threshold'),
        ).count()
        out_of_stock_count = products.filter(track_stock=True, stock_quantity=0).count()

        inventory_value = products.aggregate(
            value=Sum(F('stock_quantity') * F('cost')),
        )['value'] or 0

        movements = StockMovement.objects.all()
        if start:
            movements = movements.filter(created_at__gte=start)
        if end:
            movements = movements.filter(created_at__lte=end)

        by_type = list(
            movements.values('movement_type')
            .annotate(count=Count('id'), units=Sum('quantity'))
            .order_by('-count')
        )
        for row in by_type:
            row['type'] = row.pop('movement_type') or 'unknown'
            row['units'] = int(row['units'] or 0)

        # Top 10 products at risk: lowest stock among those that track stock.
        at_risk = list(
            products.filter(track_stock=True)
            .order_by('stock_quantity', 'name')
            .values('id', 'name', 'sku', 'stock_quantity', 'low_stock_threshold')[:10]
        )
        for r in at_risk:
            r['low_stock_threshold'] = r['low_stock_threshold'] or 0

        return Response({
            'period': label,
            'summary': {
                'low_stock_count': low_stock_count,
                'out_of_stock_count': out_of_stock_count,
                'inventory_value': float(inventory_value),
                'active_products': products.count(),
            },
            'movements_by_type': by_type,
            'at_risk': at_risk,
        })

    @action(detail=False, methods=['get'])
    def customer_outstanding(self, request):
        """Money customers owe us, plus AR aging.

        For period-awareness we filter the per-invoice list by invoice
        ``created_at``, but the totals reflect all currently-outstanding
        invoices (you want to see the full debt, not just this month's).
        """
        start, end, label = resolve_period(request)

        # All currently-outstanding invoices (balance > 0, not cancelled).
        outstanding = Invoice.objects.filter(balance__gt=0).exclude(status='cancelled')

        # Aging buckets: 0-30, 31-60, 61-90, 90+.
        today = timezone.now().date()

        def days_overdue(due):
            if not due:
                return 0
            return max(0, (today - due).days)

        invoices = outstanding.select_related('customer').values(
            'id', 'invoice_number', 'customer__name', 'customer_name', 'balance',
            'total', 'amount_paid', 'due_date', 'status', 'created_at',
        )
        invoices_list = []
        buckets = {'0_30': 0.0, '31_60': 0.0, '61_90': 0.0, '90_plus': 0.0}
        for inv in invoices:
            balance = float(inv['balance'] or 0)
            overdue = days_overdue(inv['due_date'])
            bucket = (
                '0_30' if overdue <= 30 else
                '31_60' if overdue <= 60 else
                '61_90' if overdue <= 90 else
                '90_plus'
            )
            buckets[bucket] += balance
            invoices_list.append({
                'id': inv['id'],
                'invoice_number': inv['invoice_number'],
                'customer': inv['customer__name'] or inv['customer_name'] or '(walk-in)',
                'balance': balance,
                'total': float(inv['total'] or 0),
                'amount_paid': float(inv['amount_paid'] or 0),
                'due_date': inv['due_date'].isoformat() if inv['due_date'] else None,
                'days_overdue': overdue,
                'status': inv['status'],
                'created_at': inv['created_at'].isoformat() if inv['created_at'] else None,
            })

        # Period-scoped count (new invoices opened in this period).
        new_invoices = Invoice.objects.all()
        if start:
            new_invoices = new_invoices.filter(created_at__gte=start)
        if end:
            new_invoices = new_invoices.filter(created_at__lte=end)

        # Sort: oldest overdue first.
        invoices_list.sort(key=lambda r: r['days_overdue'], reverse=True)

        return Response({
            'period': label,
            'summary': {
                'total_outstanding': sum(buckets.values()),
                'invoice_count': len(invoices_list),
                'overdue_count': sum(1 for r in invoices_list if r['days_overdue'] > 0),
                'new_invoices_in_period': new_invoices.count(),
            },
            'aging': [
                {'bucket': '0-30 days', 'amount': buckets['0_30']},
                {'bucket': '31-60 days', 'amount': buckets['31_60']},
                {'bucket': '61-90 days', 'amount': buckets['61_90']},
                {'bucket': '90+ days', 'amount': buckets['90_plus']},
            ],
            'invoices': invoices_list[:20],
        })
