"""
Investigate (and optionally repair) one customer's debt math.

Includes cancelled / fully voided sales that still leave debt on the wallet
(common reason a customer "never balances").

See the discrepancy (dry-run — prints DISCREPANCY TRAIL + WALLET TRAIL):

  python manage.py audit_customer_debt --customer-id 1
  python manage.py audit_customer_debt --customer-id 1 --set-debt 29500
  python manage.py audit_customer_debt --name "Olive"

Docker:

  docker compose exec backend python manage.py audit_customer_debt --customer-id 1
  docker compose exec backend python manage.py audit_customer_debt --customer-id 1 --set-debt 29500

Apply repair / restore known-good owed amount:

  python manage.py audit_customer_debt --customer-id 1 --apply
  python manage.py audit_customer_debt --customer-id 1 --set-debt 29500 --apply
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q, Sum

from sales.debt_management import debt_amount_from_balance, underpaid_pos_sales_for_customer
from sales.models import Customer, CustomerWalletTransaction, DebtSettlementAllocation, Sale
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
            '--set-debt',
            type=str,
            default=None,
            help=(
                'Target owed amount (positive), e.g. 29500. Dry-run shows the gap; '
                'with --apply posts a manual wallet adjustment to hit that debt.'
            ),
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help=(
                'Clear wallet residue on cancelled/voided sales, purge other rows, '
                'rebuild wallet, resync unpaid POS debt. With --set-debt, also '
                'posts the balancing manual adjustment.'
            ),
        )

    def handle(self, *args, **options):
        customer = self._resolve_customer(options)
        apply = bool(options['apply'])
        target_debt = self._parse_target_debt(options.get('set_debt'))

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

        pay_debt = self._payments_vs_debts(customer.id)
        self._print_payments_vs_debts(pay_debt, customer)

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

        # --- All completed non-voided POS sales (forensics) ---
        all_completed = list(
            Sale.objects.filter(customer_id=customer.id, status='completed')
            .exclude(refund_status='refunded')
            .exclude(sale_type='normal')
            .order_by('id')
        )
        sales = list(underpaid_pos_sales_for_customer(customer.id))
        self.stdout.write(
            f'\nCompleted POS sales (non-voided): {len(all_completed)}  '
            f'underpaid: {len(sales)}'
        )

        unpaid_sum = Decimal('0.00')
        active_sum = Decimal('0.00')
        mismatches = []
        for sale in all_completed:
            unpaid = sale_unpaid_balance(sale)
            active = active_sale_debt_amount(sale)
            stale = debt_already_cleared_from_wallet(sale)
            settled = _q(
                DebtSettlementAllocation.objects.filter(sale=sale).aggregate(
                    total=Sum('amount')
                )['total']
            )
            if unpaid > 0:
                unpaid_sum += unpaid
                active_sum += active
            mark = ''
            if unpaid > 0 and (unpaid != active or stale):
                mark = '  << MISMATCH'
                mismatches.append(sale)
            elif unpaid == 0 and active > 0:
                mark = '  << PAID BUT DEBT ROW LEFT'
                mismatches.append(sale)
            self.stdout.write(
                f'  {sale.sale_number}  total={_q(sale.total)}  '
                f'paid={_q(sale.amount_paid)}  settled_alloc={settled}  '
                f'unpaid={unpaid}  active_debt={active}'
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
        debt_vs_unpaid = shown_debt - expected_debt
        active_vs_unpaid = _q(active_sum) - expected_debt

        self._print_discrepancy_trail(
            customer=customer,
            shown_debt=shown_debt,
            expected_debt=expected_debt,
            active_sum=_q(active_sum),
            settle_total=settle_total,
            residue_debt=_q(residue_debt_total),
            orphan_total=_q(orphan_total),
            other_n=other_n,
            gap_store=gap_store,
            mismatches=mismatches,
            residue_sales=residue_sales,
            target_debt=target_debt,
        )
        self._print_wallet_trail(customer.id)

        ok = (
            gap_store == 0
            and other_n == 0
            and not mismatches
            and not residue_sales
            and not orphan_debt
            and shown_debt == expected_debt
            and (target_debt is None or shown_debt == _q(target_debt))
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
                f'debt_vs_unpaid={debt_vs_unpaid}  '
                f'active_debt_vs_unpaid={active_vs_unpaid}'
                + (
                    f'  vs_target={shown_debt - _q(target_debt)}'
                    if target_debt is not None
                    else ''
                )
            )
        )

        if not apply:
            self.stdout.write(
                '\nDRY-RUN only — nothing written.\n'
                'See DISCREPANCY TRAIL above for the gaps.\n'
                '\nRepair from ledger / cancelled residue:\n'
                f'  python manage.py audit_customer_debt '
                f'--customer-id {customer.id} --apply\n'
            )
            if target_debt is not None and shown_debt != _q(target_debt):
                self.stdout.write(
                    'Restore known-good owed amount (e.g. 29500):\n'
                    f'  python manage.py audit_customer_debt '
                    f'--customer-id {customer.id} '
                    f'--set-debt {target_debt} --apply\n'
                )
            elif target_debt is None:
                self.stdout.write(
                    'To compare against a known owed amount:\n'
                    f'  python manage.py audit_customer_debt '
                    f'--customer-id {customer.id} --set-debt 29500\n'
                )
            return

        self.stdout.write('\nApplying repair…')

        cleared = 0
        cleared_sale_ids = set()
        for sale in residue_sales:
            before = active_sale_debt_amount(sale)
            # Drop ALL wallet rows for inactive sales, then rebuild once.
            # Do not per-row adjust wallet here — voided sales often already have
            # a matching refund credit; adjusting again would double-count.
            deleted, _ = CustomerWalletTransaction.objects.filter(sale=sale).delete()
            cleared += 1
            cleared_sale_ids.add(sale.pk)
            self.stdout.write(
                f'  cleared residue on {sale.sale_number}  '
                f'(had debt={before}, deleted_rows={deleted})'
            )

        # Orphans: delete rows only; rebuild will fix wallet_balance.
        remaining_orphans = [
            r for r in self._orphan_debt_rows(customer.id)
            if r.sale_id not in cleared_sale_ids
        ]
        if remaining_orphans:
            n = len(remaining_orphans)
            CustomerWalletTransaction.objects.filter(
                pk__in=[r.pk for r in remaining_orphans]
            ).delete()
            self.stdout.write(f'  cleared {n} orphan debt row(s)')

        purge = purge_other_wallet_transactions(customer_id=customer.id)
        self.stdout.write(
            f'  purged other={purge["deleted"]}  '
            f'rebuilt_customers={purge["customers"]}'
        )
        balance = rebuild_customer_wallet_from_active_ledger(customer.id)
        self.stdout.write(f'  ledger rebuild wallet_balance={balance}')

        # Sync underpaid mismatches AND fully-paid sales that still have debt rows.
        fixed = 0
        for sale in mismatches:
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

        if target_debt is not None:
            self._apply_set_debt(customer, _q(target_debt))
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

    def _payments_vs_debts(self, customer_id: int) -> dict:
        """
        Align check: total charges (debits) − total payments (credits) = net owed.

        Ignores source_type=other (cleanup junk). Includes debt, settlements,
        till wallet payment, refund, overpayment, manual.
        """
        qs = CustomerWalletTransaction.objects.filter(
            customer_id=customer_id,
        ).exclude(source_type='other')

        by_source: dict[str, dict] = {}
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        for row in qs.values('source_type', 'transaction_type').annotate(
            total=Sum('amount'), n=Count('id'),
        ):
            src = row['source_type'] or 'unknown'
            bucket = by_source.setdefault(
                src, {'debits': Decimal('0.00'), 'credits': Decimal('0.00'), 'n': 0}
            )
            amt = _q(row['total'])
            bucket['n'] += int(row['n'] or 0)
            if row['transaction_type'] == 'credit':
                bucket['credits'] += amt
                total_credits += amt
            else:
                bucket['debits'] += amt
                total_debits += amt

        # Sale-side check (completed, non-voided POS): totals vs amount_paid.
        sales = Sale.objects.filter(
            customer_id=customer_id, status='completed',
        ).exclude(refund_status='refunded').exclude(sale_type='normal')
        sale_total = _q(sales.aggregate(t=Sum('total'))['t'])
        sale_paid = _q(sales.aggregate(t=Sum('amount_paid'))['t'])
        sale_unpaid = max(sale_total - sale_paid, Decimal('0.00'))

        net_owed = (total_debits - total_credits).quantize(Decimal('0.01'))
        return {
            'by_source': by_source,
            'total_debits': _q(total_debits),
            'total_credits': _q(total_credits),
            'net_owed': net_owed,
            'sale_total': sale_total,
            'sale_paid': sale_paid,
            'sale_unpaid': sale_unpaid,
        }

    def _print_payments_vs_debts(self, data: dict, customer: Customer):
        shown = debt_amount_from_balance(customer.wallet_balance)
        credit = (
            _q(customer.wallet_balance)
            if _q(customer.wallet_balance) > 0
            else Decimal('0.00')
        )
        net = data['net_owed']
        # Positive net_owed ⇒ customer owes; negative ⇒ store owes customer (credit).
        # When balance is -15700, net_owed should be +15700.
        wallet_match = net == shown and _q(customer.wallet_balance) <= 0
        if _q(customer.wallet_balance) > 0:
            wallet_match = net == -credit

        self.stdout.write('\n======== PAYMENTS vs DEBTS ========')
        self.stdout.write('Charges (increase what they owe):')
        for src in sorted(data['by_source'].keys()):
            d = data['by_source'][src]['debits']
            if d:
                self.stdout.write(f'  + {src:16}  {d}')
        self.stdout.write(f'  TOTAL CHARGES (debits)     = {data["total_debits"]}')

        self.stdout.write('Payments / credits (reduce what they owe):')
        for src in sorted(data['by_source'].keys()):
            c = data['by_source'][src]['credits']
            if c:
                self.stdout.write(f'  − {src:16}  {c}')
        self.stdout.write(f'  TOTAL PAYMENTS (credits)  = {data["total_credits"]}')

        self.stdout.write(
            f'\n  Formula:  charges − payments = {data["total_debits"]} − '
            f'{data["total_credits"]} = {net}\n'
            f'  Shown wallet owed                     = {shown}\n'
            f'  Aligned? wallet owed == charges−payments ?  '
            f'{"YES" if wallet_match else "NO"}'
        )
        if not wallet_match:
            self.stdout.write(
                self.style.WARNING(
                    f'  Gap (charges−payments) − shown owed = {net - shown}'
                )
            )

        self.stdout.write(
            f'\n  Sale side (completed POS): total={data["sale_total"]}  '
            f'amount_paid={data["sale_paid"]}  unpaid={data["sale_unpaid"]}\n'
            f'  Sale unpaid vs shown owed: '
            f'{"YES" if data["sale_unpaid"] == shown else "NO"}'
            f'  (gap={shown - data["sale_unpaid"]})'
        )
        self.stdout.write('======== END PAYMENTS vs DEBTS ========')

    def _print_discrepancy_trail(
        self,
        *,
        customer,
        shown_debt,
        expected_debt,
        active_sum,
        settle_total,
        residue_debt,
        orphan_total,
        other_n,
        gap_store,
        mismatches,
        residue_sales,
        target_debt,
    ):
        """Human-readable trail of where the numbers disagree."""
        self.stdout.write('\n======== DISCREPANCY TRAIL ========')
        self.stdout.write(
            f'Customer: id={customer.id}  {customer.name}\n'
            f'  A  Shown on Debt screen (wallet owed)     = {shown_debt}\n'
            f'  B  Sum unpaid on underpaid POS sales      = {expected_debt}\n'
            f'  C  Sum active debt ledger rows            = {active_sum}\n'
            f'  D  Sum debt_settlement credits            = {settle_total}\n'
            f'  E  Debt still on cancelled/voided sales   = {residue_debt}\n'
            f'  F  Orphan debt rows total                 = {orphan_total}\n'
            f'  G  source_type=other row count            = {other_n}\n'
            f'  H  Stored wallet vs ledger replay gap     = {gap_store}'
        )
        lines = []
        if shown_debt != expected_debt:
            lines.append(
                f'  • Screen owed (A) vs unpaid sales (B): '
                f'gap = {shown_debt - expected_debt}'
            )
        if active_sum != expected_debt:
            lines.append(
                f'  • Active debt rows (C) vs unpaid sales (B): '
                f'gap = {active_sum - expected_debt}'
            )
        if residue_debt > 0:
            lines.append(
                f'  • Cancelled/voided sales still have debt (E={residue_debt}) '
                f'— should be 0'
            )
        if orphan_total > 0:
            lines.append(
                f'  • Orphan debt rows (F={orphan_total}) — sale gone/cancelled'
            )
        if other_n:
            lines.append(
                f'  • {other_n} other-row(s) (G) — cleanup residue'
            )
        if gap_store != 0:
            lines.append(
                f'  • Wallet balance does not match ledger replay (H={gap_store})'
            )
        for sale in mismatches:
            unpaid = sale_unpaid_balance(sale)
            active = active_sale_debt_amount(sale)
            lines.append(
                f'  • Sale {sale.sale_number}: unpaid={unpaid}  '
                f'active_debt={active}  gap={active - unpaid}'
            )
        for sale in residue_sales:
            lines.append(
                f'  • Inactive {sale.sale_number} '
                f'[{sale.status}/{sale.refund_status}] still has wallet residue'
            )
        if target_debt is not None:
            gap_to_target = _q(target_debt) - shown_debt
            lines.append(
                f'  • Known-good target (--set-debt {_q(target_debt)}): '
                f'screen is short/over by {gap_to_target} '
                f'(need wallet {_q(customer.wallet_balance)} → '
                f'{_q(-abs(target_debt))})'
            )
        if lines:
            self.stdout.write('Gaps:')
            for line in lines:
                self.stdout.write(self.style.WARNING(line))
        else:
            self.stdout.write(self.style.SUCCESS('Gaps: none — A/B/C align.'))
        self.stdout.write('======== END TRAIL ========')

    def _print_wallet_trail(self, customer_id: int, limit: int = 25):
        """Newest wallet rows — chronological audit of what hit the balance."""
        rows = list(
            CustomerWalletTransaction.objects.filter(customer_id=customer_id)
            .select_related('sale')
            .order_by('-id')[:limit]
        )
        self.stdout.write(
            f'\n======== WALLET TRAIL (newest {len(rows)}) ========'
        )
        if not rows:
            self.stdout.write('  (no wallet rows)')
            self.stdout.write('======== END WALLET TRAIL ========')
            return
        for txn in rows:
            sale_no = ''
            if txn.sale_id and txn.sale:
                sale_no = txn.sale.sale_number
            elif txn.reference:
                sale_no = txn.reference
            when = ''
            if getattr(txn, 'created_at', None):
                when = txn.created_at.strftime('%Y-%m-%d %H:%M')
            note = (txn.notes or '')[:60]
            self.stdout.write(
                f'  #{txn.id}  {when}  {txn.transaction_type:6}  '
                f'{txn.source_type:16}  amt={_q(txn.amount)}  '
                f'after={_q(txn.balance_after)}  '
                f'{sale_no}  {note}'
            )
        self.stdout.write('======== END WALLET TRAIL ========')

    def _parse_target_debt(self, raw) -> Decimal | None:
        if raw is None or raw == '':
            return None
        try:
            value = Decimal(str(raw).replace(',', '').strip()).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError) as exc:
            raise CommandError(f'Invalid --set-debt amount: {raw!r}') from exc
        if value < 0:
            raise CommandError('--set-debt must be a positive owed amount (e.g. 29500).')
        return value

    def _apply_set_debt(self, customer: Customer, target_debt: Decimal) -> None:
        """Post a manual wallet row so shown debt equals target_debt."""
        customer.refresh_from_db()
        target_balance = (-abs(target_debt)).quantize(Decimal('0.01'))
        current = _q(customer.wallet_balance)
        delta = (target_balance - current).quantize(Decimal('0.01'))
        if delta == 0:
            self.stdout.write(f'  set-debt: already at debt={target_debt}')
            return
        if delta < 0:
            # More owed — debit
            amount = abs(delta)
            txn_type = 'debit'
        else:
            amount = delta
            txn_type = 'credit'
        customer.wallet_balance = target_balance
        customer.save(update_fields=['wallet_balance', 'updated_at'])
        CustomerWalletTransaction.objects.create(
            customer=customer,
            transaction_type=txn_type,
            source_type='manual',
            amount=amount,
            balance_after=customer.wallet_balance,
            notes=(
                f'audit_customer_debt --set-debt {target_debt} '
                f'(was debt={debt_amount_from_balance(current)})'
            ),
            reference='set-debt',
        )
        self.stdout.write(
            f'  set-debt: {txn_type} {amount}  '
            f'wallet {current} → {target_balance}  '
            f'(owed={target_debt})'
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
