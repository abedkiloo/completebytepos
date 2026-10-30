"""
Clear wrong COGS after return-for-correction (qty up/down, doubles, line remove).

  # Scan completed sales with surplus drains, shortfalls, or duplicate lines
  python manage.py repair_sale_cogs_double

  # One sale (dry-run)
  python manage.py repair_sale_cogs_double --sale SALE-XXXX

  # Soft-void surplus drains + restamp unit_cost from kept movements
  python manage.py repair_sale_cogs_double --sale SALE-XXXX --apply

  # Always rewrite unit_cost stamps from kept drains (even if already set)
  python manage.py repair_sale_cogs_double --sale SALE-XXXX --apply --force-restamp

Preferred when the cart qty is wrong or movements are short: admin-return →
fix the cart → re-approve (new code soft-voids old drains automatically).
Use this command when the cart is already correct but COGS still shows the
previous (higher/lower) cost from stale drains or stamps.
"""

from django.core.management.base import BaseCommand, CommandError

from sales.repair_sale_cogs_double import find_inflated_cogs_sales, repair_sale_cogs_double


class Command(BaseCommand):
    help = (
        'Repair trading-profit COGS after sale corrections: soft-void surplus '
        'sale drains and restamp unit costs for the current cart qty.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sale',
            action='append',
            dest='sale_numbers',
            default=[],
            help='Sale number to repair (repeatable).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Write changes. Default is dry-run only.',
        )
        parser.add_argument(
            '--no-restamp',
            action='store_true',
            help='Do not fill/rewrite unit_cost after voiding surplus drains.',
        )
        parser.add_argument(
            '--force-restamp',
            action='store_true',
            help='Rewrite unit_cost for all lines from kept movements/catalog.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Max sales to list when scanning (default 50).',
        )

    def handle(self, *args, **options):
        sale_numbers = options['sale_numbers'] or []
        apply = bool(options['apply'])
        restamp = not bool(options['no_restamp'])
        force_restamp = bool(options['force_restamp'])

        if sale_numbers:
            result = repair_sale_cogs_double(
                sale_numbers=sale_numbers,
                apply=apply,
                restamp_unit_cost=restamp,
                force_restamp=force_restamp,
            )
            if result['missing']:
                raise CommandError(
                    'Sale not found: ' + ', '.join(result['missing'])
                )
            audits = result['audits']
            mode = 'APPLYING' if apply else 'DRY-RUN'
            self.stdout.write(
                f'{mode}: {len(audits)} sale(s), '
                f'{result["surplus_count"]} surplus movement(s)'
            )
            if apply:
                self.stdout.write(
                    f'  voided={result["voided"]} '
                    f'unit_costs_stamped={result["unit_costs_stamped"]} '
                    f'force_restamp={result["force_restamp"]}'
                )
        else:
            audits = find_inflated_cogs_sales(limit=int(options['limit'] or 50))
            mode = 'SCAN'
            self.stdout.write(
                f'{mode}: {len(audits)} sale(s) needing COGS attention'
            )

        if not audits:
            self.stdout.write('Nothing to repair.')
            return

        for audit in audits:
            self.stdout.write('')
            self.stdout.write(
                f'{audit.sale_number} [{audit.status}] '
                f'items_qty={audit.item_qty} live_sale_mov_qty={audit.live_sale_mov_qty} '
                f'stamped_cogs={audit.stamped_cogs} report_cogs={audit.report_cogs}'
            )
            for issue in audit.issues:
                self.stdout.write(f'  ⚠ {issue}')
            if audit.duplicate_product_lines:
                for pid, vid, n in audit.duplicate_product_lines:
                    self.stdout.write(
                        f'    product_id={pid} variant_id={vid} lines={n}'
                    )
            if audit.surplus_movements:
                self.stdout.write(
                    f'  surplus sale movements to soft-void: {len(audit.surplus_movements)}'
                )
                for row in audit.surplus_movements[:20]:
                    self.stdout.write(
                        f'    mov#{row.movement_id} {row.product_name} '
                        f'qty={row.quantity} cost={row.total_cost}'
                    )
                if len(audit.surplus_movements) > 20:
                    self.stdout.write(
                        f'    … {len(audit.surplus_movements) - 20} more'
                    )
            if audit.needs_recomplete:
                self.stdout.write(
                    '  → Fix cart (or shortfall) via admin-return → edit → re-approve.'
                )

        if not apply and sale_numbers:
            self.stdout.write('')
            self.stdout.write(
                'Dry-run only. Re-run with --apply to soft-void surplus drains '
                'and restamp costs.'
            )
