from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import datetime, timedelta
from sales.models import Sale, SaleItem, Invoice, Customer
from products.models import Product
from inventory.models import StockMovement
from expenses.models import Expense
from income.models import Income


class ReportViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Dashboard summary data with all metrics"""
        today = timezone.now().date()
        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))
        start_of_last_month = timezone.make_aware(datetime(today.year, today.month - 1 if today.month > 1 else 12, 1))
        end_of_last_month = start_of_month - timedelta(days=1)
        
        # Today's sales
        today_sales = Sale.objects.filter(created_at__gte=start_of_day)
        today_total = today_sales.aggregate(total=Sum('total'))['total'] or 0
        today_count = today_sales.count()
        
        # This month's sales
        month_sales = Sale.objects.filter(created_at__gte=start_of_month)
        month_total = month_sales.aggregate(total=Sum('total'))['total'] or 0
        
        # Last month's sales for comparison
        last_month_sales = Sale.objects.filter(
            created_at__gte=start_of_last_month,
            created_at__lt=start_of_month
        )
        last_month_total = last_month_sales.aggregate(total=Sum('total'))['total'] or 0
        
        # Calculate sales growth percentage
        sales_growth = 0
        if last_month_total > 0:
            sales_growth = ((month_total - last_month_total) / last_month_total) * 100
        
        # Total sales (all time)
        total_sales_all = Sale.objects.aggregate(total=Sum('total'))['total'] or 0
        
        # Sales returns (sales with negative total or discount > subtotal)
        sales_returns = Sale.objects.filter(
            Q(total__lt=0) | Q(discount_amount__gt=F('subtotal'))
        )
        sales_returns_total = sales_returns.aggregate(total=Sum('total'))['total'] or 0
        sales_returns_count = sales_returns.count()
        
        # Last month sales returns for comparison
        last_month_returns = sales_returns.filter(
            created_at__gte=start_of_last_month,
            created_at__lt=start_of_month
        )
        last_month_returns_total = last_month_returns.aggregate(total=Sum('total'))['total'] or 0
        returns_growth = 0
        if last_month_returns_total != 0:
            returns_growth = ((sales_returns_total - last_month_returns_total) / abs(last_month_returns_total)) * 100 if last_month_returns_total != 0 else 0
        
        # Purchases (stock movements of type 'purchase')
        purchases = StockMovement.objects.filter(movement_type='purchase', created_at__gte=start_of_month)
        total_purchase = purchases.aggregate(total=Sum('total_cost'))['total'] or 0
        
        last_month_purchases = StockMovement.objects.filter(
            movement_type='purchase',
            created_at__gte=start_of_last_month,
            created_at__lt=start_of_month
        )
        last_month_purchase_total = last_month_purchases.aggregate(total=Sum('total_cost'))['total'] or 0
        purchase_growth = 0
        if last_month_purchase_total > 0:
            purchase_growth = ((total_purchase - last_month_purchase_total) / last_month_purchase_total) * 100
        
        # Purchase returns (stock movements of type 'return' that are returns)
        purchase_returns = StockMovement.objects.filter(
            movement_type='return',
            created_at__gte=start_of_month
        )
        purchase_returns_total = purchase_returns.aggregate(total=Sum('total_cost'))['total'] or 0
        
        # Expenses (from expenses model)
        expenses_this_month = Expense.objects.filter(
            status='approved',
            expense_date__gte=start_of_month.date()
        )
        total_expenses = expenses_this_month.aggregate(total=Sum('amount'))['total'] or 0
        
        expenses_last_month = Expense.objects.filter(
            status='approved',
            expense_date__gte=start_of_last_month.date(),
            expense_date__lt=start_of_month.date()
        )
        last_month_expenses = expenses_last_month.aggregate(total=Sum('amount'))['total'] or 0
        expenses_growth = 0
        if last_month_expenses > 0:
            expenses_growth = ((total_expenses - last_month_expenses) / last_month_expenses) * 100
        
        # Profit calculation
        profit = month_total - total_purchase - total_expenses
        last_month_profit = last_month_total - last_month_purchase_total - last_month_expenses
        profit_growth = 0
        if last_month_profit != 0:
            profit_growth = ((profit - last_month_profit) / abs(last_month_profit)) * 100 if last_month_profit != 0 else 0
        
        # Invoice due (for now, sales with payment_method other than cash that might be pending)
        # This is a simplified version - in a real system, you'd track invoices separately
        invoice_due = Sale.objects.filter(
            payment_method__in=['mpesa', 'card', 'other'],
            created_at__gte=start_of_month
        ).aggregate(total=Sum('total'))['total'] or 0
        
        # Payment returns (negative sales or refunds)
        payment_returns = abs(sales_returns_total)
        last_month_payment_returns = abs(last_month_returns_total)
        payment_returns_growth = 0
        if last_month_payment_returns > 0:
            payment_returns_growth = ((payment_returns - last_month_payment_returns) / last_month_payment_returns) * 100
        
        # Low stock products
        low_stock_count = Product.objects.filter(
            stock_quantity__lte=F('low_stock_threshold'),
            is_active=True,
            track_stock=True
        ).count()
        
        # Top selling products (this month)
        top_products = SaleItem.objects.filter(
            sale__created_at__gte=start_of_month
        ).values(
            'product__id',
            'product__name', 
            'product__sku'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('subtotal')
        ).order_by('-total_revenue')[:5]
        
        # Overall information
        suppliers_count = 0  # TODO: Add suppliers model if needed
        customers_count = 0  # TODO: Add customers model if needed
        
        return Response({
            'today': {
                'sales_count': today_count,
                'total': float(today_total),
            },
            'month': {
                'total': float(month_total),
            },
            'low_stock_count': low_stock_count,
            'top_products': list(top_products),
            'total_sales': float(total_sales_all),
            'total_purchase': float(total_purchase),
            'total_expenses': float(total_expenses),
            'profit': float(profit),
            'sales_returns': {
                'total': float(abs(sales_returns_total)),
                'count': sales_returns_count,
            },
            'purchase_returns': {
                'total': float(purchase_returns_total),
            },
            'invoice_due': float(invoice_due),
            'payment_returns': float(payment_returns),
            'growth': {
                'sales': round(sales_growth, 1),
                'returns': round(returns_growth, 1),
                'purchase': round(purchase_growth, 1),
                'profit': round(profit_growth, 1),
                'expenses': round(expenses_growth, 1),
                'payment_returns': round(payment_returns_growth, 1),
            },
            'overall': {
                'suppliers': suppliers_count,
                'customers': customers_count,
                'orders': today_count,
            },
        })

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
        
        # Daily sales breakdown
        daily_sales = queryset.extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('total')
        ).order_by('-day')
        
        return Response({
            'summary': summary,
            'by_payment_method': list(by_payment),
            'daily_breakdown': list(daily_sales),
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
        """Customer report"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        # Get sales for customers
        sales_queryset = Sale.objects.filter(sale_type='normal')
        
        if date_from:
            sales_queryset = sales_queryset.filter(created_at__gte=date_from)
        if date_to:
            sales_queryset = sales_queryset.filter(created_at__lte=date_to)
        
        # Group by customer
        customer_sales = sales_queryset.values('customer__id', 'customer__name').annotate(
            total_purchases=Sum('total'),
            order_count=Count('id'),
        ).order_by('-total_purchases')
        
        customers = []
        for item in customer_sales:
            last_sale = sales_queryset.filter(customer__id=item['customer__id']).order_by('-created_at').first()
            customers.append({
                'id': item['customer__id'],
                'name': item['customer__name'] or 'Unknown',
                'total_purchases': float(item['total_purchases'] or 0),
                'order_count': item['order_count'],
                'avg_order_value': float(item['total_purchases'] or 0) / item['order_count'] if item['order_count'] > 0 else 0,
                'last_purchase': last_sale.created_at.isoformat() if last_sale else None,
            })
        
        summary = {
            'total_customers': len(customers),
            'total_sales': sum(c['total_purchases'] for c in customers),
            'avg_order_value': sum(c['total_purchases'] for c in customers) / len(customers) if customers else 0,
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
