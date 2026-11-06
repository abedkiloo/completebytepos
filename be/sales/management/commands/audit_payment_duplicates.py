"""
Senior finance audit: payment double-counts and true duplicate money-in rows.

Reporting inflation (settlement + sale tender) is fixed in product code —
this command still reports historical overlap for auditors, and can reverse
*true* duplicate wallet settlements / invoice payments.

Dry-run (always safe):

  python manage.py audit_payment_duplicates
  python manage.py audit_payment_duplicates --days 90

Reverse proven duplicate debt settlements (keeps earliest row):

  python manage.py audit_payment_duplicates --apply-duplicate-settlements

Reverse proven duplicate invoice payments (same invoice/amount/reference/day):

  python manage.py audit_payment_duplicates --apply-duplicate-invoice-payments
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from sales.models import (
    CustomerWalletTransaction,
    DebtSettlementAllocation,
    Payment,
)
from sales.sale_debt_sync import rebuild_customer_wallet_from_active_ledger


def _q(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


class Command(BaseCommand):
    help = (
        'Audit payment trail inflation and true duplicate settlements/payments; '
        'optional --apply for duplicate row cleanup only.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Look-back window for duplicate scans (default 365).',
        )
        parser.add_argument(
            '--apply-duplicate-settlements',
            action='store_true',
            help=(
                'Reverse duplicate debt_settlement credits (same customer, amount, '
                'reference within 5 minutes). Keeps the earliest txn.'
            ),
        )
        parser.add_argument(
            '--apply-duplicate-invoice-payments',
            action='store_true',
            help=(
                'Delete duplicate invoice Payment rows (same invoice, amount, '
                'method, reference, payment_date). Keeps the earliest payment.'
            ),
        )

    def handle(self, *args, **options):
        days = max(1, int(options['days'] or 365))
        since = timezone.now() - timedelta(days=days)
        self.stdout.write(self.style.NOTICE(f'Audit window: last {days} days (since {since.date()})'))

        overlap = self._report_settlement_sale_overlap(since)
        dup_settlements = self._find_duplicate_settlements(since)
        dup_payments = self._find_duplicate_invoice_payments(since)

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('1) Trail / daily cash inflation (read-only)'))
        self.stdout.write(
            'Debt settlements bump Sale.amount_paid; old reports summed settlement '
            '+ sale tender. Product now uses checkout tender only.'
        )
        self.stdout.write(f'  Allocation rows overlapping sale tender: {overlap["rows"]}')
        self.stdout.write(f'  Overlap amount (once in settlement, once in old tender): {_q(overlap["amount"])}')

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('2) True duplicate debt settlements'))
        self.stdout.write(f'  Candidate groups: {len(dup_settlements)}')
        for group in dup_settlements[:25]:
            self.stdout.write(
                f'  customer={group["customer_id"]} amount={group["amount"]} '
                f'ref={group["reference"]!r} ids={group["ids"]} keep={group["keep_id"]}'
            )
        if len(dup_settlements) > 25:
            self.stdout.write(f'  … {len(dup_settlements) - 25} more groups')

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('3) True duplicate invoice payments'))
        self.stdout.write(f'  Candidate groups: {len(dup_payments)}')
        for group in dup_payments[:25]:
            self.stdout.write(
                f'  invoice={group["invoice_id"]} amount={group["amount"]} '
                f'method={group["payment_method"]} ref={group["reference"]!r} '
                f'ids={group["ids"]} keep={group["keep_id"]}'
            )
        if len(dup_payments) > 25:
            self.stdout.write(f'  … {len(dup_payments) - 25} more groups')

        if options['apply_duplicate_settlements']:
            reversed_n = self._apply_duplicate_settlements(dup_settlements)
            self.stdout.write(self.style.SUCCESS(f'Reversed duplicate settlements: {reversed_n}'))
        if options['apply_duplicate_invoice_payments']:
            deleted_n = self._apply_duplicate_invoice_payments(dup_payments)
            self.stdout.write(self.style.SUCCESS(f'Deleted duplicate invoice payments: {deleted_n}'))

        if not options['apply_duplicate_settlements'] and not options['apply_duplicate_invoice_payments']:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Dry-run only. Re-run with --apply-duplicate-settlements and/or '
                    '--apply-duplicate-invoice-payments after finance sign-off.'
                )
            )

    def _report_settlement_sale_overlap(self, since) -> dict:
        qs = DebtSettlementAllocation.objects.filter(
            wallet_transaction__created_at__gte=since,
            wallet_transaction__source_type='debt_settlement',
            wallet_transaction__transaction_type='credit',
        )
        agg = qs.aggregate(rows=Count('id'), amount=Sum('amount'))
        return {
            'rows': int(agg['rows'] or 0),
            'amount': agg['amount'] or Decimal('0'),
        }

    def _find_duplicate_settlements(self, since) -> list[dict]:
        """
        Same customer + amount + reference within a short window → likely double-click.
        Empty references are grouped only when created within 2 minutes of each other.
        """
        txns = list(
            CustomerWalletTransaction.objects.filter(
                source_type='debt_settlement',
                transaction_type='credit',
                created_at__gte=since,
            )
            .order_by('customer_id', 'created_at', 'id')
            .values('id', 'customer_id', 'amount', 'reference', 'created_at')
        )
        groups: list[dict] = []
        # Bucket by customer + amount + normalized reference
        buckets: dict[tuple, list] = defaultdict(list)
        for row in txns:
            key = (
                row['customer_id'],
                str(_q(row['amount'])),
                (row['reference'] or '').strip(),
            )
            buckets[key].append(row)
        for key, rows in buckets.items():
            if len(rows) < 2:
                continue
            ref = key[2]
            if ref:
                ids = [r['id'] for r in rows]
                groups.append(
                    {
                        'customer_id': key[0],
                        'amount': key[1],
                        'reference': ref,
                        'ids': ids,
                        'keep_id': ids[0],
                        'drop_ids': ids[1:],
                    }
                )
                continue
            # No reference: cluster by 2-minute proximity
            cluster = [rows[0]]
            for row in rows[1:]:
                prev = cluster[-1]
                if (row['created_at'] - prev['created_at']) <= timedelta(minutes=2):
                    cluster.append(row)
                else:
                    if len(cluster) > 1:
                        ids = [r['id'] for r in cluster]
                        groups.append(
                            {
                                'customer_id': key[0],
                                'amount': key[1],
                                'reference': '',
                                'ids': ids,
                                'keep_id': ids[0],
                                'drop_ids': ids[1:],
                            }
                        )
                    cluster = [row]
            if len(cluster) > 1:
                ids = [r['id'] for r in cluster]
                groups.append(
                    {
                        'customer_id': key[0],
                        'amount': key[1],
                        'reference': '',
                        'ids': ids,
                        'keep_id': ids[0],
                        'drop_ids': ids[1:],
                    }
                )
        return groups

    def _find_duplicate_invoice_payments(self, since) -> list[dict]:
        rows = list(
            Payment.objects.filter(created_at__gte=since)
            .exclude(notes__startswith='Initial payment from sale ')
            .order_by('invoice_id', 'created_at', 'id')
            .values(
                'id',
                'invoice_id',
                'amount',
                'payment_method',
                'reference',
                'payment_date',
            )
        )
        buckets: dict[tuple, list] = defaultdict(list)
        for row in rows:
            key = (
                row['invoice_id'],
                str(_q(row['amount'])),
                (row['payment_method'] or '').strip().lower(),
                (row['reference'] or '').strip(),
                str(row['payment_date'] or ''),
            )
            buckets[key].append(row)
        groups = []
        for key, items in buckets.items():
            if len(items) < 2:
                continue
            ids = [r['id'] for r in items]
            groups.append(
                {
                    'invoice_id': key[0],
                    'amount': key[1],
                    'payment_method': key[2],
                    'reference': key[3],
                    'ids': ids,
                    'keep_id': ids[0],
                    'drop_ids': ids[1:],
                }
            )
        return groups

    @transaction.atomic
    def _apply_duplicate_settlements(self, groups: list[dict]) -> int:
        reversed_n = 0
        touched_customers = set()
        for group in groups:
            for txn_id in group['drop_ids']:
                txn = (
                    CustomerWalletTransaction.objects.select_for_update()
                    .filter(
                        id=txn_id,
                        source_type='debt_settlement',
                        transaction_type='credit',
                    )
                    .first()
                )
                if not txn:
                    continue
                for alloc in DebtSettlementAllocation.objects.filter(
                    wallet_transaction=txn
                ).select_related('sale'):
                    sale = alloc.sale
                    if sale is not None:
                        sale.amount_paid = max(
                            Decimal('0.00'),
                            _q(sale.amount_paid) - _q(alloc.amount),
                        )
                        sale.save(update_fields=['amount_paid', 'updated_at'])
                    alloc.delete()
                touched_customers.add(txn.customer_id)
                txn.delete()
                reversed_n += 1
        for customer_id in touched_customers:
            if customer_id:
                rebuild_customer_wallet_from_active_ledger(int(customer_id))
        return reversed_n

    @transaction.atomic
    def _apply_duplicate_invoice_payments(self, groups: list[dict]) -> int:
        deleted = 0
        for group in groups:
            for pay_id in group['drop_ids']:
                pay = Payment.objects.select_for_update().filter(id=pay_id).first()
                if not pay:
                    continue
                invoice = pay.invoice
                pay.delete()
                if invoice is not None:
                    # Payment.save recomputes — force refresh via save of remaining
                    invoice.refresh_from_db()
                    remaining = invoice.payments.aggregate(t=Sum('amount'))['t'] or 0
                    invoice.amount_paid = _q(remaining)
                    invoice.balance = max(
                        Decimal('0.00'),
                        _q(invoice.total) - _q(invoice.amount_paid),
                    )
                    if invoice.balance <= 0:
                        invoice.status = 'paid'
                    elif invoice.amount_paid > 0:
                        invoice.status = 'partial'
                    invoice.save(
                        update_fields=['amount_paid', 'balance', 'status', 'updated_at']
                    )
                deleted += 1
        return deleted
