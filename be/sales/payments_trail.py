"""Store-wide money-in trail: settlements, invoice payments, sale tender.

Paginated and N+1-free — list page hydrates targets in batched queries.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from django.db.models import (
    DecimalField,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from sales.customer_detail import debt_flow_for_txn
from sales.debt_management import (
    _visible_debtor_customer_ids,
    payment_method_label,
    resolve_settlement_payment_method,
    user_display_name,
)
from sales.models import CustomerWalletTransaction, DebtSettlementAllocation, Payment, Sale

KIND_DEBT_SETTLEMENT = 'debt_settlement'
KIND_INVOICE_PAYMENT = 'invoice_payment'
KIND_SALE_PAYMENT = 'sale_payment'
ALL_KINDS = (KIND_DEBT_SETTLEMENT, KIND_INVOICE_PAYMENT, KIND_SALE_PAYMENT)

#: Max hydrated rows for Excel export (index sources already cap at 5000 each).
PAYMENTS_TRAIL_EXPORT_LIMIT = 10000

KIND_LABELS = {
    KIND_DEBT_SETTLEMENT: 'Debt collection',
    KIND_INVOICE_PAYMENT: 'Invoice payment',
    KIND_SALE_PAYMENT: 'Sale tender',
}

_METHOD_LABELS = {
    'cash': 'Cash',
    'mpesa': 'M-PESA',
    'bank_transfer': 'Bank transfer',
    'other': 'Other',
}


def _q(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def _parse_day(value):
    """Return a calendar date, or None if blank."""
    if value in (None, ''):
        return None
    raw = str(value).strip()
    dt = parse_datetime(raw)
    if dt is not None:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return timezone.localtime(dt).date()
    day = parse_date(raw)
    if day is None:
        raise ValueError('Invalid date. Use YYYY-MM-DD.')
    return day


def _method_label(method: str) -> str:
    key = (method or '').strip().lower()
    return _METHOD_LABELS.get(key, payment_method_label(key) or (method or '—') or '—')


def _parse_kinds(raw) -> List[str]:
    if raw in (None, '', 'all'):
        return list(ALL_KINDS)
    if isinstance(raw, (list, tuple)):
        parts = []
        for item in raw:
            parts.extend(str(item).split(','))
    else:
        parts = str(raw).split(',')
    kinds = [p.strip() for p in parts if p.strip() in ALL_KINDS]
    return kinds or list(ALL_KINDS)


def _resolve_trail_window(date_from, date_to):
    """Parse dates; default to last 30 days when both blank."""
    day_from = _parse_day(date_from)
    day_to = _parse_day(date_to)
    if day_from is None and day_to is None:
        day_from = timezone.localdate() - timedelta(days=30)
        day_to = timezone.localdate()
    return day_from, day_to


def _normalize_mpesa_destination_filter(raw) -> str:
    """Return ``till``, ``bank``, or ``''`` (no filter)."""
    value = (raw or '').strip().lower()
    if value in ('till', 'bank'):
        return value
    return ''


def _collect_index_rows(
    *,
    kinds: Sequence[str],
    day_from,
    day_to,
    term: str,
    visible_ids,
    mpesa_destination: str = '',
) -> List[Dict[str, Any]]:
    index_rows: List[Dict[str, Any]] = []
    if KIND_DEBT_SETTLEMENT in kinds:
        index_rows.extend(
            _settlement_index(
                day_from,
                day_to,
                term,
                visible_ids,
                mpesa_destination=mpesa_destination,
            )
        )
    # Till/bank filter only applies to debt settlements with M-Pesa codes.
    if not mpesa_destination:
        if KIND_INVOICE_PAYMENT in kinds:
            index_rows.extend(_invoice_index(day_from, day_to, term, visible_ids))
        if KIND_SALE_PAYMENT in kinds:
            index_rows.extend(_sale_tender_index(day_from, day_to, term, visible_ids))

    index_rows.sort(
        key=lambda row: (
            row['occurred_at'] or timezone.make_aware(datetime.min),
            row['source_id'],
        ),
        reverse=True,
    )
    return index_rows


def list_payments_trail(
    *,
    kind: Optional[str] = None,
    date_from=None,
    date_to=None,
    search: Optional[str] = None,
    mpesa_destination: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user=None,
) -> Dict[str, Any]:
    """
    Paginated money-in trail with balancing fields and paid-towards targets.

    Designed for operator accountability — not a live dashboard cache.

    Args:
        mpesa_destination: Optional ``till`` / ``bank`` filter for debt settlements.
    """
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    kinds = _parse_kinds(kind)
    day_from, day_to = _resolve_trail_window(date_from, date_to)
    term = (search or '').strip()
    dest = _normalize_mpesa_destination_filter(mpesa_destination)
    visible_ids = _visible_debtor_customer_ids(user)
    index_rows = _collect_index_rows(
        kinds=kinds,
        day_from=day_from,
        day_to=day_to,
        term=term,
        visible_ids=visible_ids,
        mpesa_destination=dest,
    )
    count = len(index_rows)
    start_idx = (page - 1) * page_size
    page_index = index_rows[start_idx : start_idx + page_size]
    results = _hydrate_page(page_index)

    return {
        'count': count,
        'page': page,
        'page_size': page_size,
        'results': results,
    }


def build_payments_trail_export(
    *,
    kind: Optional[str] = None,
    date_from=None,
    date_to=None,
    search: Optional[str] = None,
    mpesa_destination: Optional[str] = None,
    user=None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Unpaginated payments-trail payload for Excel (same rows as the list UI).

    Args:
        kind: Trail kind filter or ``all``.
        date_from: Inclusive start day (YYYY-MM-DD).
        date_to: Inclusive end day (YYYY-MM-DD).
        search: Optional customer / reference / payer search.
        mpesa_destination: Optional ``till`` / ``bank`` filter for settlements.
        user: Request user for debtor visibility.
        limit: Max rows to hydrate (1–PAYMENTS_TRAIL_EXPORT_LIMIT).

    Returns:
        Dict with ``results``, ``count``, ``truncated``, date window, and
        ``by_method`` totals.
    """
    if limit is None:
        limit = PAYMENTS_TRAIL_EXPORT_LIMIT
    limit = max(1, min(int(limit), PAYMENTS_TRAIL_EXPORT_LIMIT))
    kinds = _parse_kinds(kind)
    day_from, day_to = _resolve_trail_window(date_from, date_to)
    term = (search or '').strip()
    dest = _normalize_mpesa_destination_filter(mpesa_destination)
    visible_ids = _visible_debtor_customer_ids(user)
    index_rows = _collect_index_rows(
        kinds=kinds,
        day_from=day_from,
        day_to=day_to,
        term=term,
        visible_ids=visible_ids,
        mpesa_destination=dest,
    )
    count = len(index_rows)
    truncated = count > limit
    results = _hydrate_page(index_rows[:limit])
    by_method = _summarize_by_method(results)
    return {
        'count': count,
        'exported_count': len(results),
        'truncated': truncated,
        'date_from': day_from.isoformat() if day_from else None,
        'date_to': day_to.isoformat() if day_to else None,
        'results': results,
        'by_method': by_method,
        'total_amount': str(
            sum((_q(r.get('amount')) for r in results), Decimal('0.00'))
        ),
    }


