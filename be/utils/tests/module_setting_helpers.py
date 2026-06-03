"""Seed module settings so API/service tests see stable catalog + inventory flags."""

from django.core.cache import cache

from settings.models import ModuleSetting
from settings.settings_service import SettingsService


def _set_module_flag(module: str, key: str, value: bool, label: str | None = None) -> None:
    label = label or key.replace('_', ' ').title()
    ModuleSetting.objects.update_or_create(
        module=module,
        key=key,
        defaults={
            'label': label,
            'description': '',
            'default_value': value,
            'value': value,
        },
    )
    SettingsService.set(module, key, value)


def enable_products_show_status() -> None:
    cache.clear()
    _set_module_flag('products', 'show_status', True, 'Show product status')


def enable_products_list_api_fields() -> None:
    """Expose list/search fields that default hidden in module settings."""
    cache.clear()
    enable_products_show_status()
    for key in (
        'show_sku_in_list',
        'show_cost_price',
        'show_mrp',
        'show_low_stock_badges',
    ):
        _set_module_flag('products', key, True)


def enable_inventory_api_features() -> None:
    cache.clear()
    for key in (
        'enable_inventory_report',
        'show_low_stock_alerts',
        'show_out_of_stock_alerts',
        'enable_stock_purchases',
        'enable_stock_adjustments',
    ):
        _set_module_flag('inventory', key, True)
