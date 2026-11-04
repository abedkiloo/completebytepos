"""Per-store toggles and catalog feature helpers for the daily notes module."""

from settings.module_features import is_module_feature_enabled
from settings.settings_service import SettingsService


def _flag(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get('daily_notes', key, default=default))


def daily_notes_allow_sales_access() -> bool:
    return _flag('allow_sales_access', True)


def daily_notes_allow_manager_view_all() -> bool:
    return _flag('allow_manager_view_all', True)


def daily_notes_allow_sales_view_all() -> bool:
    return _flag('allow_sales_view_all', False)


def daily_notes_priority_enabled() -> bool:
    """Catalog feature: Highest / Medium / Less on notes and tasks."""
    return is_module_feature_enabled('daily_notes', 'note_priority')


def daily_notes_tasks_enabled() -> bool:
    return is_module_feature_enabled('daily_notes', 'daily_tasks')


def daily_notes_checklists_enabled() -> bool:
    return is_module_feature_enabled('daily_notes', 'checklists')


def daily_notes_sticky_enabled() -> bool:
    return is_module_feature_enabled('daily_notes', 'sticky_notes')