def _summarize_by_method(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, Any]] = {}
    for row in results:
        method = (row.get('payment_method') or 'other').strip().lower() or 'other'
        bucket = buckets.setdefault(
            method,
            {
                'payment_method': method,
                'payment_method_label': row.get('payment_method_label')
                or _method_label(method),
                'count': 0,
                'total': Decimal('0.00'),
            },
        )
        bucket['count'] += 1
        bucket['total'] += _q(row.get('amount'))
    ordered = sorted(buckets.values(), key=lambda b: b['payment_method'])
    return [
        {
            'payment_method': b['payment_method'],
            'payment_method_label': b['payment_method_label'],
            'count': b['count'],
            'total': str(_q(b['total'])),
        }
        for b in ordered
    ]


def summarize_payments_trail(
    *,
    kind: Optional[str] = None,
    date_from=None,
    date_to=None,
    search: Optional[str] = None,
    mpesa_destination: Optional[str] = None,
    user=None,
) -> Dict[str, Any]:
    """
    Totals for the selected Payments trail filters (full range, not one page).

    Returns:
        Dict with ``count``, ``total_amount``, ``by_method``, date window, and
        truncation flags (same row cap as Excel export).
    """
    payload = build_payments_trail_export(
        kind=kind,
        date_from=date_from,
        date_to=date_to,
        search=search,
        mpesa_destination=mpesa_destination,
        user=user,
    )
    return {
        'count': payload['count'],
        'included_count': payload['exported_count'],
        'truncated': payload['truncated'],
        'total_amount': payload['total_amount'],
        'by_method': payload['by_method'],
        'date_from': payload['date_from'],
        'date_to': payload['date_to'],
    }


