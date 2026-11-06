"""
Backfill DebtSettlementAllocation for settlements that bumped Sale.amount_paid
without leaving an allocation row (causes Payments trail "Sale tender" doubles).

Dry-run:

  python manage.py backfill_settlement_allocations
  python manage.py backfill_settlement_allocations --customer-id 482

Apply:

  python manage.py backfill_settlement_allocations --apply
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from sales.sale_debt_sync import backfill_missing_settlement_allocations


class Command(BaseCommand):
    help = (
        'Create missing settlement→sale allocation rows so money-in reports '
        'do not double-count debt collections as sale tender.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--customer-id', type=int, default=None)
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Write allocation rows. Without this flag, only prints what would run.',
        )

    def handle(self, *args, **options):
        customer_id = options.get('customer_id')
        apply = bool(options.get('apply'))
        if not apply:
            from django.db.models import Count

            from sales.models import CustomerWalletTransaction

            qs = CustomerWalletTransaction.objects.filter(
                source_type='debt_settlement',
                transaction_type='credit',
            ).annotate(alloc_n=Count('sale_allocations')).filter(alloc_n=0)
            if customer_id is not None:
                qs = qs.filter(customer_id=customer_id)
            n = qs.count()
            self.stdout.write(
                self.style.WARNING(
                    f'Dry-run: {n} debt settlement(s) have no sale allocation. '
                    f'Re-run with --apply to link them (does not change balances).'
                )
            )
            return

        result = backfill_missing_settlement_allocations(customer_id=customer_id)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {result['allocations_created']} allocation(s) "
                f"across {result['sales_touched']} sale(s)."
            )
        )
        self.stdout.write(
            'Refresh Payments trail — Sale tender rows that only mirrored '
            'collections should disappear from totals.'
        )
