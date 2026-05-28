from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action, api_view, permission_classes
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.management import call_command
from django.core.management.base import CommandError
from .models import ModuleSettings, ModuleFeature, Branch, Tenant
from .serializers import (
    ModuleSettingsSerializer, ModuleFeatureSerializer,
    BranchSerializer, BranchListSerializer,
    TenantSerializer, TenantListSerializer
)
from accounts.permissions import IsSuperAdmin
from .utils import get_current_tenant, get_current_branch, set_current_tenant, set_current_branch, is_branch_support_enabled
from .module_catalog import apply_module_preset, build_modules_response
from .setup_status import get_setup_status
from accounts.role_definitions import BOOTSTRAP_USERS
import logging
import os
import sys
from io import StringIO

logger = logging.getLogger(__name__)


class ModuleSettingsViewSet(viewsets.ModelViewSet):
    """Module settings - only super admins can modify"""
    queryset = ModuleSettings.objects.all()
    serializer_class = ModuleSettingsSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['module_name']
    
    def get_permissions(self):
        """Only super admins can modify"""
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]
    
    def list(self, request, *args, **kwargs):
        """List modules (flat map) + grouped catalog + install presets."""
        return Response(build_modules_response())

    @action(detail=False, methods=['post'], url_path='apply-preset')
    def apply_preset(self, request):
        """Apply an install preset (super admin only). Body: { \"preset_id\": \"retail_starter\" }"""
        preset_id = request.data.get('preset_id')
        if not preset_id:
            return Response({'error': 'preset_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            data = apply_module_preset(preset_id, user=request.user)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)
    
    def update(self, request, *args, **kwargs):
        """Update module setting - only super admins"""
        instance = self.get_object()
        instance.is_enabled = request.data.get('is_enabled', instance.is_enabled)
        instance.description = request.data.get('description', instance.description)
        instance.updated_by = request.user
        instance.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update module setting - only super admins"""
        return self.update(request, *args, **kwargs)


class ModuleFeatureViewSet(viewsets.ModelViewSet):
    """Module feature settings - only super admins can modify"""
    queryset = ModuleFeature.objects.all().select_related('module')
    serializer_class = ModuleFeatureSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['module', 'display_order', 'feature_name']
    
    def get_permissions(self):
        """Only super admins can modify"""
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        module_id = self.request.query_params.get('module', None)
        if module_id:
            queryset = queryset.filter(module_id=module_id)
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        logger.info(f"Feature updated: {serializer.instance.feature_name} (enabled: {serializer.instance.is_enabled}) by {self.request.user.username}")


class TenantViewSet(viewsets.ModelViewSet):
    """Tenant (Business/Company) management - super admins can manage all"""
    queryset = Tenant.objects.all().select_related('owner', 'created_by')
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TenantListSerializer
        return TenantSerializer
    
    def get_queryset(self):
        queryset = Tenant.objects.all().select_related('owner', 'created_by')
        is_active = self.request.query_params.get('is_active', None)
        search = self.request.query_params.get('search', None)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(city__icontains=search)
            )
        
        return queryset
    
    def get_permissions(self):
        """Only super admins can modify tenants"""
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        logger.info(f"Tenant created: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        logger.info(f"Tenant updated: {serializer.instance.name} by {self.request.user.username}")
        super().perform_update(serializer)
    
    def perform_destroy(self, instance):
        logger.warning(f"Tenant deleted: {instance.name} by {self.request.user.username}")
        super().perform_destroy(instance)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active tenants"""
        tenants = Tenant.objects.filter(is_active=True).order_by('name')
        serializer = TenantListSerializer(tenants, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def set_current(self, request, pk=None):
        """Set this tenant as the current tenant for the session"""
        tenant = self.get_object()
        if not tenant.is_active:
            return Response(
                {'error': 'Cannot set inactive tenant as current'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        set_current_tenant(request, tenant)
        logger.info(f"Current tenant set to: {tenant.name} by {request.user.username}")
        
        serializer = TenantSerializer(tenant)
        return Response({
            'message': f'Current tenant set to {tenant.name}',
            'tenant': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    def clear_current(self, request):
        """Clear current tenant"""
        set_current_tenant(request, None)
        logger.info(f"Current tenant cleared by {request.user.username}")
        return Response({'message': 'Current tenant cleared.'})


class BranchViewSet(viewsets.ModelViewSet):
    """Branch management - filtered by current tenant"""
    queryset = Branch.objects.all().select_related('tenant', 'manager', 'created_by')
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return BranchListSerializer
        return BranchSerializer
    
    def get_queryset(self):
        """Filter branches by current tenant"""
        # If branch support is not enabled, return empty queryset
        if not is_branch_support_enabled():
            logger.debug("Branch support is disabled - returning empty queryset")
            return Branch.objects.none()
        
        queryset = Branch.objects.all().select_related('tenant', 'manager', 'created_by')
        
        # Filter by tenant
        tenant = get_current_tenant(self.request)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
            logger.debug(f"Filtering branches for tenant: {tenant.name}")
        else:
            logger.warning("No tenant found - showing all branches")
        
        # Additional filters
        is_active = self.request.query_params.get('is_active', None)
        search = self.request.query_params.get('search', None)
        tenant_id = self.request.query_params.get('tenant_id', None)
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(branch_code__icontains=search) |
                Q(city__icontains=search) |
                Q(address__icontains=search)
            )
        
        return queryset
    
    def get_permissions(self):
        """Only super admins can modify branches"""
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]
    
    def get_serializer_context(self):
        """Add tenant to serializer context"""
        context = super().get_serializer_context()
        tenant = get_current_tenant(self.request)
        if tenant:
            context['tenant_id'] = tenant.id
        return context
    
    def perform_create(self, serializer):
        """Set tenant from current tenant if not provided"""
        # Check if branch support is enabled
        if not is_branch_support_enabled():
            logger.warning(f"Branch creation attempted but branch support is disabled by {self.request.user.username}")
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Multi-branch support is not enabled. Please enable it in module settings first.")
        
        tenant = get_current_tenant(self.request)
        if not tenant:
            logger.error("No tenant found when creating branch")
            from rest_framework.exceptions import ValidationError
            raise ValidationError("No tenant found. Please ensure a tenant is configured.")
        
        # Save with tenant and created_by
        serializer.save(tenant=tenant, created_by=self.request.user)
        logger.info(f"Branch created: {serializer.instance.name} for tenant {tenant.name} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        logger.info(f"Branch updated: {serializer.instance.name} by {self.request.user.username}")
        super().perform_update(serializer)
    
    def perform_destroy(self, instance):
        logger.warning(f"Branch deleted: {instance.name} by {self.request.user.username}")
        super().perform_destroy(instance)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active branches for current tenant"""
        tenant = get_current_tenant(request)
        branches = Branch.get_active_branches(tenant=tenant)
        serializer = BranchListSerializer(branches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def headquarters(self, request):
        """Get headquarters branch for current tenant"""
        tenant = get_current_tenant(request)
        hq = Branch.get_headquarters(tenant=tenant)
        if hq:
            serializer = BranchSerializer(hq)
            return Response(serializer.data)
        return Response({'detail': 'No headquarters branch found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def set_current(self, request, pk=None):
        """Set this branch as the current branch for the session"""
        branch = self.get_object()
        if not branch.is_active:
            return Response(
                {'error': 'Cannot set inactive branch as current'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Also set the tenant if not already set
        if not get_current_tenant(request):
            set_current_tenant(request, branch.tenant)
        
        set_current_branch(request, branch)
        logger.info(f"Current branch set to: {branch.name} by {request.user.username}")
        
        serializer = BranchSerializer(branch)
        return Response({
            'message': f'Current branch set to {branch.name}',
            'branch': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    def clear_current(self, request):
        """Clear current branch (show all branches)"""
        set_current_branch(request, None)
        logger.info(f"Current branch cleared by {request.user.username}")
        return Response({'message': 'Current branch cleared. Showing all branches.'})


@api_view(['GET'])
@permission_classes([AllowAny])
def setup_status(request):
    """Whether first-time installation is required (no auth)."""
    return Response(get_setup_status())


def _bootstrap_credentials_payload():
    primary = BOOTSTRAP_USERS[0]
    return {
        'primary': {
            'username': primary['username'],
            'password': primary['password'],
            'label': primary['label'],
        },
        'users': [
            {
                'username': spec['username'],
                'password': spec['password'],
                'label': spec['label'],
            }
            for spec in BOOTSTRAP_USERS
        ],
    }


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow installation without authentication
def fresh_install(request):
    """
    Complete fresh installation endpoint
    Runs all setup steps: delete DB, migrations, superuser, permissions, modules, etc.
    """
    try:
        include_test_data = request.data.get('include_test_data', False)
        skip_db_delete = request.data.get('skip_db_delete', False)
        
        # Capture command output
        output_buffer = StringIO()
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        
        steps = []
        
        try:
            # Step 1: Reset database (PostgreSQL schema or legacy SQLite file)
            if not skip_db_delete:
                steps.append({'step': 1, 'name': 'Preparing fresh database', 'status': 'running'})
                try:
                    from django.conf import settings as django_settings
                    import django
                    django.setup()
                    from config.database import is_postgresql_config, reset_default_database
                    if is_postgresql_config(django_settings.DATABASES):
                        reset_default_database()
                        steps[-1]['status'] = 'completed'
                        steps[-1]['message'] = 'PostgreSQL schema reset'
                    else:
                        reset_default_database()
                        steps[-1]['status'] = 'completed'
                        steps[-1]['message'] = 'SQLite database file removed'
                except Exception as e:
                    steps[-1]['status'] = 'warning'
                    steps[-1]['message'] = str(e)[:120]
            
            # Step 2: Create migrations
            steps.append({'step': 2, 'name': 'Creating migrations', 'status': 'running'})
            try:
                call_command('makemigrations', verbosity=0)
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = 'Migrations created'
            except Exception as e:
                steps[-1]['status'] = 'warning'
                steps[-1]['message'] = str(e)[:100]
            
            # Step 3: Run migrations
            steps.append({'step': 3, 'name': 'Running migrations', 'status': 'running'})
            try:
                call_command('migrate', verbosity=0, interactive=False)
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = 'Migrations applied'
            except Exception as e:
                steps[-1]['status'] = 'error'
                steps[-1]['message'] = str(e)[:100]
                raise
            
            # Step 4: Bootstrap users (admin, manager, sales)
            steps.append({'step': 4, 'name': 'Creating bootstrap users', 'status': 'running'})
            try:
                call_command('create_users', verbosity=0)
                admin = BOOTSTRAP_USERS[0]
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = (
                    f'Users ready — sign in as {admin["username"]} / {admin["password"]}'
                )
            except Exception as e:
                steps[-1]['status'] = 'error'
                steps[-1]['message'] = str(e)[:100]
                raise
            
            # Step 5: Initialize permissions and roles
            steps.append({'step': 5, 'name': 'Initializing permissions and roles', 'status': 'running'})
            try:
                call_command('init_permissions', verbosity=0)
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = 'Permissions and roles initialized'
            except Exception as e:
                steps[-1]['status'] = 'warning'
                steps[-1]['message'] = str(e)[:100]
            
            # Step 6: Initialize modules
            steps.append({'step': 6, 'name': 'Initializing modules and features', 'status': 'running'})
            try:
                call_command('init_modules', verbosity=0)
                preset_id = request.data.get('module_preset', 'retail_starter')
                admin_user = User.objects.filter(username=BOOTSTRAP_USERS[0]['username']).first()
                apply_module_preset(preset_id, user=admin_user)
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = f'Modules initialized (preset: {preset_id})'
            except Exception as e:
                steps[-1]['status'] = 'warning'
                steps[-1]['message'] = str(e)[:100]
            
            # Step 7: Initialize accounting accounts
            steps.append({'step': 7, 'name': 'Initializing accounting accounts', 'status': 'running'})
            try:
                call_command('init_accounts', verbosity=0)
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = 'Accounting accounts initialized'
            except Exception as e:
                steps[-1]['status'] = 'warning'
                steps[-1]['message'] = str(e)[:100]
            
            # Step 8: Initialize expense categories
            steps.append({'step': 8, 'name': 'Initializing expense categories', 'status': 'running'})
            try:
                call_command('init_expense_categories', verbosity=0)
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = 'Expense categories initialized'
            except Exception as e:
                steps[-1]['status'] = 'warning'
                steps[-1]['message'] = str(e)[:100]
            
            # Step 9: Setup new organization
            steps.append({'step': 9, 'name': 'Setting up organization', 'status': 'running'})
            try:
                call_command('setup_new_organization', verbosity=0)
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = 'Organization setup complete'
            except Exception as e:
                steps[-1]['status'] = 'warning'
                steps[-1]['message'] = str(e)[:100]
            
            # Step 10: Populate data (optional)
            if include_test_data:
                steps.append({'step': 10, 'name': 'Populating comprehensive soft furnishings data', 'status': 'running'})
                try:
                    users_count = request.data.get('users', 20)
                    products_count = request.data.get('products', 200)
                    customers_count = request.data.get('customers', 50)
                    sales_count = request.data.get('sales', 100)
                    expenses_count = request.data.get('expenses', 30)
                    call_command('populate_test_data',
                                users=users_count,
                                products=products_count,
                                customers=customers_count,
                                sales=sales_count,
                                expenses=expenses_count,
                                verbosity=0)
                    steps[-1]['status'] = 'completed'
                    steps[-1]['message'] = f'Soft furnishings data populated ({users_count} users, {products_count} products, {customers_count} customers, {sales_count} sales, {expenses_count} expenses)'
                except Exception as e:
                    steps[-1]['status'] = 'warning'
                    steps[-1]['message'] = str(e)[:100]
            
        finally:
            sys.stdout = old_stdout
        
        creds = _bootstrap_credentials_payload()
        return Response({
            'success': True,
            'message': 'Installation completed successfully',
            'steps': steps,
            'credentials': creds,
            # Legacy flat shape for older clients
            'username': creds['primary']['username'],
            'password': creds['primary']['password'],
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Installation failed: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
            'steps': steps if 'steps' in locals() else []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
