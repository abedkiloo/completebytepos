"""Who may edit catalog vs transactional product fields (module settings + role)."""

from __future__ import annotations

from accounts.sensitive_edits import INVENTORY_REPORT_FIELDS
from settings.settings_service import SettingsService


def _products_flag(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get('products', key, default=default))


def products_sales_catalog_access_enabled() -> bool:
    """Sales may open Products/Categories when module + store catalog flags are on."""
    from settings.models import StoreSettings

    if not _products_flag('allow_sales_catalog_access', True):
        return False
    store = StoreSettings.load()
    return bool(store.allow_sales_add_products)


def products_sales_may_edit_catalog_details() -> bool:
    return _products_flag('allow_sales_edit_catalog_details', True)


def products_sales_may_edit_pricing() -> bool:
    return _products_flag('allow_sales_edit_pricing', False)


def products_sales_may_edit_cost() -> bool:
    return _products_flag('allow_sales_edit_cost', False)


def products_sales_may_edit_stock() -> bool:
    return _products_flag('allow_sales_edit_stock', False)


def products_manager_may_edit_pricing() -> bool:
    return _products_flag('allow_manager_edit_pricing', True)


def products_manager_may_edit_cost() -> bool:
    return _products_flag('allow_manager_edit_cost', False)


def user_is_super_admin(user) -> bool:
    """
    True when this person is a Super Admin.

    Args:
        user: Signed-in user. None and anonymous are False.

    Returns:
        bool. A Django superuser, the super_admin role, or the Super Admin
        custom role. A manager and a sales person are False.

    Raises:
        None.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return resolve_user_role(user) == 'super_admin'


def resolve_user_role(user) -> str:
    if not user or not getattr(user, 'is_authenticated', False):
        return 'anonymous'
    if user.is_superuser:
        return 'super_admin'
    profile = getattr(user, 'profile', None)
    if profile is None:
        return 'anonymous'
    if profile.role == 'super_admin':
        return 'super_admin'
    custom = getattr(profile, 'custom_role', None)
    if custom and custom.name == 'Super Admin':
        return 'super_admin'
    if profile.role == 'manager' or (custom and custom.name == 'Manager'):
        return 'manager'
    return 'sales'


def user_may_edit_catalog_details(user) -> bool:
    role = resolve_user_role(user)
    if role == 'super_admin':
        return True
    if role == 'manager':
        return True
    if role == 'sales':
        return (
            products_sales_catalog_access_enabled()
            and products_sales_may_edit_catalog_details()
        )
    return False


def user_may_edit_product_pricing(user) -> bool:
    role = resolve_user_role(user)
    if role == 'super_admin':
        return True
    if role == 'manager':
        return products_manager_may_edit_pricing()
    if role == 'sales':
        return (
            products_sales_catalog_access_enabled()
            and products_sales_may_edit_pricing()
        )
    return False


def user_may_edit_product_cost(user) -> bool:
    """
    True only for a Super Admin.

    Args:
        user: Signed-in user. A manager stays False even when the old
            manager-cost setting is on.

    Returns:
        bool.

    Raises:
        None.
    """
    return user_is_super_admin(user)


def user_may_edit_product_stock(user) -> bool:
    role = resolve_user_role(user)
    if role == 'super_admin':
        return True
    if role == 'manager':
        return True
    if role == 'sales':
        return (
            products_sales_catalog_access_enabled()
            and products_sales_may_edit_stock()
        )
    return False


def user_may_edit_any_product_financial_field(user) -> bool:
    return (
        user_may_edit_product_pricing(user)
        or user_may_edit_product_cost(user)
        or user_may_edit_product_stock(user)
    )


def drop_on_hand_from_catalog_edit(*maps) -> None:
    """
    Remove the on-hand count from a product or size edit.

    Args:
        maps: Write payloads. Each is a dict of at most a few dozen fields.
            Only ``stock_quantity`` is removed. Description, price, and the
            other fields stay.

    Returns:
        None. The pieces on the shelf are unchanged. A stock purchase or a
        stock count still changes that number.

    Raises:
        None.
    """
    for item in maps:
        if isinstance(item, dict):
            item.pop('stock_quantity', None)


def strip_product_fields_by_access(
    data: dict,
    *,
    user,
    instance=None,
    is_create: bool = True,
) -> dict:
    """Remove fields the user is not allowed to write."""
    from decimal import Decimal

    # Cost is not pricing — managers may edit cost without price access (and vice versa).
    pricing_only_fields = ('price', 'mrp', 'selling_price')
    if not user_may_edit_product_pricing(user):
        for key in pricing_only_fields:
            data.pop(key, None)
        if is_create:
            data['price'] = Decimal('0')
            data['mrp'] = Decimal('0')

    if not user_may_edit_product_cost(user):
        data.pop('cost', None)
        if is_create:
            data['cost'] = Decimal('0')

    if not user_may_edit_product_stock(user):
        if is_create:
            data.setdefault('stock_quantity', 0)
        for key in INVENTORY_REPORT_FIELDS:
            if is_create and key == 'stock_quantity':
                continue
            data.pop(key, None)

    return data
