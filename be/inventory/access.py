"""Inventory gates: ModuleSetting toggles AND catalog ModuleFeature flags."""

from __future__ import annotations

from settings.module_features import is_module_feature_enabled

from inventory.module_settings import (
    inventory_allow_movement_undo,
    inventory_enable_inventory_report,
    inventory_enable_stock_adjustments,
    inventory_enable_stock_purchases,
    inventory_enable_stock_transfers,
    inventory_show_low_stock_alerts,
    inventory_show_movement_cost,
    inventory_show_out_of_stock_alerts,
    inventory_show_stock_movements,
)


def _catalog_stock_feature(feature_key: str) -> bool:
    return is_module_feature_enabled('inventory', feature_key) or is_module_feature_enabled(
        'stock', feature_key
    )


def stock_movements_allowed() -> bool:
    return inventory_show_stock_movements() and _catalog_stock_feature('stock_adjustments')


def stock_adjustments_allowed() -> bool:
    return inventory_enable_stock_adjustments() and _catalog_stock_feature(
        'stock_adjustments'
    )


def stock_purchases_allowed() -> bool:
    if not inventory_enable_stock_purchases():
        return False
    return _catalog_stock_feature('stock_adjustments') or is_module_feature_enabled(
        'stock', 'manage_stock'
    )


def stock_transfers_allowed() -> bool:
    return inventory_enable_stock_transfers() and _catalog_stock_feature('stock_transfers')


def low_stock_alerts_allowed() -> bool:
    return inventory_show_low_stock_alerts() and _catalog_stock_feature('low_stock_alerts')


def out_of_stock_alerts_allowed() -> bool:
    return inventory_show_out_of_stock_alerts() and _catalog_stock_feature(
        'out_of_stock_alerts'
    )


def inventory_report_allowed() -> bool:
    return inventory_enable_inventory_report() and _catalog_stock_feature(
        'inventory_reports'
    )


def movement_undo_allowed() -> bool:
    return inventory_allow_movement_undo() and _catalog_stock_feature('stock_adjustments')


def movement_cost_visible() -> bool:
    return inventory_show_movement_cost()
