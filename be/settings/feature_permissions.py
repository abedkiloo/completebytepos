"""DRF permissions for Module Settings feature toggles (catalog features)."""

from __future__ import annotations

from rest_framework import permissions

from settings.module_features import is_module_feature_enabled


class RequireModuleFeature(permissions.BasePermission):
    """Deny the request when a catalog feature flag is off."""

    def __init__(self, module_name: str, feature_key: str):
        self.module_name = module_name
        self.feature_key = feature_key
        self.message = (
            f'The {feature_key} feature is disabled for the {module_name} module.'
        )

    def has_permission(self, request, view):
        return is_module_feature_enabled(self.module_name, self.feature_key)


def feature_disabled_response(module_name: str, feature_key: str) -> dict:
    return {
        'error': (
            f'The {feature_key} feature is disabled for the {module_name} module.'
        ),
    }
