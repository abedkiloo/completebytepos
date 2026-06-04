"""Helpers for module feature toggles used by the API layer."""

from settings.module_features import is_module_feature_enabled


def is_product_variants_enabled() -> bool:
    """True when Products → Variants (size/color) is enabled in Module Settings."""
    return is_module_feature_enabled('products', 'product_variants')
