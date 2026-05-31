"""Product active/inactive behaviour when ``products_show_status`` is disabled."""

from django.db.models import Q, QuerySet

from settings.settings_service import SettingsService


def products_show_status_enabled() -> bool:
    """When False, status UI is hidden and inactive products behave as active operationally."""
    from settings.store_settings_helpers import entity_status_visible

    return entity_status_visible(
        bool(SettingsService.get('products', 'show_status', default=True))
    )


def operational_product_filter() -> Q:
    """Q filter for operational lookups (sales, POS, inventory). Empty when status is hidden."""
    if products_show_status_enabled():
        return Q(is_active=True)
    return Q()


def apply_operational_product_filter(queryset: QuerySet) -> QuerySet:
    """Restrict queryset to sellable products when status management is enabled."""
    op_filter = operational_product_filter()
    if op_filter:
        return queryset.filter(op_filter)
    return queryset


def strip_product_status_filter(filters: dict | None) -> dict:
    """Remove ``is_active`` list filter when status is hidden (management UI)."""
    if filters is None:
        return {}
    if products_show_status_enabled():
        return filters
    cleaned = dict(filters)
    cleaned.pop('is_active', None)
    return cleaned


def strip_product_status_from_write_data(data: dict) -> dict:
    """Preserve stored ``is_active`` when status field is hidden from clients."""
    if products_show_status_enabled():
        return data
    data = dict(data)
    data.pop('is_active', None)
    return data


def get_operational_product(product_id):
    """Fetch a product for sales/POS; ignores ``is_active`` when status is hidden."""
    from products.models import Product

    return apply_operational_product_filter(Product.objects.filter(id=product_id)).get()


def get_operational_variant(variant_id, product):
    """Fetch a variant for sales/POS; ignores ``is_active`` when status is hidden."""
    from products.models import ProductVariant

    qs = ProductVariant.objects.filter(id=variant_id, product=product)
    if products_show_status_enabled():
        qs = qs.filter(is_active=True)
    return qs.get()
