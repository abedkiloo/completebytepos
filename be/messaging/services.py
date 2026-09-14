from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from sales.models import Customer

from .models import MessageOutbox
from .providers import get_sms_provider
from .templates_sms import render_debt_reminder_sms


class MessagingError(ValidationError):
    pass


@transaction.atomic
def queue_debt_reminders(*, created_by=None, limit: int = 50) -> list[MessageOutbox]:
    """
    Basic overdue wallet debt reminders: customers with negative wallet_balance.
    Creates a lightweight PaymentIntent-less reminder using a public token stub
    on MessageOutbox body link (token = customer id hex for demo).
    """
    debtors = (
        Customer.objects.filter(wallet_balance__lt=0)
        .order_by('wallet_balance')[:limit]
    )
    queued = []
    provider = get_sms_provider()
    for customer in debtors:
        phone = (customer.phone or '').strip()
        if not phone:
            continue
        amount = abs(customer.wallet_balance)
        token = f'debt-{customer.pk}'
        body = render_debt_reminder_sms(
            customer_name=customer.name,
            amount=amount,
            public_token=token,
        )
        msg = MessageOutbox.objects.create(
            to_phone=phone,
            body=body,
            template_key=MessageOutbox.TEMPLATE_DEBT_REMINDER,
            customer=customer,
            created_by=created_by,
        )
        result = provider.send(to=phone, body=body)
        msg.provider = getattr(provider, 'name', '') or ''
        if result.ok:
            msg.status = MessageOutbox.STATUS_SENT
            msg.provider_ref = result.provider_ref
            msg.sent_at = timezone.now()
        else:
            msg.status = MessageOutbox.STATUS_FAILED
            msg.error = result.error
        msg.save()
        queued.append(msg)
    return queued


def owed_amount(customer: Customer) -> Decimal:
    bal = customer.wallet_balance or Decimal('0')
    return abs(bal) if bal < 0 else Decimal('0')
