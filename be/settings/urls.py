from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ModuleSettingsViewSet, ModuleFeatureViewSet,
    TenantViewSet, BranchViewSet,
    fresh_install,
    setup_status,
    store_settings,
    module_settings_detail,
)

router = DefaultRouter()
router.register(r'modules', ModuleSettingsViewSet, basename='module-settings')
router.register(r'module-features', ModuleFeatureViewSet, basename='module-feature')
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'branches', BranchViewSet, basename='branch')

urlpatterns = [
    path('', include(router.urls)),
    path('setup-status/', setup_status, name='setup-status'),
    path('fresh-install/', fresh_install, name='fresh-install'),
    path('store-settings/', store_settings, name='store-settings'),
    path('<str:module_name>/', module_settings_detail, name='module-settings-detail'),
]
