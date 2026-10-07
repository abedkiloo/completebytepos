"""Customer wallet debt summary and debtor listing for Debt Management."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Case, DecimalField, F, Max, Min, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date

from sales.models import Customer, CustomerWalletTransaction, Sale

AGING_BUCKETS = ('0_7', '8_30', '31_60', '60_plus')
_DECIMAL = DecimalField(max_digits=14, decimal_places=2)


def debt_amount_from_balance(balance) -> Decimal:
    bal = Decimal(str(balance or 0))
    return abs(bal) if bal < 0 else Decimal('0')


def underpaid_pos_sales_qs():
    return (
        Sale.objects.filter(
            status='completed',
            amount_paid__lt=F('total'),
            customer_id__isnull=False,
        )
        .exclude(refund_status='refunded')
        .exclude(sale_type='normal')
    )


def underpaid_pos_sales_for_customer(customer_id: int):
    return underpaid_pos_sales_qs().filter(customer_id=customer_id).select_related(
        'customer'
    ).order_by('id')


def _sales_with_active_debt():
    return CustomerWalletTransaction.objects.filter(
        source_type='debt',
        transaction_type='debit',
        sale_id__isnull=False,
    ).values('sale_id')


def sale_needs_wallet_debt_heal(sale: Sale, *, active_amount=None, stale=None) -> bool:
    """
    True when an underpaid POS sale is missing from the customer wallet.

    Do **not** heal when active debt rows still exist — settlements credit the
    wallet without changing sale.amount_paid, and re-syncing would wipe them.
    """
    from sales.sale_debt_sync import (
        active_sale_debt_amount,
        debt_already_cleared_from_wallet,
        sale_unpaid_balance,
    )

    unpaid = sale_unpaid_balance(sale)
    if unpaid <= 0:
        return False
    if stale is None:
        stale = debt_already_cleared_from_wallet(sale)
    if stale:
        return True
    if active_amount is None:
        active_amount = active_sale_debt_amount(sale)
    return active_amount == 0


def customer_ids_needing_wallet_debt_heal() -> set:
    """Customers with underpaid POS sales that have no active wallet debt row."""
    return set(
        underpaid_pos_sales_qs()
        .exclude(pk__in=_sales_with_active_debt())
        .values_list('customer_id', flat=True)
        .distinct()
    )


def missing_unpaid_debt_by_customer(customer_ids) -> Dict[int, Decimal]:
    """Sum of unpaid balances on underpaid POS sales with no active debt txn."""
    ids = list(customer_ids or [])
    if not ids:
        return {}
    rows = (
        underpaid_pos_sales_qs()
        .filter(customer_id__in=ids)
        .exclude(pk__in=_sales_with_active_debt())
        .values('customer_id')
        .annotate(unpaid=Sum(F('total') - F('amount_paid')))
    )
    return {
        row['customer_id']: Decimal(str(row['unpaid'] or 0)).quantize(Decimal('0.01'))
        for row in rows
        if row['unpaid']
    }


def ensure_wallet_matches_unpaid_sales(customer: Customer, *, user=None) -> int:
    """
    Post missing wallet debt for underpaid POS sales stuck off the wallet.

    Also repairs stale sale.amount_paid after wallet settlements so Orders match
    the debt board. Batches active-debt lookups (no per-sale N+1). Intended for
    single-customer paths (profile / receive payment), not the debtors list.
    """
    from sales.sale_debt_sync import (
        debt_already_cleared_from_wallet,
        reconcile_sale_payments_with_wallet,
        sync_sale_customer_debt,
    )

    # Historical settlements left amount_paid at 0 — align Orders with wallet first.
    fixed = reconcile_sale_payments_with_wallet(customer)

    sales = list(underpaid_pos_sales_for_customer(customer.pk))
    if not sales:
        return fixed

    sale_ids = [s.pk for s in sales]
    active_by_sale = {
        row['sale_id']: Decimal(str(row['total'] or 0))
        for row in CustomerWalletTransaction.objects.filter(
            sale_id__in=sale_ids,
            source_type='debt',
            transaction_type='debit',
        )
        .values('sale_id')
        .annotate(total=Sum('amount'))
    }

    for sale in sales:
        active = active_by_sale.get(sale.pk, Decimal('0'))
        stale = False
        if active > 0:
            stale = debt_already_cleared_from_wallet(sale)
        if not sale_needs_wallet_debt_heal(sale, active_amount=active, stale=stale):
            continue
        sync_sale_customer_debt(
            sale,
            user=user,
            reason=f'Debt board sync for {sale.sale_number}',
        )
        fixed += 1
    if fixed:
        customer.refresh_from_db()
    return fixed


def collectible_debt_amount(
    customer: Customer,
    *,
    missing_unpaid: Optional[Dict[int, Decimal]] = None,
) -> Decimal:
    """Wallet debt, or unpaid POS shortfall not yet on the wallet."""
    wallet = debt_amount_from_balance(customer.wallet_balance)
    if wallet > 0:
        return wallet
    annotated = getattr(customer, 'collectible_debt', None)
    if annotated is not None:
        return Decimal(str(annotated or 0))
    if missing_unpaid is not None:
        return Decimal(str(missing_unpaid.get(customer.id) or 0))
    amounts = missing_unpaid_debt_by_customer([customer.id])
    return Decimal(str(amounts.get(customer.id) or 0))


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


def originating_debt_customer_ids(user) -> set:
    """
    Customers whose remaining wallet debt started on this user's sale or order.

    Remaining balance is still customer-level: if someone else later collected
    part of the debt, this user still sees that customer (not other cashiers'
    debtors).
    """
    from sales.visibility import own_sales_q

    uid = getattr(user, 'pk', None) or getattr(user, 'id', None)
    if uid is None:
        return set()

    ids = set(
        CustomerWalletTransaction.objects.filter(
            source_type='debt',
            sale_id__isnull=False,
        )
        .filter(Q(sale__cashier_id=uid) | Q(sale__served_by_id=uid))
        .values_list('customer_id', flat=True)
    )
    ids.update(
        CustomerWalletTransaction.objects.filter(
            source_type='debt',
            created_by_id=uid,
        ).values_list('customer_id', flat=True)
    )
    ids.update(
        Sale.objects.filter(
            own_sales_q(user),
            customer_id__isnull=False,
            status='completed',
            amount_paid__lt=F('total'),
        ).values_list('customer_id', flat=True)
    )
    try:
        from agents.models import FieldOrder

        fo_pks = list(
            FieldOrder.objects.filter(created_by_id=uid).values_list('pk', flat=True)
        )
        if fo_pks:
            refs = [f'FO-{pk}' for pk in fo_pks]
            ids.update(
                CustomerWalletTransaction.objects.filter(
                    source_type='debt',
                    reference__in=refs,
                ).values_list('customer_id', flat=True)
            )
    except Exception:
        pass
    ids.discard(None)
    return ids


def _visible_debtor_customer_ids(user) -> Optional[set]:
    """None = every debtor; a set (possibly empty) = restrict to those customers."""
    if user is None:
        return None
    from sales.visibility import user_sees_all_debt

    if user_sees_all_debt(user):
        return None
    return originating_debt_customer_ids(user)


def _annotate_collectible_debt(qs):
    """Annotate wallet_debt, missing_unpaid, and collectible_debt in SQL."""
    missing = (
        underpaid_pos_sales_qs()
        .filter(customer_id=OuterRef('pk'))
        .exclude(pk__in=_sales_with_active_debt())
        .values('customer_id')
        .annotate(t=Sum(F('total') - F('amount_paid')))
        .values('t')[:1]
    )
    wallet_debt = Case(
        When(wallet_balance__lt=0, then=-F('wallet_balance')),
        default=Value(Decimal('0.00')),
        output_field=_DECIMAL,
    )
    return qs.annotate(
        missing_unpaid=Coalesce(
            Subquery(missing, output_field=_DECIMAL),
            Value(Decimal('0.00')),
        ),
        wallet_debt=wallet_debt,
    ).annotate(
        collectible_debt=Case(
            When(wallet_debt__gt=0, then=F('wallet_debt')),
            default=F('missing_unpaid'),
            output_field=_DECIMAL,
        )
    )


def _debtor_queryset(search: Optional[str] = None, is_active: bool = True, user=None):
    """
    Customers who still owe and can be collected on the debt board.

    Uses SQL annotations (no Python heal-id materialization) so count/list/summary
    stay fast under concurrent load.
    """
    del is_active  # owing customers stay visible regardless of active flag
    qs = _annotate_collectible_debt(Customer.objects.all()).filter(
        collectible_debt__gt=0
    )
    visible = _visible_debtor_customer_ids(user)
    if visible is not None:
        if not visible:
            return qs.none()
        qs = qs.filter(pk__in=visible)
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


def _annotate_debt_age(qs):
    oldest_debt = (
        CustomerWalletTransaction.objects.filter(
            customer_id=OuterRef('pk'),
            source_type='debt',
        )
        .order_by('created_at')
        .values('created_at')[:1]
    )
    oldest_sale = (
        underpaid_pos_sales_qs()
        .filter(customer_id=OuterRef('pk'))
        .order_by('occurred_at')
        .values('occurred_at')[:1]
    )
    return qs.annotate(
        oldest_debt_at=Subquery(oldest_debt),
        oldest_sale_at=Subquery(oldest_sale),
    )


def _aging_bucket_date_filter(aging_bucket: str, today: date):
    """Q filter on annotated oldest_debt_at / oldest_sale_at for a bucket."""
    if aging_bucket not in AGING_BUCKETS:
        return Q()
    # Prefer debt txn date, else underpaid sale date, else created_at.
    # Approximate with OR of date fields falling in the bucket window.
    if aging_bucket == '0_7':
        start = today - timedelta(days=7)
        return (
            Q(oldest_debt_at__date__gte=start)
            | (Q(oldest_debt_at__isnull=True) & Q(oldest_sale_at__date__gte=start))
            | (
                Q(oldest_debt_at__isnull=True)
                & Q(oldest_sale_at__isnull=True)
                & Q(created_at__date__gte=start)
            )
        )
    if aging_bucket == '8_30':
        start = today - timedelta(days=30)
        end = today - timedelta(days=8)
        return (
            Q(oldest_debt_at__date__gte=start, oldest_debt_at__date__lte=end)
            | (
                Q(oldest_debt_at__isnull=True)
                & Q(oldest_sale_at__date__gte=start, oldest_sale_at__date__lte=end)
            )
            | (
                Q(oldest_debt_at__isnull=True)
                & Q(oldest_sale_at__isnull=True)
                & Q(created_at__date__gte=start, created_at__date__lte=end)
            )
        )
    if aging_bucket == '31_60':
        start = today - timedelta(days=60)
        end = today - timedelta(days=31)
        return (
            Q(oldest_debt_at__date__gte=start, oldest_debt_at__date__lte=end)
            | (
                Q(oldest_debt_at__isnull=True)
                & Q(oldest_sale_at__date__gte=start, oldest_sale_at__date__lte=end)
            )
            | (
                Q(oldest_debt_at__isnull=True)
                & Q(oldest_sale_at__isnull=True)
                & Q(created_at__date__gte=start, created_at__date__lte=end)
            )
        )
    # 60_plus
    end = today - timedelta(days=61)
    return (
        Q(oldest_debt_at__date__lte=end)
        | (Q(oldest_debt_at__isnull=True) & Q(oldest_sale_at__date__lte=end))
        | (
            Q(oldest_debt_at__isnull=True)
            & Q(oldest_sale_at__isnull=True)
            & Q(created_at__date__lte=end)
        )
    )


def build_debt_summary(user=None) -> Dict[str, Any]:
    """Aggregate cards + aging for the Debt Management dashboard (SQL aggregates)."""
    qs = _annotate_debt_age(_debtor_queryset(user=user))
    agg = qs.aggregate(
        customers_with_debt=Sum(
            Case(When(collectible_debt__gt=0, then=Value(1)), default=Value(0))
        ),
        total_debt=Coalesce(Sum('collectible_debt'), Value(Decimal('0.00'))),
    )
    # Count via qs.count() is clearer / portable across DBs
    customers_with_debt = qs.count()
    total_debt = Decimal(str(agg['total_debt'] or 0)).quantize(Decimal('0.01'))
    average_debt = (
        (total_debt / customers_with_debt).quantize(Decimal('0.01'))
        if customers_with_debt
        else Decimal('0.00')
    )

    collected_qs = CustomerWalletTransaction.objects.filter(
        source_type='debt_settlement',
        created_at__gte=_start_of_today(),
    )
    visible_ids = _visible_debtor_customer_ids(user)
    if visible_ids is not None:
        collected_qs = collected_qs.filter(customer_id__in=list(visible_ids) or [])
    collected = collected_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    aging = empty_aging()
    today = timezone.localdate()
    # One pass: fetch only id + amounts + date anchors (no full customer rows beyond that)
    for row in qs.values(
        'id', 'collectible_debt', 'oldest_debt_at', 'oldest_sale_at', 'created_at'
    ).iterator(chunk_size=500):
        amount = Decimal(str(row['collectible_debt'] or 0))
        oldest = row['oldest_debt_at'] or row['oldest_sale_at'] or row['created_at']
        if oldest is None:
            days = 0
        else:
            if timezone.is_aware(oldest):
                oldest_day = timezone.localtime(oldest).date()
            else:
                oldest_day = oldest.date() if hasattr(oldest, 'date') else oldest
            days = max(0, (today - oldest_day).days)
        bucket = aging_bucket_for_days(days)
        aging[bucket]['count'] += 1
        aging[bucket]['amount'] += amount

    return {
        'customers_with_debt': customers_with_debt,
        'total_debt': total_debt,
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
    user=None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Paginated debtor rows with age and last activity.

    Orders and paginates in SQL when possible — does not load every debtor into
    Python before slicing.
    """
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 25)))

    qs = _annotate_debt_age(_debtor_queryset(search=search, user=user))
    today = timezone.localdate()
    if aging_bucket and aging_bucket in AGING_BUCKETS:
        qs = qs.filter(_aging_bucket_date_filter(aging_bucket, today))

    reverse = ordering.startswith('-')
    key = ordering.lstrip('-') or 'debt_amount'
    order_map = {
        'debt_amount': 'collectible_debt',
        'name': 'name',
        'saved': 'created_at',
        'created_at': 'created_at',
        'debt_age_days': 'oldest_debt_at',
    }
    order_field = order_map.get(key, 'collectible_debt')
    if reverse:
        if key == 'debt_age_days':
            # Older debt first when descending age → smaller/earlier dates first
            qs = qs.order_by(F('oldest_debt_at').asc(nulls_last=True), 'id')
        else:
            qs = qs.order_by(F(order_field).desc(nulls_last=True), 'id')
    else:
        if key == 'debt_age_days':
            qs = qs.order_by(F('oldest_debt_at').desc(nulls_last=True), 'id')
        else:
            qs = qs.order_by(F(order_field).asc(nulls_last=True), 'id')

    total = qs.count()
    start = (page - 1) * page_size
    page_customers = list(qs[start : start + page_size])
    if not page_customers:
        return [], total

    debtor_ids = [c.id for c in page_customers]
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
    for customer in page_customers:
        amount = Decimal(str(getattr(customer, 'collectible_debt', 0) or 0))
        oldest = (
            getattr(customer, 'oldest_debt_at', None)
            or getattr(customer, 'oldest_sale_at', None)
        )
        days = _debt_age_days(customer, oldest, now=now)
        bucket = aging_bucket_for_days(days)
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
                'created_at': (
                    customer.created_at.isoformat() if customer.created_at else None
                ),
            }
        )

    return rows, total


