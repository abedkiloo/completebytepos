"""Daily sales tracking service — order classification (paid vs debt) and daily summaries."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.utils import timezone

from sales.debt_management import list_debt_collections
from sales.models import CustomerWalletTransaction, Sale


def parse_target_date(date_str: Optional[str]) -> Tuple[date, datetime, datetime]:
    """Parse date string (YYYY-MM-DD) into target date and timezone-aware day bounds."""
    tz = timezone.get_current_timezone()
    if not date_str:
        target = timezone.localdate()
    else:
        try:
            target = datetime.strptime(str(date_str).strip(), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            raise ValueError('Invalid date format. Expected YYYY-MM-DD.')

    start_of_day = timezone.make_aware(datetime.combine(target, datetime.min.time()), tz)
    end_of_day = timezone.make_aware(datetime.combine(target, datetime.max.time()), tz)
    return target, start_of_day, end_of_day


def classify_sale_payment(total: Decimal, amount_paid: Decimal) -> Tuple[Decimal, Decimal, str]:
    """Classify a sale into paid_amount, debt_amount, and payment_status ('paid', 'debt', 'partial')."""
    total = max(Decimal('0.00'), total)
    amount_paid = max(Decimal('0.00'), amount_paid)

    paid_amount = min(amount_paid, total)
    debt_amount = max(Decimal('0.00'), total - amount_paid)

    if debt_amount == Decimal('0.00'):
        status = 'paid'
    elif paid_amount == Decimal('0.00'):
        status = 'debt'
    else:
        status = 'partial'

    return paid_amount, debt_amount, status


def serialize_daily_order(sale: Sale) -> Dict[str, Any]:
    """Serialize a single sale for the daily orders list."""
    total = Decimal(str(sale.total or 0))
    amount_paid = Decimal(str(sale.amount_paid or 0))
    paid_amount, debt_amount, payment_status = classify_sale_payment(total, amount_paid)

    customer_data = None
    if sale.customer:
        customer_data = {
            'id': sale.customer.id,
            'name': sale.customer.name,
            'phone': sale.customer.phone or '',
            'customer_code': sale.customer.customer_code,
            'wallet_balance': str(sale.customer.wallet_balance),
        }

    served_by_name = None
    staff = sale.served_by or sale.cashier
    if staff:
        full = staff.get_full_name().strip()
        served_by_name = full or staff.username

    return {
        'id': sale.id,
        'sale_number': sale.sale_number,
        'occurred_at': sale.occurred_at.isoformat() if sale.occurred_at else None,
        'created_at': sale.created_at.isoformat() if sale.created_at else None,
        'customer': customer_data,
        'cashier_name': sale.cashier.username if sale.cashier else None,
        'served_by_name': served_by_name,
        'sale_type': sale.sale_type,
        'status': sale.status,
        'total': str(total.quantize(Decimal('0.01'))),
        'amount_paid': str(amount_paid.quantize(Decimal('0.01'))),
        'paid_amount': str(paid_amount.quantize(Decimal('0.01'))),
        'debt_amount': str(debt_amount.quantize(Decimal('0.01'))),
        'payment_status': payment_status,
        'payment_method': sale.payment_method,
        'payment_reference': sale.payment_reference or '',
        'item_count': sale.item_count,
        'refund_status': sale.refund_status,
        'amount_refunded': str(sale.amount_refunded.quantize(Decimal('0.01'))),
        'is_late_entry': sale.is_late_entry,
        'notes': sale.notes or '',
    }


def get_daily_sales_report(
    *,
    date_str: Optional[str] = None,
    payment_status: Optional[str] = None,
    payment_method: Optional[str] = None,
    search: Optional[str] = None,
    ordering: Optional[str] = '-occurred_at',
    page: int = 1,
    page_size: int = 25,
    branch_id: Optional[int] = None,
    base_queryset: Optional[Any] = None,
    cashier_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Compile daily sales summaries, metrics, and filtered order list for a specific date."""
    target_date, start_of_day, end_of_day = parse_target_date(date_str)

    if base_queryset is not None:
        qs = base_queryset
    else:
        qs = Sale.objects.all().select_related('customer', 'cashier', 'served_by', 'branch')

    base_qs = (
        qs.filter(
            status='completed',
            occurred_at__gte=start_of_day,
            occurred_at__lte=end_of_day,
        )
        .prefetch_related('items__product', 'items__refund_lines')
    )

    if branch_id:
        base_qs = base_qs.filter(branch_id=branch_id)

    if cashier_id:
        base_qs = base_qs.filter(
            Q(cashier_id=cashier_id) | Q(served_by_id=cashier_id)
        )

    # Compute daily aggregates across all completed sales of that day
    all_day_sales = list(base_qs)

    total_sales = Decimal('0.00')
    total_paid_upfront = Decimal('0.00')
    total_debt_incurred = Decimal('0.00')
    paid_orders_count = 0
    debt_orders_count = 0
    partial_orders_count = 0
    by_method_breakdown: Dict[str, Dict[str, Any]] = {}

    for s in all_day_sales:
        s_total = Decimal(str(s.total or 0))
        s_paid = Decimal(str(s.amount_paid or 0))
        p_amount, d_amount, p_status = classify_sale_payment(s_total, s_paid)

        total_sales += s_total
        total_paid_upfront += p_amount
        total_debt_incurred += d_amount

        if p_status == 'paid':
            paid_orders_count += 1
        elif p_status == 'debt':
            debt_orders_count += 1
        elif p_status == 'partial':
            partial_orders_count += 1
            debt_orders_count += 1  # Included in debt orders count (took on debt)

        method = s.payment_method or 'other'
        if method not in by_method_breakdown:
            by_method_breakdown[method] = {'count': 0, 'total': Decimal('0.00')}
        by_method_breakdown[method]['count'] += 1
        by_method_breakdown[method]['total'] += p_amount

    # Settlements of prior customer debts collected on that day (who paid, how much)
    collections = list_debt_collections(on_date=target_date, page=1, page_size=200)
    total_debt_collected = Decimal(str(collections.get('total') or 0))
    debt_settlement_count = int(collections.get('count') or 0)

    total_cash_in = total_paid_upfront + Decimal(str(total_debt_collected))

    # Apply order filtering for the table view
    orders_qs = base_qs

    if search:
        st = str(search).strip()
        if st:
            orders_qs = orders_qs.filter(
                Q(sale_number__icontains=st)
                | Q(customer__name__icontains=st)
                | Q(customer__phone__icontains=st)
                | Q(customer__customer_code__icontains=st)
                | Q(cashier__username__icontains=st)
                | Q(notes__icontains=st)
            )

    if payment_method:
        orders_qs = orders_qs.filter(payment_method=payment_method)

    # Filter by payment status in python or DB
    # Note: since paid vs debt involves total vs amount_paid, filtering in Python or DB:
    # In DB:
    # paid: amount_paid >= total
    # debt: amount_paid < total (includes partial and full debt)
    # full_debt: amount_paid == 0
    # partial: amount_paid > 0 and amount_paid < total
    if payment_status == 'paid':
        orders_qs = orders_qs.filter(amount_paid__gte=F('total'))
    elif payment_status == 'debt':
        orders_qs = orders_qs.filter(amount_paid__lt=F('total'))
    elif payment_status == 'partial':
        orders_qs = orders_qs.filter(amount_paid__gt=0, amount_paid__lt=F('total'))

    # Ordering
    valid_orderings = {
        '-occurred_at': '-occurred_at',
        'occurred_at': 'occurred_at',
        '-total': '-total',
        'total': 'total',
        '-created_at': '-created_at',
        'created_at': 'created_at',
    }
    order_by_field = valid_orderings.get(ordering, '-occurred_at')
    orders_qs = orders_qs.order_by(order_by_field)

    # Pagination
    page_num = max(1, int(page or 1))
    size = max(1, min(100, int(page_size or 25)))
    paginator = Paginator(orders_qs, size)
    page_obj = paginator.get_page(page_num)

    serialized_orders = [serialize_daily_order(sale) for sale in page_obj.object_list]

    return {
        'date': target_date.isoformat(),
        'summary': {
            'total_sales': str(total_sales.quantize(Decimal('0.01'))),
            'orders_count': len(all_day_sales),
            'total_paid': str(total_paid_upfront.quantize(Decimal('0.01'))),
            'paid_orders_count': paid_orders_count,
            'total_debt_incurred': str(total_debt_incurred.quantize(Decimal('0.01'))),
            'debt_orders_count': debt_orders_count,
            'partial_orders_count': partial_orders_count,
            'total_debt_collected': str(Decimal(str(total_debt_collected)).quantize(Decimal('0.01'))),
            'debt_settlement_count': debt_settlement_count,
            'total_collected': str(total_cash_in.quantize(Decimal('0.01'))),
            'payment_methods': {
                k: {
                    'count': v['count'],
                    'total': str(v['total'].quantize(Decimal('0.01'))),
                }
                for k, v in by_method_breakdown.items()
            },
        },
        'orders': serialized_orders,
        'collections': collections,
        'pagination': {
            'count': paginator.count,
            'page': page_obj.number,
            'page_size': size,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        },
    }


