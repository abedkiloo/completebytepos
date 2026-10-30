"""
Remove source_type=other wallet rows that polluted customer debt ledgers.

Dry-run (list customers + counts):
  python manage.py purge_wallet_other

Apply for everyone:
  python manage.py purge_wallet_other --apply

One customer:
  python manage.py purge_wallet_other --customer-id 42 --apply
"""

from django.core.management.base import BaseCommand, CommandError

from sales.models import Customer, CustomerWalletTransaction
from sales.sale_debt_sync import purge_other_wallet_transactions


class Command(BaseCommand):
    help = 'Delete wallet source_type=other rows and rebuild customer debt balances.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer-id',
            type=int,
            help='Limit purge to one customer id.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Delete rows and rebuild wallets. Default is dry-run only.',
        )

    def handle(self, *args, **options):
        customer_id = options.get('customer_id')
        qs = CustomerWalletTransaction.objects.filter(source_type='other')
        if customer_id is not None:
            if not Customer.objects.filter(pk=customer_id).exists():
                raise CommandError(f'Customer {customer_id} not found.')
            qs = qs.filter(customer_id=customer_id)

        from django.db.models import Count

        rows = list(
            qs.values('customer_id')
            .annotate(n=Count('id'))
            .order_by('customer_id')
        )
        total = sum(r['n'] for r in rows)
        self.stdout.write(
            f'Found {total} other wallet row(s) across {len(rows)} customer(s).\n'
        )
        for row in rows[:50]:
            name = (
                Customer.objects.filter(pk=row['customer_id'])
                .values_list('name', flat=True)
                .first()
                or '?'
            )
            self.stdout.write(f'  customer_id={row["customer_id"]}  {name}  other_rows={row["n"]}')
        if len(rows) > 50:
            self.stdout.write(f'  … and {len(rows) - 50} more customers')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('\nDRY-RUN only. Re-run with --apply to delete and rebuild.'))
            return

        result = purge_other_wallet_transactions(customer_id=customer_id)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDeleted {result["deleted"]} other row(s); '
                f'rebuilt {result["customers"]} customer wallet(s).'
            )
        )
        for item in result['rebuilt'][:20]:
            self.stdout.write(
                f'  customer_id={item["customer_id"]}  wallet_balance={item["wallet_balance"]}'
            )
