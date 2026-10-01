"""Manager/admin correction of a sale's business date."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from sales.sale_completion_approval import user_can_complete_sales

DATE_CORRECTION_NOT_ALLOWED = 'Only a manager or admin can change the sale date.'
DATE_CORRECTION_STATUS_BLOCKED = 'This sale cannot have its date changed.'
DATE_CORRECTION_FUTURE = 'Sale date cannot be more than one day in the future.'
BLOCKED_STATUSES = frozenset({'cancelled'})


def user_can_correct_sale_date(user) -> bool:
    return user_can_complete_sales(user)


def sale_date_can_be_corrected(sale, user) -> bool:
    if not user_can_correct_sale_date(user):
        return False
    return getattr(sale, 'status', None) not in BLOCKED_STATUSES


def parse_sale_date_payload(data, *, current) -> datetime:
    payload = data or {}
    raw_at = payload.get('occurred_at')
    raw_on = payload.get('occurred_on') or payload.get('sale_date')
    if raw_at not in (None, ''):
        occurred_at = raw_at if isinstance(raw_at, datetime) else parse_datetime(str(raw_at))
        if occurred_at is None:
            raise ValidationError({'occurred_at': 'Enter a valid date and time.'})
        if timezone.is_naive(occurred_at):
            occurred_at = timezone.make_aware(occurred_at, timezone.get_current_timezone())
        return occurred_at
    if raw_on not in (None, ''):
        day = raw_on if hasattr(raw_on, 'year') and not isinstance(raw_on, datetime) else parse_date(str(raw_on))
        if day is None:
            raise ValidationError({'occurred_on': 'Enter a valid sale date.'})
        current_local = timezone.localtime(current or timezone.now())
        combined = datetime.combine(day, current_local.time() or time(12, 0))
        return timezone.make_aware(combined, timezone.get_current_timezone())
    raise ValidationError({'occurred_on': 'Sale date is required.'})


def validate_sale_date_correction(occurred_at: datetime) -> None:
    if occurred_at is None:
        raise ValidationError({'occurred_on': 'Sale date is required.'})
    local_day = timezone.localtime(occurred_at).date()
    today = timezone.localdate()
    if local_day > today + timedelta(days=1):
        raise ValidationError({'occurred_on': DATE_CORRECTION_FUTURE})
    from sales.backfill_policy import backfill_max_days

    max_days = backfill_max_days()
    if max_days and local_day < today - timedelta(days=max_days):
        raise ValidationError({
            'occurred_on': f'Sale date cannot be more than {max_days} days in the past.',
        })


def _sale_local_date(when):
    if when is None:
        return None
    if timezone.is_aware(when):
        return timezone.localtime(when).date()
    return when.date()


@transaction.atomic
def correct_sale_occurred_at(sale, occurred_at: datetime, *, user) -> object:
    if not user_can_correct_sale_date(user):
        raise ValidationError(DATE_CORRECTION_NOT_ALLOWED)
    if getattr(sale, 'status', None) in BLOCKED_STATUSES:
        raise ValidationError(DATE_CORRECTION_STATUS_BLOCKED)
    validate_sale_date_correction(occurred_at)

    previous = sale.occurred_at
    previous_day = _sale_local_date(previous)
    new_day = timezone.localtime(occurred_at).date()
    if previous and timezone.localtime(previous) == timezone.localtime(occurred_at):
        return sale

    sale.occurred_at = occurred_at
    sale.save(update_fields=['occurred_at', 'updated_at'])
    _shift_related_books(sale, previous_day=previous_day, new_day=new_day)
    return sale


def _shift_related_books(sale, *, previous_day, new_day) -> None:
    from accounting.models import JournalEntry, Transaction
    from sales.models import Invoice, Payment

    JournalEntry.objects.filter(
        reference_type='sale',
        reference_id=sale.id,
    ).update(entry_date=new_day)
    Transaction.objects.filter(
        reference_type='sale',
        reference_id=sale.id,
    ).update(transaction_date=new_day)

    invoices = Invoice.objects.filter(sale=sale)
    for invoice in invoices:
        if invoice.issued_date is None or invoice.issued_date == previous_day:
            invoice.issued_date = new_day
            invoice.save(update_fields=['issued_date', 'updated_at'])
        payments = Payment.objects.filter(invoice=invoice)
        if previous_day is None:
            payments.update(payment_date=new_day)
        else:
            payments.filter(payment_date=previous_day).update(payment_date=new_day)
