from .models import Branch, Tenant, ModuleFeature
import logging

logger = logging.getLogger(__name__)


def is_branch_support_enabled():
    """Check if multi-branch support is enabled in module settings"""
    try:
        return ModuleFeature.is_feature_enabled('settings', 'multi_branch_support')
    except:
        # Default to False if not configured (branches are optional)
        return False


def get_current_tenant(request):
    """Get the current tenant from request session or user"""
    # Try to get from session first
    tenant_id = request.session.get('current_tenant_id')
    if tenant_id:
        try:
            tenant = Tenant.objects.get(id=tenant_id, is_active=True)
            logger.debug(f"Got tenant from session: {tenant.name}")
            return tenant
        except Tenant.DoesNotExist:
            logger.debug(f"Tenant {tenant_id} from session not found")
            pass
    
    # Try to get from header
    tenant_id = request.META.get('HTTP_X_TENANT_ID')
    if tenant_id:
        try:
            tenant = Tenant.objects.get(id=int(tenant_id), is_active=True)
            logger.debug(f"Got tenant from header: {tenant.name}")
            return tenant
        except (Tenant.DoesNotExist, ValueError) as e:
            logger.debug(f"Tenant from header error: {e}")
            pass
    
    # Try to get from query params
    tenant_id = request.query_params.get('tenant_id')
    if tenant_id:
        try:
            tenant = Tenant.objects.get(id=int(tenant_id), is_active=True)
            logger.debug(f"Got tenant from query: {tenant.name}")
            return tenant
        except (Tenant.DoesNotExist, ValueError) as e:
            logger.debug(f"Tenant from query error: {e}")
            pass
    
    # Default to first active tenant (for single-tenant systems)
    tenant = Tenant.get_default_tenant()
    if tenant:
        logger.debug(f"Using default tenant: {tenant.name}")
        return tenant
    
    logger.warning("No tenant found - system may not be properly configured")
    return None


def set_current_tenant(request, tenant):
    """Set the current tenant in session"""
    if tenant:
        request.session['current_tenant_id'] = tenant.id
        request.session.modified = True
        logger.debug(f"Set current tenant in session: {tenant.name}")
    else:
        request.session.pop('current_tenant_id', None)
        request.session.modified = True
        logger.debug("Cleared current tenant from session")


def get_current_branch(request, tenant=None):
    """Get the current branch from request session or header, optionally filtered by tenant"""
    # If branch support is not enabled, return None
    if not is_branch_support_enabled():
        logger.debug("Branch support is disabled - returning None")
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
                logger.debug(f"Got branch from session: {branch.name}")
                return branch
        except Branch.DoesNotExist:
            logger.debug(f"Branch {branch_id} from session not found")
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
                logger.debug(f"Got branch from header: {branch.name}")
                return branch
        except (Branch.DoesNotExist, ValueError) as e:
            logger.debug(f"Branch from header error: {e}")
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
                logger.debug(f"Got branch from query: {branch.name}")
                return branch
        except (Branch.DoesNotExist, ValueError) as e:
            logger.debug(f"Branch from query error: {e}")
            pass
    
    # Default to headquarters or first active branch for tenant
    if tenant:
        hq = Branch.get_headquarters(tenant=tenant)
        if hq:
            logger.debug(f"Using headquarters branch for tenant: {hq.name}")
            return hq
        
        # Fallback to first active branch for tenant
        branch = Branch.get_active_branches(tenant=tenant).first()
        if branch:
            logger.debug(f"Using first active branch for tenant: {branch.name}")
            return branch
    
    # Fallback to any headquarters or first active branch (if no tenant)
    hq = Branch.get_headquarters()
    if hq:
        logger.debug(f"Using any headquarters branch: {hq.name}")
        return hq
    
    # Last fallback
    branch = Branch.get_active_branches().first()
    if branch:
        logger.debug(f"Using first active branch: {branch.name}")
        return branch
    
    logger.debug("No branch found - branches may not be configured or enabled")
    return None


def set_current_branch(request, branch):
    """Set the current branch in session"""
    if branch:
        request.session['current_branch_id'] = branch.id
        request.session.modified = True
        logger.debug(f"Set current branch in session: {branch.name}")
    else:
        request.session.pop('current_branch_id', None)
        request.session.modified = True
        logger.debug("Cleared current branch from session")
