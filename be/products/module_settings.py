"""Products module flags via SettingsService (single source of truth)."""

from settings.settings_service import SettingsService

MODULE = 'products'


def _enabled(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get(MODULE, key, default=default))


def products_show_cost_price() -> bool:
    return _enabled('show_cost_price', True)


def products_show_mrp() -> bool:
    return _enabled('show_mrp', True)


def products_show_sku_in_list() -> bool:
    return _enabled('show_sku_in_list', False)


def products_show_low_stock_badges() -> bool:
    return _enabled('show_low_stock_badges', True)


def products_bulk_operations_enabled() -> bool:
    return _enabled('enable_bulk_operations', True)


def products_csv_import_export_enabled() -> bool:
    return _enabled('enable_csv_import_export', True)


def products_allow_sales_catalog_access() -> bool:
    return _enabled('allow_sales_catalog_access', True)


def apply_product_list_representation_flags(data: dict) -> dict:
    """Strip fields hidden by module settings (read serializers)."""
    from products.status_rules import products_show_status_enabled

    if not products_show_status_enabled():
        data.pop('is_active', None)
    if not products_show_cost_price():
        data.pop('cost', None)
    if not products_show_mrp():
        data.pop('mrp', None)
    if not products_show_sku_in_list():
        data.pop('sku', None)
    if not products_show_low_stock_badges():
        data.pop('is_low_stock', None)
    return data
