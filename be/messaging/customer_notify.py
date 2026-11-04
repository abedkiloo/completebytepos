"""
Customer-triggered SMS hooks (sale, debt, welcome).

Public entry points:
    - ``notify_customer_*`` — queue outbox + send on commit
    - ``dispatch_outbox`` — single-message provider send

Never raises into sales/payment paths; failures are logged and return ``None``.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import MessageOutbox
from .providers import get_sms_provider
from .templates_sms import (
    customer_first_name,
    customer_greeting_name,
    render_customer_welcome_sms,
    render_debt_increase_sms,
    render_debt_settlement_sms,
    render_sale_completed_sms,
)

logger = logging.getLogger(__name__)


def dispatch_outbox(msg: MessageOutbox) -> MessageOutbox:
    """
    Send one outbox message synchronously.

    Args:
        msg: Row with ``to_phone`` and ``body``.

    Returns:
        Updated row with ``sent`` or ``failed`` status and provider metadata.

    Side effects:
        External SMS API call.
    """
    provider = get_sms_provider()
    result = provider.send(to=msg.to_phone, body=msg.body)
    msg.provider = getattr(provider, 'name', '') or ''
    if result.ok:
        msg.status = MessageOutbox.STATUS_SENT
        msg.provider_ref = result.provider_ref
        msg.sent_at = timezone.now()
        msg.error = ''
    else:
        msg.status = MessageOutbox.STATUS_FAILED
        msg.error = result.error
    msg.save(
        update_fields=['provider', 'status', 'provider_ref', 'sent_at', 'error']
    )
    return msg


def _owed(customer) -> Decimal:
    bal = getattr(customer, 'wallet_balance', None) or Decimal('0')
    bal = Decimal(str(bal))
    return abs(bal) if bal < 0 else Decimal('0')


def _queue_customer_sms(*, customer, body: str, template_key: str, created_by=None):
    phone = (getattr(customer, 'phone', None) or '').strip()
    if not phone or not customer:
        return None
    msg = MessageOutbox.objects.create(
        to_phone=phone,
        body=body,
        template_key=template_key,
        customer=customer,
        created_by=created_by,
    )

    def _send():
        try:
            dispatch_outbox(msg)
        except Exception:
            logger.exception('SMS dispatch failed for outbox %s', msg.pk)

    transaction.on_commit(_send)
    return msg


def notify_customer_sale_completed(
    sale,
    *,
    user=None,
    force_late_entry: bool = False,
) -> MessageOutbox | None:
    """
    Queue sale-complete SMS after checkout.

    Late/backfill sales (``entry_source='backfill'``) are skipped unless
    ``force_late_entry=True`` — callers must opt in (Record past sale /
    ``notify_customer`` on ``_apply_sale_payment``).

    Args:
        sale: Completed sale with optional customer and line items.
        user: Stored as ``created_by`` on outbox.
        force_late_entry: When True, allow SMS for backfill/late sales.
            Default False preserves historical “never text late sales”
            unless the operator explicitly chose to send.

    Returns:
        Outbox row when queued, else ``None`` (no customer/phone, skipped
        late entry, or errors swallowed).

    Side effects:
        Creates outbox; sends on transaction commit via ``dispatch_outbox``.
    """
    try:
        customer = getattr(sale, 'customer', None)
        if customer is None:
            return None
        if getattr(sale, 'entry_source', '') == 'backfill':
            if not force_late_entry:
                return None
            from sales.module_settings import sales_late_sale_sms_enabled

            if not sales_late_sale_sms_enabled():
                return None
        customer.refresh_from_db(fields=['wallet_balance', 'phone', 'name', 'owner_name', 'contact_person'])
        paid = Decimal(str(sale.amount_paid or 0))
        total = Decimal(str(sale.total or 0))
        unpaid = total - paid
        balance = _owed(customer)
        # Prefer showing sale unpaid if wallet not yet reflecting; else wallet owed.
        show_balance = unpaid if unpaid > 0 else (balance if balance > 0 else None)
        if unpaid > 0 and balance > 0:
            show_balance = balance
        items = sale.items.select_related(
            'product', 'variant', 'variant__size', 'variant__color', 'size', 'color'
        ).all()
        body = render_sale_completed_sms(
            first_name=customer_first_name(customer),
            sale_number=sale.sale_number or str(sale.pk),
            total=total,
            paid=paid,
            balance_owed=show_balance,
            items=items,
            payment_reference=getattr(sale, 'payment_reference', None) or '',
        )
        return _queue_customer_sms(
            customer=customer,
            body=body,
            template_key=MessageOutbox.TEMPLATE_SALE_COMPLETED,
            created_by=user,
        )
    except Exception:
        logger.exception('notify_customer_sale_completed failed for sale %s', getattr(sale, 'pk', None))
        return None


def notify_customer_debt_increase(customer, *, amount, user=None) -> MessageOutbox | None:
    """
    Queue SMS when customer debt increases outside a sale-complete flow.

    Args:
        customer: Target customer with phone.
        amount: Positive debt increase amount; ignored when ≤ 0.
        user: Outbox ``created_by``.

    Returns:
        Outbox row or ``None`` when skipped/failed (logged, not raised).
    """
    try:
        amount = Decimal(str(amount or 0))
        if amount <= 0 or customer is None:
            return None
        customer.refresh_from_db(fields=['wallet_balance', 'phone', 'name', 'owner_name', 'contact_person'])
        body = render_debt_increase_sms(
            first_name=customer_first_name(customer),
            amount=amount,
            balance_owed=_owed(customer),
        )
        return _queue_customer_sms(
            customer=customer,
            body=body,
            template_key=MessageOutbox.TEMPLATE_DEBT_INCREASE,
            created_by=user,
        )
    except Exception:
        logger.exception('notify_customer_debt_increase failed for customer %s', getattr(customer, 'pk', None))
        return None


def notify_customer_debt_settlement(
    customer, *, amount, payment_reference: str | None = None, user=None,
) -> MessageOutbox | None:
    """
    Queue SMS when a debt payment is recorded.

    Args:
        customer: Debtor receiving confirmation.
        amount: Payment amount; must be > 0.
        payment_reference: Optional M-Pesa or receipt reference in body.
        user: Outbox ``created_by``.

    Returns:
        Outbox row or ``None`` when skipped/failed.
    """
    try:
        amount = Decimal(str(amount or 0))
        if amount <= 0 or customer is None:
            return None
        customer.refresh_from_db(fields=['wallet_balance', 'phone', 'name', 'owner_name', 'contact_person'])
        body = render_debt_settlement_sms(
            first_name=customer_first_name(customer),
            amount=amount,
            balance_owed=_owed(customer),
            payment_reference=payment_reference,
        )
        return _queue_customer_sms(
            customer=customer,
            body=body,
            template_key=MessageOutbox.TEMPLATE_DEBT_SETTLEMENT,
            created_by=user,
        )
    except Exception:
        logger.exception(
            'notify_customer_debt_settlement failed for customer %s',
            getattr(customer, 'pk', None),
        )
        return None


def notify_customer_welcome(customer, *, user=None) -> MessageOutbox | None:
    """
    Queue welcome SMS for a newly registered customer/duka.

    Args:
        customer: Must have phone for send.
        user: Outbox ``created_by``.

    Returns:
        Outbox row or ``None`` when no phone or on internal error.
    """
    try:
        if customer is None:
            return None
        customer.refresh_from_db(fields=['phone', 'name', 'owner_name', 'contact_person'])
        phone = (getattr(customer, 'phone', None) or '').strip()
        if not phone:
            return None
        from settings.store_settings_helpers import resolved_store_name

        body = render_customer_welcome_sms(
            name=customer_greeting_name(customer),
            store_name=resolved_store_name() or 'Omuwenga',
        )
        return _queue_customer_sms(
            customer=customer,
            body=body,
            template_key=MessageOutbox.TEMPLATE_CUSTOMER_WELCOME,
            created_by=user,
        )
    except Exception:
        logger.exception(
            'notify_customer_welcome failed for customer %s',
            getattr(customer, 'pk', None),
        )
        return None
