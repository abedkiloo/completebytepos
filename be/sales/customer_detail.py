"""Lifetime customer profile: standing, orders, and debt/payment trail."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.db.models import Sum

from sales.daily_sales import classify_sale_payment, serialize_daily_order
from sales.debt_management import debt_amount_from_balance
from sales.models import Customer, CustomerWalletTransaction, Sale
from utils.list_ordering import mapped_ordering


def _q(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def _debt_from_balance(balance: Decimal) -> Decimal:
    return debt_amount_from_balance(balance).quantize(Decimal('0.01'))


def balance_before_from_txn(transaction_type: str, amount: Decimal, balance_after: Decimal) -> Decimal:
    """Reconstruct wallet balance before a ledger row (balance_before is not stored)."""
    amount = _q(amount)
    balance_after = _q(balance_after)
    if transaction_type == 'credit':
        return (balance_after - amount).quantize(Decimal('0.01'))
    # debit (and unknown) move balance down
    return (balance_after + amount).quantize(Decimal('0.01'))


def debt_flow_for_txn(
    *,
    transaction_type: str,
    source_type: str,
    amount: Decimal,
    balance_after: Decimal,
    sale: Optional[Sale] = None,
) -> Dict[str, Any]:
    """
    Narrative for a wallet event, e.g.:
      previous_debt 600 · paid 300 · new_debt 300
      previous_debt 0 · sale_paid 330 · debt_added 270 · new_debt 270
    """
    amount = _q(amount)
    balance_after = _q(balance_after)
    balance_before = balance_before_from_txn(transaction_type, amount, balance_after)
    previous_debt = _debt_from_balance(balance_before)
    new_debt = _debt_from_balance(balance_after)

    sale_total = None
    sale_paid = None
    debt_added = None
    payment_amount = None

    if source_type == 'debt_settlement' and transaction_type == 'credit':
        payment_amount = amount
    elif source_type == 'debt' and transaction_type == 'debit':
        debt_added = amount
        if sale is not None:
            sale_total = _q(sale.total)
            paid, _, _ = classify_sale_payment(Decimal(str(sale.total or 0)), Decimal(str(sale.amount_paid or 0)))
            sale_paid = paid
    elif source_type == 'payment' and transaction_type == 'debit':
        payment_amount = amount  # wallet credit used toward a sale
    elif transaction_type == 'credit':
        payment_amount = amount

    return {
        'balance_before': str(balance_before),
        'balance_after': str(balance_after),
        'previous_debt': str(previous_debt),
        'new_debt': str(new_debt),
        'payment_amount': str(payment_amount) if payment_amount is not None else None,
        'debt_added': str(debt_added) if debt_added is not None else None,
        'sale_total': str(sale_total) if sale_total is not None else None,
        'sale_paid': str(sale_paid) if sale_paid is not None else None,
        'delta_debt': str((new_debt - previous_debt).quantize(Decimal('0.01'))),
    }


def serialize_ledger_entry(txn: CustomerWalletTransaction) -> Dict[str, Any]:
    from sales.debt_management import (
        payment_method_label,
        resolve_settlement_payment_method,
        user_display_name,
    )

    flow = debt_flow_for_txn(
        transaction_type=txn.transaction_type,
        source_type=txn.source_type,
        amount=Decimal(str(txn.amount or 0)),
        balance_after=Decimal(str(txn.balance_after or 0)),
        sale=txn.sale,
    )
    created_by_name = user_display_name(txn.created_by) if txn.created_by_id else ''
    method = ''
    method_label = ''
    if txn.source_type == 'debt_settlement':
        method = resolve_settlement_payment_method(txn)
        method_label = payment_method_label(method)

    return {
        'id': txn.id,
        'transaction_type': txn.transaction_type,
        'source_type': txn.source_type,
        'amount': str(_q(txn.amount)),
        'payment_method': method,
        'payment_method_label': method_label,
        'reference': txn.reference or '',
        'notes': txn.notes or '',
        'sale': txn.sale_id,
        'sale_number': txn.sale.sale_number if txn.sale_id and txn.sale else None,
        'created_by_name': created_by_name,
        'created_at': txn.created_at.isoformat() if txn.created_at else None,
        **flow,
    }


def _serialize_customer_profile(customer: Customer) -> Dict[str, Any]:
    wallet_balance = _q(customer.wallet_balance)
    wallet_debt = _debt_from_balance(wallet_balance)
    wallet_credit = wallet_balance if wallet_balance > 0 else Decimal('0.00')
    invoice_outstanding = _q(customer.total_outstanding)
    standing = 'debt' if wallet_debt > 0 or invoice_outstanding > 0 else 'good'
    if wallet_credit > 0 and wallet_debt == 0 and invoice_outstanding == 0:
        standing = 'credit'

    return {
        'id': customer.id,
        'name': customer.name,
        'phone': customer.phone or '',
        'email': customer.email or '',
        'customer_code': customer.customer_code,
        'customer_type': customer.customer_type,
        'city': customer.city or '',
        'address': customer.address or '',
        'country': customer.country or '',
        'tax_id': customer.tax_id or '',
        'notes': customer.notes or '',
        'owner_name': customer.owner_name or '',
        'contact_person': customer.contact_person or '',
        'typical_goods': list(customer.typical_goods or []),
        'is_active': customer.is_active,
        'wallet_balance': str(wallet_balance),
        'wallet_debt': str(wallet_debt),
        'wallet_credit': str(wallet_credit),
        'total_outstanding': str(invoice_outstanding),
        'total_invoices': customer.total_invoices,
        'standing': standing,
    }


def _standing_summary(customer: Customer) -> Dict[str, Any]:
    from django.db.models import Count

    profile = _serialize_customer_profile(customer)
    lifetime = Sale.objects.filter(customer_id=customer.id, status='completed').aggregate(
        count=Count('id'),
        total=Sum('total'),
    )
    wallet_sums = {
        row['source_type']: row['total']
        for row in CustomerWalletTransaction.objects.filter(
            customer_id=customer.id,
            source_type__in=('debt', 'debt_settlement'),
        )
        .values('source_type')
        .annotate(total=Sum('amount'))
    }
    total_debt_incurred = wallet_sums.get('debt') or Decimal('0.00')
    total_debt_collected = wallet_sums.get('debt_settlement') or Decimal('0.00')

    return {
        'standing': profile['standing'],
        'wallet_balance': profile['wallet_balance'],
        'wallet_debt': profile['wallet_debt'],
        'wallet_credit': profile['wallet_credit'],
        'total_outstanding': profile['total_outstanding'],
        'lifetime_orders': int(lifetime['count'] or 0),
        'lifetime_sales_total': str(_q(lifetime['total'] or 0)),
        'total_debt_incurred': str(_q(total_debt_incurred)),
        'total_debt_collected': str(_q(total_debt_collected)),
    }


def _paginate(queryset, page: int, page_size: int) -> Tuple[List[Any], Dict[str, Any]]:
    page_num = max(1, int(page or 1))
    size = max(1, min(100, int(page_size or 25)))
    paginator = Paginator(queryset, size)
    page_obj = paginator.get_page(page_num)
    return list(page_obj.object_list), {
        'count': paginator.count,
        'page': page_obj.number,
        'page_size': size,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
    }


def get_customer_detail(
    *,
    customer_id: int,
    orders_page: int = 1,
    orders_page_size: int = 25,
    ledger_page: int = 1,
    ledger_page_size: int = 50,
    orders_ordering: str | None = None,
    ledger_ordering: str | None = None,
    base_sales_queryset=None,
) -> Dict[str, Any]:
    """Compose lifetime customer profile for the detail screen."""
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist as exc:
        raise LookupError('Customer not found.') from exc

    # Align wallet with underpaid POS sales so profile debt matches Debt Management.
    from sales.debt_management import ensure_wallet_matches_unpaid_sales

    ensure_wallet_matches_unpaid_sales(customer)
    customer.refresh_from_db()

    if base_sales_queryset is not None:
        sales_qs = base_sales_queryset.filter(customer_id=customer.id, status='completed')
    else:
        sales_qs = Sale.objects.filter(customer_id=customer.id, status='completed')

    order_fields = mapped_ordering(
        orders_ordering,
        aliases={'name': 'sale_number', 'saved': 'created_at'},
        allowed={'name', 'saved', 'created_at', 'occurred_at', 'sale_number'},
        default=('-occurred_at', '-created_at'),
    )
    sales_qs = (
        sales_qs.select_related('customer', 'cashier', 'served_by')
        .prefetch_related('items__product', 'items__refund_lines')
        .order_by(*order_fields)
    )
    order_rows, orders_pagination = _paginate(sales_qs, orders_page, orders_page_size)
    orders = [serialize_daily_order(sale) for sale in order_rows]

    ledger_fields = mapped_ordering(
        ledger_ordering,
        aliases={'name': 'source_type', 'saved': 'created_at'},
        allowed={'name', 'saved', 'created_at', 'source_type'},
        default=('-created_at', '-id'),
    )
    ledger_qs = (
        CustomerWalletTransaction.objects.filter(customer_id=customer.id)
        .select_related('sale', 'created_by')
        .order_by(*ledger_fields)
    )
    ledger_rows, ledger_pagination = _paginate(ledger_qs, ledger_page, ledger_page_size)
    ledger = [serialize_ledger_entry(txn) for txn in ledger_rows]

    return {
        'customer': _serialize_customer_profile(customer),
        'standing_summary': _standing_summary(customer),
        'orders': orders,
        'orders_pagination': orders_pagination,
        'ledger': ledger,
        'ledger_pagination': ledger_pagination,
    }
