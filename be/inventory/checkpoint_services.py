"""Stock checkpoint open / count / close + Inventory journal alignment."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounting.models import Account, AccountType, JournalEntry, Transaction
from inventory.models import StockCheckpoint, StockCheckpointLine, StockMovement
from inventory.module_settings import inventory_block_sales_during_checkpoint
from inventory.services import StockMovementService
from products.models import Product, ProductVariant


INVENTORY_ACCOUNT_CODE = '1300'
VARIANCE_ACCOUNT_CODE = '6400'


def product_blocked_by_open_checkpoint(product_id: int, variant_id: Optional[int] = None):
    """
    Return the open pending checkpoint line blocking this SKU, or None.
    Only checkpoints with block_sales=True enforce a sell freeze.
    Variant lines block that variant; product-level pending lines block the product
    when no variant is specified (and also block all variants of that product).
    """
    qs = StockCheckpointLine.objects.filter(
        status=StockCheckpointLine.STATUS_PENDING,
        checkpoint__status=StockCheckpoint.STATUS_OPEN,
        checkpoint__block_sales=True,
        product_id=product_id,
    ).select_related('checkpoint', 'product', 'variant')

    if variant_id:
        line = qs.filter(Q(variant_id=variant_id) | Q(variant__isnull=True)).first()
    else:
        line = qs.filter(variant__isnull=True).first()
        if line is None:
            # Any pending variant line also blocks selling the product without variant
            line = qs.filter(variant__isnull=False).first()
    return line


def assert_product_sellable(product, variant=None):
    """Raise ValidationError if an open checkpoint still needs a count for this SKU."""
    if product is None or not getattr(product, 'track_stock', True):
        return
    line = product_blocked_by_open_checkpoint(
        product.id,
        variant.id if variant is not None else None,
    )
    if line is None:
        return
    name = product.name
    if variant is not None:
        name = f'{name} ({getattr(variant, "sku", None) or variant.id})'
    raise ValidationError(
        f'Stock checkpoint open — count stock at hand before selling {name}.'
    )


def blocked_product_ids() -> set[int]:
    """Product ids blocked from sale (pending lines on open block_sales checkpoints)."""
    return set(
        StockCheckpointLine.objects.filter(
            status=StockCheckpointLine.STATUS_PENDING,
            checkpoint__status=StockCheckpoint.STATUS_OPEN,
            checkpoint__block_sales=True,
        ).values_list('product_id', flat=True)
    )


def latest_closed_checkpoint() -> Optional[StockCheckpoint]:
    return (
        StockCheckpoint.objects.filter(status=StockCheckpoint.STATUS_CLOSED)
        .order_by('-closed_at', '-id')
        .first()
    )


def _on_hand(product: Product, variant: Optional[ProductVariant]) -> int:
    if variant is not None:
        return int(variant.stock_quantity or 0)
    return int(product.stock_quantity or 0)


def _unit_cost(product: Product, variant: Optional[ProductVariant]) -> Decimal:
    if variant is not None and variant.cost is not None:
        return Decimal(str(variant.cost))
    return Decimal(str(product.cost or 0))


def _ensure_inventory_accounts():
    asset_type, _ = AccountType.objects.get_or_create(
        name='asset',
        defaults={'normal_balance': 'debit'},
    )
    expense_type, _ = AccountType.objects.get_or_create(
        name='expense',
        defaults={'normal_balance': 'debit'},
    )
    inventory, _ = Account.objects.get_or_create(
        account_code=INVENTORY_ACCOUNT_CODE,
        defaults={
            'name': 'Inventory',
            'account_type': asset_type,
            'description': 'Product inventory',
            'opening_balance': Decimal('0.00'),
            'current_balance': Decimal('0.00'),
        },
    )
    variance, _ = Account.objects.get_or_create(
        account_code=VARIANCE_ACCOUNT_CODE,
        defaults={
            'name': 'Inventory count variance',
            'account_type': expense_type,
            'description': 'Stock checkpoint count variance',
            'opening_balance': Decimal('0.00'),
            'current_balance': Decimal('0.00'),
        },
    )
    return inventory, variance


def post_inventory_count_journal(
    *,
    line: StockCheckpointLine,
    delta: int,
    amount: Decimal,
    user=None,
):
    """
    Align Inventory (1300) with counted stock value change.
    count up  → Debit Inventory / Credit variance
    count down → Debit variance / Credit Inventory
    """
    if delta == 0 or amount <= 0:
        return None

    inventory, variance = _ensure_inventory_accounts()
    today = timezone.localdate()
    ref = f'CHECKPOINT-{line.checkpoint_id}-L{line.id}'
    desc = (
        f'Stock checkpoint count: {line.product.name} '
        f'({line.system_qty_at_open} → {line.counted_qty})'
    )

    txn = Transaction.objects.create(
        transaction_date=today,
        description=desc,
        reference=ref,
        reference_type='stock_checkpoint',
        reference_id=line.checkpoint_id,
        created_by=user,
    )

    if delta > 0:
        debit_account, credit_account = inventory, variance
        debit_desc = f'Inventory increase — {desc}'
        credit_desc = f'Count variance credit — {desc}'
    else:
        debit_account, credit_account = variance, inventory
        debit_desc = f'Count variance debit — {desc}'
        credit_desc = f'Inventory decrease — {desc}'

    debit = JournalEntry.objects.create(
        entry_date=today,
        account=debit_account,
        entry_type='debit',
        amount=amount,
        description=debit_desc,
        reference=ref,
        reference_type='stock_checkpoint',
        reference_id=line.checkpoint_id,
        created_by=user,
    )
    credit = JournalEntry.objects.create(
        entry_date=today,
        account=credit_account,
        entry_type='credit',
        amount=amount,
        description=credit_desc,
        reference=ref,
        reference_type='stock_checkpoint',
        reference_id=line.checkpoint_id,
        created_by=user,
    )
    txn.journal_entries.add(debit, credit)
    return txn


@transaction.atomic
def open_checkpoint(
    *,
    title: str,
    user,
    product_ids: Optional[Iterable[int]] = None,
    include_all_tracked: bool = False,
    notes: str = '',
    block_sales: Optional[bool] = None,
) -> StockCheckpoint:
    title = (title or '').strip()
    if not title:
        raise ValidationError('Title is required.')

    if include_all_tracked:
        products = list(
            Product.objects.filter(is_active=True, track_stock=True).prefetch_related(
                'variants'
            )
        )
    else:
        ids = [int(x) for x in (product_ids or [])]
        if not ids:
            raise ValidationError('Select at least one product, or include all tracked stock.')
        products = list(
            Product.objects.filter(id__in=ids, track_stock=True).prefetch_related('variants')
        )
        if not products:
            raise ValidationError('No tracked products found for the given ids.')

    if block_sales is None:
        block_sales = inventory_block_sales_during_checkpoint()

    checkpoint = StockCheckpoint.objects.create(
        title=title,
        status=StockCheckpoint.STATUS_OPEN,
        block_sales=bool(block_sales),
        notes=(notes or '').strip(),
        opened_by=user,
    )

    lines = []
    for product in products:
        variants = [v for v in product.variants.all() if getattr(product, 'has_variants', False)]
        if product.has_variants and variants:
            for variant in variants:
                lines.append(
                    StockCheckpointLine(
                        checkpoint=checkpoint,
                        product=product,
                        variant=variant,
                        system_qty_at_open=_on_hand(product, variant),
                        unit_cost_snapshot=_unit_cost(product, variant),
                        status=StockCheckpointLine.STATUS_PENDING,
                    )
                )
        else:
            lines.append(
                StockCheckpointLine(
                    checkpoint=checkpoint,
                    product=product,
                    variant=None,
                    system_qty_at_open=_on_hand(product, None),
                    unit_cost_snapshot=_unit_cost(product, None),
                    status=StockCheckpointLine.STATUS_PENDING,
                )
            )

    StockCheckpointLine.objects.bulk_create(lines)
    return checkpoint


@transaction.atomic
def count_checkpoint_line(
    *,
    line_id: int,
    counted_qty: int,
    user,
    branch=None,
) -> StockCheckpointLine:
    try:
        line = (
            StockCheckpointLine.objects.select_for_update()
            .select_related('checkpoint', 'product', 'variant')
            .get(pk=line_id)
        )
    except StockCheckpointLine.DoesNotExist:
        raise ValidationError('Checkpoint line not found.')

    if line.checkpoint.status != StockCheckpoint.STATUS_OPEN:
        raise ValidationError('Only open checkpoints can be counted.')
    if line.status == StockCheckpointLine.STATUS_COUNTED:
        raise ValidationError('This line is already counted.')

    try:
        counted_qty = int(counted_qty)
    except (TypeError, ValueError):
        raise ValidationError('Enter a valid stock-at-hand quantity.')
    if counted_qty < 0:
        raise ValidationError('Stock at hand cannot be negative.')

    product = line.product
    variant = line.variant
    current = _on_hand(product, variant)
    delta = counted_qty - current
    unit_cost = line.unit_cost_snapshot or _unit_cost(product, variant)

    movement = None
    if delta != 0:
        movement = StockMovementService().adjust_stock(
            product_id=product.id,
            variant_id=variant.id if variant else None,
            quantity=delta,
            notes=f'Stock checkpoint #{line.checkpoint_id}: set on-hand to {counted_qty}',
            user=user,
            branch=branch,
            unit_cost=unit_cost,
        )
        # Retarget reference for audit trail
        movement.reference = f'CHECKPOINT-{line.checkpoint_id}'
        movement.save(update_fields=['reference'])

    line.counted_qty = counted_qty
    line.status = StockCheckpointLine.STATUS_COUNTED
    line.counted_at = timezone.now()
    line.counted_by = user
    line.movement = movement
    line.save(
        update_fields=[
            'counted_qty',
            'status',
            'counted_at',
            'counted_by',
            'movement',
        ]
    )

    amount = (Decimal(str(abs(delta))) * Decimal(str(unit_cost or 0))).quantize(
        Decimal('0.01')
    )
    post_inventory_count_journal(line=line, delta=delta, amount=amount, user=user)
    return line


@transaction.atomic
def close_checkpoint(*, checkpoint_id: int, user) -> StockCheckpoint:
    try:
        checkpoint = StockCheckpoint.objects.select_for_update().get(pk=checkpoint_id)
    except StockCheckpoint.DoesNotExist:
        raise ValidationError('Checkpoint not found.')

    if checkpoint.status != StockCheckpoint.STATUS_OPEN:
        raise ValidationError('Only open checkpoints can be closed.')

    pending = checkpoint.lines.filter(status=StockCheckpointLine.STATUS_PENDING).count()
    if pending:
        raise ValidationError(
            f'Count all lines before closing ({pending} still pending).'
        )

    checkpoint.status = StockCheckpoint.STATUS_CLOSED
    checkpoint.closed_at = timezone.now()
    checkpoint.closed_by = user
    checkpoint.save(update_fields=['status', 'closed_at', 'closed_by'])
    return checkpoint


@transaction.atomic
def cancel_checkpoint(*, checkpoint_id: int, user) -> StockCheckpoint:
    """Abandon an open checkpoint and lift sell blocks without adjusting stock."""
    try:
        checkpoint = StockCheckpoint.objects.select_for_update().get(pk=checkpoint_id)
    except StockCheckpoint.DoesNotExist:
        raise ValidationError('Checkpoint not found.')

    if checkpoint.status != StockCheckpoint.STATUS_OPEN:
        raise ValidationError('Only open checkpoints can be cancelled.')

    checkpoint.status = StockCheckpoint.STATUS_CANCELLED
    checkpoint.closed_at = timezone.now()
    checkpoint.closed_by = user
    checkpoint.save(update_fields=['status', 'closed_at', 'closed_by'])
    return checkpoint
