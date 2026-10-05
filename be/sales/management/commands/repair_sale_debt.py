"""
Repair customer wallet debt after a sale was corrected but debt did not update.

Example (unit price 1,600 × qty 110 − discount 5,500, unpaid in full):

  Subtotal  = 1,600 × 110 = 176,000
  Discount  = 5,500
  Sale total = 170,500
  Paid      = 0  (or whatever was recorded)
  Unpaid    = total − paid  → this must equal active customer debt for the sale

  python manage.py repair_sale_debt --sale SALE-XXXX
  python manage.py repair_sale_debt --sale SALE-XXXX --apply
  python manage.py repair_sale_debt --customer-id 42 --apply
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from sales.models import Sale
from sales.sale_debt_sync import (
    active_sale_debt_amount,
    sale_unpaid_balance,
    sync_sale_customer_debt,
)


class Command(BaseCommand):
    help = 'Sync customer debt to match unpaid balances on corrected POS sales.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sale', action='append', dest='sale_numbers', default=[],
            help='Sale number to repair (repeatable).',
        )
        parser.add_argument(
            '--customer-id', type=int,
            help='Repair all completed underpaid POS sales for this customer.',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='Write wallet/debt changes. Default is dry-run only.',
        )

    def handle(self, *args, **options):
        qs = (
            Sale.objects.filter(status='completed', amount_paid__lt=F('total'))
            .exclude(refund_status='refunded')
            .exclude(sale_type='normal')
            .filter(customer_id__isnull=False)
            .select_related('customer')
            .order_by('id')
        )
        if options['sale_numbers']:
            qs = qs.filter(sale_number__in=options['sale_numbers'])
        if options.get('customer_id'):
            qs = qs.filter(customer_id=options['customer_id'])
        if not options['sale_numbers'] and not options.get('customer_id'):
            raise CommandError('Pass --sale SALE-… and/or --customer-id N.')

        sales = list(qs)
        if not sales:
            self.stdout.write('No matching underpaid completed POS sales.')
            return

        apply = options['apply']
        self.stdout.write(
            f'{"APPLYING" if apply else "DRY-RUN"} debt sync for {len(sales)} sale(s)\n'
        )
        for sale in sales:
            unpaid = sale_unpaid_balance(sale)
            active = active_sale_debt_amount(sale)
            wallet = sale.customer.wallet_balance
            self.stdout.write(
                f'{sale.sale_number}  customer={sale.customer.name}  '
                f'total={sale.total}  paid={sale.amount_paid}  '
                f'unpaid={unpaid}  active_debt={active}  wallet={wallet}'
            )
            if unpaid == active:
                self.stdout.write(self.style.SUCCESS('  already synced'))
                continue
            gap = unpaid - active
            self.stdout.write(
                f'  needs wallet/debt adjustment of {gap} '
                f'(debt should be {unpaid})'
            )
            if not apply:
                continue
            result = sync_sale_customer_debt(
                sale,
                reason=f'repair_sale_debt for {sale.sale_number}',
            )
            self.stdout.write(self.style.SUCCESS(
                f'  {result["action"]}: adjusted {result["adjusted"]}  '
                f'wallet {result["wallet_before"]} → {result["wallet_after"]}  '
                f'debt now {result["active_debt_after"]}'
            ))

        if not apply:
            self.stdout.write(
                '\nRe-run with --apply to write changes. '
                'Math: unpaid = sale.total − sale.amount_paid; '
                'that unpaid amount must appear as active customer debt.'
            )
