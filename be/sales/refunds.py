"""Process sale refunds: stock return, wallet credit, accounting, audit."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from inventory.models import StockMovement
from sales.models import Sale, SaleItem, SaleRefund, SaleRefundItem
from sales.refund_allocation import compute_refund_allocation


class SaleRefundService:
    @transaction.atomic
    def create_refund(
        self,
        sale: Sale,
        *,
        reason: str,
        user,
        items: Optional[List[Dict[str, Any]]] = None,
        full: bool = False,
    ) -> SaleRefund:
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError({'reason': 'A reason is required for refunds.'})
        if sale.status != 'completed':
            raise ValidationError('Only completed sales can be refunded.')
        if sale.refund_status == 'refunded':
            raise ValidationError('This sale has already been fully refunded.')

        lines = self._resolve_refund_lines(sale, items=items, full=full)
        if not lines:
            raise ValidationError({'items': 'Select at least one item to refund.'})

        amount = sum((line['subtotal'] for line in lines), Decimal('0'))
        if amount <= 0:
            raise ValidationError('Refund amount must be greater than zero.')
        if amount > sale.refundable_remaining():
            raise ValidationError(
                f'Refund amount ({amount}) exceeds remaining refundable balance '
                f'({sale.refundable_remaining()}).'
            )

        refund_type = 'full' if amount >= sale.refundable_remaining() else 'partial'
        refund = SaleRefund.objects.create(
            sale=sale,
            refund_type=refund_type,
            amount=amount,
            reason=reason,
            refunded_by=user,
        )

        branch = sale.branch
        reference = refund.refund_number
        for line in lines:
            sale_item = line['sale_item']
            qty = line['quantity']
            SaleRefundItem.objects.create(
                refund=refund,
                sale_item=sale_item,
                product=sale_item.product,
                variant=sale_item.variant,
                quantity=qty,
                unit_price=line['unit_price'],
                subtotal=line['subtotal'],
            )
            self._return_stock(
                sale=sale,
                sale_item=sale_item,
                quantity=qty,
                branch=branch,
                user=user,
                reference=reference,
                notes=f'Refund {reference} for {sale.sale_number}',
            )

        self._credit_wallet_if_needed(sale, amount, refund, user)
        self._reverse_customer_debt_if_needed(sale, amount, refund, user)
        self._sync_sale_refund_status(sale)

        try:
            from accounting.services import create_sale_refund_journal_entry

            create_sale_refund_journal_entry(refund)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                'Journal entry failed for refund %s', refund.refund_number
            )

        return refund

    def _resolve_refund_lines(
        self,
        sale: Sale,
        *,
        items: Optional[List[Dict[str, Any]]],
        full: bool,
    ) -> List[Dict[str, Any]]:
        refunded_by_item = self._refunded_qty_by_sale_item(sale)
        sale_items = {item.id: item for item in sale.items.select_related('product', 'variant')}
        lines: List[Dict[str, Any]] = []

        if full:
            payload = []
            for item in sale_items.values():
                already = refunded_by_item.get(item.id, 0)
                remaining = item.quantity - already
                if remaining > 0:
                    payload.append({'sale_item_id': item.id, 'quantity': remaining})
        else:
            payload = items or []

        for row in payload:
            item_id = row.get('sale_item_id')
            qty = int(row.get('quantity') or 0)
            if not item_id or qty <= 0:
                continue
            sale_item = sale_items.get(int(item_id))
            if not sale_item:
                raise ValidationError({'items': f'Invalid sale line id: {item_id}'})
            already = refunded_by_item.get(sale_item.id, 0)
            remaining = sale_item.quantity - already
            if qty > remaining:
                raise ValidationError(
                    {
                        'items': (
                            f'Cannot refund {qty} units of {sale_item.product.name}; '
                            f'only {remaining} remaining.'
                        )
                    }
                )
            unit_price = sale_item.unit_price
            lines.append(
                {
                    'sale_item': sale_item,
                    'quantity': qty,
                    'unit_price': unit_price,
                    'subtotal': Decimal(str(qty)) * unit_price,
                }
            )
        return lines

    @staticmethod
    def _refunded_qty_by_sale_item(sale: Sale) -> Dict[int, int]:
        rows = (
            SaleRefundItem.objects.filter(refund__sale=sale)
            .values('sale_item_id')
            .annotate(total=Sum('quantity'))
        )
        return {row['sale_item_id']: int(row['total'] or 0) for row in rows}

    @staticmethod
    def _return_stock(
        *,
        sale: Sale,
        sale_item: SaleItem,
        quantity: int,
        branch,
        user,
        reference: str,
        notes: str,
    ) -> None:
        product = sale_item.product
        if not product.track_stock:
            return
        unit_cost = product.cost or Decimal('0')
        StockMovement.objects.create(
            branch=branch,
            product=product,
            variant=sale_item.variant,
            movement_type='return',
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=quantity * unit_cost,
            reference=reference,
            user=user,
            notes=notes,
        )

    @staticmethod
    def _credit_wallet_if_needed(sale: Sale, amount: Decimal, refund: SaleRefund, user) -> None:
        if not sale.customer_id or sale.total <= 0:
            return
        allocation = compute_refund_allocation(sale, amount)
        credit_amount = allocation['wallet_back']
        if credit_amount <= 0:
            return
        from sales.services import CustomerService

        CustomerService().update_wallet_balance(
            sale.customer,
            credit_amount,
            transaction_type='credit',
            source_type='refund',
            sale=sale,
            reference=refund.refund_number,
            notes=f'Wallet payment reversed for refund of {sale.sale_number}',
            user=user,
        )

    @staticmethod
    def _reverse_customer_debt_if_needed(
        sale: Sale, amount: Decimal, refund: SaleRefund, user
    ) -> None:
        """Restore customer account when reversing pay-later / partial-payment debt."""
        if not sale.customer_id or sale.total <= 0:
            return
        allocation = compute_refund_allocation(sale, amount)
        reversal = allocation['debt_back']
        if reversal <= 0:
            return
        from sales.models import CustomerWalletTransaction

        customer = sale.customer
        customer.refresh_from_db()
        customer.wallet_balance += reversal
        customer.save(update_fields=['wallet_balance', 'updated_at'])
        CustomerWalletTransaction.objects.create(
            customer=customer,
            transaction_type='credit',
            source_type='refund',
            amount=reversal,
            balance_after=customer.wallet_balance,
            sale=sale,
            reference=refund.refund_number,
            notes=f'Account debt reversed for refund of {sale.sale_number}',
            created_by=user,
        )

    @staticmethod
    def _sync_sale_refund_status(sale: Sale) -> None:
        remaining = sale.refundable_remaining()
        if remaining <= 0:
            sale.refund_status = 'refunded'
        else:
            sale.refund_status = 'partial'
        sale.save(update_fields=['refund_status', 'updated_at'])