def _aggregate_sales_day(sales: List[Sale]) -> Dict[str, Any]:
    total_sales = Decimal('0.00')
    total_paid = Decimal('0.00')
    total_debt = Decimal('0.00')
    paid_count = 0
    debt_count = 0
    partial_count = 0

    for sale in sales:
        s_total = Decimal(str(sale.total or 0))
        s_paid = Decimal(str(sale.amount_paid or 0))
        paid_amount, debt_amount, status = classify_sale_payment(s_total, s_paid)
        total_sales += s_total
        total_paid += paid_amount
        total_debt += debt_amount
        if status == 'paid':
            paid_count += 1
        elif status == 'debt':
            debt_count += 1
        else:
            partial_count += 1
            debt_count += 1

    day_status = 'good'
    if total_debt > 0 and total_paid > 0:
        day_status = 'mixed'
    elif total_debt > 0:
        day_status = 'debt'

    return {
        'orders_count': len(sales),
        'total_sales': str(total_sales.quantize(Decimal('0.01'))),
        'total_paid': str(total_paid.quantize(Decimal('0.01'))),
        'total_debt_incurred': str(total_debt.quantize(Decimal('0.01'))),
        'paid_orders_count': paid_count,
        'debt_orders_count': debt_count,
        'partial_orders_count': partial_count,
        'day_standing': day_status,
    }


