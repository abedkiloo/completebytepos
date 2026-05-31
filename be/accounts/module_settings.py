"""Users & permissions module flags via SettingsService."""

from settings.settings_service import SettingsService

MODULE = 'users'


def _enabled(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get(MODULE, key, default=default))


def users_show_email() -> bool:
    return _enabled('show_user_email', True)


def users_show_phone() -> bool:
    return _enabled('show_user_phone', True)


def users_show_full_name() -> bool:
    return _enabled('show_user_full_name', True)


def users_show_status() -> bool:
    from settings.store_settings_helpers import entity_status_visible

    return entity_status_visible(_enabled('show_user_status', True))


def users_show_date_joined() -> bool:
    return _enabled('show_date_joined', True)


def users_show_staff_flag() -> bool:
    return _enabled('show_staff_flag', True)


def users_enable_create() -> bool:
    return _enabled('enable_user_create', True)


def users_enable_edit() -> bool:
    return _enabled('enable_user_edit', True)


def users_enable_delete() -> bool:
    return _enabled('enable_user_delete', True)


def users_enable_inline_role_assignment() -> bool:
    return _enabled('enable_inline_role_assignment', True)


def users_enable_role_create() -> bool:
    return _enabled('enable_role_create', True)


def users_enable_role_edit() -> bool:
    return _enabled('enable_role_edit', True)


def users_enable_role_delete() -> bool:
    return _enabled('enable_role_delete', True)


def users_enable_permission_catalog() -> bool:
    return _enabled('enable_permission_catalog', True)


def apply_profile_representation_flags(data: dict) -> dict:
    data = dict(data)
    if not users_show_phone():
        data.pop('phone_number', None)
    if not users_show_status():
        data.pop('is_active', None)
    if not users_enable_inline_role_assignment():
        data.pop('custom_role', None)
        data.pop('custom_role_id', None)
    return data


def apply_user_representation_flags(data: dict) -> dict:
    data = dict(data)
    if not users_show_email():
        data.pop('email', None)
    if not users_show_full_name():
        data.pop('first_name', None)
        data.pop('last_name', None)
    if not users_show_status():
        data.pop('is_active', None)
    if not users_show_date_joined():
        data.pop('date_joined', None)
    if not users_show_staff_flag():
        data.pop('is_staff', None)
    if isinstance(data.get('profile'), dict):
        data['profile'] = apply_profile_representation_flags(data['profile'])
    return data


def validate_user_write(attrs: dict) -> dict:
    attrs = dict(attrs)
    if not users_show_email():
        attrs.pop('email', None)
    if not users_show_full_name():
        attrs.pop('first_name', None)
        attrs.pop('last_name', None)
    if not users_show_status():
        attrs.pop('is_active', None)
    if not users_show_staff_flag():
        attrs.pop('is_staff', None)
    if not users_enable_inline_role_assignment():
        attrs.pop('role', None)
        attrs.pop('custom_role_id', None)
    if not users_show_phone():
        attrs.pop('phone_number', None)
    return attrs
