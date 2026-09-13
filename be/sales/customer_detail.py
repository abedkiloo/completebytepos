"""Lifetime customer profile: standing, orders, and debt/payment trail."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.db.models import Sum

from sales.daily_sales import classify_sale_payment, serialize_daily_order
from sales.debt_management import debt_amount_from_balance
from sales.models import Customer, CustomerWalletTransaction, Sale


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
    flow = debt_flow_for_txn(
        transaction_type=txn.transaction_type,
        source_type=txn.source_type,
        amount=Decimal(str(txn.amount or 0)),
        balance_after=Decimal(str(txn.balance_after or 0)),
        sale=txn.sale,
    )
    created_by_name = None
    if txn.created_by_id:
        created_by_name = txn.created_by.username

    return {
        'id': txn.id,
        'transaction_type': txn.transaction_type,
        'source_type': txn.source_type,
        'amount': str(_q(txn.amount)),
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
        'is_active': customer.is_active,
        'wallet_balance': str(wallet_balance),
        'wallet_debt': str(wallet_debt),
        'wallet_credit': str(wallet_credit),
        'total_outstanding': str(invoice_outstanding),
        'total_invoices': customer.total_invoices,
        'standing': standing,
    }


def _standing_summary(customer: Customer) -> Dict[str, Any]:
    profile = _serialize_customer_profile(customer)
    lifetime_sales = Sale.objects.filter(customer_id=customer.id, status='completed')
    lifetime_count = lifetime_sales.count()
    lifetime_total = lifetime_sales.aggregate(t=Sum('total'))['t'] or Decimal('0.00')

    debt_txns = CustomerWalletTransaction.objects.filter(
        customer_id=customer.id,
        source_type='debt',
    )
    settlements = CustomerWalletTransaction.objects.filter(
        customer_id=customer.id,
        source_type='debt_settlement',
    )
    total_debt_incurred = debt_txns.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    total_debt_collected = settlements.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    return {
        'standing': profile['standing'],
        'wallet_balance': profile['wallet_balance'],
        'wallet_debt': profile['wallet_debt'],
        'wallet_credit': profile['wallet_credit'],
        'total_outstanding': profile['total_outstanding'],
        'lifetime_orders': lifetime_count,
        'lifetime_sales_total': str(_q(lifetime_total)),
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
    base_sales_queryset=None,
) -> Dict[str, Any]:
    """Compose lifetime customer profile for the detail screen."""
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist as exc:
        raise LookupError('Customer not found.') from exc

    if base_sales_queryset is not None:
        sales_qs = base_sales_queryset.filter(customer_id=customer.id, status='completed')
    else:
        sales_qs = Sale.objects.filter(customer_id=customer.id, status='completed')

    sales_qs = (
        sales_qs.select_related('customer', 'cashier', 'served_by')
        .prefetch_related('items__product', 'items__refund_lines')
        .order_by('-occurred_at', '-created_at')
    )
    order_rows, orders_pagination = _paginate(sales_qs, orders_page, orders_page_size)
    orders = [serialize_daily_order(sale) for sale in order_rows]

    ledger_qs = (
        CustomerWalletTransaction.objects.filter(customer_id=customer.id)
        .select_related('sale', 'created_by')
        .order_by('-created_at', '-id')
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
