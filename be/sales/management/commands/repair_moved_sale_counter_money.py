"""
One-time fix for a moved sale whose counter money stayed on the old customer.

Counter money is the debt, the wallet used at the till, or an overpayment
that is still linked to the sale. A later debt repayment is not moved.
Run with no flag to see the rows. Add ``--apply`` to write them.

  python manage.py repair_moved_sale_counter_money
  python manage.py repair_moved_sale_counter_money --apply
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F, Q

from sales.models import CustomerWalletTransaction
from sales.sale_debt_sync import rebuild_customer_wallet_from_active_ledger

_COUNTER_SOURCES = ('debt', 'payment', 'overpayment')


def misplaced_counter_rows():
    """
    Counter rows still on a customer who no longer owns the moved sale.

    Args:
        None.

    Returns:
        QuerySet: 0–5000 wallet rows. A row is included only when the sale
        notes say it was moved, or the audit log records that move. Later
        repayments are excluded. No writes.

    Raises:
        None.
    """
    from accounts.models import AuditLog

    moved_ids = []
    logs = AuditLog.objects.filter(
        action='sale_customer_transferred',
    ).order_by('-id').values_list('changes', flat=True)[:500]
    for changes in logs:
        if not isinstance(changes, dict):
            continue
        try:
            moved_ids.append(int(changes.get('sale_id')))
        except (TypeError, ValueError):
            continue
    return (
        CustomerWalletTransaction.objects.filter(
            source_type__in=_COUNTER_SOURCES,
            sale__status='completed',
            sale__customer_id__isnull=False,
        )
        .exclude(customer_id=F('sale__customer_id'))
        .filter(
            Q(sale__notes__icontains='Moved from ')
            | Q(sale_id__in=moved_ids or [0])
        )
        .select_related('sale', 'sale__customer', 'customer')
        .order_by('sale_id', 'id')
    )


class Command(BaseCommand):
    """Move counter money onto the customer who now owns a moved sale."""

    help = 'Put counter money for a moved sale onto the customer who owns it now.'

    def add_arguments(self, parser):
        """
        Add the write flag.

        Args:
            parser: Django argument parser.

        Returns:
            None.

        Raises:
            None.
        """
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Write the customer change. Without this flag, only print the rows.',
        )

    def handle(self, *args, **options):
        """
        Print the stranded counter rows, and move them when --apply is set.

        Args:
            args: Unused positional args.
            options: ``apply`` is True only when the operator passed --apply.

        Returns:
            None. Prints one line per row. Names and amounts only, no phones.

        Raises:
            None. A database error from the wallet rebuild is left to Django.
        """
        rows = list(misplaced_counter_rows()[:500])
        apply = bool(options.get('apply'))
        if not rows:
            self.stdout.write('No moved sale has counter money on the old customer.')
            return
        self.stdout.write(
            f'{"APPLYING" if apply else "DRY-RUN"} {len(rows)} counter row(s) on moved sales.'
        )
        customer_ids = set()
        for row in rows:
            sale = row.sale
            self.stdout.write(
                f'{sale.sale_number}  {row.source_type} {row.amount}  '
                f'{row.customer.name} -> {sale.customer.name}'
            )
            customer_ids.add(int(row.customer_id))
            customer_ids.add(int(sale.customer_id))
        if not apply:
            self.stdout.write('Nothing written. Run again with --apply to fix these rows.')
            return
        with transaction.atomic():
            for row in rows:
                CustomerWalletTransaction.objects.filter(pk=row.pk).update(
                    customer_id=row.sale.customer_id,
                )
            for customer_id in sorted(customer_ids):
                rebuild_customer_wallet_from_active_ledger(customer_id)
        self.stdout.write(f'Updated {len(rows)} row(s).')
