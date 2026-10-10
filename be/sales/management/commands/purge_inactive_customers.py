"""
Permanently delete deactivated (is_active=False) customers.

Sales/invoices/payment intents keep history (SET_NULL). Wallet rows and sites
cascade. Field orders that block delete are removed first.

  python manage.py purge_inactive_customers --dry-run
  python manage.py purge_inactive_customers --apply

UAT has no reliable backups — --apply is irreversible.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from sales.models import Customer


class Command(BaseCommand):
    help = (
        'Permanently delete deactivated customers. '
        'Default is dry-run; pass --apply to delete. Irreversible.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List targets without deleting (default when --apply is omitted).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually delete deactivated customers (irreversible).',
        )
        parser.add_argument(
            '--ids',
            type=str,
            default='',
            help='Comma-separated customer PKs to purge (must be inactive). '
                 'If omitted, all inactive customers are targeted.',
        )

    def handle(self, *args, **options):
        apply = bool(options.get('apply'))
        dry_run = not apply or bool(options.get('dry_run'))
        if options.get('apply') and options.get('dry_run'):
            dry_run = True

        qs = Customer.objects.filter(is_active=False).annotate(
            sale_count=Count('sales', distinct=True),
            invoice_count=Count('invoices', distinct=True),
            wallet_tx_count=Count('wallet_transactions', distinct=True),
            site_count=Count('sites', distinct=True),
            field_order_count=Count('field_orders', distinct=True),
        ).order_by('id')

        ids_raw = (options.get('ids') or '').strip()
        if ids_raw:
            try:
                id_list = [int(x.strip()) for x in ids_raw.split(',') if x.strip()]
            except ValueError:
                self.stderr.write(self.style.ERROR('--ids must be comma-separated integers'))
                return
            qs = qs.filter(pk__in=id_list)
            missing = set(id_list) - set(qs.values_list('pk', flat=True))
            if missing:
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipping ids not found or still active: {sorted(missing)}'
                    )
                )

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No inactive customers to purge.'))
            return

        self.stdout.write(
            f'Targeting {total} inactive customer(s)'
            + (' (dry-run)' if dry_run else ' — DELETING')
            + ':\n'
        )
        for row in qs[:200]:
            self.stdout.write(
                f"  #{row.pk} {row.name!r} phone={row.phone or '-'} "
                f"sales={row.sale_count} invoices={row.invoice_count} "
                f"wallet_tx={row.wallet_tx_count} sites={row.site_count} "
                f"field_orders={row.field_order_count}"
            )
        if total > 200:
            self.stdout.write(f'  ... and {total - 200} more')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDry-run only. Would permanently delete {total} customer(s). '
                    'Sale/invoice history keeps customer_id null. '
                    'Re-run with --apply to delete. UAT has no backups — this cannot be undone.'
                )
            )
            return

        pk_list = list(qs.values_list('pk', flat=True))
        with transaction.atomic():
            # FieldOrder PROTECTs Customer and CustomerSite — remove blockers first.
            try:
                from agents.models import FieldOrder
            except ImportError:
                FieldOrder = None
            if FieldOrder is not None:
                fo_deleted, _ = FieldOrder.objects.filter(
                    Q(customer_id__in=pk_list) | Q(site__customer_id__in=pk_list)
                ).delete()
                if fo_deleted:
                    self.stdout.write(f'Removed {fo_deleted} field-order row(s) that blocked delete.')

            deleted_count, details = Customer.objects.filter(pk__in=pk_list).delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nPermanently deleted {deleted_count} DB row(s) '
                    f'for {len(pk_list)} inactive customer(s). Details: {details}'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Irreversible. Sales/invoices that pointed at these customers '
                    'now have customer=NULL.'
                )
            )
