"""
Build API catalog and apply install presets from module_registry + DB state.
"""

from __future__ import annotations

from django.contrib.auth.models import User

from .models import ModuleFeature, ModuleSettings
from .module_registry import (
    DOMAINS,
    MODULE_BY_NAME,
    MODULE_DEFINITIONS,
    ROLLUP_UNDER,
    get_preset_manifest,
    resolve_preset,
)
from .utils import is_branch_support_enabled


def _feature_payload(feature: ModuleFeature) -> dict:
    return {
        'id': feature.id,
        'feature_key': feature.feature_key,
        'feature_name': feature.feature_name,
        'is_enabled': feature.is_enabled,
        'description': feature.description,
        'display_order': feature.display_order,
    }


def _module_flat_dict(module: ModuleSettings) -> dict:
    features = {}
    for feature in module.features.all().order_by('display_order', 'feature_name'):
        features[feature.feature_key] = _feature_payload(feature)

    meta = MODULE_BY_NAME.get(module.module_name, {})
    return {
        'id': module.id,
        'module_name': module.module_name,
        'is_enabled': module.is_enabled,
        'description': module.description or meta.get('description', ''),
        'module_name_display': meta.get('display_name') or module.get_module_name_display(),
        'domain': meta.get('domain', 'legacy'),
        'sort_order': meta.get('sort_order', 999),
        'rollup_under': meta.get('rollup_under') or ROLLUP_UNDER.get(module.module_name),
        'features': features,
    }


def build_modules_response() -> dict:
    """Flat dict keyed by module_name (legacy) plus structured catalog."""
    modules_qs = ModuleSettings.objects.prefetch_related('features').all()
    by_name = {m.module_name: _module_flat_dict(m) for m in modules_qs}

    catalog = []
    for domain in sorted(DOMAINS, key=lambda d: d['sort_order']):
        primary_defs = [
            m
            for m in MODULE_DEFINITIONS
            if m.get('domain') == domain['id'] and not m.get('rollup_under')
        ]
        primary_defs.sort(key=lambda m: m.get('sort_order', 99))

        modules_out = []
        for defn in primary_defs:
            name = defn['module_name']
            if name not in by_name:
                continue
            mod = dict(by_name[name])
            children = [
                by_name[child]
                for child, parent in ROLLUP_UNDER.items()
                if parent == name and child in by_name
            ]
            if children:
                mod['rollup_children'] = sorted(
                    children, key=lambda c: c.get('sort_order', 999)
                )
            modules_out.append(mod)

        if modules_out:
            catalog.append(
                {
                    'id': domain['id'],
                    'label': domain['label'],
                    'description': domain['description'],
                    'sort_order': domain['sort_order'],
                    'modules': modules_out,
                }
            )

    registered = set(MODULE_BY_NAME.keys())
    orphans = [
        by_name[n]
        for n in sorted(by_name.keys())
        if n not in registered
    ]
    if orphans:
        catalog.append(
            {
                'id': 'legacy',
                'label': 'Legacy / unmapped',
                'description': 'Rows from older installs — disable or migrate to grouped modules.',
                'sort_order': 999,
                'modules': orphans,
            }
        )

    flat = dict(by_name)
    flat['_meta'] = {
        'branch_support_enabled': is_branch_support_enabled(),
        'catalog_version': 2,
        'presets': get_preset_manifest(),
        'domains': [
            {
                'id': d['id'],
                'label': d['label'],
                'description': d['description'],
            }
            for d in sorted(DOMAINS, key=lambda x: x['sort_order'])
        ],
    }
    flat['catalog'] = catalog
    return flat


def get_enabled_modules_flat() -> dict:
    """Module map for login/me (no catalog/_meta) — full objects with features."""
    data = build_modules_response()
    return {
        k: v
        for k, v in data.items()
        if k not in ('catalog',) and not str(k).startswith('_')
    }


def apply_module_preset(preset_id: str, user: User | None = None) -> dict:
    """Apply a named preset to all modules/features in the database."""
    resolved = resolve_preset(preset_id)
    target_modules = resolved['modules']
    target_features = resolved['features']
    disable_unlisted = resolved['disable_unlisted']

    all_modules = {
        m.module_name: m for m in ModuleSettings.objects.prefetch_related('features').all()
    }

    for name, module in all_modules.items():
        defn = MODULE_BY_NAME.get(name, {})
        if disable_unlisted:
            enabled = target_modules.get(name, False)
        elif name in target_modules:
            enabled = target_modules[name]
        elif defn.get('rollup_under'):
            enabled = target_modules.get(name, False)
        else:
            enabled = module.is_enabled

        if module.is_enabled != enabled:
            module.is_enabled = enabled
            module.updated_by = user
            module.save(update_fields=['is_enabled', 'updated_at', 'updated_by'])

        feat_keys = target_features.get(name)
        if feat_keys is not None:
            key_set = set(feat_keys)
            for feature in module.features.all():
                should_enable = feature.feature_key in key_set and module.is_enabled
                if feature.is_enabled != should_enable:
                    feature.is_enabled = should_enable
                    feature.updated_by = user
                    feature.save(update_fields=['is_enabled', 'updated_at', 'updated_by'])
        elif disable_unlisted and not module.is_enabled:
            module.features.update(is_enabled=False)

    return build_modules_response()
