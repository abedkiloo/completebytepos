"""
Record sales for field orders packed before packing created a sale.

Those orders already put their total on the customer's debt (reference FO-<id>),
so the backfilled sale reuses that debt instead of adding it again. Their stock
was never taken off, so by default the sale moves stock now; pass --skip-stock
if the shelves were already corrected by hand.

  python manage.py backfill_field_sales            # list what would change
  python manage.py backfill_field_sales --apply
  python manage.py backfill_field_sales --apply --skip-stock
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from agents.field_sale import record_field_sale
from agents.models import FieldOrder
from agents.order_services import FieldOrderTransitionError
from sales.models import CustomerWalletTransaction


class Command(BaseCommand):
    help = 'Create the missing sales for field orders packed before field sales existed.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the sales (default: dry run).')
        parser.add_argument('--skip-stock', action='store_true', help='Do not move stock for these sales.')

    def handle(self, *args, **options):
        apply = options['apply']
        move_stock = not options['skip_stock']
        orders = (
            FieldOrder.objects.filter(stock_allocated=True, sale__isnull=True)
            .exclude(status=FieldOrder.STATUS_CANCELLED)
            .select_related('created_by', 'customer')
            .order_by('packed_at', 'pk')
        )
        created = failed = 0
        for order in orders:
            agent = order.created_by.username if order.created_by else 'unknown agent'
            legacy_debt = CustomerWalletTransaction.objects.filter(
                source_type='debt', reference=f'FO-{order.pk}', sale__isnull=True,
            )
            label = f'Field order #{order.pk} by {agent} (packed {order.packed_at:%Y-%m-%d})' if order.packed_at else f'Field order #{order.pk} by {agent}'
            if not apply:
                self.stdout.write(f'{label}: would record sale; existing debt reused: {legacy_debt.exists()}')
                continue
            try:
                with transaction.atomic():
                    has_debt = legacy_debt.exists()
                    sale = record_field_sale(order, move_stock=move_stock, post_debt=not has_debt)
                    legacy_debt.update(sale=sale)
            except FieldOrderTransitionError as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f'{label}: skipped — {exc.message_dict}'))
                continue
            created += 1
            self.stdout.write(self.style.SUCCESS(f'{label}: recorded {sale.sale_number}'))
        if apply:
            self.stdout.write(f'Done: {created} sale(s) recorded, {failed} skipped.')
        else:
            self.stdout.write('Dry run only. Re-run with --apply to record these sales.')
