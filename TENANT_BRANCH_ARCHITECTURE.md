# Tenant & Branch Architecture Implementation

## Overview

The system has been updated to implement a **Tenant (Business/Company) → Branch (Outlet)** architecture:

- **Tenant** = Business/Company (top level organization)
- **Branch** = Physical or logical outlet under that business
- **By default, there are NO branches** - branches are added through module settings

## Architecture Changes

### 1. Tenant Model (`be/settings/models.py`)

**New Model:** `Tenant`
- Represents a Business/Company
- Fields: `name`, `code`, `registration_number`, `tax_id`, `address`, `city`, `country`, `phone`, `email`, `website`
- One tenant per organization
- Has an `owner` (User) who is the primary administrator

### 2. Branch Model Updated (`be/settings/models.py`)

**Updated Model:** `Branch`
- Now has a **ForeignKey to Tenant** (`tenant`)
- `branch_code` is now unique **within a tenant** (not globally unique)
- `is_headquarters` is now per-tenant (one HQ per tenant)
- Methods updated:
  - `get_headquarters(tenant=None)` - Get HQ for a specific tenant
  - `get_active_branches(tenant=None)` - Get active branches for a tenant

### 3. Utility Functions Updated (`be/settings/utils.py`)

**New Functions:**
- `get_current_tenant(request)` - Gets current tenant from session/header/query
- `set_current_tenant(request, tenant)` - Sets tenant in session

**Updated Functions:**
- `get_current_branch(request, tenant=None)` - Now filters by tenant automatically
- `set_current_branch(request, branch)` - Also sets tenant if not already set

### 4. Views Updated (`be/settings/views.py`)

**New ViewSet:** `TenantViewSet`
- Full CRUD for tenants
- Endpoints:
  - `GET /api/settings/tenants/` - List all tenants
  - `GET /api/settings/tenants/active/` - Get active tenants
  - `POST /api/settings/tenants/{id}/set_current/` - Set current tenant
  - `POST /api/settings/tenants/clear_current/` - Clear current tenant

**Updated ViewSet:** `BranchViewSet`
- Now filters branches by current tenant
- `get_queryset()` automatically filters by `get_current_tenant(request)`
- `perform_create()` automatically sets tenant from current tenant

### 5. Logging Added

**Effective logging** (not over-logging) added to:
- `settings` app - Tenant/Branch operations
- `sales` app - Sale creation, invoice operations
- `inventory` app - Stock movements
- `expenses` app - Expense operations
- `income` app - Income operations

**Log Levels:**
- `INFO` - Important operations (create, update, delete)
- `WARNING` - Potential issues (missing branch, tenant mismatch)
- `ERROR` - Actual errors
- `DEBUG` - Detailed debugging (only in development)

## Database Structure

### Default State
- **1 Tenant** created (CompleteByte Business)
- **0 Branches** (branches added through module settings)
- **21 Users** (1 superuser + 20 regular users)
- **100 Customers** (no branch assigned by default)
- **990 Products** with variants

### Branch Creation
Branches are **NOT** created automatically. They must be added through:
- Module Settings UI (for super admins)
- Branch Management API (`POST /api/settings/branches/`)

## API Changes

### Tenant Endpoints
```
GET    /api/settings/tenants/              - List tenants
GET    /api/settings/tenants/{id}/         - Get tenant details
POST   /api/settings/tenants/              - Create tenant (super admin)
PUT    /api/settings/tenants/{id}/         - Update tenant (super admin)
DELETE /api/settings/tenants/{id}/         - Delete tenant (super admin)
GET    /api/settings/tenants/active/        - Get active tenants
POST   /api/settings/tenants/{id}/set_current/  - Set current tenant
POST   /api/settings/tenants/clear_current/     - Clear current tenant
```

### Branch Endpoints (Updated)
```
GET    /api/settings/branches/              - List branches (filtered by current tenant)
GET    /api/settings/branches/{id}/         - Get branch details
POST   /api/settings/branches/              - Create branch (auto-assigns to current tenant)
PUT    /api/settings/branches/{id}/         - Update branch (super admin)
DELETE /api/settings/branches/{id}/         - Delete branch (super admin)
GET    /api/settings/branches/active/      - Get active branches (for current tenant)
GET    /api/settings/branches/headquarters/ - Get HQ branch (for current tenant)
POST   /api/settings/branches/{id}/set_current/  - Set current branch
POST   /api/settings/branches/clear_current/     - Clear current branch
```

## Data Flow

### 1. System Initialization
1. Create superuser
2. Create default tenant (CompleteByte Business)
3. **No branches created** - system works without branches initially

### 2. Adding Branches
1. Super admin goes to Module Settings
2. Navigates to Branch Management
3. Creates branches under the current tenant
4. Each branch belongs to the tenant

### 3. Using the System
1. User logs in
2. System loads current tenant (defaults to first active tenant)
3. User selects a branch (if branches exist)
4. All operations are filtered by tenant and branch

## Frontend Updates Needed

The frontend needs to be updated to:
1. **Handle Tenant Selection** - Show tenant selector (if multiple tenants)
2. **Handle Branch Selection** - Show branch selector (only if branches exist)
3. **Branch Management UI** - Allow creating branches through module settings
4. **Tenant Context** - Pass tenant ID in headers/requests

## Testing Checklist

- [x] Database cleared and recreated
- [x] Tenant model created
- [x] Branch model updated with tenant FK
- [x] All migrations applied
- [x] Test data populated (1 tenant, 0 branches, 20 users, 100 customers, 1000 products)
- [ ] Frontend updated for tenant/branch selection
- [ ] End-to-end testing completed
- [ ] Logging verified

## Next Steps

1. **Update Frontend:**
   - Add tenant selector component
   - Update branch selector to work with tenant context
   - Update branch management UI to create branches under tenant

2. **Test End-to-End:**
   - Login
   - Create a branch through module settings
   - Select branch
   - Create a sale
   - Verify data is filtered correctly

3. **Verify Logging:**
   - Check logs for important operations
   - Ensure no over-logging
   - Verify error logging works
