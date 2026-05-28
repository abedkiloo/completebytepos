"""
Detect whether the application has completed first-time setup.
Used by the install wizard and login redirect flow.
"""

from __future__ import annotations

from django.contrib.auth.models import User

from settings.models import ModuleSettings, Tenant


def get_setup_status() -> dict:
    user_count = User.objects.count()
    module_count = ModuleSettings.objects.count()
    tenant_count = Tenant.objects.count()

    # Fresh DB: no users or modules were never seeded.
    needs_install = user_count == 0 or module_count == 0

    return {
        'installed': not needs_install,
        'needs_install': needs_install,
        'user_count': user_count,
        'module_count': module_count,
        'tenant_count': tenant_count,
    }
