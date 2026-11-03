"""
Investigate (and optionally repair) one customer's debt math.

Includes cancelled / fully voided sales that still leave debt on the wallet
(common reason a customer "never balances").

Dry-run:

  python manage.py audit_customer_debt --customer-id 42
  python manage.py audit_customer_debt --name "Olive"

Apply — clear residue on cancelled/voided sales, purge ``other`` rows,
rebuild wallet, resync underpaid completed POS sales:

  python manage.py audit_customer_debt --customer-id 42 --apply
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q, Sum

from sales.debt_management import debt_amount_from_balance, underpaid_pos_sales_for_customer
from sales.models import Customer, CustomerWalletTransaction, Sale
from sales.sale_completion_approval import reverse_sale_wallet_effects
from sales.sale_debt_sync import (
    active_sale_debt_amount,
    debt_already_cleared_from_wallet,
    purge_other_wallet_transactions,
    rebuild_customer_wallet_from_active_ledger,
    sale_unpaid_balance,
    sync_sale_customer_debt,
)


def _q(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


INACTIVE_SALE_Q = Q(status='cancelled') | Q(refund_status='refunded')


class Command(BaseCommand):
    help = (
        'Audit one customer debt vs unpaid + cancelled/voided sales; '
        'optional --apply repair.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--customer-id', type=int, help='Customer primary key.')
        parser.add_argument('--name', type=str, help='Case-insensitive name contains.')
        parser.add_argument(
            '--apply',
            action='store_true',
            help=(
                'Clear wallet residue on cancelled/voided sales, purge other rows, '
                'rebuild wallet, resync unpaid POS debt.'
            ),
        )

    def handle(self, *args, **options):
        customer = self._resolve_customer(options)
        apply = bool(options['apply'])

        self.stdout.write(
            f'\n{"APPLY" if apply else "AUDIT"}  '
            f'customer_id={customer.id}  {customer.name}\n'
            f'  stored wallet_balance={_q(customer.wallet_balance)}  '
            f'(shown debt={debt_amount_from_balance(customer.wallet_balance)})\n'
        )

        ledger = self._ledger_breakdown(customer.id)
        self.stdout.write('Ledger by source_type:')
        for row in ledger:
            self.stdout.write(
                f'  {row["source_type"]:16}  '
                f'n={row["n"]}  debits={row["debits"]}  credits={row["credits"]}'
            )
        if not ledger:
            self.stdout.write('  (no wallet rows)')

        replayed = self._replay_balance(customer.id)
        stored = _q(customer.wallet_balance)
        gap_store = stored - replayed
        self.stdout.write(
            f'\nReplay non-other ledger → {replayed}  '
            f'(stored − replay = {gap_store})'
        )
        if gap_store != 0:
            self.stdout.write(
                self.style.WARNING(
                    '  wallet_balance does not match real ledger replay'
                )
            )

        other_n = CustomerWalletTransaction.objects.filter(
            customer_id=customer.id, source_type='other',
        ).count()
        if other_n:
            self.stdout.write(
                self.style.WARNING(
                    f'  {other_n} source_type=other row(s) — usually correction residue'
                )
            )

        # --- Active underpaid completed POS ---
        sales = list(underpaid_pos_sales_for_customer(customer.id))
        completed = (
            Sale.objects.filter(customer_id=customer.id, status='completed')
            .exclude(refund_status='refunded')
            .count()
        )
        self.stdout.write(
            f'\nCompleted sales (non-voided): {completed}  '
            f'underpaid POS: {len(sales)}'
        )

        unpaid_sum = Decimal('0.00')
        active_sum = Decimal('0.00')
        mismatches = []
        for sale in sales:
            unpaid = sale_unpaid_balance(sale)
            active = active_sale_debt_amount(sale)
            stale = debt_already_cleared_from_wallet(sale)
            unpaid_sum += unpaid
            active_sum += active
            mark = ''
            if unpaid != active or stale:
                mark = '  << MISMATCH'
                mismatches.append(sale)
            self.stdout.write(
                f'  {sale.sale_number}  total={_q(sale.total)}  '
                f'paid={_q(sale.amount_paid)}  unpaid={unpaid}  '
                f'active_debt={active}'
                f'{"  stale_other_reverse" if stale else ""}'
                f'{mark}'
            )

        # --- Cancelled / voided sales (should carry NO debt) ---
        inactive = list(
            Sale.objects.filter(customer_id=customer.id)
            .filter(INACTIVE_SALE_Q)
            .order_by('id')
        )
        residue_sales = []
        residue_debt_total = Decimal('0.00')
        self.stdout.write(
            f'\nCancelled / voided sales: {len(inactive)}'
        )
        if not inactive:
            self.stdout.write('  (none)')
        for sale in inactive:
            debt = active_sale_debt_amount(sale)
            wallet_n = CustomerWalletTransaction.objects.filter(
                sale=sale,
                source_type__in=('payment', 'overpayment', 'debt'),
            ).count()
            kind = (
                'voided'
                if (getattr(sale, 'refund_status', 'none') or 'none') == 'refunded'
                else sale.status
            )
            mark = ''
            if debt > 0 or wallet_n > 0:
                mark = '  << RESIDUE (should be cleared)'
                residue_sales.append(sale)
                residue_debt_total += debt
            self.stdout.write(
                f'  {sale.sale_number}  [{kind}]  total={_q(sale.total)}  '
                f'paid={_q(sale.amount_paid)}  leftover_debt={debt}  '
                f'wallet_rows={wallet_n}{mark}'
            )

        # Debt rows whose sale is missing or inactive (orphans)
        orphan_debt = self._orphan_debt_rows(customer.id)
        orphan_total = sum((_q(r.amount) for r in orphan_debt), Decimal('0.00'))
        if orphan_debt:
            self.stdout.write(
                self.style.WARNING(
                    f'\nOrphan debt rows (sale missing/inactive): '
                    f'n={len(orphan_debt)}  total={orphan_total}'
                )
            )
            for r in orphan_debt[:20]:
                self.stdout.write(
                    f'  txn={r.id}  sale_id={r.sale_id}  amount={_q(r.amount)}  '
                    f'{r.reference or ""}'
                )

        settlements = CustomerWalletTransaction.objects.filter(
            customer_id=customer.id,
            source_type='debt_settlement',
            transaction_type='credit',
        ).aggregate(total=Sum('amount'), n=Count('id'))
        settle_total = _q(settlements['total'])
        self.stdout.write(
            f'\nDebt settlements: n={settlements["n"] or 0}  total={settle_total}'
        )
        self.stdout.write(
            f'Sum unpaid underpaid sales={_q(unpaid_sum)}  '
            f'sum active debt rows={_q(active_sum)}  '
            f'cancelled/void residue debt={_q(residue_debt_total)}'
        )

        expected_debt = max(_q(unpaid_sum), Decimal('0.00'))
        shown_debt = debt_amount_from_balance(customer.wallet_balance)
        self.stdout.write(
            f'Shown wallet debt={shown_debt}  '
            f'vs unpaid sales total={expected_debt}'
        )

        ok = (
            gap_store == 0
            and other_n == 0
            and not mismatches
            and not residue_sales
            and not orphan_debt
            and shown_debt == expected_debt
        )
        if ok:
            self.stdout.write(self.style.SUCCESS('\nLooks consistent — no repair needed.'))
            return

        self.stdout.write(
            self.style.WARNING(
                f'\nIssues found: other_rows={other_n}  '
                f'sale_mismatches={len(mismatches)}  '
                f'cancelled_void_residue={len(residue_sales)}  '
                f'orphan_debt={len(orphan_debt)}  '
                f'wallet_vs_ledger={gap_store}  '
                f'debt_vs_unpaid={shown_debt - expected_debt}'
            )
        )

        if not apply:
            self.stdout.write(
                '\nDRY-RUN only. To repair this customer:\n'
                f'  python manage.py audit_customer_debt '
                f'--customer-id {customer.id} --apply\n'
            )
            return

        self.stdout.write('\nApplying repair…')

        cleared = 0
        cleared_sale_ids = set()
        for sale in residue_sales:
            before = active_sale_debt_amount(sale)
            reverse_sale_wallet_effects(
                sale,
                user=None,
                reason=f'audit_customer_debt clear {sale.status}/{sale.refund_status}',
            )
            # Also drop any other residue still tied to this inactive sale.
            CustomerWalletTransaction.objects.filter(
                sale=sale, source_type='other',
            ).delete()
            cleared += 1
            cleared_sale_ids.add(sale.pk)
            self.stdout.write(
                f'  cleared residue on {sale.sale_number}  '
                f'(had debt={before})'
            )

        # Re-read orphans after residue clear (those sales are already cleaned).
        remaining_orphans = [
            r for r in self._orphan_debt_rows(customer.id)
            if r.sale_id not in cleared_sale_ids
        ]
        if remaining_orphans:
            customer.refresh_from_db()
            for txn in remaining_orphans:
                amount = _q(txn.amount)
                if txn.transaction_type == 'debit':
                    customer.wallet_balance += amount
                else:
                    customer.wallet_balance -= amount
                customer.save(update_fields=['wallet_balance', 'updated_at'])
                txn.delete()
            self.stdout.write(
                f'  cleared {len(remaining_orphans)} orphan debt row(s)'
            )

        purge = purge_other_wallet_transactions(customer_id=customer.id)
        self.stdout.write(
            f'  purged other={purge["deleted"]}  '
            f'rebuilt_customers={purge["customers"]}'
        )
        balance = rebuild_customer_wallet_from_active_ledger(customer.id)
        self.stdout.write(f'  ledger rebuild wallet_balance={balance}')

        fixed = 0
        for sale in underpaid_pos_sales_for_customer(customer.id):
            unpaid = sale_unpaid_balance(sale)
            active = active_sale_debt_amount(sale)
            if unpaid == active and not debt_already_cleared_from_wallet(sale):
                continue
            result = sync_sale_customer_debt(
                sale,
                reason=f'audit_customer_debt for {sale.sale_number}',
            )
            fixed += 1
            self.stdout.write(
                f'  synced {sale.sale_number}: {result["action"]}  '
                f'adjusted={result.get("adjusted")}  '
                f'debt_after={result.get("active_debt_after")}  '
                f'wallet {result.get("wallet_before")} → {result.get("wallet_after")}'
            )

        final = rebuild_customer_wallet_from_active_ledger(customer.id)
        customer.refresh_from_db()
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. wallet_balance={_q(customer.wallet_balance)}  '
                f'(replay={final})  '
                f'debt={debt_amount_from_balance(customer.wallet_balance)}  '
                f'cancelled_cleared={cleared}  sales_synced={fixed}'
            )
        )

    def _orphan_debt_rows(self, customer_id: int):
        """Debt/payment rows whose sale is gone, cancelled, or fully voided."""
        rows = list(
            CustomerWalletTransaction.objects.filter(
                customer_id=customer_id,
                source_type__in=('debt', 'payment', 'overpayment'),
                sale_id__isnull=False,
            ).select_related('sale')
        )
        orphans = []
        for row in rows:
            sale = row.sale
            if sale is None:
                orphans.append(row)
                continue
            if sale.status == 'cancelled':
                orphans.append(row)
                continue
            if (getattr(sale, 'refund_status', 'none') or 'none') == 'refunded':
                orphans.append(row)
        return orphans

    def _resolve_customer(self, options) -> Customer:
        cid = options.get('customer_id')
        name = (options.get('name') or '').strip()
        if cid:
            try:
                return Customer.objects.get(pk=cid)
            except Customer.DoesNotExist as exc:
                raise CommandError(f'Customer {cid} not found.') from exc
        if not name:
            raise CommandError('Pass --customer-id N or --name "…"')
        matches = list(
            Customer.objects.filter(name__icontains=name).order_by('id')[:20]
        )
        if not matches:
            raise CommandError(f'No customer matching name "{name}".')
        if len(matches) > 1:
            lines = '\n'.join(
                f'  id={c.id}  {c.name}  wallet={_q(c.wallet_balance)}'
                for c in matches
            )
            raise CommandError(
                f'{len(matches)} customers match "{name}". Pick one with '
                f'--customer-id:\n{lines}'
            )
        return matches[0]

    def _ledger_breakdown(self, customer_id: int) -> list[dict]:
        rows = (
            CustomerWalletTransaction.objects.filter(customer_id=customer_id)
            .values('source_type')
            .annotate(
                n=Count('id'),
                debits=Sum(
                    'amount',
                    filter=Q(transaction_type='debit'),
                ),
                credits=Sum(
                    'amount',
                    filter=Q(transaction_type='credit'),
                ),
            )
            .order_by('source_type')
        )
        return [
            {
                'source_type': r['source_type'],
                'n': r['n'],
                'debits': _q(r['debits']),
                'credits': _q(r['credits']),
            }
            for r in rows
        ]

    def _replay_balance(self, customer_id: int) -> Decimal:
        balance = Decimal('0.00')
        for txn in (
            CustomerWalletTransaction.objects.filter(customer_id=customer_id)
            .exclude(source_type='other')
            .order_by('id')
        ):
            amount = _q(txn.amount)
            if txn.transaction_type == 'credit':
                balance += amount
            else:
                balance -= amount
            balance = _q(balance)
        return balance
