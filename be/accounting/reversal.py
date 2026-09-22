"""Reverse posted journal transactions so books stay balanced after a correction."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import JournalEntry, Transaction

REVERSAL_TYPE = 'reversal'


def transaction_is_reversed(txn: Transaction) -> bool:
    return Transaction.objects.filter(
        reference_type=REVERSAL_TYPE,
        reference_id=txn.id,
    ).exists()


def source_transactions(reference_type: str, reference_id: int):
    return Transaction.objects.filter(
        reference_type=reference_type,
        reference_id=reference_id,
    ).prefetch_related('journal_entries')


@transaction.atomic
def reverse_posted_transaction(txn: Transaction, *, reason: str, user) -> Transaction:
    """Create a balancing opposite of ``txn``. Never deletes original journals."""
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError({'reason': 'A reason is required to reverse a journal.'})
    if transaction_is_reversed(txn):
        raise ValidationError('This transaction has already been reversed.')

    entries = list(txn.journal_entries.all())
    if not entries:
        raise ValidationError('This transaction has no journal lines to reverse.')

    today = timezone.now().date()
    reverse = Transaction.objects.create(
        transaction_date=today,
        description=f'Reversal of {txn.transaction_number}: {reason}',
        reference=txn.transaction_number,
        reference_type=REVERSAL_TYPE,
        reference_id=txn.id,
        created_by=user,
    )
    created = []
    for line in entries:
        swapped = 'credit' if line.entry_type == 'debit' else 'debit'
        created.append(
            JournalEntry.objects.create(
                entry_date=today,
                account=line.account,
                entry_type=swapped,
                amount=line.amount,
                description=f'Reversal: {line.description}',
                reference=txn.transaction_number,
                reference_type=REVERSAL_TYPE,
                reference_id=txn.id,
                created_by=user,
            )
        )
    reverse.journal_entries.add(*created)
    if not reverse.validate_balance():
        raise ValidationError('Reversal journals did not balance.')
    return reverse


def reverse_source_documents(reference_type: str, reference_id: int, *, reason: str, user) -> list[Transaction]:
    """Reverse every unreversed posting for a source document (expense, income, sale)."""
    reversed_txns = []
    for txn in source_transactions(reference_type, reference_id):
        if transaction_is_reversed(txn):
            continue
        reversed_txns.append(reverse_posted_transaction(txn, reason=reason, user=user))
    return reversed_txns
