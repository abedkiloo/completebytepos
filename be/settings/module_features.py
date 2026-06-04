"""
Canonical module feature resolution (DB + registry defaults).

Use ``is_module_feature_enabled`` everywhere — API, serializers, sales, and
feature_flags — so toggles in Module Settings match runtime behaviour.
"""

from __future__ import annotations

from typing import Dict

from settings.module_registry import MODULE_DEFINITIONS

# {(module_name, feature_key): enabled_by_default} from module_registry.py
FEATURE_DEFAULTS: Dict[str, Dict[str, bool]] = {}


def _build_feature_defaults() -> Dict[str, Dict[str, bool]]:
    out: Dict[str, Dict[str, bool]] = {}
    for module_def in MODULE_DEFINITIONS:
        name = module_def['module_name']
        out[name] = {}
        for feat in module_def.get('features', []):
            out[name][feat['key']] = feat.get('enabled_by_default', True)
    return out


FEATURE_DEFAULTS.update(_build_feature_defaults())


def registry_default(module_name: str, feature_key: str) -> bool:
    """Default when the feature row is missing (fresh install / partial seed)."""
    return FEATURE_DEFAULTS.get(module_name, {}).get(feature_key, True)


def is_module_feature_enabled(module_name: str, feature_key: str) -> bool:
    from settings.models import ModuleSettings

    try:
        module = ModuleSettings.objects.get(module_name=module_name)
    except ModuleSettings.DoesNotExist:
        return registry_default(module_name, feature_key)

    if not module.is_enabled:
        return False

    feature = module.features.filter(feature_key=feature_key).first()
    if feature is None:
        return registry_default(module_name, feature_key)
    return bool(feature.is_enabled)
