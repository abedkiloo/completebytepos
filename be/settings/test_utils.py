"""Test helpers for module feature flags."""

from settings.models import ModuleSettings, ModuleFeature, StoreSettings


def disable_maker_checker() -> None:
    """Turn off maker-checker so stock/catalog API tests apply changes immediately."""
    store = StoreSettings.load()
    if store.maker_checker_enabled:
        store.maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled'])


def enable_maker_checker(*, emergency_stock_mode: bool = False) -> None:
    store = StoreSettings.load()
    store.maker_checker_enabled = True
    store.emergency_stock_mode = emergency_stock_mode
    store.save(update_fields=['maker_checker_enabled', 'emergency_stock_mode'])


def enable_product_variants() -> None:
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='products',
        defaults={'description': 'Product management module', 'is_enabled': True},
    )
    if not module.is_enabled:
        module.is_enabled = True
        module.save(update_fields=['is_enabled'])
    ModuleFeature.objects.update_or_create(
        module=module,
        feature_key='product_variants',
        defaults={
            'feature_name': 'Product Variants (Sizes/Colors)',
            'description': 'Enable product variants',
            'is_enabled': True,
            'display_order': 3,
        },
    )


def disable_product_variants() -> None:
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='products',
        defaults={'description': 'Product management module', 'is_enabled': True},
    )
    ModuleFeature.objects.update_or_create(
        module=module,
        feature_key='product_variants',
        defaults={
            'feature_name': 'Product Variants (Sizes/Colors)',
            'description': 'Enable product variants',
            'is_enabled': False,
            'display_order': 3,
        },
    )
    feature = module.features.filter(feature_key='product_variants').first()
    if feature and feature.is_enabled:
        feature.is_enabled = False
        feature.save(update_fields=['is_enabled'])


def enable_multi_branch_support() -> None:
    """Turn on multi-branch feature for transfer / branch-scoped inventory tests."""
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='settings',
        defaults={'description': 'System settings module', 'is_enabled': True},
    )
    if not module.is_enabled:
        module.is_enabled = True
        module.save(update_fields=['is_enabled'])
    ModuleFeature.objects.update_or_create(
        module=module,
        feature_key='multi_branch_support',
        defaults={
            'feature_name': 'Multi-Branch Support',
            'description': 'Enable multi-branch functionality',
            'is_enabled': True,
            'display_order': 6,
        },
    )


def disable_multi_branch_support() -> None:
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='settings',
        defaults={'description': 'System settings module', 'is_enabled': True},
    )
    ModuleFeature.objects.update_or_create(
        module=module,
        feature_key='multi_branch_support',
        defaults={
            'feature_name': 'Multi-Branch Support',
            'description': 'Enable multi-branch functionality',
            'is_enabled': False,
            'display_order': 6,
        },
    )
