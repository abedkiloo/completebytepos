"""
Read-only report of completed sales where less than the total was recorded as paid.

For each sale it shows whether the shortfall is tracked somewhere (customer debt
or an invoice balance) or missing, plus what the salesperson sent for approval.

  python manage.py audit_unpaid_sales
  python manage.py audit_unpaid_sales --date-from 2026-10-01 --date-to 2026-10-03
  python manage.py audit_unpaid_sales --sale SALE-CC9E8B54
"""

from datetime import datetime, time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Sum
from django.utils import timezone

from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from sales.models import CustomerWalletTransaction, Sale


class Command(BaseCommand):
    help = 'List completed sales paid below their total and whether the balance is tracked.'

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

    def handle(self, *args, **options):
        qs = (
            Sale.objects.filter(status='completed', amount_paid__lt=F('total'))
            .exclude(refund_status='refunded')
            .select_related('customer', 'cashier', 'served_by')
            .order_by('-occurred_at')
        )
        if options['date_from']:
            qs = qs.filter(occurred_at__gte=self._day_bound(options['date_from']))
        if options['date_to']:
            qs = qs.filter(occurred_at__lte=self._day_bound(options['date_to'], end=True))
        if options['sale_numbers']:
            qs = qs.filter(sale_number__in=options['sale_numbers'])

        sales = list(qs)
        self.stdout.write(f'{len(sales)} completed sale(s) paid below total\n')
        missing_total = Decimal('0')
        missing_count = 0
        for sale in sales:
            short = (sale.total or 0) - (sale.amount_paid or 0)
            debt = (
                CustomerWalletTransaction.objects.filter(sale=sale, source_type='debt')
                .aggregate(total=Sum('amount'))['total'] or Decimal('0')
            )
            invoice = sale.invoices.order_by('-id').first()
            invoice_balance = invoice.balance if invoice else None
            change = (
                PendingChange.objects.filter(
                    action_type=ACTION_SALE_COMPLETE,
                    entity_type='sales.Sale',
                    entity_id=str(sale.pk),
                )
                .order_by('-id')
                .first()
            )
            payload = (change.apply_payload or {}) if change else {}

            tracked = debt > 0 or (invoice_balance or 0) > 0
            if not tracked:
                missing_total += short
                missing_count += 1
            verdict = 'TRACKED' if tracked else 'NOT TRACKED'
            style = self.style.SUCCESS if tracked else self.style.ERROR

            self.stdout.write(style(
                f'{sale.sale_number}  {verdict}  short KES {short}'
            ))
            seller = sale.served_by or sale.cashier
            self.stdout.write(
                f'  day {timezone.localtime(sale.occurred_at):%Y-%m-%d %H:%M}  '
                f'seller {getattr(seller, "username", "-")}  '
                f'type {sale.sale_type}  source {sale.entry_source}  '
                f'channel {sale.client_channel}'
            )
            self.stdout.write(
                f'  total {sale.total}  paid {sale.amount_paid}  method {sale.payment_method}  '
                f'customer {sale.customer.name if sale.customer else "(walk-in)"}'
            )
            self.stdout.write(
                f'  debt recorded {debt}  invoice balance '
                f'{invoice_balance if invoice is not None else "(no invoice)"}'
            )
            if change:
                self.stdout.write(
                    f'  approval {change.status} by '
                    f'{getattr(change.checked_by, "username", "-")}  sent paid '
                    f'{payload.get("amount_paid", "-")}  partial '
                    f'{payload.get("allow_partial", "-")}  wallet '
                    f'{payload.get("use_wallet", "-")}'
                )
            else:
                self.stdout.write('  approval none (completed directly)')

        self.stdout.write(
            f'\n{missing_count} sale(s) with KES {missing_total} owed but not tracked '
            'as customer debt or an invoice.'
        )