def debtor_count(user=None) -> int:
    return _debtor_queryset(user=user).count()


def user_display_name(user) -> str:
    if not user:
        return ''
    full = (user.get_full_name() or '').strip()
    return full or user.get_username()


def _user_label(user) -> str:
    return user_display_name(user)


_PAYMENT_METHOD_LABELS = {
    'cash': 'Cash',
    'mpesa': 'M-PESA',
}


def resolve_settlement_payment_method(txn) -> str:
    """Stored method, or infer from legacy notes text."""
    stored = (getattr(txn, 'payment_method', None) or '').strip().lower()
    if stored in _PAYMENT_METHOD_LABELS:
        return stored
    notes = (getattr(txn, 'notes', None) or '').lower()
    if 'via m-pesa' in notes or 'via mpesa' in notes:
        return 'mpesa'
    if 'via cash' in notes:
        return 'cash'
    return stored


def payment_method_label(method: str) -> str:
    key = (method or '').strip().lower()
    return _PAYMENT_METHOD_LABELS.get(key, '')


def list_debt_collections(
    *,
    on_date=None,
    page: int = 1,
    page_size: int = 50,
    user=None,
    own_only: bool = False,
) -> Dict[str, Any]:
    """
    Debt payments (wallet settlements) for one local calendar day.

    Each row is one payment: who paid, how much, when, and who recorded it.
    ``own_only`` limits rows to customers whose debt this user originated, even
    for managers (used by the per-person daily sales view).
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
    if own_only and user is not None:
        visible_ids = originating_debt_customer_ids(user)
    else:
        visible_ids = _visible_debtor_customer_ids(user)
    if visible_ids is not None:
        qs = qs.filter(customer_id__in=list(visible_ids) or [])

    total_amount = qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    count = qs.count()
    start_idx = (page - 1) * page_size
    rows = list(qs[start_idx : start_idx + page_size])

    results = []
    for txn in rows:
        customer = txn.customer
        method = resolve_settlement_payment_method(txn)
        results.append(
            {
                'id': txn.id,
                'customer_id': txn.customer_id,
                'customer_name': customer.name if customer else '',
                'customer_phone': (customer.phone or '') if customer else '',
                'customer_code': (customer.customer_code or '') if customer else '',
                'amount': str(Decimal(str(txn.amount)).quantize(Decimal('0.01'))),
                'balance_after': str(Decimal(str(txn.balance_after)).quantize(Decimal('0.01'))),
                'payment_method': method,
                'payment_method_label': payment_method_label(method) or '—',
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
