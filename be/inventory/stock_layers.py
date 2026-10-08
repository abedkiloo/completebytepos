"""
FIFO stock layers: each purchase keeps its cost + selling price until depleted.

Catalog product.price / product.cost (and variant equivalents) mirror the oldest
open layer so POS lists stay correct without a separate price engine.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import F, Prefetch, Sum
from django.utils import timezone

from inventory.module_settings import inventory_enable_stock_layers
from inventory.models import StockLayer, StockMovement
from products.models import Product, ProductVariant


def layers_enabled() -> bool:
    return inventory_enable_stock_layers()


def open_layers_prefetch():
    """Prefetch open layers (ordered) for product detail without N+1."""
    return Prefetch(
        'stock_layers',
        queryset=(
            StockLayer.objects.filter(qty_remaining__gt=0)
            .select_related('variant', 'variant__size', 'variant__color')
            .order_by('received_at', 'id')
        ),
        to_attr='open_stock_layers',
    )


def ensure_opening_layer_if_needed(
    *,
    product_id: int,
    variant_id: Optional[int] = None,
) -> StockLayer | None:
    """
    If on-hand stock exists but no open layer (e.g. test fixtures / pre-layer
    stock), create one opening layer from current catalog cost/price.
    """
    if not layers_enabled():
        return None
    if open_layers_qs(product_id=product_id, variant_id=variant_id).exists():
        return None

    if variant_id:
        variant = (
            ProductVariant.objects.filter(pk=variant_id)
            .select_related('product')
            .first()
        )
        if variant is None:
            return None
        qty = int(variant.stock_quantity or 0)
        cost = (
            variant.cost
            if variant.cost is not None
            else Decimal(str(variant.product.cost or 0))
        )
        sell = (
            variant.price
            if variant.price is not None
            else Decimal(str(variant.product.price or 0))
        )
        received_at = variant.created_at or timezone.now()
    else:
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return None
        qty = int(product.stock_quantity or 0)
        cost = Decimal(str(product.cost or 0))
        sell = Decimal(str(product.price or 0))
        received_at = product.created_at or timezone.now()

    if qty <= 0:
        return None

    return StockLayer.objects.create(
        product_id=product_id,
        variant_id=variant_id,
        qty_received=qty,
        qty_remaining=qty,
        unit_cost=cost,
        unit_sell_price=sell,
        received_at=received_at,
        source_movement=None,
    )


def bulk_ensure_opening_layers() -> int:
    """
    Create missing opening layers for tracked SKUs with on-hand stock.

    Fixed query budget (open keys + products + variants + bulk_create) instead
    of per-SKU exists()/fetch. Returns number of layers created.
    """
    if not layers_enabled():
        return 0

    open_keys = {
        (pid, vid)
        for pid, vid in StockLayer.objects.filter(qty_remaining__gt=0).values_list(
            'product_id', 'variant_id'
        )
    }

    to_create: list[StockLayer] = []
    now = timezone.now()

    for product in Product.objects.filter(
        track_stock=True,
        has_variants=False,
        stock_quantity__gt=0,
    ).only('id', 'cost', 'price', 'created_at', 'stock_quantity').iterator(chunk_size=500):
        if (product.id, None) in open_keys:
            continue
        qty = int(product.stock_quantity or 0)
        if qty <= 0:
            continue
        to_create.append(
            StockLayer(
                product_id=product.id,
                variant_id=None,
                qty_received=qty,
                qty_remaining=qty,
                unit_cost=Decimal(str(product.cost or 0)),
                unit_sell_price=Decimal(str(product.price or 0)),
                received_at=product.created_at or now,
                source_movement=None,
            )
        )

    for variant in (
        ProductVariant.objects.filter(
            is_active=True,
            stock_quantity__gt=0,
            product__track_stock=True,
            product__has_variants=True,
        )
        .select_related('product')
        .only(
            'id',
            'product_id',
            'stock_quantity',
            'cost',
            'price',
            'created_at',
            'product__id',
            'product__cost',
            'product__price',
        )
        .iterator(chunk_size=500)
    ):
        if (variant.product_id, variant.id) in open_keys:
            continue
        qty = int(variant.stock_quantity or 0)
        if qty <= 0:
            continue
        cost = (
            variant.cost
            if variant.cost is not None
            else Decimal(str(variant.product.cost or 0))
        )
        sell = (
            variant.price
            if variant.price is not None
            else Decimal(str(variant.product.price or 0))
        )
        to_create.append(
            StockLayer(
                product_id=variant.product_id,
                variant_id=variant.id,
                qty_received=qty,
                qty_remaining=qty,
                unit_cost=cost,
                unit_sell_price=sell,
                received_at=variant.created_at or now,
                source_movement=None,
            )
        )

    # has_variants=True but no active variant rows — value parent stock.
    shell_qs = Product.objects.filter(
        track_stock=True,
        has_variants=True,
        stock_quantity__gt=0,
    ).only('id', 'cost', 'price', 'created_at', 'stock_quantity')
    shell_ids = list(shell_qs.values_list('id', flat=True))
    if shell_ids:
        with_variants = set(
            ProductVariant.objects.filter(
                product_id__in=shell_ids,
                is_active=True,
            ).values_list('product_id', flat=True)
        )
        for product in shell_qs.iterator(chunk_size=500):
            if product.id in with_variants or (product.id, None) in open_keys:
                continue
            qty = int(product.stock_quantity or 0)
            if qty <= 0:
                continue
            to_create.append(
                StockLayer(
                    product_id=product.id,
                    variant_id=None,
                    qty_received=qty,
                    qty_remaining=qty,
                    unit_cost=Decimal(str(product.cost or 0)),
                    unit_sell_price=Decimal(str(product.price or 0)),
                    received_at=product.created_at or now,
                    source_movement=None,
                )
            )

    if to_create:
        StockLayer.objects.bulk_create(to_create, batch_size=500)
    return len(to_create)


def open_layers_qs(*, product_id: int, variant_id: Optional[int] = None):
    qs = StockLayer.objects.filter(
        product_id=product_id,
        qty_remaining__gt=0,
    ).order_by('received_at', 'id')
    if variant_id:
        qs = qs.filter(variant_id=variant_id)
    else:
        qs = qs.filter(variant__isnull=True)
    return qs


def oldest_open_layer(*, product_id: int, variant_id: Optional[int] = None) -> StockLayer | None:
    return open_layers_qs(product_id=product_id, variant_id=variant_id).first()


def sync_catalog_from_oldest_layer(*, product_id: int, variant_id: Optional[int] = None) -> None:
    """Set catalog cost/price from the oldest open layer (or leave as-is if none)."""
    layer = oldest_open_layer(product_id=product_id, variant_id=variant_id)
    if layer is None:
        return
    if variant_id:
        ProductVariant.objects.filter(pk=variant_id).update(
            cost=layer.unit_cost,
            price=layer.unit_sell_price,
        )
        product = Product.objects.filter(pk=product_id).only('id', 'has_variants').first()
        if product and product.has_variants:
            from products.stock_utils import sync_product_cost_from_variants

            sync_product_cost_from_variants(product)
            any_layer = (
                StockLayer.objects.filter(product_id=product_id, qty_remaining__gt=0)
                .order_by('received_at', 'id')
                .first()
            )
            if any_layer:
                Product.objects.filter(pk=product_id).update(
                    price=any_layer.unit_sell_price,
                    cost=any_layer.unit_cost,
                )
    else:
        Product.objects.filter(pk=product_id).update(
            cost=layer.unit_cost,
            price=layer.unit_sell_price,
        )


def create_layer_for_purchase(
    *,
    movement: StockMovement,
    unit_sell_price: Decimal,
) -> StockLayer:
    """Create a layer after a purchase movement (qty already applied to stock)."""
    qty = abs(int(movement.quantity or 0))
    cost = Decimal(str(movement.unit_cost or 0))
    sell = Decimal(str(unit_sell_price or 0))
    layer = StockLayer.objects.create(
        product_id=movement.product_id,
        variant_id=movement.variant_id,
        qty_received=qty,
        qty_remaining=qty,
        unit_cost=cost,
        unit_sell_price=sell,
        received_at=movement.created_at or timezone.now(),
        source_movement=movement,
    )
    sync_catalog_from_oldest_layer(
        product_id=movement.product_id,
        variant_id=movement.variant_id,
    )
    return layer


def plan_fifo_allocations(
    *,
    product_id: int,
    variant_id: Optional[int],
    quantity: int,
) -> list[dict]:
    """
    Plan FIFO drain without mutating.

    Returns list of {layer, quantity, unit_cost, unit_sell_price}.
    When layers are disabled or no layers exist, returns a single synthetic
    allocation using catalog cost/price (layer=None).
    """
    qty = int(quantity or 0)
    if qty <= 0:
        return []

    if not layers_enabled():
        return _catalog_fallback(product_id, variant_id, qty)

    # Prefer one layers query; only materialize opening layer if none exist.
    layers = list(open_layers_qs(product_id=product_id, variant_id=variant_id))
    if not layers:
        ensure_opening_layer_if_needed(product_id=product_id, variant_id=variant_id)
        layers = list(open_layers_qs(product_id=product_id, variant_id=variant_id))
    if not layers:
        return _catalog_fallback(product_id, variant_id, qty)

    remaining = qty
    plan: list[dict] = []
    for layer in layers:
        if remaining <= 0:
            break
        take = min(remaining, int(layer.qty_remaining))
        if take <= 0:
            continue
        plan.append({
            'layer': layer,
            'quantity': take,
            'unit_cost': Decimal(str(layer.unit_cost)),
            'unit_sell_price': Decimal(str(layer.unit_sell_price)),
        })
        remaining -= take

    if remaining > 0:
        if plan:
            last = plan[-1]
            plan.append({
                'layer': last['layer'],
                'quantity': remaining,
                'unit_cost': last['unit_cost'],
                'unit_sell_price': last['unit_sell_price'],
                'oversell': True,
            })
        else:
            plan.extend(_catalog_fallback(product_id, variant_id, remaining))
    return plan


def _catalog_fallback(product_id, variant_id, qty: int) -> list[dict]:
    product = Product.objects.filter(pk=product_id).only('id', 'price', 'cost').first()
    variant = None
    if variant_id:
        variant = (
            ProductVariant.objects.filter(pk=variant_id)
            .only('id', 'price', 'cost')
            .first()
        )
    if variant is not None and variant.price is not None:
        sell = Decimal(str(variant.price))
    else:
        sell = Decimal(str(getattr(product, 'price', 0) or 0))
    if variant is not None and variant.cost is not None:
        cost = Decimal(str(variant.cost))
    else:
        cost = Decimal(str(getattr(product, 'cost', 0) or 0))
    return [{
        'layer': None,
        'quantity': qty,
        'unit_cost': cost,
        'unit_sell_price': sell,
    }]


@transaction.atomic
def apply_fifo_sale_drain(
    *,
    product_id: int,
    variant_id: Optional[int],
    quantity: int,
) -> list[dict]:
    """
    Decrement open layers FIFO. Returns applied allocation dicts
    (same shape as plan_fifo_allocations, with refreshed layer refs).
    """
    qty = int(quantity or 0)
    if qty <= 0 or not layers_enabled():
        return plan_fifo_allocations(
            product_id=product_id, variant_id=variant_id, quantity=qty
        )

    # Lock open layers first; only create an opening layer if nothing is open.
    layers = list(
        open_layers_qs(product_id=product_id, variant_id=variant_id).select_for_update()
    )
    if not layers:
        ensure_opening_layer_if_needed(product_id=product_id, variant_id=variant_id)
        layers = list(
            open_layers_qs(product_id=product_id, variant_id=variant_id).select_for_update()
        )

    remaining = qty
    applied: list[dict] = []
    for layer in layers:
        if remaining <= 0:
            break
        take = min(remaining, int(layer.qty_remaining))
        if take <= 0:
            continue
        StockLayer.objects.filter(pk=layer.pk).update(
            qty_remaining=F('qty_remaining') - take
        )
        layer.qty_remaining = int(layer.qty_remaining) - take
        applied.append({
            'layer': layer,
            'quantity': take,
            'unit_cost': Decimal(str(layer.unit_cost)),
            'unit_sell_price': Decimal(str(layer.unit_sell_price)),
        })
        remaining -= take

    if remaining > 0:
        applied.extend(_catalog_fallback(product_id, variant_id, remaining))

    sync_catalog_from_oldest_layer(product_id=product_id, variant_id=variant_id)
    return applied


@transaction.atomic
def restore_layer_qty(*, layer_id: int, quantity: int) -> None:
    """Return qty to a layer after refund (clamped to qty_received)."""
    if not layers_enabled() or not layer_id or quantity <= 0:
        return
    layer = StockLayer.objects.select_for_update().filter(pk=layer_id).first()
    if layer is None:
        return
    new_rem = min(int(layer.qty_received), int(layer.qty_remaining) + int(quantity))
    StockLayer.objects.filter(pk=layer.pk).update(qty_remaining=new_rem)
    sync_catalog_from_oldest_layer(
        product_id=layer.product_id,
        variant_id=layer.variant_id,
    )


def layer_stock_value_rows():
    """Open layers for valuation reports."""
    return (
        StockLayer.objects.filter(qty_remaining__gt=0)
        .select_related(
            'product', 'product__category', 'variant', 'variant__size', 'variant__color'
        )
        .order_by('product__name', 'received_at', 'id')
    )


def total_remaining_for(*, product_id: int, variant_id: Optional[int] = None) -> int:
    qs = StockLayer.objects.filter(product_id=product_id, qty_remaining__gt=0)
    if variant_id:
        qs = qs.filter(variant_id=variant_id)
    else:
        qs = qs.filter(variant__isnull=True)
    return int(qs.aggregate(t=Sum('qty_remaining'))['t'] or 0)
