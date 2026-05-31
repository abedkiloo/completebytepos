"""Employees module flags via SettingsService."""

from settings.settings_service import SettingsService

MODULE = 'employees'


def _enabled(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get(MODULE, key, default=default))


def employees_show_employee_id() -> bool:
    return _enabled('show_employee_id', True)


def employees_show_salary() -> bool:
    return _enabled('show_salary', False)


def employees_show_department() -> bool:
    return _enabled('show_department', True)


def employees_show_contact_details() -> bool:
    return _enabled('show_contact_details', True)


def employees_show_notes() -> bool:
    return _enabled('show_employee_notes', True)


def employees_show_status() -> bool:
    from settings.store_settings_helpers import entity_status_visible

    return entity_status_visible(_enabled('show_employee_status', True))


def employees_enable_create() -> bool:
    return _enabled('enable_employee_create', True)


def employees_enable_edit() -> bool:
    return _enabled('enable_employee_edit', True)


def employees_enable_delete() -> bool:
    return _enabled('enable_employee_delete', True)


def employees_enable_statistics() -> bool:
    return _enabled('enable_employee_statistics', True)


def apply_employee_representation_flags(data: dict) -> dict:
    if not employees_show_employee_id():
        data.pop('employee_id', None)
    if not employees_show_salary():
        data.pop('salary', None)
    if not employees_show_department():
        data.pop('department', None)
    if not employees_show_contact_details():
        data.pop('email', None)
        data.pop('phone', None)
        data.pop('address', None)
    if not employees_show_notes():
        data.pop('notes', None)
    if not employees_show_status():
        data.pop('status', None)
        data.pop('is_active', None)
    return data


def validate_employee_write(attrs: dict) -> dict:
    attrs = dict(attrs)
    if not employees_show_salary():
        attrs.pop('salary', None)
    if not employees_show_department():
        attrs.pop('department', None)
    if not employees_show_contact_details():
        attrs.pop('email', None)
        attrs.pop('phone', None)
        attrs.pop('address', None)
    if not employees_show_notes():
        attrs.pop('notes', None)
    if not employees_show_status():
        attrs.pop('status', None)
    if not employees_show_department() and 'department' not in attrs:
        attrs['department'] = 'other'
    if not employees_show_status() and 'status' not in attrs:
        attrs['status'] = 'active'
    return attrs
