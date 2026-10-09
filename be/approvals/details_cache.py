"""
Batch-load related rows for pending-change / sale approval detail serialization.

List serializers call ``build_details_cache`` once, then detail builders read
from the cache so a page of approvals stays O(1) queries (no per-row N+1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from approvals.models import PendingChange
from approvals.registry import (
    ACTION_CATEGORY_DEACTIVATE,
    ACTION_CATEGORY_DELETE,
    ACTION_DEBT_COLLECTION,
    ACTION_ROLE_PERMISSIONS,
    ACTION_SALE_BACKFILL,
    ACTION_SALE_COMPLETE,
    ACTION_STOCK_ADJUST,
    ACTION_STOCK_PURCHASE,
    ACTION_STOCK_TRANSFER,
)


@dataclass
class DetailsCache:
    sales: dict[int, Any] = field(default_factory=dict)
    products: dict[int, Any] = field(default_factory=dict)
    variants: dict[int, Any] = field(default_factory=dict)
    customers: dict[int, Any] = field(default_factory=dict)
    categories: dict[int, Any] = field(default_factory=dict)
    roles: dict[int, Any] = field(default_factory=dict)
    permissions: dict[int, Any] = field(default_factory=dict)
    branches: dict[int, Any] = field(default_factory=dict)
    # sale_id → latest pending sale_complete change (for till-queue details)
    pending_complete_by_sale_id: dict[int, PendingChange] = field(default_factory=dict)


def _as_int(value) -> int | None:
    try:
        if value in (None, ''):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def build_details_cache(changes: Iterable[PendingChange]) -> DetailsCache:
    """One batched hydrate for a list of PendingChange rows."""
    changes = list(changes)
    cache = DetailsCache()
    if not changes:
        return cache

    sale_ids: set[int] = set()
    product_ids: set[int] = set()
    variant_ids: set[int] = set()
    customer_ids: set[int] = set()
    category_ids: set[int] = set()
    role_ids: set[int] = set()
    permission_ids: set[int] = set()
    branch_ids: set[int] = set()

    for change in changes:
        payload = change.apply_payload or {}
        proposed = change.proposed_values or {}
        original = change.original_values or {}
        entity_id = _as_int(change.entity_id)

        if change.action_type == ACTION_DEBT_COLLECTION and entity_id is not None:
            customer_ids.add(entity_id)
        elif change.action_type == ACTION_SALE_BACKFILL:
            cid = _as_int(payload.get('customer_id'))
            if cid is not None:
                customer_ids.add(cid)
            for row in payload.get('items') or []:
                pid = _as_int(row.get('product_id'))
                vid = _as_int(row.get('variant_id'))
                if pid is not None:
                    product_ids.add(pid)
                if vid is not None:
                    variant_ids.add(vid)
        elif change.action_type in (
            ACTION_STOCK_ADJUST, ACTION_STOCK_PURCHASE, ACTION_STOCK_TRANSFER,
        ):
            pid = _as_int(payload.get('product_id'))
            vid = _as_int(payload.get('variant_id'))
            if pid is not None:
                product_ids.add(pid)
            if vid is not None:
                variant_ids.add(vid)
            for key in ('branch_id', 'to_branch_id'):
                bid = _as_int(payload.get(key))
                if bid is not None:
                    branch_ids.add(bid)
        elif change.action_type in (ACTION_CATEGORY_DEACTIVATE, ACTION_CATEGORY_DELETE):
            if entity_id is not None:
                category_ids.add(entity_id)
        elif change.action_type == ACTION_ROLE_PERMISSIONS:
            if entity_id is not None:
                role_ids.add(entity_id)
            for raw in (
                proposed.get('permission_ids')
                or payload.get('permission_ids')
                or []
            ):
                pid = _as_int(raw)
                if pid is not None:
                    permission_ids.add(pid)
            for raw in original.get('permission_ids') or []:
                pid = _as_int(raw)
                if pid is not None:
                    permission_ids.add(pid)
        elif change.entity_type == 'sales.Sale' and entity_id is not None:
            sale_ids.add(entity_id)
        elif change.entity_type == 'products.Product' and entity_id is not None:
            product_ids.add(entity_id)
        elif change.entity_type == 'products.ProductVariant' and entity_id is not None:
            variant_ids.add(entity_id)
        elif change.action_type == ACTION_SALE_COMPLETE and entity_id is not None:
            sale_ids.add(entity_id)

    if sale_ids:
        from sales.models import Sale

        for sale in (
            Sale.objects.filter(pk__in=sale_ids)
            .select_related('customer', 'cashier', 'served_by')
            .prefetch_related(
                'items__product',
                'items__variant',
                'items__size',
                'items__color',
            )
        ):
            cache.sales[sale.pk] = sale

    if product_ids:
        from products.models import Product

        for product in Product.objects.select_related('category').filter(pk__in=product_ids):
            cache.products[product.pk] = product

    if variant_ids:
        from products.models import ProductVariant

        for variant in (
            ProductVariant.objects.select_related('product', 'size', 'color')
            .filter(pk__in=variant_ids)
        ):
            cache.variants[variant.pk] = variant
            if variant.product_id and variant.product_id not in cache.products:
                cache.products[variant.product_id] = variant.product

    if customer_ids:
        from sales.models import Customer

        for customer in Customer.objects.filter(pk__in=customer_ids):
            cache.customers[customer.pk] = customer

    if category_ids:
        from products.models import Category

        for category in Category.objects.filter(pk__in=category_ids):
            cache.categories[category.pk] = category

    if role_ids:
        from accounts.models import Role

        for role in Role.objects.filter(pk__in=role_ids):
            cache.roles[role.pk] = role

    if permission_ids:
        from accounts.models import Permission

        for perm in Permission.objects.filter(pk__in=permission_ids):
            cache.permissions[perm.pk] = perm

    if branch_ids:
        from settings.models import Branch

        for branch in Branch.objects.filter(pk__in=branch_ids):
            cache.branches[branch.pk] = branch

    return cache


def build_sale_approval_cache(sales: Iterable) -> DetailsCache:
    """Batch pending sale_complete payloads for the till approval list."""
    sales = [s for s in sales if getattr(s, 'status', None) == 'pending_approval']
    cache = DetailsCache()
    if not sales:
        return cache
    entity_ids = [str(s.pk) for s in sales]
    for change in (
        PendingChange.objects.filter(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id__in=entity_ids,
            status=PendingChange.STATUS_PENDING,
        ).order_by('-id')
    ):
        sale_id = _as_int(change.entity_id)
        if sale_id is None or sale_id in cache.pending_complete_by_sale_id:
            continue
        cache.pending_complete_by_sale_id[sale_id] = change
    return cache
