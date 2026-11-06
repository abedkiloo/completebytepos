"""
Overwrite completed sale-line unit_cost stamps with current catalog COST.

Use after you have corrected product/variant costs on the Products screen so
Trading profit COGS matches those values. New sales keep using FIFO stamps.

  # Preview how many lines would change
  python manage.py rectify_sale_costs_to_catalog

  # One sale or a date window
  python manage.py rectify_sale_costs_to_catalog --sale SALE-36FE40AD
  python manage.py rectify_sale_costs_to_catalog --date-from 2026-10-01 --date-to 2026-10-31

  # Write stamps
  python manage.py rectify_sale_costs_to_catalog --apply
"""

from django.core.management.base import BaseCommand, CommandError

from sales.rectify_sale_costs_to_catalog import (
    day_end,
    day_start,
    rectify_sale_costs_to_catalog,
)


class Command(BaseCommand):
    help = (
        'Set SaleItem.unit_cost on completed sales to the current product/variant '
        'catalog cost so Trading profit COGS matches Products. Dry-run by default.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sale',
            action='append',
            dest='sale_numbers',
            default=[],
            help='Sale number to rectify (repeatable).',
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
            default=50,
            help='Max planned rows to print (default 50; 0 = all).',
        )

    def handle(self, *args, **options):
        try:
            date_from = day_start(options['date_from']) if options.get('date_from') else None
            date_to = day_end(options['date_to']) if options.get('date_to') else None
        except ValueError as exc:
            raise CommandError(f'Bad date: {exc}') from exc

        apply = bool(options['apply'])
        planned, applied = rectify_sale_costs_to_catalog(
            sale_numbers=options['sale_numbers'] or None,
            date_from=date_from,
            date_to=date_to,
            apply=apply,
        )

        mode = 'APPLYING' if apply else 'DRY-RUN'
        self.stdout.write(f'{mode}: {len(planned)} sale line(s) differ from catalog cost\n')
        if not planned:
            self.stdout.write(
                'Nothing to do — completed lines already match catalog, '
                'or catalog cost is missing/zero.'
            )
            return

        limit = options['limit']
        if limit == 0:
            limit = len(planned)
        for row in planned[:limit]:
            old = 'null' if row.old_unit_cost is None else str(row.old_unit_cost)
            variant = f' [{row.variant_label}]' if row.variant_label else ''
            self.stdout.write(
                f'  {row.sale_number}  {row.product_name}{variant}  '
                f'qty={row.quantity}  {old} → {row.new_unit_cost}'
            )
        if len(planned) > limit:
            self.stdout.write(f'  … {len(planned) - limit} more')

        if apply:
            self.stdout.write(
                self.style.SUCCESS(f'\nUpdated {applied} SaleItem unit_cost stamp(s).')
            )
            self.stdout.write(
                'Re-open Trading profit → Gross sales / COGS to confirm the new costs.'
            )
        else:
            self.stdout.write(
                self.style.WARNING('\nDry-run only. Re-run with --apply to write stamps.')
            )
