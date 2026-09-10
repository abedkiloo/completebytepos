"""Customer wallet debt summary and debtor listing for Debt Management."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Max, Min, Q, Sum
from django.utils import timezone

from sales.models import Customer, CustomerWalletTransaction, Sale

AGING_BUCKETS = ('0_7', '8_30', '31_60', '60_plus')


def debt_amount_from_balance(balance) -> Decimal:
    bal = Decimal(str(balance or 0))
    return abs(bal) if bal < 0 else Decimal('0')


def aging_bucket_for_days(days: int) -> str:
    if days <= 7:
        return '0_7'
    if days <= 30:
        return '8_30'
    if days <= 60:
        return '31_60'
    return '60_plus'


def empty_aging() -> Dict[str, Dict[str, Any]]:
    return {
        key: {'count': 0, 'amount': Decimal('0.00')}
        for key in AGING_BUCKETS
    }


def _start_of_today():
    today = timezone.localdate()
    return timezone.make_aware(datetime.combine(today, datetime.min.time()))


def _debtor_queryset(search: Optional[str] = None, is_active: bool = True):
    qs = Customer.objects.filter(wallet_balance__lt=0)
    if is_active:
        qs = qs.filter(is_active=True)
    if search:
        term = str(search).strip()
        if term:
            qs = qs.filter(
                Q(name__icontains=term)
                | Q(phone__icontains=term)
                | Q(customer_code__icontains=term)
                | Q(email__icontains=term)
            )
    return qs


def build_debt_summary() -> Dict[str, Any]:
    """Aggregate cards + aging for the Debt Management dashboard."""
    debtors = list(_debtor_queryset().only('id', 'wallet_balance', 'created_at', 'updated_at'))
    customers_with_debt = len(debtors)
    total_debt = sum(
        (debt_amount_from_balance(c.wallet_balance) for c in debtors),
        Decimal('0'),
    )
    average_debt = (
        (total_debt / customers_with_debt).quantize(Decimal('0.01'))
        if customers_with_debt
        else Decimal('0.00')
    )

    collected = (
        CustomerWalletTransaction.objects.filter(
            source_type='debt_settlement',
            created_at__gte=_start_of_today(),
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )

    aging = empty_aging()
    if debtors:
        debtor_ids = [c.id for c in debtors]
        oldest_by_customer = {
            row['customer_id']: row['oldest']
            for row in CustomerWalletTransaction.objects.filter(
                customer_id__in=debtor_ids,
                source_type='debt',
            )
            .values('customer_id')
            .annotate(oldest=Min('created_at'))
        }
        now = timezone.now()
        for customer in debtors:
            amount = debt_amount_from_balance(customer.wallet_balance)
            oldest = oldest_by_customer.get(customer.id) or customer.created_at or now
            days = max(0, (now.date() - timezone.localtime(oldest).date()).days)
            bucket = aging_bucket_for_days(days)
            aging[bucket]['count'] += 1
            aging[bucket]['amount'] += amount

    return {
        'customers_with_debt': customers_with_debt,
        'total_debt': total_debt.quantize(Decimal('0.01')),
        'average_debt': average_debt,
        'collected_today': Decimal(str(collected)).quantize(Decimal('0.01')),
        'aging': {
            key: {
                'count': aging[key]['count'],
                'amount': aging[key]['amount'].quantize(Decimal('0.01')),
            }
            for key in AGING_BUCKETS
        },
    }


def serialize_debt_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    aging = summary.get('aging') or {}
    return {
        'customers_with_debt': int(summary.get('customers_with_debt') or 0),
        'total_debt': str(summary.get('total_debt') or '0.00'),
        'average_debt': str(summary.get('average_debt') or '0.00'),
        'collected_today': str(summary.get('collected_today') or '0.00'),
        'aging': {
            key: {
                'count': int((aging.get(key) or {}).get('count') or 0),
                'amount': str((aging.get(key) or {}).get('amount') or '0.00'),
            }
            for key in AGING_BUCKETS
        },
    }


def _debt_age_days(customer: Customer, oldest_debt_at, now=None) -> int:
    now = now or timezone.now()
    anchor = oldest_debt_at or customer.created_at or now
    return max(0, (now.date() - timezone.localtime(anchor).date()).days)


def list_debtors(
    *,
    search: Optional[str] = None,
    aging_bucket: Optional[str] = None,
    ordering: str = '-debt_amount',
    page: int = 1,
    page_size: int = 25,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Paginated debtor rows with age and last activity.
    ordering: debt_amount | -debt_amount | debt_age_days | -debt_age_days | name | -name
    """
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 25)))

    qs = _debtor_queryset(search=search)
    customers = list(qs)
    if not customers:
        return [], 0

    debtor_ids = [c.id for c in customers]
    oldest_by_customer = {
        row['customer_id']: row['oldest']
        for row in CustomerWalletTransaction.objects.filter(
            customer_id__in=debtor_ids,
            source_type='debt',
        )
        .values('customer_id')
        .annotate(oldest=Min('created_at'))
    }
    last_payment_by_customer = {
        row['customer_id']: row['latest']
        for row in CustomerWalletTransaction.objects.filter(
            customer_id__in=debtor_ids,
            source_type='debt_settlement',
        )
        .values('customer_id')
        .annotate(latest=Max('created_at'))
    }
    last_sale_by_customer = {
        row['customer_id']: row['latest']
        for row in Sale.objects.filter(
            customer_id__in=debtor_ids,
            status='completed',
        )
        .values('customer_id')
        .annotate(latest=Max('created_at'))
    }

    now = timezone.now()
    rows: List[Dict[str, Any]] = []
    for customer in customers:
        amount = debt_amount_from_balance(customer.wallet_balance)
        oldest = oldest_by_customer.get(customer.id)
        days = _debt_age_days(customer, oldest, now=now)
        bucket = aging_bucket_for_days(days)
        if aging_bucket and aging_bucket in AGING_BUCKETS and bucket != aging_bucket:
            continue
        rows.append(
            {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone or '',
                'email': customer.email or '',
                'customer_code': customer.customer_code or '',
                'wallet_balance': str(customer.wallet_balance),
                'debt_amount': str(amount.quantize(Decimal('0.01'))),
                'debt_age_days': days,
                'aging_bucket': bucket,
                'oldest_debt_at': oldest.isoformat() if oldest else None,
                'last_sale_at': (
                    last_sale_by_customer[customer.id].isoformat()
                    if customer.id in last_sale_by_customer
                    else None
                ),
                'last_payment_at': (
                    last_payment_by_customer[customer.id].isoformat()
                    if customer.id in last_payment_by_customer
                    else None
                ),
            }
        )

    reverse = ordering.startswith('-')
    key = ordering.lstrip('-') or 'debt_amount'
    if key == 'debt_amount':
        rows.sort(key=lambda r: Decimal(r['debt_amount']), reverse=reverse)
    elif key == 'debt_age_days':
        rows.sort(key=lambda r: r['debt_age_days'], reverse=reverse)
    elif key == 'name':
        rows.sort(key=lambda r: (r['name'] or '').lower(), reverse=reverse)
    else:
        rows.sort(key=lambda r: Decimal(r['debt_amount']), reverse=True)

    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return rows[start:end], total


def debtor_count() -> int:
    return _debtor_queryset().count()
