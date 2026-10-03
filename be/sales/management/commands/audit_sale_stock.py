"""
Read-only check that completed sales reduced stock.

For each completed sale it compares the quantity sold on each tracked item with the
"sale" stock movements recorded under the sale number, and says why stock may not
have moved (stock not tracked, setting off, still waiting for approval).

  python manage.py audit_sale_stock
  python manage.py audit_sale_stock --date-from 2026-10-01 --date-to 2026-10-03
  python manage.py audit_sale_stock --sale SALE-CC9E8B54
"""

from collections import defaultdict
from datetime import datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from django.utils import timezone

from inventory.models import StockMovement
from sales.models import Sale
from sales.module_settings import sales_validate_stock_before_sale


class Command(BaseCommand):
    help = 'List completed sales whose items did not reduce stock.'

    def add_arguments(self, parser):
        parser.add_argument('--date-from', help='YYYY-MM-DD (sale day, inclusive).')
        parser.add_argument('--date-to', help='YYYY-MM-DD (sale day, inclusive).')
        parser.add_argument('--sale', action='append', dest='sale_numbers', default=[])

    def _day_bound(self, raw, end=False):
        try:
            day = datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError as exc:
            raise CommandError(f'Bad date "{raw}", expected YYYY-MM-DD.') from exc
        return timezone.make_aware(datetime.combine(day, time.max if end else time.min))

    def _filtered(self, qs, options):
        if options['date_from']:
            qs = qs.filter(occurred_at__gte=self._day_bound(options['date_from']))
        if options['date_to']:
            qs = qs.filter(occurred_at__lte=self._day_bound(options['date_to'], end=True))
        if options['sale_numbers']:
            qs = qs.filter(sale_number__in=options['sale_numbers'])
        return qs

    def handle(self, *args, **options):
        validation_on = sales_validate_stock_before_sale()
        self.stdout.write(
            f'Setting "Validate stock before sale": {"ON" if validation_on else "OFF"}'
        )
        if not validation_on:
            self.stdout.write(self.style.WARNING(
                '  Before the fix, sales made while this was OFF did not reduce stock.'
            ))

        pending = self._filtered(Sale.objects.filter(status='pending_approval'), options)
        pending_count = pending.count()
        if pending_count:
            self.stdout.write(self.style.WARNING(
                f'{pending_count} sale(s) still waiting for manager approval — '
                'their stock only goes down once approved.'
            ))

        sales = list(
            self._filtered(Sale.objects.filter(status='completed'), options)
            .select_related('cashier', 'served_by')
            .prefetch_related('items__product', 'items__variant')
            .order_by('-occurred_at')
        )
        self.stdout.write(f'Checking {len(sales)} completed sale(s)\n')

        untracked_lines = 0
        bad_sales = 0
        missing_by_product = defaultdict(int)
        for sale in sales:
            moved = dict(
                StockMovement.objects.filter(reference=sale.sale_number, movement_type='sale')
                .values_list('product_id')
                .annotate(total=Sum('quantity'))
            )
            sold = defaultdict(int)
            names = {}
            not_tracked = []
            for item in sale.items.all():
                if not item.product.track_stock:
                    not_tracked.append(item.product.name)
                    continue
                sold[item.product_id] += int(item.quantity)
                names[item.product_id] = item.product.name

            problems = []
            for product_id, qty in sold.items():
                got = int(moved.get(product_id) or 0)
                if got < qty:
                    problems.append((names[product_id], qty, got))
                    missing_by_product[names[product_id]] += qty - got
            untracked_lines += len(not_tracked)
            if not problems:
                continue
            bad_sales += 1
            seller = sale.served_by or sale.cashier
            self.stdout.write(self.style.ERROR(
                f'{sale.sale_number}  STOCK NOT REDUCED  '
                f'{timezone.localtime(sale.occurred_at):%Y-%m-%d %H:%M}  '
                f'seller {getattr(seller, "username", "-")}  source {sale.entry_source}'
            ))
            for name, qty, got in problems:
                self.stdout.write(f'  {name}: sold {qty}, stock reduced by {got}')

        self.stdout.write('')
        if missing_by_product:
            self.stdout.write('Quantity sold but never taken off stock, per product:')
            for name, qty in sorted(missing_by_product.items(), key=lambda row: -row[1]):
                self.stdout.write(f'  {name}: {qty}')
        if untracked_lines:
            self.stdout.write(
                f'{untracked_lines} sale line(s) are for products with "Track stock" off '
                '(those never change stock by design).'
            )
        self.stdout.write(
            f'\n{bad_sales} of {len(sales)} completed sale(s) did not fully reduce stock.'
        )
