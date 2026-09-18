"""Customer wallet debt summary and debtor listing for Debt Management."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Max, Min, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

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


def _local_day_bounds(day=None):
    """Inclusive start/end datetimes for a local calendar day."""
    day = day or timezone.localdate()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    if timezone.is_naive(start):
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(start, tz)
        end = timezone.make_aware(end, tz)
    return start, end


def _start_of_today():
    start, _end = _local_day_bounds()
    return start


def parse_collection_date(value) -> date:
    """Parse YYYY-MM-DD; None means today. Raises ValueError if invalid."""
    if value in (None, ''):
        return timezone.localdate()
    parsed = parse_date(str(value).strip()[:10])
    if parsed is None:
        raise ValueError('Invalid date. Use YYYY-MM-DD.')
    return parsed


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


def _user_label(user) -> str:
    if not user:
        return ''
    full = (user.get_full_name() or '').strip()
    return full or user.get_username()


def list_debt_collections(
    *,
    on_date=None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """
    Debt payments (wallet settlements) for one local calendar day.

    Each row is one payment: who paid, how much, when, and who recorded it.
    """
    day = on_date or timezone.localdate()
    start, end = _local_day_bounds(day)
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))

    qs = (
        CustomerWalletTransaction.objects.filter(
            source_type='debt_settlement',
            created_at__gte=start,
            created_at__lte=end,
        )
        .select_related('customer', 'created_by', 'sale')
        .order_by('-created_at', '-id')
    )
    total_amount = qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    count = qs.count()
    start_idx = (page - 1) * page_size
    rows = list(qs[start_idx : start_idx + page_size])

    results = []
    for txn in rows:
        customer = txn.customer
        results.append(
            {
                'id': txn.id,
                'customer_id': txn.customer_id,
                'customer_name': customer.name if customer else '',
                'customer_phone': (customer.phone or '') if customer else '',
                'customer_code': (customer.customer_code or '') if customer else '',
                'amount': str(Decimal(str(txn.amount)).quantize(Decimal('0.01'))),
                'balance_after': str(Decimal(str(txn.balance_after)).quantize(Decimal('0.01'))),
                'reference': txn.reference or '',
                'notes': txn.notes or '',
                'sale_number': txn.sale.sale_number if txn.sale_id and txn.sale else None,
                'received_by': _user_label(txn.created_by),
                'created_at': txn.created_at.isoformat() if txn.created_at else None,
            }
        )

    return {
        'date': day.isoformat(),
        'count': count,
        'page': page,
        'page_size': page_size,
        'total': str(Decimal(str(total_amount)).quantize(Decimal('0.01'))),
        'results': results,
    }