def _settlement_index(
    day_from,
    day_to,
    term,
    visible_ids,
    *,
    mpesa_destination: str = '',
) -> List[Dict[str, Any]]:
    from django.db.models.functions import Coalesce

    qs = CustomerWalletTransaction.objects.filter(
        source_type='debt_settlement',
        transaction_type='credit',
    ).annotate(effective_at=Coalesce('occurred_at', 'created_at'))
    if day_from:
        qs = qs.filter(effective_at__date__gte=day_from)
    if day_to:
        qs = qs.filter(effective_at__date__lte=day_to)
    if visible_ids is not None:
        qs = qs.filter(customer_id__in=list(visible_ids) or [])
    if mpesa_destination:
        qs = qs.filter(mpesa_destination=mpesa_destination)
    if term:
        qs = qs.filter(
            Q(customer__name__icontains=term)
            | Q(customer__phone__icontains=term)
            | Q(customer__customer_code__icontains=term)
            | Q(reference__icontains=term)
            | Q(notes__icontains=term)
            | Q(payer_name__icontains=term)
            | Q(payer_phone__icontains=term)
        )
    return [
        {
            'kind': KIND_DEBT_SETTLEMENT,
            'source_id': row['id'],
            'occurred_at': row['effective_at'],
        }
        for row in qs.order_by('-effective_at', '-id').values('id', 'effective_at')[:5000]
    ]


def _invoice_index(day_from, day_to, term, visible_ids) -> List[Dict[str, Any]]:
    # Skip "Initial payment from sale …" — that cash is already the sale tender row.
    qs = Payment.objects.exclude(notes__startswith='Initial payment from sale ')
    if day_from:
        qs = qs.filter(created_at__date__gte=day_from)
    if day_to:
        qs = qs.filter(created_at__date__lte=day_to)
    if visible_ids is not None:
        qs = qs.filter(invoice__customer_id__in=list(visible_ids) or [])
    if term:
        qs = qs.filter(
            Q(invoice__customer__name__icontains=term)
            | Q(invoice__customer_name__icontains=term)
            | Q(invoice__invoice_number__icontains=term)
            | Q(reference__icontains=term)
        )
    return [
        {
            'kind': KIND_INVOICE_PAYMENT,
            'source_id': row['id'],
            'occurred_at': row['created_at'],
        }
        for row in qs.order_by('-created_at', '-id').values('id', 'created_at')[:5000]
    ]


def _sale_tender_index(day_from, day_to, term, visible_ids) -> List[Dict[str, Any]]:
    """Sale checkout tender only — excludes amount_paid bumps from debt settlements."""
    settled_sub = (
        DebtSettlementAllocation.objects.filter(sale_id=OuterRef('pk'))
        .values('sale_id')
        .annotate(total=Sum('amount'))
        .values('total')[:1]
    )
    dec = DecimalField(max_digits=14, decimal_places=2)
    zero = Value(0, output_field=dec)
    qs = (
        Sale.objects.filter(status='completed', amount_paid__gt=0)
        .annotate(
            settled_total=Coalesce(
                Subquery(settled_sub, output_field=dec),
                zero,
            )
        )
        .annotate(
            tender=Greatest(
                F('amount_paid') - F('settled_total'),
                zero,
                output_field=dec,
            )
        )
        .filter(tender__gt=0)
    )
    if day_from:
        qs = qs.filter(occurred_at__date__gte=day_from)
    if day_to:
        qs = qs.filter(occurred_at__date__lte=day_to)
    if visible_ids is not None:
        qs = qs.filter(customer_id__in=list(visible_ids) or [])
    if term:
        qs = qs.filter(
            Q(customer__name__icontains=term)
            | Q(customer__phone__icontains=term)
            | Q(sale_number__icontains=term)
            | Q(payment_reference__icontains=term)
        )
    return [
        {
            'kind': KIND_SALE_PAYMENT,
            'source_id': row['id'],
            'occurred_at': row['occurred_at'] or row['created_at'],
            'tender_amount': row['tender'],
        }
        for row in qs.order_by('-occurred_at', '-id').values(
            'id', 'occurred_at', 'created_at', 'tender'
        )[:5000]
    ]


