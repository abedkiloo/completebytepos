"""Catalog rules when sales staff add products without pricing."""

from decimal import Decimal

from settings.models import StoreSettings
from settings.store_settings_helpers import user_may_edit_pricing

PRICING_FIELDS = ('price', 'mrp', 'cost')


def sales_catalog_mode_active(user):
    if not user or not user.is_authenticated:
        return False
    if user_may_edit_pricing(user):
        return False
    store = StoreSettings.load()
    return store.allow_sales_add_products and store.sales_catalog_skip_pricing


def apply_sales_catalog_rules(data, *, user, is_create=True):
    """
    Strip pricing from product payloads for sales staff in catalog mode.
    ``data`` may be a dict of model field names (price/mrp/cost).
    """
    if not sales_catalog_mode_active(user):
        return data

    for key in PRICING_FIELDS:
        data.pop(key, None)

    if is_create:
        data['price'] = Decimal('0')
        data['mrp'] = Decimal('0')
        data['cost'] = Decimal('0')

    return data
