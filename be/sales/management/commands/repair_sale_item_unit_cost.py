"""
One-time alignment: stamp SaleItem.unit_cost where it is null/0 using the same
sources trading-profit already falls back to (FIFO allocations → sale stock
movements → catalog). Clears the orange "stamped line cost was 0" warnings.

  # Preview everything that would change
  python manage.py repair_sale_item_unit_cost

  # Limit to a period or sale
  python manage.py repair_sale_item_unit_cost --date-from 2026-10-01 --date-to 2026-10-28
  python manage.py repair_sale_item_unit_cost --sale SALE-00016874

  # Write the stamps
  python manage.py repair_sale_item_unit_cost --apply
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from sales.repair_sale_item_unit_cost import (
    day_end,
    day_start,
    repair_unit_costs,
)


class Command(BaseCommand):
    help = (
        'Stamp missing/zero SaleItem.unit_cost from layer allocations, '
        'sale stock movements, or catalog so trading-profit COGS stops falling back.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sale',
            action='append',
            dest='sale_numbers',
            default=[],
            help='Sale number to repair (repeatable).',
        )
        parser.add_argument('--date-from', help='YYYY-MM-DD (sale day, inclusive).')
        parser.add_argument('--date-to', help='YYYY-MM-DD (sale day, inclusive).')
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Write unit_cost stamps. Default is dry-run only.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Optional max number of planned rows to print (0 = all).',
        )

    def handle(self, *args, **options):
        try:
            date_from = day_start(options['date_from']) if options.get('date_from') else None
            date_to = day_end(options['date_to']) if options.get('date_to') else None
        except ValueError as exc:
            raise CommandError(f'Bad date: {exc}') from exc

        apply = bool(options['apply'])
        repairs, applied = repair_unit_costs(
            sale_numbers=options['sale_numbers'] or None,
            date_from=date_from,
            date_to=date_to,
            apply=apply,
        )

        mode = 'APPLYING' if apply else 'DRY-RUN'
        self.stdout.write(f'{mode}: {len(repairs)} sale line(s) can be stamped\n')
        if not repairs:
            self.stdout.write('Nothing to do — no completed lines with missing/zero unit cost,')
            self.stdout.write('or no allocation/movement/catalog cost was found for them.')
            return

        by_source = Counter(row.source for row in repairs)
        for source, count in sorted(by_source.items()):
            self.stdout.write(f'  source={source}: {count}')

        limit = options['limit'] or len(repairs)
        for row in repairs[:limit]:
            old = 'null' if row.old_unit_cost is None else str(row.old_unit_cost)
            self.stdout.write(
                f'  {row.sale_number}  {row.product_name}  qty={row.quantity}  '
                f'{old} → {row.new_unit_cost}  ({row.source})'
            )
        if len(repairs) > limit:
            self.stdout.write(f'  … {len(repairs) - limit} more')

        if apply:
            self.stdout.write(self.style.SUCCESS(f'\nUpdated {applied} SaleItem row(s).'))
            self.stdout.write(
                'Re-open Trading profit → Costs to confirm the orange warnings are gone.'
            )
        else:
            self.stdout.write(
                self.style.WARNING('\nDry-run only. Re-run with --apply to write stamps.')
            )
