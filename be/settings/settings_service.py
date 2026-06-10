"""Read/write per-module settings with a short-lived cache."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

from .models import ModuleSetting
from .module_settings_registry import MODULE_SETTING_DEFINITIONS

CACHE_TTL_SECONDS = 30
_MODULE_CACHE_PREFIX = 'module_settings:module:'
_KEY_CACHE_PREFIX = 'module_settings:key:'

SETTING_META_KEYS = frozenset({'reason', 'change_reason'})


def coerce_module_setting_value(value: Any) -> Any:
    """Normalize boolean toggles from JSON or multipart bodies."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ('true', '1', 'yes', 'on'):
            return True
        if lowered in ('false', '0', 'no', 'off'):
            return False
    return value


class SettingsService:
    """Single entry point for module-scoped feature flags."""

    @classmethod
    def _module_cache_key(cls, module: str) -> str:
        return f'{_MODULE_CACHE_PREFIX}{module}'

    @classmethod
    def _key_cache_key(cls, module: str, key: str) -> str:
        return f'{_KEY_CACHE_PREFIX}{module}:{key}'

    @classmethod
    def invalidate(cls, module: str) -> None:
        cache.delete(cls._module_cache_key(module))
        for definition in MODULE_SETTING_DEFINITIONS.get(module, []):
            cache.delete(cls._key_cache_key(module, definition['key']))

    @classmethod
    def registry_default(cls, module: str, key: str) -> Any:
        for definition in MODULE_SETTING_DEFINITIONS.get(module, []):
            if definition['key'] == key:
                return definition['default_value']
        return None

    @classmethod
    def get(cls, module: str, key: str, default: Any = None) -> Any:
        cached = cache.get(cls._key_cache_key(module, key))
        if cached is not None:
            return cached

        resolved_default = (
            default if default is not None else cls.registry_default(module, key)
        )
        try:
            row = ModuleSetting.objects.get(module=module, key=key)
            value = row.value if row.value is not None else row.default_value
        except ModuleSetting.DoesNotExist:
            value = resolved_default

        cache.set(cls._key_cache_key(module, key), value, CACHE_TTL_SECONDS)
        return value

    @classmethod
    def get_module(cls, module: str) -> dict[str, Any]:
        cached = cache.get(cls._module_cache_key(module))
        if cached is not None:
            return dict(cached)

        result: dict[str, Any] = {}
        rows = {r.key: r for r in ModuleSetting.objects.filter(module=module)}
        for definition in MODULE_SETTING_DEFINITIONS.get(module, []):
            key = definition['key']
            if key in rows:
                row = rows[key]
                result[key] = row.value if row.value is not None else row.default_value
            else:
                result[key] = definition['default_value']

        for key, row in rows.items():
            if key not in result:
                result[key] = row.value if row.value is not None else row.default_value

        cache.set(cls._module_cache_key(module), result, CACHE_TTL_SECONDS)
        return result

    @classmethod
    def set(cls, module: str, key: str, value: Any, *, user=None) -> ModuleSetting:
        definition = next(
            (d for d in MODULE_SETTING_DEFINITIONS.get(module, []) if d['key'] == key),
            None,
        )
        defaults = {
            'label': definition['label'] if definition else key.replace('_', ' ').title(),
            'description': definition.get('description', '') if definition else '',
            'default_value': definition['default_value'] if definition else value,
            'value': value,
            'display_order': definition.get('display_order', 0) if definition else 0,
        }
        row, _created = ModuleSetting.objects.get_or_create(
            module=module,
            key=key,
            defaults=defaults,
        )
        row.value = value
        if user is not None:
            row.updated_by = user
        row.save()
        cls.invalidate(module)
        return row

    @classmethod
    def set_many(cls, module: str, values: dict[str, Any], *, user=None) -> None:
        for key, value in values.items():
            cls.set(module, key, value, user=user)
