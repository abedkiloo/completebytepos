"""
Read/write per-module typed settings with a short-lived cache.

Public entry points:
    - ``SettingsService.get`` / ``get_module`` / ``set`` / ``set_many`` / ``invalidate``
    - HTTP under ``/api/settings/``

Cache TTL is ``CACHE_TTL_SECONDS`` (30). Missing rows fall back to registry
defaults (or the caller ``default``). Does not toggle ``ModuleSettings``
enable/disable — that is a separate model.
"""

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
    """
    Normalize boolean toggles from JSON or multipart bodies.

    Args:
        value: Raw input. Bools pass through; strings
            ``true``/``1``/``yes``/``on`` (case-insensitive) → True;
            ``false``/``0``/``no``/``off`` → False. Other types unchanged.

    Returns:
        Coerced bool when recognized; otherwise the original ``value``.
    """
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
    """
    Single entry point for module-scoped ``ModuleSetting`` key/value flags.

    Keys are defined in ``MODULE_SETTING_DEFINITIONS``. Writes invalidate
    both per-key and per-module cache entries.
    """

    @classmethod
    def _module_cache_key(cls, module: str) -> str:
        return f'{_MODULE_CACHE_PREFIX}{module}'

    @classmethod
    def _key_cache_key(cls, module: str, key: str) -> str:
        return f'{_KEY_CACHE_PREFIX}{module}:{key}'

    @classmethod
    def invalidate(cls, module: str) -> None:
        """Drop cached values for ``module`` and each registered key under it."""
        cache.delete(cls._module_cache_key(module))
        for definition in MODULE_SETTING_DEFINITIONS.get(module, []):
            cache.delete(cls._key_cache_key(module, definition['key']))

    @classmethod
    def registry_default(cls, module: str, key: str) -> Any:
        """
        Return the registry default for ``(module, key)``, or ``None`` if unknown.
        """
        for definition in MODULE_SETTING_DEFINITIONS.get(module, []):
            if definition['key'] == key:
                return definition['default_value']
        return None

    @classmethod
    def get(cls, module: str, key: str, default: Any = None) -> Any:
        """
        Read one setting value with cache.

        Args:
            module: Module slug (e.g. ``employees``, ``appraisals``).
            key: Setting key within that module.
            default: Fallback when no DB row and no registry default.
                ``None`` means “use registry default if any”.

        Returns:
            Stored ``value``, else row ``default_value``, else resolved default.
            Cached for ``CACHE_TTL_SECONDS`` (30).
        """
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
        """
        Return all known keys for ``module`` (registry + any extra DB rows).

        Returns:
            Shallow dict copy suitable for API responses. Cached 30s.
        """
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
        """
        Upsert one setting and invalidate caches.

        Args:
            module / key: Target setting coordinates.
            value: JSON-serializable value to store (caller validates type).
            user: Optional ``updated_by``.

        Returns:
            Persisted ``ModuleSetting`` row.
        """
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
        cache.delete(cls._key_cache_key(module, key))
        cls.invalidate(module)
        return row

    @classmethod
    def set_many(cls, module: str, values: dict[str, Any], *, user=None) -> None:
        """
        Set multiple keys under ``module``.

        Args:
            module: Module slug.
            values: Map of key → value. Meta keys like ``reason`` should be
                stripped by the caller (see ``SETTING_META_KEYS``).
            user: Optional actor for ``updated_by`` on each row.

        Returns:
            None.
        """
        for key, value in values.items():
            cls.set(module, key, value, user=user)
