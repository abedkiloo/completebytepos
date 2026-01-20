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
        """List all module settings with features"""
        modules = ModuleSettings.objects.prefetch_related('features').all()
        data = {}
        for module in modules:
            # Get all features for this module
            features = {}
            for feature in module.features.all():
                features[feature.feature_key] = {
                    'id': feature.id,
                    'feature_key': feature.feature_key,
                    'feature_name': feature.feature_name,
                    'is_enabled': feature.is_enabled,
                    'description': feature.description,
                    'display_order': feature.display_order,
                }
            
            data[module.module_name] = {
                'id': module.id,
                'is_enabled': module.is_enabled,
                'description': module.description,
                'module_name_display': module.get_module_name_display(),
                'features': features,
            }
        
        # Add branch support status for convenience
        data['_meta'] = {
            'branch_support_enabled': is_branch_support_enabled(),
        }
        
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
            # Step 1: Delete database
            if not skip_db_delete:
                steps.append({'step': 1, 'name': 'Preparing fresh database', 'status': 'running'})
                db_path = 'db.sqlite3'
                if os.path.exists(db_path):
                    os.remove(db_path)
                    steps[-1]['status'] = 'completed'
                    steps[-1]['message'] = 'Existing database deleted'
                else:
                    steps[-1]['status'] = 'completed'
                    steps[-1]['message'] = 'No existing database found'
            
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
            
            # Step 4: Create superuser
            steps.append({'step': 4, 'name': 'Creating superuser', 'status': 'running'})
            try:
                user, created = User.objects.get_or_create(
                    username='admin@3@1',
                    defaults={
                        'email': 'admin@3@1',
                        'is_staff': True,
                        'is_superuser': True,
                        'is_active': True
                    }
                )
                user.set_password('admin@3@1')
                user.save()
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = 'Superuser created (username: admin@3@1, password: admin@3@1)'
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
                steps[-1]['status'] = 'completed'
                steps[-1]['message'] = 'Modules and features initialized'
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
        
        return Response({
            'success': True,
            'message': 'Installation completed successfully',
            'steps': steps,
            'credentials': {
                'username': 'admin',
                'password': 'admin'
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Installation failed: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
            'steps': steps if 'steps' in locals() else []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
