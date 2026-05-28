"""Helpers for module feature toggles used by the API layer."""


def is_product_variants_enabled() -> bool:
    """True when Products → Product Variants is enabled in Module Settings."""
    from settings.models import ModuleSettings

    try:
        module = ModuleSettings.objects.get(module_name='products')
    except ModuleSettings.DoesNotExist:
        return False

    if not module.is_enabled:
        return False

    feature = module.features.filter(feature_key='product_variants').first()
    return bool(feature and feature.is_enabled)
