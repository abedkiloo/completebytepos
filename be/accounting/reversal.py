"""
Reverse posted journal transactions without deleting historical lines.

Public entry points:
    - ``reverse_posted_transaction`` — mirror one ``Transaction``
    - ``reverse_source_documents`` — reverse all postings for a source id
    - ``transaction_is_reversed`` / ``source_transactions`` — lookup helpers

Side effects: creates new ``Transaction`` and ``JournalEntry`` rows with swapped
debit/credit; updates ``Account.current_balance``. Original postings remain.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import JournalEntry, Transaction

REVERSAL_TYPE = 'reversal'


def transaction_is_reversed(txn: Transaction) -> bool:
    """
    Check whether a balancing reversal transaction already exists.

    Args:
        txn: Posted transaction to inspect.

    Returns:
        True if any ``Transaction`` has ``reference_type='reversal'`` and
        ``reference_id=txn.id``; False otherwise.
    """
    return Transaction.objects.filter(
        reference_type=REVERSAL_TYPE,
        reference_id=txn.id,
    ).exists()


def source_transactions(reference_type: str, reference_id: int):
    """
    Load all GL transactions posted against one source document.

    Args:
        reference_type: Source module key (e.g. ``income``, ``expense``, ``sale``).
        reference_id: Primary key of the source row.

    Returns:
        ``QuerySet`` of ``Transaction`` with ``journal_entries`` prefetched.
    """
    return Transaction.objects.filter(
        reference_type=reference_type,
        reference_id=reference_id,
    ).prefetch_related('journal_entries')


@transaction.atomic
def reverse_posted_transaction(txn: Transaction, *, reason: str, user) -> Transaction:
    """
    Create an opposite journal transaction for one posted ``txn``.

    Never deletes original lines. Reversal dated ``timezone.now().date()``.

    Args:
        txn: Transaction with at least one journal line; must not already be reversed.
        reason: Non-blank explanation stored in reversal description.
        user: Acting user on new lines and reversal header.

    Returns:
        New ``Transaction`` linked to offsetting ``JournalEntry`` rows.

    Raises:
        ValidationError: Missing reason, already reversed, no lines, or imbalance
            after creation.

    Side effects:
        Creates reversal GL rows; refreshes affected account balances.
    """
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
    """
    Reverse every unreversed posting for one source document.

    Args:
        reference_type: Same key used when journals were created (e.g. ``income``).
        reference_id: Source row primary key.
        reason: Passed to each ``reverse_posted_transaction`` call.
        user: Acting user for all reversal rows.

    Returns:
        List of newly created reversal ``Transaction`` instances (may be empty if
        nothing to reverse or all already reversed).

    Raises:
        ValidationError: Propagated from ``reverse_posted_transaction`` on first failure.

    Side effects:
        One reversal transaction per original posting still open.
    """
    reversed_txns = []
    for txn in source_transactions(reference_type, reference_id):
        if transaction_is_reversed(txn):
            continue
        reversed_txns.append(reverse_posted_transaction(txn, reason=reason, user=user))
    return reversed_txns
