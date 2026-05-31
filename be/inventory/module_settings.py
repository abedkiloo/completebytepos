"""Inventory / stock module flags via SettingsService."""

from settings.settings_service import SettingsService

MODULE = 'inventory'


def _enabled(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get(MODULE, key, default=default))


def inventory_show_stock_movements() -> bool:
    return _enabled('show_stock_movements', True)


def inventory_enable_stock_adjustments() -> bool:
    return _enabled('enable_stock_adjustments', True)


def inventory_enable_stock_purchases() -> bool:
    return _enabled('enable_stock_purchases', True)


def inventory_enable_stock_transfers() -> bool:
    return _enabled('enable_stock_transfers', True)


def inventory_show_low_stock_alerts() -> bool:
    return _enabled('show_low_stock_alerts', True)


def inventory_show_out_of_stock_alerts() -> bool:
    return _enabled('show_out_of_stock_alerts', True)


def inventory_enable_inventory_report() -> bool:
    return _enabled('enable_inventory_report', True)


def inventory_show_movement_cost() -> bool:
    return _enabled('show_movement_cost', True)


def inventory_allow_movement_undo() -> bool:
    return _enabled('allow_movement_undo', True)


def apply_stock_movement_representation_flags(data: dict) -> dict:
    """Strip cost fields from movement payloads when hidden."""
    if not inventory_show_movement_cost():
        data.pop('unit_cost', None)
        data.pop('total_cost', None)
    return data