def get_customer_day_detail(
    *,
    customer_id: int,
    date_str: Optional[str] = None,
    base_queryset: Optional[Any] = None,
) -> Dict[str, Any]:
    """Customer profile + standing + orders/summary for a single business day."""
    from sales.models import Customer

    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist as exc:
        raise LookupError('Customer not found.') from exc

    target_date, start_of_day, end_of_day = parse_target_date(date_str)

    if base_queryset is not None:
        qs = base_queryset
    else:
        qs = Sale.objects.all().select_related('customer', 'cashier', 'served_by')

    day_sales = list(
        qs.filter(
            status='completed',
            customer_id=customer.id,
            occurred_at__gte=start_of_day,
            occurred_at__lte=end_of_day,
        )
        .prefetch_related('items__product', 'items__refund_lines')
        .order_by('-occurred_at')
    )

    day_summary = _aggregate_sales_day(day_sales)

    wallet_balance = Decimal(str(customer.wallet_balance or 0))
    wallet_debt = abs(wallet_balance) if wallet_balance < 0 else Decimal('0.00')
    wallet_credit = wallet_balance if wallet_balance > 0 else Decimal('0.00')
    standing = 'good' if wallet_debt == 0 else 'debt'

    settlements_today = (
        CustomerWalletTransaction.objects.filter(
            customer_id=customer.id,
            source_type='debt_settlement',
            created_at__gte=start_of_day,
            created_at__lte=end_of_day,
        ).aggregate(s=Sum('amount'))['s']
        or Decimal('0.00')
    )

    lifetime_sales = Sale.objects.filter(customer_id=customer.id, status='completed')
    lifetime_count = lifetime_sales.count()
    lifetime_total = lifetime_sales.aggregate(t=Sum('total'))['t'] or Decimal('0.00')

    return {
        'date': target_date.isoformat(),
        'customer': {
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone or '',
            'email': customer.email or '',
            'customer_code': customer.customer_code,
            'customer_type': customer.customer_type,
            'city': customer.city or '',
            'address': customer.address or '',
            'is_active': customer.is_active,
            'wallet_balance': str(wallet_balance.quantize(Decimal('0.01'))),
            'wallet_debt': str(wallet_debt.quantize(Decimal('0.01'))),
            'wallet_credit': str(wallet_credit.quantize(Decimal('0.01'))),
            'standing': standing,
            'total_outstanding': str(
                Decimal(str(customer.total_outstanding or 0)).quantize(Decimal('0.01'))
            ),
        },
        'day_summary': {
            **day_summary,
            'debt_collected': str(Decimal(str(settlements_today)).quantize(Decimal('0.01'))),
        },
        'standing_summary': {
            'standing': standing,
            'wallet_balance': str(wallet_balance.quantize(Decimal('0.01'))),
            'wallet_debt': str(wallet_debt.quantize(Decimal('0.01'))),
            'wallet_credit': str(wallet_credit.quantize(Decimal('0.01'))),
            'lifetime_orders': lifetime_count,
            'lifetime_sales_total': str(Decimal(str(lifetime_total)).quantize(Decimal('0.01'))),
        },
        'orders': [serialize_daily_order(sale) for sale in day_sales],
    }
