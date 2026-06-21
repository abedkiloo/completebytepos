from .models import Branch, Tenant, ModuleFeature, ModuleSettings
import logging

logger = logging.getLogger(__name__)


def is_branch_support_enabled():
    """Check if multi-branch support is enabled in module settings."""
    try:
        module = ModuleSettings.objects.get(module_name='settings')
    except ModuleSettings.DoesNotExist:
        return False
    if not module.is_enabled:
        return False
    try:
        feature = ModuleFeature.objects.get(
            module=module,
            feature_key='multi_branch_support',
        )
        return feature.is_enabled
    except ModuleFeature.DoesNotExist:
        # Unconfigured installs: branches are optional until explicitly enabled.
        return False


def get_current_tenant(request):
    """Get the current tenant from request session or user"""
    # Try to get from session first
    tenant_id = request.session.get('current_tenant_id')
    if tenant_id:
        try:
            tenant = Tenant.objects.get(id=tenant_id, is_active=True)
            return tenant
        except Tenant.DoesNotExist:
            pass
    
    # Try to get from header
    tenant_id = request.META.get('HTTP_X_TENANT_ID')
    if tenant_id:
        try:
            tenant = Tenant.objects.get(id=int(tenant_id), is_active=True)
            return tenant
        except (Tenant.DoesNotExist, ValueError) as e:
            pass
    
    # Try to get from query params
    tenant_id = request.query_params.get('tenant_id')
    if tenant_id:
        try:
            tenant = Tenant.objects.get(id=int(tenant_id), is_active=True)
            return tenant
        except (Tenant.DoesNotExist, ValueError) as e:
            pass
    
    # Default to first active tenant (for single-tenant systems)
    tenant = Tenant.get_default_tenant()
    if tenant:
        return tenant
    
    logger.warning("No tenant found - system may not be properly configured")
    return None


def set_current_tenant(request, tenant):
    """Set the current tenant in session"""
    if tenant:
        request.session['current_tenant_id'] = tenant.id
        request.session.modified = True
    else:
        request.session.pop('current_tenant_id', None)
        request.session.modified = True


def get_current_branch(request, tenant=None):
    """Get the current branch from request session or header, optionally filtered by tenant"""
    # If branch support is not enabled, return None
    if not is_branch_support_enabled():
        return None
    
    if not tenant:
        tenant = get_current_tenant(request)
    
    # Try to get from session first
    branch_id = request.session.get('current_branch_id')
    if branch_id:
        try:
            branch = Branch.objects.get(id=branch_id, is_active=True)
            # Verify branch belongs to tenant if tenant is specified
            if tenant and branch.tenant != tenant:
                logger.warning(f"Branch {branch_id} does not belong to tenant {tenant.id}")
                branch_id = None
            else:
                return branch
        except Branch.DoesNotExist:
            pass
    
    # Try to get from header
    branch_id = request.META.get('HTTP_X_BRANCH_ID')
    if branch_id:
        try:
            branch = Branch.objects.get(id=int(branch_id), is_active=True)
            # Verify branch belongs to tenant if tenant is specified
            if tenant and branch.tenant != tenant:
                logger.warning(f"Branch {branch_id} from header does not belong to tenant {tenant.id}")
                branch_id = None
            else:
                return branch
        except (Branch.DoesNotExist, ValueError) as e:
            pass
    
    # Try to get from query params
    branch_id = request.query_params.get('branch_id')
    if branch_id:
        try:
            branch = Branch.objects.get(id=int(branch_id), is_active=True)
            # Verify branch belongs to tenant if tenant is specified
            if tenant and branch.tenant != tenant:
                logger.warning(f"Branch {branch_id} from query does not belong to tenant {tenant.id}")
                branch_id = None
            else:
                return branch
        except (Branch.DoesNotExist, ValueError) as e:
            pass
    
    # Default to headquarters or first active branch for tenant
    if tenant:
        hq = Branch.get_headquarters(tenant=tenant)
        if hq:
            return hq
        
        # Fallback to first active branch for tenant
        branch = Branch.get_active_branches(tenant=tenant).first()
        if branch:
            return branch
    
    # Fallback to any headquarters or first active branch (if no tenant)
    hq = Branch.get_headquarters()
    if hq:
        return hq
    
    # Last fallback
    branch = Branch.get_active_branches().first()
    if branch:
        return branch
    
    return None


def set_current_branch(request, branch):
    """Set the current branch in session"""
    if branch:
        request.session['current_branch_id'] = branch.id
        request.session.modified = True
    else:
        request.session.pop('current_branch_id', None)
        request.session.modified = True
