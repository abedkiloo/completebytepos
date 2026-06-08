"""Per-store toggles for the daily notes module."""

from settings.settings_service import SettingsService


def _flag(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get('daily_notes', key, default=default))


def daily_notes_allow_sales_access() -> bool:
    return _flag('allow_sales_access', True)


def daily_notes_allow_manager_view_all() -> bool:
    return _flag('allow_manager_view_all', True)


def daily_notes_allow_sales_view_all() -> bool:
    return _flag('allow_sales_view_all', False)
