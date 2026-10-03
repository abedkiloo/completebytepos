"""
Finish sales left in "awaiting payment" by the retired collect step.

Each sale is completed the same way a manager approval does: stock moves out,
the payment / debt / wallet effects are posted, and the journal entry is written.

  python manage.py complete_awaiting_payment_sales --dry-run
  python manage.py complete_awaiting_payment_sales
  python manage.py complete_awaiting_payment_sales --sale SALE-1A2B3C --user admin
  python manage.py complete_awaiting_payment_sales --assume-paid-in-full
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from sales.models import CustomerWalletTransaction, Sale


class _DryRunRollback(Exception):
    pass


class Command(BaseCommand):
    help = (
        'Complete sales stuck in "awaiting payment" (the removed collect step): '
        'post stock, payment/debt, and books as a manager approval would.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run each sale and roll it back, showing what would happen.',
        )
        parser.add_argument(
            '--sale',
            action='append',
            dest='sale_numbers',
            default=[],
            help='Only this sale number (repeat for several).',
        )
        parser.add_argument(
            '--user',
            help=(
                'Username recorded on stock, wallet, and journal entries. '
                'Defaults to the manager who approved the sale, then the cashier.'
            ),
        )
        parser.add_argument(
            '--assume-paid-in-full',
            action='store_true',
            help='Treat every sale as fully paid in cash instead of using the recorded amount.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        forced_user = self._resolve_user(options.get('user'))

        qs = Sale.objects.filter(status='awaiting_payment').select_related(
            'customer', 'cashier',
        ).order_by('occurred_at', 'id')
        if options['sale_numbers']:
            qs = qs.filter(sale_number__in=options['sale_numbers'])

        sales = list(qs)
        self.stdout.write(
            f'Found {len(sales)} sale(s) awaiting payment'
            + (' (dry-run, nothing will be saved)' if dry_run else '')
        )

        done = skipped = 0
        for sale in sales:
            ok, message = self._complete_one(
                sale,
                forced_user=forced_user,
                assume_paid=options['assume_paid_in_full'],
                dry_run=dry_run,
            )
            if ok:
                done += 1
                self.stdout.write(self.style.SUCCESS(f'  {sale.sale_number}: {message}'))
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'  {sale.sale_number}: skipped — {message}'))

        verb = 'Would complete' if dry_run else 'Completed'
        self.stdout.write(self.style.SUCCESS(f'\n{verb} {done} sale(s). Skipped {skipped}.'))

    def _resolve_user(self, username):
        if not username:
            return None
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f'No user named "{username}".')
        return user

    def _latest_change(self, sale):
        return (
            PendingChange.objects.filter(
                action_type=ACTION_SALE_COMPLETE,
                entity_type='sales.Sale',
                entity_id=str(sale.pk),
            )
            .order_by('-id')
            .first()
        )

    def _build_payload(self, sale, change, *, assume_paid):
        payload = dict((change.apply_payload or {}) if change else {})
        payload.setdefault('payment_method', sale.payment_method or 'cash')
        payload.setdefault('payment_reference', sale.payment_reference or '')
        payload.setdefault('sale_type', sale.sale_type or 'pos')
        if assume_paid:
            payload.update({
                'amount_paid': str(sale.total),
                'use_wallet': False,
                'allow_partial': False,
            })
            payload.pop('wallet_amount_locked', None)
            return payload, None

        payload.setdefault('amount_paid', str(sale.amount_paid or 0))
        paid = Decimal(str(payload.get('amount_paid') or 0))
        if paid >= (sale.total or 0) or payload.get('use_wallet'):
            return payload, None
        if sale.customer_id is None:
            return None, (
                f'only KES {paid} of KES {sale.total} recorded and no customer to '
                'hold the debt. Re-run with --assume-paid-in-full if it was paid.'
            )
        payload['allow_partial'] = True
        if payload['sale_type'] == 'normal':
            payload.setdefault('invoice', {})
        return payload, None

    def _complete_one(self, sale, *, forced_user, assume_paid, dry_run):
        from sales.sale_completion_approval import complete_queued_sale

        change = self._latest_change(sale)
        user = forced_user or (change.checked_by if change else None) or sale.cashier
        if user is None:
            return False, 'no user to record the entries under; pass --user.'

        payload, problem = self._build_payload(sale, change, assume_paid=assume_paid)
        if problem:
            return False, problem

        try:
            with transaction.atomic():
                complete_queued_sale(sale, user, payload)
                sale.refresh_from_db()
                if change and change.status == PendingChange.STATUS_PENDING:
                    change.status = PendingChange.STATUS_APPROVED
                    change.checked_by = user
                    change.checked_at = timezone.now()
                    change.save(update_fields=['status', 'checked_by', 'checked_at'])
                summary = self._summary(sale, user)
                if dry_run:
                    raise _DryRunRollback(summary)
        except _DryRunRollback as preview:
            return True, f'would complete — {preview}'
        except ValidationError as exc:
            return False, '; '.join(exc.messages)

        try:
            from utils.audit_events import log_sale_completed

            log_sale_completed(None, sale, source='complete_awaiting_payment_script')
        except Exception:
            pass
        return True, f'completed — {summary}'

    def _summary(self, sale, user):
        debt = CustomerWalletTransaction.objects.filter(
            sale=sale, source_type='debt',
        ).first()
        parts = [f'total KES {sale.total}', f'paid KES {sale.amount_paid}']
        if debt:
            parts.append(f'debt KES {debt.amount} on {sale.customer.name}')
        invoice = getattr(sale, 'invoices', None)
        if invoice is not None and invoice.exists():
            parts.append(f'invoice balance KES {invoice.first().balance}')
        parts.append(f'recorded by {user.username}')
        return ', '.join(parts)
