from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.db.models import Q
from .models import UserProfile, Permission, Role, AuditLog
from .serializers import (
    UserSerializer, UserProfileSerializer, LoginSerializer,
    PermissionSerializer, RoleSerializer,
    RoleListSerializer, UserCreateSerializer, AuditLogSerializer
)
from .permissions import IsSuperAdmin, IsAdmin, HasPermission, CanViewAuditLog
from accounts.module_settings import (
    users_enable_create,
    users_enable_edit,
    users_enable_delete,
    users_enable_inline_role_assignment,
    users_enable_role_create,
    users_enable_role_edit,
    users_enable_role_delete,
    users_enable_permission_catalog,
    users_show_phone,
)
from accounts.user_write import prepare_user_write_data, apply_profile_updates
# Module settings moved to settings app
from settings.models import ModuleSettings, ModuleFeature
from settings.module_catalog import get_enabled_modules_flat
from utils.audit_helpers import audited_perform_create, audited_perform_destroy, audited_perform_update, log_domain_event
from utils.audit_mixin import AuditedModelViewSetMixin


def _user_can_manage_permissions(user) -> bool:
    """Super admins, legacy admins, and staff can view the permission catalog."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    if profile and (profile.is_super_admin or profile.is_admin):
        return True
    return False


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """View permissions - only admins can view"""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['module', 'action']

    @staticmethod
    def _feature_disabled_response(feature_label: str):
        return Response(
            {'error': f'{feature_label} is disabled in store settings.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    def get_queryset(self):
        try:
            if not hasattr(self, 'request') or not hasattr(self.request, 'user'):
                return Permission.objects.none()
            if _user_can_manage_permissions(self.request.user):
                return Permission.objects.all()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in PermissionViewSet.get_queryset: {e}")
        return Permission.objects.none()
    
    def list(self, request, *args, **kwargs):
        """List all permissions with pagination"""
        if not users_enable_permission_catalog():
            return self._feature_disabled_response('Permission catalog')
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
        if not users_enable_permission_catalog():
            return self._feature_disabled_response('Permission catalog')
        try:
            user = request.user
            if not _user_can_manage_permissions(user):
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

    @action(detail=False, methods=['get'])
    def by_domain(self, request):
        """Permissions grouped by catalog domain, then catalog module."""
        if not users_enable_permission_catalog():
            return self._feature_disabled_response('Permission catalog')
        try:
            user = request.user
            if not _user_can_manage_permissions(user):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        from settings.module_registry import DOMAINS, get_permission_domain_info

        domain_order = {d['id']: d['sort_order'] for d in DOMAINS}
        tree: dict[str, dict] = {}

        for permission in Permission.objects.all().order_by('module', 'action'):
            info = get_permission_domain_info(permission.module)
            domain_id = info['domain']
            if domain_id not in tree:
                tree[domain_id] = {
                    'id': domain_id,
                    'label': info['domain_label'],
                    'sort_order': domain_order.get(domain_id, 999),
                    'modules': {},
                }
            mod_key = info['catalog_module']
            mod_label = info['catalog_module_label']
            if mod_key not in tree[domain_id]['modules']:
                tree[domain_id]['modules'][mod_key] = {
                    'id': mod_key,
                    'label': mod_label,
                    'permissions': [],
                }
            tree[domain_id]['modules'][mod_key]['permissions'].append(
                PermissionSerializer(permission).data
            )

        catalog = []
        for domain_id in sorted(tree.keys(), key=lambda k: tree[k]['sort_order']):
            entry = tree[domain_id]
            modules_list = [
                entry['modules'][k]
                for k in sorted(entry['modules'].keys(), key=lambda m: entry['modules'][m]['label'])
            ]
            catalog.append(
                {
                    'id': entry['id'],
                    'label': entry['label'],
                    'sort_order': entry['sort_order'],
                    'modules': modules_list,
                }
            )

        return Response({'catalog': catalog})


class RoleViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """Manage roles - only super admins can create/edit/delete"""
    queryset = Role.objects.all().prefetch_related('permissions')
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    audit_module = 'roles'
    ordering = ['name']

    @staticmethod
    def _feature_disabled_response(feature_label: str):
        return Response(
            {'error': f'{feature_label} is disabled in store settings.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    
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
        audited_perform_create(self, serializer, created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        if not users_enable_role_create():
            return self._feature_disabled_response('Creating roles')
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not users_enable_role_edit():
            return self._feature_disabled_response('Editing roles')

        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        from approvals.permissions import is_maker_checker_enabled
        from approvals.serializers import PendingChangeSerializer
        from approvals.settings_integration import queue_role_permission_assign

        validated = dict(serializer.validated_data)
        pending = None
        if is_maker_checker_enabled() and 'permissions' in validated:
            reason = (
                request.data.get('change_reason')
                or request.data.get('reason')
                or ''
            )
            if not str(reason).strip():
                return Response(
                    {'reason': 'A reason is required to change role permissions.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            perm_ids = [p.pk for p in validated['permissions']]
            pending = queue_role_permission_assign(
                request,
                instance,
                perm_ids,
                reason=str(reason).strip(),
            )
            validated.pop('permissions', None)
            serializer.validated_data.pop('permissions', None)

        if validated:
            self.perform_update(serializer)
        elif pending is None:
            return Response(serializer.data)

        instance.refresh_from_db()
        data = self.get_serializer(instance).data
        if pending:
            return Response(
                {
                    'message': 'Change submitted for approval, not yet active.',
                    'pending_change': PendingChangeSerializer(pending).data,
                    'role': data,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        if not users_enable_role_edit():
            return self._feature_disabled_response('Editing roles')
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not users_enable_role_delete():
            return self._feature_disabled_response('Deleting roles')
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def assign_permissions(self, request, pk=None):
        """Assign permissions to a role"""
        if not users_enable_role_edit():
            return self._feature_disabled_response('Editing roles')
        role = self.get_object()
        permission_ids = request.data.get('permission_ids', [])

        from approvals.permissions import is_maker_checker_enabled
        from approvals.serializers import PendingChangeSerializer
        from approvals.settings_integration import queue_role_permission_assign

        if is_maker_checker_enabled():
            reason = (
                request.data.get('change_reason')
                or request.data.get('reason')
                or ''
            )
            if not str(reason).strip():
                return Response(
                    {'reason': 'A reason is required to change role permissions.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pending = queue_role_permission_assign(
                request,
                role,
                permission_ids,
                reason=str(reason).strip(),
            )
            return Response(
                {
                    'message': 'Change submitted for approval, not yet active.',
                    'pending_change': PendingChangeSerializer(pending).data,
                    'role': RoleSerializer(role).data,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        permissions = Permission.objects.filter(id__in=permission_ids)
        role.permissions.set(permissions)
        log_domain_event(
            request,
            'assign_permissions',
            role,
            module='roles',
            changes={'permission_ids': list(permission_ids)},
        )

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

    @staticmethod
    def _feature_disabled_response(feature_label: str):
        return Response(
            {'error': f'{feature_label} is disabled in store settings.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    
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
        """
        Per-action permission map.

        Self-service actions (``update``, ``partial_update``, ``change_password``)
        must be reachable by *any* authenticated user because the view body
        differentiates "I'm editing me" (allowed) from "I'm editing someone
        else" (admin-only). Gating these at ``IsAdmin`` would short-circuit
        that logic and 403 every cashier who tried to change their own
        password or email.

        Administrative actions (``create``, ``destroy``, ``assign_role``) stay
        behind ``IsAdmin`` - ``destroy`` further restricts itself to super-admins
        inside the action body for safety.
        """
        action = getattr(self, 'action', None)
        if action in (
            'list', 'retrieve',
            'update', 'partial_update',
            'change_password',
            'search',
        ):
            return [IsAuthenticated()]
        # create, destroy, assign_role, and anything else default to admin.
        return [IsAdmin()]
    
    def create(self, request, *args, **kwargs):
        """Create new user - only admins"""
        if not users_enable_create():
            return self._feature_disabled_response('Creating users')
        serializer = UserCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        log_domain_event(
            request,
            AuditLog.ACTION_CREATE,
            user,
            module='users',
            changes={'username': user.username},
        )
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
            data, profile_data = prepare_user_write_data(request.data)
            data.pop('is_staff', None)
            data.pop('is_superuser', None)
            profile_data.pop('role', None)
            profile_data.pop('custom_role_id', None)
            profile_data.pop('custom_role', None)
            if 'profile' in data:
                nested = data.pop('profile')
                if isinstance(nested, dict):
                    if 'phone_number' in nested and users_show_phone():
                        profile_data['phone_number'] = nested.get('phone_number') or ''

            serializer = self.get_serializer(user, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            apply_profile_updates(user, profile_data)
            return Response(UserSerializer(user).data)

        # Admins can update other users
        if current_user.is_staff or (hasattr(current_user, 'profile') and current_user.profile and current_user.profile.is_admin):
            if not users_enable_edit():
                return self._feature_disabled_response('Editing users')
            data, profile_data = prepare_user_write_data(request.data)
            serializer = self.get_serializer(user, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            apply_profile_updates(user, profile_data)
            return Response(UserSerializer(user).data)
        
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete user - only super admins"""
        if not users_enable_delete():
            return self._feature_disabled_response('Deleting users')
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
        if not users_enable_inline_role_assignment():
            return self._feature_disabled_response('Inline role assignment')
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
        try:
            query = request.query_params.get('q', '').strip()
            if not query:
                return Response([])
            
            # Safely parse limit parameter with validation
            limit_param = request.query_params.get('limit', '10')
            try:
                limit = int(limit_param)
                # Validate limit is reasonable (between 1 and 1000)
                if limit < 1:
                    limit = 10
                elif limit > 1000:
                    limit = 1000
            except (ValueError, TypeError):
                limit = 10
            
            users = User.objects.filter(
                Q(username__icontains=query) |
                Q(email__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            )[:limit]
            serializer = UserSerializer(users, many=True)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in user search: {e}", exc_info=True)
            return Response(
                {'error': 'An error occurred while searching users'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    
    @action(
        detail=False, methods=['post'],
        permission_classes=[AllowAny],
        # Login is the front door — throttle aggressively. See
        # config/settings.py:REST_FRAMEWORK for the actual rate string.
        throttle_classes=[__import__('rest_framework.throttling', fromlist=['ScopedRateThrottle']).ScopedRateThrottle],
    )
    def login(self, request):
        """User login - returns JWT tokens.

        Rate limit: configured via ``DEFAULT_THROTTLE_RATES['login']`` (currently
        10/min per IP). Both successes and failures are recorded in the
        ``AuditLog`` so we can detect credential-stuffing attempts.
        """
        import logging
        from utils.audit import log_audit
        from accounts.models import AuditLog as _AuditLog
        logger = logging.getLogger(__name__)

        # The throttle scope must match a key in DEFAULT_THROTTLE_RATES.
        self.throttle_scope = 'login'

        # SECURITY: never log request.data here - it contains the cleartext
        # password. Log only the non-sensitive metadata needed to debug login
        # issues (origin, attempted username).
        attempted_username = request.data.get('username') if hasattr(request, 'data') else None
        logger.info(
            "Login attempt: user=%s origin=%s",
            attempted_username or '<missing>',
            request.META.get('HTTP_ORIGIN', '-'),
        )

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
            
            enabled_modules = get_enabled_modules_flat()

            try:
                from sales.services import SaleService
                SaleService().purge_stale_holdings(user)
            except Exception as purge_err:
                logger.warning('Stale holding purge failed for %s: %s', username, purge_err)

            response_data = {
                'message': 'Login successful',
                'user': user_serializer.data,
                'profile': profile,
                'permissions': permissions,
                'enabled_modules': enabled_modules,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
            logger.info("Login successful for user: %s", username)
            # Audit success - one row per login.
            log_audit(request, _AuditLog.ACTION_LOGIN, user, module='users')
            return Response(response_data)
        else:
            logger.warning("Login failed - invalid credentials for user: %s", username)
            # Audit failure WITHOUT the password (the helper only sees the
            # request metadata, never the body). Pass username via changes.
            log_audit(
                request, _AuditLog.ACTION_LOGIN_FAILED, None,
                module='users',
                changes={'attempted_username': username},
            )
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
            from utils.audit import log_audit
            from accounts.models import AuditLog as _AuditLog

            log_audit(request, _AuditLog.ACTION_LOGOUT, request.user, module='users')
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
        
        enabled_modules = get_enabled_modules_flat()

        return Response({
            'user': user_serializer.data,
            'profile': profile,
            'permissions': permissions,
            'enabled_modules': enabled_modules,
            'is_super_admin': request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile and request.user.profile.is_super_admin),
            'is_admin': request.user.is_staff or (hasattr(request.user, 'profile') and request.user.profile and request.user.profile.is_admin),
        })


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only view onto the append-only audit log. Gated to super-admins
    only - we don't want regular admins to see who looked at what (that's a
    privacy + power concentration issue).

    Supports filtering via query params:
      * ``user``        - user id
      * ``action``      - exact match ('create', 'update', 'login', etc.)
      * ``module``      - exact match ('sales', 'products', ...)
      * ``object_type`` - exact match ('sales.Sale', ...)
      * ``date_from``   - YYYY-MM-DD inclusive
      * ``date_to``     - YYYY-MM-DD inclusive
      * ``q``           - free-text search over username / object_repr / path
    """
    queryset = AuditLog.objects.all().select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, CanViewAuditLog]
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        if params.get('user'):
            qs = qs.filter(user_id=params['user'])
        if params.get('action'):
            qs = qs.filter(action=params['action'])
        if params.get('module'):
            qs = qs.filter(module=params['module'])
        if params.get('object_type'):
            qs = qs.filter(object_type=params['object_type'])
        if params.get('date_from'):
            qs = qs.filter(created_at__date__gte=params['date_from'])
        if params.get('date_to'):
            qs = qs.filter(created_at__date__lte=params['date_to'])
        if params.get('q'):
            term = params['q']
            qs = qs.filter(
                Q(username_snapshot__icontains=term) |
                Q(object_repr__icontains=term) |
                Q(path__icontains=term)
            )
        return qs


# Module settings ViewSets moved to settings app
# See settings/views.py for ModuleSettingsViewSet and ModuleFeatureViewSet
