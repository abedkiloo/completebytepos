from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ModuleSettingsViewSet, ModuleFeatureViewSet,
    TenantViewSet, BranchViewSet,
    fresh_install
)

router = DefaultRouter()
router.register(r'modules', ModuleSettingsViewSet, basename='module-settings')
router.register(r'module-features', ModuleFeatureViewSet, basename='module-feature')
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'branches', BranchViewSet, basename='branch')

urlpatterns = [
    path('', include(router.urls)),
    path('fresh-install/', fresh_install, name='fresh-install'),
]
