"""
Permission decorators and mixins for role-based access control
"""
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status


class HasPermission(permissions.BasePermission):
    """Check if user has specific permission"""
    
    def __init__(self, module, action):
        self.module = module
        self.action = action
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if hasattr(request.user, 'profile'):
            return request.user.profile.has_permission(self.module, self.action)
        
        return False


class HasModuleAccess(permissions.BasePermission):
    """Check if user has access to a module"""
    
    def __init__(self, module):
        self.module = module
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if hasattr(request.user, 'profile'):
            return request.user.profile.has_module_access(self.module)
        
        return False


class IsSuperAdmin(permissions.BasePermission):
    """Check if user is super admin"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if hasattr(request.user, 'profile'):
            return request.user.profile.is_super_admin
        
        return False


class IsAdmin(permissions.BasePermission):
    """Check if user is admin or super admin"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        if hasattr(request.user, 'profile'):
            return request.user.profile.is_admin
        
        return False


def check_permission(module, action):
    """Decorator to check permission on a view method"""
    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if hasattr(request.user, 'profile'):
                if not request.user.profile.has_permission(module, action):
                    return Response(
                        {'error': f'Permission denied: {module}.{action}'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                return Response(
                    {'error': 'User profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def check_module_access(module):
    """Decorator to check module access on a view method"""
    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if hasattr(request.user, 'profile'):
                if not request.user.profile.has_module_access(module):
                    return Response(
                        {'error': f'Access denied to module: {module}'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                return Response(
                    {'error': 'User profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator

