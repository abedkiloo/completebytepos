"""Domain-specific audit log writers — thin wrappers over ``audit_helpers``."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Model

from accounts.models import AuditLog
from utils.audit_helpers import log_domain_event, log_model_change


def _money(value) -> str:
    if value is None:
        return ''
    return str(Decimal(str(value)))


def log_sale_completed(request, sale, *, source: str = 'checkout'):
    """
    Audit when a sale is completed and tender is recorded.

    Args:
        request: Actor request (may be None).
        sale: Saved ``sales.Sale`` instance.
        source: Origin label (``checkout``, ``approval``, …); max useful ~32 chars.

    Returns:
        None.

    Side effects:
        Appends one ``AuditLog`` row with ``lifecycle=money_posted``.
    """
    items = list(sale.items.all()) if hasattr(sale, 'items') else []
    customer = getattr(sale, 'customer', None)
    action = 'checkout' if source == 'checkout' else 'sale_completed'
    method = getattr(sale, 'payment_method', '') or ''
    total = _money(getattr(sale, 'total', None))
    paid = _money(getattr(sale, 'amount_paid', None))
    log_domain_event(
        request,
        action,
        sale,
        module='sales',
        changes={
            'lifecycle': 'money_posted',
            'source': source,
            'sale_number': getattr(sale, 'sale_number', ''),
            'amount': paid or total,
            'total': total,
            'amount_paid': paid,
            'payment_method': method,
            'reference': getattr(sale, 'payment_reference', '') or '',
            'status': getattr(sale, 'status', ''),
            'item_count': len(items),
            'customer_id': getattr(sale, 'customer_id', None),
            'customer_name': getattr(customer, 'name', '') if customer else '',
            'customer_code': getattr(customer, 'customer_code', '') if customer else '',
        },
        object_repr=(
            f"Sale money posted · {getattr(sale, 'sale_number', sale.pk)} · "
            f"{total or paid} · {method or '—'}"
        )[:255],
    )


def log_debt_settlement_posted(
    request,
    *,
    customer,
    txn,
    amount,
    payment_method: str = '',
    reference: str = '',
    pending_change_id=None,
    via: str = 'direct',
):
    """
    Audit the moment cash actually hits the customer wallet.

    Distinct from ``pending_submit`` / ``pending_approve`` so finance can see
    workflow vs money posted as separate audit rows.

    Args:
        request: Actor request-like object (``user``, ``META``, ``path``, ``method``).
        customer: Customer whose wallet was credited.
        txn: ``CustomerWalletTransaction`` (or compatible) for object_id.
        amount: Decimal/str/float collection amount (> 0).
        payment_method: Tender label (cash, mpesa, …); falls back to txn.
        reference: External ref (e.g. M-PESA code); falls back to txn.
        pending_change_id: Optional linked PendingChange pk when via approval.
        via: ``direct`` or ``approval``.

    Returns:
        None.

    Side effects:
        Appends one ``AuditLog`` with action ``debt_settlement_posted``.
    """
    changes = {
        'lifecycle': 'money_posted',
        'via': via,
        'amount': _money(amount),
        'payment_method': payment_method or getattr(txn, 'payment_method', '') or '',
        'reference': reference or getattr(txn, 'reference', '') or '',
        'transaction_id': getattr(txn, 'id', None),
        'customer_id': getattr(customer, 'id', None),
        'customer_name': getattr(customer, 'name', '') or '',
        'customer_code': getattr(customer, 'customer_code', '') or '',
        'wallet_balance_after': _money(getattr(customer, 'wallet_balance', None)),
    }
    if pending_change_id is not None:
        changes['pending_change_id'] = pending_change_id
    method = changes['payment_method'] or '—'
    ref = changes['reference']
    label = (
        f"Money posted · debt collection · {changes['amount']} · {method}"
        + (f" · ref {ref}" if ref else '')
        + f" · {changes['customer_name'] or 'Customer'}"
    )
    instance = txn if isinstance(txn, Model) else None
    log_domain_event(
        request,
        'debt_settlement_posted',
        instance,
        module='sales',
        changes=changes,
        object_repr=label[:255],
    )


def log_debt_settlement_corrected(
    request,
    *,
    customer,
    txn,
    old_amount,
    new_amount,
    reason: str = '',
):
    """
    Audit admin correction of cash collected on a posted debt settlement.

    Args:
        request: Actor request-like object.
        customer: Customer whose wallet was adjusted.
        txn: Updated ``CustomerWalletTransaction``.
        old_amount: Amount before correction.
        new_amount: Amount after correction (>= 0.01).
        reason: Optional free-text reason (truncated in changes).

    Returns:
        None.

    Side effects:
        Appends one ``AuditLog`` with action ``debt_settlement_corrected``.
    """
    changes = {
        'lifecycle': 'money_corrected',
        'old_amount': _money(old_amount),
        'new_amount': _money(new_amount),
        'transaction_id': getattr(txn, 'id', None),
        'customer_id': getattr(customer, 'id', None),
        'customer_name': getattr(customer, 'name', '') or '',
        'wallet_balance_after': _money(getattr(customer, 'wallet_balance', None)),
        'reason': (reason or '')[:200],
    }
    label = (
        f"Money corrected · debt collection · {changes['old_amount']} → "
        f"{changes['new_amount']} · {changes['customer_name'] or 'Customer'}"
    )
    instance = txn if isinstance(txn, Model) else None
    log_domain_event(
        request,
        'debt_settlement_corrected',
        instance,
        module='sales',
        changes=changes,
        object_repr=label[:255],
    )


def log_holding_saved(request, holding, *, created: bool):
    log_domain_event(
        request,
        'holding_save',
        holding,
        module='sales',
        changes={
            'created': created,
            'sale_number': getattr(holding, 'sale_number', ''),
            'status': getattr(holding, 'status', ''),
            'item_count': holding.items.count(),
        },
    )


def log_sale_refunded(request, sale, refund):
    log_domain_event(
        request,
        'refund',
        refund,
        module='sales',
        changes={
            'sale_number': getattr(sale, 'sale_number', ''),
            'refund_number': getattr(refund, 'refund_number', ''),
            'refund_type': getattr(refund, 'refund_type', ''),
            'amount': _money(getattr(refund, 'amount', None)),
            'reason': (getattr(refund, 'reason', '') or '')[:500],
            'sale_refund_status': getattr(sale, 'refund_status', ''),
        },
    )


def log_sale_rolled_back(request, sale, refund):
    log_domain_event(
        request,
        'rollback',
        refund,
        module='sales',
        changes={
            'sale_number': getattr(sale, 'sale_number', ''),
            'refund_number': getattr(refund, 'refund_number', ''),
            'refund_type': getattr(refund, 'refund_type', ''),
            'amount': _money(getattr(refund, 'amount', None)),
            'reason': (getattr(refund, 'reason', '') or '')[:500],
            'sale_refund_status': getattr(sale, 'refund_status', ''),
        },
    )


def log_sale_unvoided(request, sale, *, kind='unvoid', reason=''):
    log_domain_event(
        request,
        kind if kind in ('unvoid', 'uncancel') else 'unvoid',
        sale,
        module='sales',
        changes={
            'sale_number': getattr(sale, 'sale_number', ''),
            'sale_status': getattr(sale, 'status', ''),
            'sale_refund_status': getattr(sale, 'refund_status', ''),
            'reason': (reason or '')[:500],
        },
    )


def log_holding_cancelled(request, holding):
    log_domain_event(
        request,
        'holding_cancel',
        holding,
        module='sales',
        changes={'sale_number': getattr(holding, 'sale_number', '')},
    )


def log_sale_discarded(request, sale, *, reason: str = ''):
    """
    Audit permanent removal of a returned sale.

    Args:
        request: Authenticated request.
        sale: Sale with status discarded.
        reason: Admin reason (truncated to 500 chars).
    """
    log_domain_event(
        request,
        'sale_discarded',
        sale,
        module='sales',
        changes={
            'sale_number': getattr(sale, 'sale_number', ''),
            'status': getattr(sale, 'status', ''),
            'reason': (reason or '')[:500],
        },
    )


def log_product_write(request, product: Model, *, before: Model | None, action: str):
    log_model_change(request, action, product, module='products', before=before)


def log_sale_date_corrected(request, sale, *, previous):
    log_domain_event(
        request,
        'update',
        sale,
        module='sales',
        changes={
            'sale_number': getattr(sale, 'sale_number', ''),
            'occurred_at_from': previous.isoformat() if previous else '',
            'occurred_at_to': (
                sale.occurred_at.isoformat() if getattr(sale, 'occurred_at', None) else ''
            ),
        },
    )


def log_stock_movement_event(request, movement: Model, *, event: str, payload: dict | None = None):
    changes = dict(payload or {})
    changes['movement_type'] = getattr(movement, 'movement_type', '')
    changes['quantity'] = getattr(movement, 'quantity', None)
    log_domain_event(request, event, movement, module='inventory', changes=changes)


def log_approval_event(request, instance: Model, *, module: str):
    log_domain_event(
        request,
        'approve',
        instance,
        module=module,
        changes={'status': getattr(instance, 'status', '')},
    )


def log_permission_denied(request, *, module: str, action: str, detail: str = ''):
    log_domain_event(
        request,
        AuditLog.ACTION_PERMISSION_DENIED,
        None,
        module=module,
        changes={'action': action, 'detail': detail},
    )


def log_simple_action(
    request,
    action: str,
    instance=None,
    *,
    module: str,
    changes: dict | None = None,
    object_repr: str | None = None,
):
    """
    Non-blocking audit for any module action (dispatch, delivery, messaging, …).

    Args:
        request: Actor request (may be None for system jobs).
        action: Short verb (≤32 chars), e.g. ``pack``, ``arrive``, ``sms_send``.
        instance: Related model instance, or None.
        module: Permission module string (``dispatch``, ``delivery``, …).
        changes: Optional JSON-safe payload.
        object_repr: Optional display string.

    Returns:
        None. Never raises to callers.
    """
    try:
        log_domain_event(
            request,
            action,
            instance,
            module=module,
            changes=changes or {},
            object_repr=object_repr,
        )
    except Exception:
        # Defensive: log_domain_event already swallows; keep callers safe.
        pass
