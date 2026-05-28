from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, AuthViewSet,
    PermissionViewSet, RoleViewSet, AuditLogViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'auth', AuthViewSet, basename='auth')
# Module settings moved to settings app - see settings/urls.py
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
]
