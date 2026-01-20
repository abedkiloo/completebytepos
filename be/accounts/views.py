from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.db.models import Q
from .models import UserProfile, Permission, Role
from .serializers import (
    UserSerializer, UserProfileSerializer, LoginSerializer,
    PermissionSerializer, RoleSerializer,
    RoleListSerializer, UserCreateSerializer
)
from .permissions import IsSuperAdmin, IsAdmin, HasPermission
# Module settings moved to settings app
from settings.models import ModuleSettings, ModuleFeature


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """View permissions - only admins can view"""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['module', 'action']
    
    def get_queryset(self):
        # Only admins can view permissions
        try:
            if not hasattr(self, 'request') or not hasattr(self.request, 'user'):
                return Permission.objects.none()
            user = self.request.user
            if user and user.is_authenticated and (user.is_staff or (hasattr(user, 'profile') and user.profile and user.profile.is_admin)):
                return Permission.objects.all()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in PermissionViewSet.get_queryset: {e}")
        return Permission.objects.none()
    
    def list(self, request, *args, **kwargs):
        """List all permissions with pagination"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in PermissionViewSet.list: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {'error': 'Failed to load permissions', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def by_module(self, request):
        """Get permissions grouped by module"""
        try:
            user = request.user
            if not (user and (user.is_staff or (hasattr(user, 'profile') and user.profile and user.profile.is_admin))):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        modules = {}
        for permission in Permission.objects.all():
            module = permission.get_module_display()
            if module not in modules:
                modules[module] = []
            modules[module].append(PermissionSerializer(permission).data)
        
        return Response(modules)


class RoleViewSet(viewsets.ModelViewSet):
    """Manage roles - only super admins can create/edit/delete"""
    queryset = Role.objects.all().prefetch_related('permissions')
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['name']
    
    def get_queryset(self):
        # All authenticated users can view roles
        try:
            if not hasattr(self, 'request') or not hasattr(self.request, 'user'):
                return Role.objects.none()
            return Role.objects.all().prefetch_related('permissions')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in RoleViewSet.get_queryset: {e}")
            return Role.objects.none()
    
    def get_serializer_class(self):
        action = getattr(self, 'action', None)
        if action == 'list':
            return RoleListSerializer
        return RoleSerializer
    
    def get_permissions(self):
        """Only super admins can modify roles"""
        action = getattr(self, 'action', None)
        if action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]
    
    def list(self, request, *args, **kwargs):
        """List all roles with pagination"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in RoleViewSet.list: {e}")
            return Response(
                {'error': 'Failed to load roles', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def assign_permissions(self, request, pk=None):
        """Assign permissions to a role"""
        role = self.get_object()
        permission_ids = request.data.get('permission_ids', [])
        
        permissions = Permission.objects.filter(id__in=permission_ids)
        role.permissions.set(permissions)
        
        return Response({
            'message': f'Permissions assigned to {role.name}',
            'role': RoleSerializer(role).data
        })
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users with this role"""
        role = self.get_object()
        users = User.objects.filter(profile__custom_role=role)
        return Response({
            'role': role.name,
            'users': UserSerializer(users, many=True).data
        })


class UserViewSet(viewsets.ModelViewSet):
    """Manage users with role-based permissions"""
    queryset = User.objects.all().select_related('profile', 'profile__custom_role').prefetch_related('profile__custom_role__permissions')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['username']
    
    def get_serializer_class(self):
        action = getattr(self, 'action', None)
        if action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.all()
        
        # Ensure requesting user has a profile
        try:
            if not hasattr(user, 'profile') or user.profile is None:
                UserProfile.objects.get_or_create(user=user, defaults={'role': 'cashier'})
        except Exception:
            pass  # Continue even if profile creation fails
        
        # Super admins can see all users
        if user.is_superuser or (hasattr(user, 'profile') and user.profile and user.profile.is_super_admin):
            return queryset.select_related('profile', 'profile__custom_role').prefetch_related('profile__custom_role__permissions')
        
        # Admins can see all users
        if user.is_staff or (hasattr(user, 'profile') and user.profile and user.profile.is_admin):
            return queryset.select_related('profile', 'profile__custom_role').prefetch_related('profile__custom_role__permissions')
        
        # Regular users can only see themselves
        return queryset.filter(id=user.id).select_related('profile', 'profile__custom_role').prefetch_related('profile__custom_role__permissions')
    
    def list(self, request, *args, **kwargs):
        """List all users with pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def get_permissions(self):
        """Check permissions based on action"""
        action = getattr(self, 'action', None)
        if action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        # For create, update, delete - need admin or super admin
        return [IsAdmin()]
    
    def create(self, request, *args, **kwargs):
        """Create new user - only admins"""
        serializer = UserCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Update user - admins can update any, users can update themselves"""
        user = self.get_object()
        current_user = request.user
        
        # Users can update their own profile (except role)
        if user.id == current_user.id:
            # Don't allow changing role or staff status
            data = request.data.copy()
            data.pop('is_staff', None)
            data.pop('is_superuser', None)
            if 'profile' in data:
                profile_data = data['profile']
                profile_data.pop('role', None)
                profile_data.pop('custom_role_id', None)
            
            serializer = self.get_serializer(user, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        
        # Admins can update other users
        if current_user.is_staff or (hasattr(current_user, 'profile') and current_user.profile and current_user.profile.is_admin):
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete user - only super admins"""
        user = request.user
        if not (user.is_superuser or (hasattr(user, 'profile') and user.profile and user.profile.is_super_admin)):
            return Response(
                {'error': 'Only super admins can delete users'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        """Assign a role to a user"""
        user = self.get_object()
        role_id = request.data.get('role_id')
        
        if not role_id:
            return Response(
                {'error': 'role_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return Response(
                {'error': 'Role not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user, role='cashier')
        
        user.profile.custom_role = role
        user.profile.save()
        
        return Response({
            'message': f'Role {role.name} assigned to {user.username}',
            'user': UserSerializer(user).data
        })
    
    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """Change user password"""
        user = self.get_object()
        current_user = request.user
        new_password = request.data.get('new_password')
        
        if not new_password:
            return Response(
                {'error': 'new_password is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Users can change their own password, admins can change any
        if user.id != current_user.id:
            if not (current_user.is_staff or (hasattr(current_user, 'profile') and current_user.profile and current_user.profile.is_admin)):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        user.set_password(new_password)
        user.save()
        
        return Response({'message': 'Password changed successfully'})
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search users"""
        query = request.query_params.get('q', '')
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )[:20]
        return Response(UserSerializer(users, many=True).data)


class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """User login - returns JWT tokens"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Use print to ensure it shows up immediately
        import sys
        print("=" * 80, file=sys.stdout)
        print("[LOGIN VIEW] LOGIN REQUEST RECEIVED", file=sys.stdout)
        print(f"Method: {request.method}", file=sys.stdout)
        print(f"Path: {request.path}", file=sys.stdout)
        print(f"Origin: {request.META.get('HTTP_ORIGIN', 'No Origin')}", file=sys.stdout)
        print(f"Content-Type: {request.META.get('CONTENT_TYPE', 'No Content-Type')}", file=sys.stdout)
        print(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'N/A')[:100]}", file=sys.stdout)
        print(f"Request Data: {request.data if hasattr(request, 'data') else 'No data'}", file=sys.stdout)
        print("=" * 80, file=sys.stdout)
        sys.stdout.flush()
        
        # Also use logger
        logger.info("=" * 80)
        logger.info("LOGIN REQUEST RECEIVED")
        logger.info(f"Method: {request.method}")
        logger.info(f"Path: {request.path}")
        logger.info(f"Origin: {request.META.get('HTTP_ORIGIN', 'No Origin')}")
        logger.info(f"Content-Type: {request.META.get('CONTENT_TYPE', 'No Content-Type')}")
        logger.info(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'N/A')[:100]}")
        logger.info(f"Request Data: {request.data if hasattr(request, 'data') else 'No data'}")
        logger.info("=" * 80)
        
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        from django.contrib.auth import authenticate
        user = authenticate(username=username, password=password)
        
        if user is not None:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            user_serializer = UserSerializer(user)
            
            # Get user profile and permissions
            profile = None
            permissions = []
            try:
                if hasattr(user, 'profile') and user.profile:
                    profile = UserProfileSerializer(user.profile).data
                    permissions = PermissionSerializer(user.profile.get_all_permissions(), many=True).data
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error getting profile/permissions for user {user.id}: {e}")
            
            # Get enabled modules
            enabled_modules = {}
            for module in ModuleSettings.objects.all():
                enabled_modules[module.module_name] = module.is_enabled
            
            response_data = {
                'message': 'Login successful',
                'user': user_serializer.data,
                'profile': profile,
                'permissions': permissions,
                'enabled_modules': enabled_modules,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
            logger.info(f"Login successful for user: {username}")
            logger.info("=" * 80)
            return Response(response_data)
        else:
            logger.warning(f"Login failed - Invalid credentials for user: {username}")
            logger.info("=" * 80)
            response = Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            # Ensure CORS headers are added to error response
            # The CORS middleware should handle this, but we ensure it here
            origin = request.META.get('HTTP_ORIGIN')
            if origin:
                from django.conf import settings
                if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False):
                    response['Access-Control-Allow-Origin'] = origin
                elif origin in getattr(settings, 'CORS_ALLOWED_ORIGINS', []):
                    response['Access-Control-Allow-Origin'] = origin
                if getattr(settings, 'CORS_ALLOW_CREDENTIALS', False):
                    response['Access-Control-Allow-Credentials'] = 'true'
            return response

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """User logout - blacklist refresh token"""
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception:
                    # Token might already be blacklisted or invalid, that's okay
                    pass
            return Response({'message': 'Logout successful'})
        except Exception as e:
            return Response(
                {'error': 'Logout failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current user information"""
        user_serializer = UserSerializer(request.user)
        
        profile = None
        permissions = []
        try:
            if hasattr(request.user, 'profile') and request.user.profile:
                profile = UserProfileSerializer(request.user.profile).data
                permissions = PermissionSerializer(request.user.profile.get_all_permissions(), many=True).data
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting profile/permissions for user {request.user.id}: {e}")
        
        # Get enabled modules
        enabled_modules = {}
        for module in ModuleSettings.objects.all():
            enabled_modules[module.module_name] = module.is_enabled
        
        return Response({
            'user': user_serializer.data,
            'profile': profile,
            'permissions': permissions,
            'enabled_modules': enabled_modules,
            'is_super_admin': request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile and request.user.profile.is_super_admin),
            'is_admin': request.user.is_staff or (hasattr(request.user, 'profile') and request.user.profile and request.user.profile.is_admin),
        })


# Module settings ViewSets moved to settings app
# See settings/views.py for ModuleSettingsViewSet and ModuleFeatureViewSet