def _hydrate_page(page_index: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not page_index:
        return []

    settlement_ids = [r['source_id'] for r in page_index if r['kind'] == KIND_DEBT_SETTLEMENT]
    invoice_ids = [r['source_id'] for r in page_index if r['kind'] == KIND_INVOICE_PAYMENT]
    sale_ids = [r['source_id'] for r in page_index if r['kind'] == KIND_SALE_PAYMENT]

    settlements = {
        t.id: t
        for t in CustomerWalletTransaction.objects.filter(id__in=settlement_ids)
        .select_related('customer', 'created_by', 'sale')
    }
    allocations_by_txn: Dict[int, List[Dict[str, Any]]] = {tid: [] for tid in settlement_ids}
    if settlement_ids:
        for alloc in (
            DebtSettlementAllocation.objects.filter(wallet_transaction_id__in=settlement_ids)
            .select_related('sale')
            .order_by('id')
        ):
            allocations_by_txn.setdefault(alloc.wallet_transaction_id, []).append(
                {
                    'type': 'sale',
                    'sale_id': alloc.sale_id,
                    'sale_number': alloc.sale.sale_number if alloc.sale_id else None,
                    'amount': str(_q(alloc.amount)),
                    'label': (
                        f'Sale {alloc.sale.sale_number}'
                        if alloc.sale_id and alloc.sale
                        else 'Sale'
                    ),
                }
            )

    invoices = {
        p.id: p
        for p in Payment.objects.filter(id__in=invoice_ids).select_related(
            'invoice', 'invoice__customer', 'recorded_by'
        )
    }
    sales = {
        s.id: s
        for s in Sale.objects.filter(id__in=sale_ids).select_related('customer', 'cashier')
    }

    results = []
    for row in page_index:
        if row['kind'] == KIND_DEBT_SETTLEMENT:
            txn = settlements.get(row['source_id'])
            if txn:
                results.append(_serialize_settlement(txn, allocations_by_txn.get(txn.id, [])))
        elif row['kind'] == KIND_INVOICE_PAYMENT:
            pay = invoices.get(row['source_id'])
            if pay:
                results.append(_serialize_invoice_payment(pay))
        elif row['kind'] == KIND_SALE_PAYMENT:
            sale = sales.get(row['source_id'])
            if sale:
                tender = row.get('tender_amount')
                results.append(_serialize_sale_tender(sale, tender_amount=tender))
    return results


def _serialize_settlement(txn: CustomerWalletTransaction, targets: List[Dict[str, Any]]) -> Dict[str, Any]:
    method = resolve_settlement_payment_method(txn)
    flow = debt_flow_for_txn(
        transaction_type=txn.transaction_type,
        source_type=txn.source_type,
        amount=Decimal(str(txn.amount or 0)),
        balance_after=Decimal(str(txn.balance_after or 0)),
        sale=txn.sale,
    )
    customer = txn.customer
    if not targets:
        targets = [
            {
                'type': 'customer_debt',
                'label': 'Customer wallet debt',
                'amount': str(_q(txn.amount)),
            }
        ]
    from sales.collection_payer import mpesa_destination_label

    dest = (getattr(txn, 'mpesa_destination', None) or '').strip().lower()
    from sales.wallet_receipt import is_backdated_wallet_txn, receipt_image_url

    when = txn.effective_occurred_at
    return {
        'kind': KIND_DEBT_SETTLEMENT,
        'id': txn.id,
        'occurred_at': when.isoformat() if when else None,
        'amount': str(_q(txn.amount)),
        'payment_method': method,
        'payment_method_label': _method_label(method),
        'reference': txn.reference or '',
        'notes': txn.notes or '',
        'payer_name': (getattr(txn, 'payer_name', None) or '').strip(),
        'payer_phone': (getattr(txn, 'payer_phone', None) or '').strip(),
        'mpesa_destination': dest,
        'mpesa_destination_label': mpesa_destination_label(dest),
        'receipt_image_url': receipt_image_url(txn),
        'is_backdated': is_backdated_wallet_txn(txn),
        'customer_id': txn.customer_id,
        'customer_name': customer.name if customer else '',
        'customer_code': (customer.customer_code or '') if customer else '',
        'customer_phone': (customer.phone or '') if customer else '',
        'received_by': user_display_name(txn.created_by),
        'paid_towards': targets,
        'paid_towards_label': ', '.join(t['label'] for t in targets if t.get('label')) or 'Customer debt',
        **flow,
    }


def _serialize_invoice_payment(pay: Payment) -> Dict[str, Any]:
    invoice = pay.invoice
    customer = invoice.customer if invoice else None
    name = (
        (customer.name if customer else '')
        or (invoice.customer_name if invoice else '')
        or ''
    )
    inv_no = invoice.invoice_number if invoice else ''
    target = {
        'type': 'invoice',
        'invoice_id': pay.invoice_id,
        'invoice_number': inv_no,
        'label': f'Invoice {inv_no}' if inv_no else 'Invoice',
        'amount': str(_q(pay.amount)),
    }
    method = (pay.payment_method or '').strip().lower()
    return {
        'kind': KIND_INVOICE_PAYMENT,
        'id': pay.id,
        'occurred_at': pay.created_at.isoformat() if pay.created_at else None,
        'amount': str(_q(pay.amount)),
        'payment_method': method,
        'payment_method_label': _method_label(method),
        'reference': pay.reference or '',
        'notes': pay.notes or '',
        'customer_id': customer.id if customer else None,
        'customer_name': name,
        'customer_code': (customer.customer_code or '') if customer else '',
        'customer_phone': (customer.phone or '') if customer else '',
        'received_by': user_display_name(pay.recorded_by),
        'paid_towards': [target],
        'paid_towards_label': target['label'],
        'balance_before': None,
        'balance_after': str(_q(invoice.balance)) if invoice else None,
        'previous_debt': None,
        'new_debt': None,
        'payment_amount': str(_q(pay.amount)),
        'debt_added': None,
        'sale_total': str(_q(invoice.total)) if invoice else None,
        'sale_paid': None,
        'delta_debt': None,
    }


def _serialize_sale_tender(
    sale: Sale,
    *,
    tender_amount=None,
) -> Dict[str, Any]:
    from sales.sale_debt_sync import sale_checkout_tender_amount

    customer = sale.customer
    unpaid = max(Decimal('0.00'), _q(sale.total) - _q(sale.amount_paid))
    method = (sale.payment_method or '').strip().lower()
    if tender_amount is None:
        tender = sale_checkout_tender_amount(sale)
    else:
        tender = _q(tender_amount)
    target = {
        'type': 'sale',
        'sale_id': sale.id,
        'sale_number': sale.sale_number,
        'label': f'Sale {sale.sale_number}',
        'amount': str(tender),
    }
    return {
        'kind': KIND_SALE_PAYMENT,
        'id': sale.id,
        'occurred_at': (sale.occurred_at or sale.created_at).isoformat()
        if (sale.occurred_at or sale.created_at)
        else None,
        'amount': str(tender),
        'payment_method': method,
        'payment_method_label': _method_label(method),
        'reference': getattr(sale, 'payment_reference', '') or '',
        'notes': '',
        'customer_id': sale.customer_id,
        'customer_name': customer.name if customer else '',
        'customer_code': (customer.customer_code or '') if customer else '',
        'customer_phone': (customer.phone or '') if customer else '',
        'received_by': user_display_name(sale.cashier),
        'paid_towards': [target],
        'paid_towards_label': target['label'],
        'balance_before': None,
        'balance_after': None,
        'previous_debt': None,
        'new_debt': str(_q(unpaid)) if unpaid > 0 else '0.00',
        'payment_amount': str(tender),
        'debt_added': None,
        'sale_total': str(_q(sale.total)),
        'sale_paid': str(_q(sale.amount_paid)),
        'checkout_tender': str(tender),
        'delta_debt': None,
    }
