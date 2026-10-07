"""Store-wide money-in trail: settlements, invoice payments, sale tender.

Paginated and N+1-free — list page hydrates targets in batched queries.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from django.db.models import Q
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


def list_payments_trail(
    *,
    kind: Optional[str] = None,
    date_from=None,
    date_to=None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user=None,
) -> Dict[str, Any]:
    """
    Paginated money-in trail with balancing fields and paid-towards targets.

    Designed for operator accountability — not a live dashboard cache.
    """
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    kinds = _parse_kinds(kind)
    day_from = _parse_day(date_from)
    day_to = _parse_day(date_to)
    # Bound unbounded scans so the trail stays fast without a cache layer.
    if day_from is None and day_to is None:
        day_from = timezone.localdate() - timedelta(days=30)
        day_to = timezone.localdate()
    term = (search or '').strip()

    visible_ids = _visible_debtor_customer_ids(user)

    index_rows: List[Dict[str, Any]] = []
    if KIND_DEBT_SETTLEMENT in kinds:
        index_rows.extend(_settlement_index(day_from, day_to, term, visible_ids))
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


def _settlement_index(day_from, day_to, term, visible_ids) -> List[Dict[str, Any]]:
    qs = CustomerWalletTransaction.objects.filter(
        source_type='debt_settlement',
        transaction_type='credit',
    )
    if day_from:
        qs = qs.filter(created_at__date__gte=day_from)
    if day_to:
        qs = qs.filter(created_at__date__lte=day_to)
    if visible_ids is not None:
        qs = qs.filter(customer_id__in=list(visible_ids) or [])
    if term:
        qs = qs.filter(
            Q(customer__name__icontains=term)
            | Q(customer__phone__icontains=term)
            | Q(customer__customer_code__icontains=term)
            | Q(reference__icontains=term)
            | Q(notes__icontains=term)
        )
    return [
        {
            'kind': KIND_DEBT_SETTLEMENT,
            'source_id': row['id'],
            'occurred_at': row['created_at'],
        }
        for row in qs.order_by('-created_at', '-id').values('id', 'created_at')[:5000]
    ]


def _invoice_index(day_from, day_to, term, visible_ids) -> List[Dict[str, Any]]:
    qs = Payment.objects.all()
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
    qs = Sale.objects.filter(status='completed', amount_paid__gt=0)
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
        }
        for row in qs.order_by('-occurred_at', '-id').values(
            'id', 'occurred_at', 'created_at'
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
                results.append(_serialize_sale_tender(sale))
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
    return {
        'kind': KIND_DEBT_SETTLEMENT,
        'id': txn.id,
        'occurred_at': txn.created_at.isoformat() if txn.created_at else None,
        'amount': str(_q(txn.amount)),
        'payment_method': method,
        'payment_method_label': _method_label(method),
        'reference': txn.reference or '',
        'notes': txn.notes or '',
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


def _serialize_sale_tender(sale: Sale) -> Dict[str, Any]:
    customer = sale.customer
    unpaid = max(Decimal('0.00'), _q(sale.total) - _q(sale.amount_paid))
    method = (sale.payment_method or '').strip().lower()
    target = {
        'type': 'sale',
        'sale_id': sale.id,
        'sale_number': sale.sale_number,
        'label': f'Sale {sale.sale_number}',
        'amount': str(_q(sale.amount_paid)),
    }
    return {
        'kind': KIND_SALE_PAYMENT,
        'id': sale.id,
        'occurred_at': (sale.occurred_at or sale.created_at).isoformat()
        if (sale.occurred_at or sale.created_at)
        else None,
        'amount': str(_q(sale.amount_paid)),
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
        'payment_amount': str(_q(sale.amount_paid)),
        'debt_added': None,
        'sale_total': str(_q(sale.total)),
        'sale_paid': str(_q(sale.amount_paid)),
        'delta_debt': None,
    }
