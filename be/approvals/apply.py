"""Apply approved pending changes to live data."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.registry import (
    ACTION_CATEGORY_DELETE,
    ACTION_CATEGORY_DEACTIVATE,
    ACTION_PRODUCT_DELETE,
    ACTION_PRODUCT_DEACTIVATE,
    ACTION_PRODUCT_PRICE,
    ACTION_PRODUCT_STOCK,
    ACTION_PRODUCT_TAX,
    ACTION_PRODUCT_UNIT,
    ACTION_ROLE_PERMISSIONS,
    ACTION_SALE_COMPLETED_EDIT,
    ACTION_STOCK_ADJUST,
    ACTION_STOCK_PURCHASE,
    ACTION_STOCK_TRANSFER,
)


def apply_pending_change(change: PendingChange) -> None:
    if change.action_type == ACTION_PRODUCT_DELETE:
        if change.entity_type == 'products.ProductVariant':
            _apply_variant_delete(change)
        else:
            _apply_product_delete(change)
        return
    if change.action_type in (ACTION_STOCK_ADJUST, ACTION_STOCK_PURCHASE, ACTION_STOCK_TRANSFER):
        _apply_stock_movement(change)
        return
    if change.entity_type == 'products.ProductVariant':
        _apply_variant(change)
        return
    if change.entity_type == 'products.Product':
        _apply_product(change)
        return
    if change.entity_type == 'products.Category':
        _apply_category(change)
        return
    if change.entity_type == 'settings.StoreSettings':
        _apply_store_settings(change)
        return
    if change.entity_type == 'settings.ModuleSetting':
        _apply_module_settings(change)
        return
    if change.entity_type == 'accounts.Role' and change.action_type == ACTION_ROLE_PERMISSIONS:
        _apply_role_permissions(change)
        return
    if change.entity_type == 'sales.Sale' and change.action_type == ACTION_SALE_COMPLETED_EDIT:
        _apply_sale_completed_edit(change)
        return
    raise ValidationError(f'Unsupported pending change: {change.action_type}')


def _apply_product_delete(change: PendingChange) -> None:
    from products.models import Product

    Product.objects.filter(pk=change.entity_id).delete()


def _apply_variant_delete(change: PendingChange) -> None:
    from products.models import ProductVariant

    ProductVariant.objects.filter(pk=change.entity_id).delete()


def _apply_variant(change: PendingChange) -> None:
    from products.models import ProductVariant

    variant = ProductVariant.objects.get(pk=change.entity_id)
    proposed = dict(change.proposed_values)
    if 'selling_price' in proposed and 'price' not in proposed:
        proposed['price'] = proposed.pop('selling_price')
    for key, value in proposed.items():
        if hasattr(variant, key):
            setattr(variant, key, value)
    variant.save()
    if 'stock_quantity' in proposed:
        product = variant.product
        if product and product.has_variants and product.track_stock:
            from products.stock_utils import sync_product_stock_from_variants

            sync_product_stock_from_variants(product)


def _apply_category(change: PendingChange) -> None:
    from products.models import Category

    if change.action_type == ACTION_CATEGORY_DELETE:
        Category.objects.filter(pk=change.entity_id).delete()
        return
    category = Category.objects.get(pk=change.entity_id)
    for key, value in change.proposed_values.items():
        if hasattr(category, key):
            setattr(category, key, value)
    category.save()


def _apply_product(change: PendingChange) -> None:
    from products.models import Product

    product = Product.objects.get(pk=change.entity_id)
    proposed = dict(change.proposed_values)
    if 'selling_price' in proposed and 'price' not in proposed:
        proposed['price'] = proposed.pop('selling_price')
    for key, value in proposed.items():
        if hasattr(product, key):
            setattr(product, key, value)
    product.save()


def _apply_stock_movement(change: PendingChange) -> None:
    from inventory.services import StockMovementService

    payload = change.apply_payload or {}
    service = StockMovementService()
    user = change.made_by
    product_id = payload.get('product_id')
    variant_id = payload.get('variant_id')
    quantity = payload.get('quantity')
    notes = payload.get('notes', '')
    unit_cost = payload.get('unit_cost')
    branch = payload.get('branch_id')

    from settings.models import Branch

    branch_obj = Branch.objects.filter(pk=branch).first() if branch else None
    if unit_cost is not None and unit_cost != '':
        unit_cost = Decimal(str(unit_cost))

    if change.action_type == ACTION_STOCK_ADJUST:
        service.adjust_stock(
            product_id=product_id,
            variant_id=variant_id,
            quantity=int(quantity),
            notes=notes or f'Approved pending change #{change.id}',
            user=user,
            branch=branch_obj,
            unit_cost=unit_cost,
        )
    elif change.action_type == ACTION_STOCK_PURCHASE:
        service.purchase_stock(
            product_id=product_id,
            variant_id=variant_id,
            quantity=int(quantity),
            unit_cost=unit_cost,
            notes=notes,
            user=user,
            branch=branch_obj,
            reference=payload.get('reference', ''),
        )
    elif change.action_type == ACTION_STOCK_TRANSFER:
        from settings.models import Branch as BranchModel

        to_branch = BranchModel.objects.get(pk=payload['to_branch_id'])
        from_branch = branch_obj
        service.transfer_stock(
            product_id=product_id,
            variant_id=variant_id,
            quantity=int(quantity),
            from_branch=from_branch,
            to_branch=to_branch,
            notes=notes,
            user=user,
        )


def _apply_store_settings(change: PendingChange) -> None:
    from settings.models import StoreSettings

    store = StoreSettings.load()
    for key, value in change.proposed_values.items():
        if hasattr(store, key):
            setattr(store, key, value)
    store.save()


def _apply_module_settings(change: PendingChange) -> None:
    from settings.settings_service import SettingsService

    payload = change.apply_payload or {}
    module = payload.get('module') or change.entity_id
    updates = payload.get('updates') or change.proposed_values
    SettingsService.set_many(module, updates, user=change.checked_by)


def _apply_role_permissions(change: PendingChange) -> None:
    from accounts.models import Permission, Role

    role = Role.objects.get(pk=change.entity_id)
    ids = change.proposed_values.get('permission_ids') or change.apply_payload.get('permission_ids') or []
    perms = Permission.objects.filter(id__in=ids)
    role.permissions.set(perms)


def _apply_sale_completed_edit(change: PendingChange) -> None:
    from approvals.sales_policy import SALE_EDIT_QUEUEABLE_FIELDS
    from sales.models import Sale

    sale = Sale.objects.get(pk=change.entity_id)
    for key, value in change.proposed_values.items():
        if key in SALE_EDIT_QUEUEABLE_FIELDS and hasattr(sale, key):
            setattr(sale, key, value)
    fields = [k for k in change.proposed_values if k in SALE_EDIT_QUEUEABLE_FIELDS]
    if fields:
        sale.save(update_fields=fields)
