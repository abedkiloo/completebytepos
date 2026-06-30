"""
Reports service layer — aggregations and period parsing (no ORM in views).
"""
from datetime import datetime, timedelta

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from expenses.models import Expense
from inventory.models import StockMovement
from products.models import Product
from sales.models import Sale, SaleItem


def resolve_period(request):
    """
    Parse ``?period=today|week|month|year`` into a (start, end, label) tuple.
  Falls back to explicit ``date_from`` / ``date_to`` query params.
    """
    now = timezone.now()
    today = now.date()
    params = getattr(request, 'query_params', request.GET)
    period = (params.get('period') or '').lower().strip()

    if period == 'today':
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        return start, now, 'today'
    if period == 'week':
        start = timezone.make_aware(datetime.combine(today - timedelta(days=6), datetime.min.time()))
        return start, now, 'week'
    if period == 'month':
        start = timezone.make_aware(datetime.combine(today.replace(day=1), datetime.min.time()))
        return start, now, 'month'
    if period == 'year':
        start = timezone.make_aware(datetime(today.year, 1, 1))
        return start, now, 'year'

    date_from = params.get('date_from')
    date_to = params.get('date_to')
    start = None
    end = None
    if date_from:
        try:
            start = timezone.make_aware(datetime.strptime(date_from, '%Y-%m-%d'))
        except (TypeError, ValueError):
            start = None
    if date_to:
        try:
            end = timezone.make_aware(
                datetime.combine(datetime.strptime(date_to, '%Y-%m-%d').date(), datetime.max.time())
            )
        except (TypeError, ValueError):
            end = None
    return start, end, 'custom'


class ReportDashboardService:
    """Dashboard KPI bundle used by the home screen."""

    @staticmethod
    def get_dashboard_summary():
        today = timezone.now().date()
        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))
        start_of_last_month = timezone.make_aware(
            datetime(today.year, today.month - 1 if today.month > 1 else 12, 1)
        )

        today_sales = Sale.objects.filter(occurred_at__gte=start_of_day, status='completed')
        today_total = today_sales.aggregate(total=Sum('total'))['total'] or 0
        today_count = today_sales.count()

        month_sales = Sale.objects.filter(occurred_at__gte=start_of_month, status='completed')
        month_total = month_sales.aggregate(total=Sum('total'))['total'] or 0

        last_month_sales = Sale.objects.filter(
            created_at__gte=start_of_last_month,
            created_at__lt=start_of_month,
            status='completed',
        )
        last_month_total = last_month_sales.aggregate(total=Sum('total'))['total'] or 0

        sales_growth = 0
        if last_month_total > 0:
            sales_growth = ((month_total - last_month_total) / last_month_total) * 100

        total_sales_all = Sale.objects.filter(status='completed').aggregate(total=Sum('total'))['total'] or 0

        sales_returns = Sale.objects.filter(
            Q(total__lt=0) | Q(discount_amount__gt=F('subtotal'))
        )
        sales_returns_total = sales_returns.aggregate(total=Sum('total'))['total'] or 0
        sales_returns_count = sales_returns.count()

        last_month_returns = sales_returns.filter(
            created_at__gte=start_of_last_month,
            created_at__lt=start_of_month,
        )
        last_month_returns_total = last_month_returns.aggregate(total=Sum('total'))['total'] or 0
        returns_growth = 0
        if last_month_returns_total != 0:
            returns_growth = (
                (sales_returns_total - last_month_returns_total) / abs(last_month_returns_total)
            ) * 100

        purchases = StockMovement.objects.filter(movement_type='purchase', created_at__gte=start_of_month)
        total_purchase = purchases.aggregate(total=Sum('total_cost'))['total'] or 0

        last_month_purchases = StockMovement.objects.filter(
            movement_type='purchase',
            created_at__gte=start_of_last_month,
            created_at__lt=start_of_month,
        )
        last_month_purchase_total = last_month_purchases.aggregate(total=Sum('total_cost'))['total'] or 0
        purchase_growth = 0
        if last_month_purchase_total > 0:
            purchase_growth = ((total_purchase - last_month_purchase_total) / last_month_purchase_total) * 100

        purchase_returns = StockMovement.objects.filter(
            movement_type='return',
            created_at__gte=start_of_month,
        )
        purchase_returns_total = purchase_returns.aggregate(total=Sum('total_cost'))['total'] or 0

        expenses_this_month = Expense.objects.filter(
            status='approved',
            expense_date__gte=start_of_month.date(),
        )
        total_expenses = expenses_this_month.aggregate(total=Sum('amount'))['total'] or 0

        expenses_last_month = Expense.objects.filter(
            status='approved',
            expense_date__gte=start_of_last_month.date(),
            expense_date__lt=start_of_month.date(),
        )
        last_month_expenses = expenses_last_month.aggregate(total=Sum('amount'))['total'] or 0
        expenses_growth = 0
        if last_month_expenses > 0:
            expenses_growth = ((total_expenses - last_month_expenses) / last_month_expenses) * 100

        profit = month_total - total_purchase - total_expenses
        last_month_profit = last_month_total - last_month_purchase_total - last_month_expenses
        profit_growth = 0
        if last_month_profit != 0:
            profit_growth = ((profit - last_month_profit) / abs(last_month_profit)) * 100

        invoice_due = Sale.objects.filter(
            payment_method__in=['mpesa', 'card', 'other'],
            created_at__gte=start_of_month,
            status='completed',
        ).aggregate(total=Sum('total'))['total'] or 0

        payment_returns = abs(sales_returns_total)
        last_month_payment_returns = abs(last_month_returns_total)
        payment_returns_growth = 0
        if last_month_payment_returns > 0:
            payment_returns_growth = (
                (payment_returns - last_month_payment_returns) / last_month_payment_returns
            ) * 100

        low_stock_count = Product.objects.filter(
            stock_quantity__lte=F('low_stock_threshold'),
            is_active=True,
            track_stock=True,
        ).count()

        top_products = list(
            SaleItem.objects.filter(sale__created_at__gte=start_of_month, sale__status='completed')
            .values('product__id', 'product__name', 'product__sku')
            .annotate(total_quantity=Sum('quantity'), total_revenue=Sum('subtotal'))
            .order_by('-total_revenue')[:5]
        )

        return {
            'today': {
                'sales_count': today_count,
                'total': float(today_total),
            },
            'month': {
                'total': float(month_total),
            },
            'low_stock_count': low_stock_count,
            'top_products': top_products,
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
                'suppliers': 0,
                'customers': 0,
                'orders': today_count,
            },
        }
