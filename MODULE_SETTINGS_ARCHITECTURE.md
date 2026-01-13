# Module Settings Management Architecture

## Overview
The module settings system provides a hierarchical, granular control mechanism for enabling/disabling modules and their features across the CompleteByte POS system.

## Architecture Layers

### 1. Database Layer (Backend Models)

#### ModuleSettings Model
```python
Location: be/accounts/models.py

Fields:
- module_name: CharField (choices from MODULE_CHOICES)
- is_enabled: BooleanField (enable/disable module)
- description: TextField
- updated_by: ForeignKey (tracks who last modified)
- created_at, updated_at: DateTimeFields

Available Modules:
- products, sales, customers, invoicing, inventory, stock
- expenses, income, bank_accounts, money_transfer
- accounting, balance_sheet, trial_balance, cash_flow, account_statement
- barcodes, reports, settings
```

#### ModuleFeature Model
```python
Location: be/accounts/models.py

Fields:
- module: ForeignKey (links to ModuleSettings)
- feature_key: CharField (unique identifier)
- feature_name: CharField (display name)
- is_enabled: BooleanField (enable/disable feature)
- description: TextField
- display_order: IntegerField (for UI ordering)
- updated_by: ForeignKey

Relationship:
- One ModuleSettings → Many ModuleFeatures
- Features are nested within modules
```

### 2. API Layer (Django REST Framework)

#### Endpoints

**Module Settings:**
- `GET /api/accounts/modules/` - List all modules with features
- `GET /api/accounts/modules/{id}/` - Get single module
- `PUT /api/accounts/modules/{id}/` - Update module (super admin only)
- `PATCH /api/accounts/modules/{id}/` - Partial update (super admin only)

**Module Features:**
- `GET /api/accounts/module-features/` - List all features
- `GET /api/accounts/module-features/{id}/` - Get single feature
- `PUT /api/accounts/module-features/{id}/` - Update feature (super admin only)
- `PATCH /api/accounts/module-features/{id}/` - Partial update (super admin only)

#### Permissions

**View Access:**
- Any authenticated user can view modules/features

**Modify Access:**
- Only super admins can modify modules/features
- Permission check: `IsSuperAdmin()` custom permission
- Checks: `user.is_superuser` OR `user.profile.is_super_admin`

#### Response Format

**List Modules Response:**
```json
{
  "products": {
    "id": 1,
    "is_enabled": true,
    "description": "Product management module",
    "module_name_display": "Products Management",
    "features": {
      "qr_printing": {
        "id": 1,
        "feature_key": "qr_printing",
        "feature_name": "QR Code Printing",
        "is_enabled": true,
        "description": "Enable QR code generation",
        "display_order": 1
      },
      ...
    }
  },
  ...
}
```

### 3. Frontend Layer (React)

#### Component Structure

**ModuleSettings Component:**
```
Location: fe/src/components/ModuleSettings/ModuleSettings.js

State Management:
- modules: Array of module objects
- loading: Boolean (loading state)
- saving: Object (tracks which items are being saved)
- expandedModules: Object (tracks expanded/collapsed state)

Key Functions:
- loadModules(): Fetches all modules from API
- handleToggleModule(): Toggles module on/off
- handleToggleFeature(): Toggles feature on/off
- handleToggleCategory(): Toggles entire category
```

#### API Integration

**Service Layer:**
```javascript
Location: fe/src/services/api.js

modulesAPI:
- list(): GET all modules
- get(id): GET single module
- update(id, data): PUT update module
- patch(id, data): PATCH partial update

moduleFeaturesAPI:
- list(params): GET all features
- get(id): GET single feature
- update(id, data): PUT update feature
- patch(id, data): PATCH partial update
```

#### Data Flow

```
1. Component Mounts
   ↓
2. loadModules() called
   ↓
3. API Request: GET /api/accounts/modules/
   ↓
4. Backend: ModuleSettingsViewSet.list()
   - Fetches all ModuleSettings with prefetch_related('features')
   - Builds nested structure with features
   ↓
5. Response sent to frontend
   ↓
6. Frontend processes data:
   - Converts object to array
   - Groups by category
   - Initializes expanded state
   ↓
7. UI renders modules with toggle switches
```

### 4. Permission & Access Control

#### Backend Permission Checks

**IsSuperAdmin Permission:**
```python
Location: be/accounts/permissions.py

Checks:
1. User is authenticated
2. user.is_superuser == True OR
3. user.profile.is_super_admin == True
```

**ViewSet Permission Logic:**
```python
def get_permissions(self):
    if self.action in ['list', 'retrieve']:
        return [IsAuthenticated()]  # Anyone authenticated
    return [IsSuperAdmin()]  # Only super admins can modify
```

#### Frontend Permission Checks

**Super Admin Detection:**
```javascript
const user = JSON.parse(localStorage.getItem('user') || '{}');
const userProfile = user.profile || {};
const isSuperAdmin = 
  userProfile.role === 'super_admin' || 
  user.is_superuser || 
  userProfile.is_super_admin;
```

**UI Restrictions:**
- Toggle switches disabled if not super admin
- Error messages shown if non-admin tries to modify
- Visual indicators (badges) show admin status

### 5. Cascading Behavior

#### Module Disable → Features Disable
When a module is disabled:
1. All features within that module are automatically disabled
2. Frontend sends parallel API requests to disable all features
3. Local state updated to reflect changes
4. User sees immediate feedback

#### Category Toggle → All Modules Toggle
When a category toggle is clicked:
1. All modules in that category are enabled/disabled
2. All features in those modules are also updated
3. Confirmation dialog shown for disable operations
4. Batch updates sent to backend

### 6. Initialization

#### Database Setup

**Management Command:**
```bash
python manage.py init_modules
```

**What it does:**
1. Creates ModuleSettings records for all defined modules
2. Creates ModuleFeature records for each module's features
3. Sets default `is_enabled=True` for all
4. Updates existing modules if configuration changed
5. Skips modules that already exist

**Location:** `be/accounts/management/commands/init_modules.py`

### 7. Usage in Application

#### Sidebar Visibility Control

**Layout Component:**
```javascript
Location: fe/src/components/Layout/Layout.js

Functions:
- isModuleEnabled(moduleName): Checks if module is enabled
- isFeatureEnabled(moduleName, featureKey): Checks if feature is enabled

Usage:
{isModuleEnabled('sales') && (
  <div>Sales Section</div>
)}

{isFeatureEnabled('sales', 'pos') && (
  <Link to="/pos">POS</Link>
)}
```

#### Caching

**LocalStorage Cache:**
- Module settings cached in `localStorage.getItem('enabled_modules')`
- Updated on login and when settings change
- Used as fallback if API fails
- Refreshed when module settings page loads

### 8. Data Structure Example

```javascript
// Module Settings Structure
{
  "products": {
    "id": 1,
    "module_name": "products",
    "module_name_display": "Products Management",
    "is_enabled": true,
    "description": "Product management module",
    "features": {
      "qr_printing": {
        "id": 1,
        "feature_key": "qr_printing",
        "feature_name": "QR Code Printing",
        "is_enabled": true,
        "description": "Enable QR code generation",
        "display_order": 1
      },
      "barcode_printing": { ... },
      ...
    }
  },
  "sales": { ... },
  ...
}
```

### 9. Category Grouping

**Frontend Categories:**
- Core Business Operations: products, sales, customers, invoicing, inventory, stock
- Financial Management: expenses, income, bank_accounts, money_transfer
- Accounting & Reporting: accounting, balance_sheet, trial_balance, cash_flow, account_statement, reports
- Tools & Utilities: barcodes
- System Administration: settings

**Location:** `fe/src/components/ModuleSettings/ModuleSettings.js` - `getModuleCategory()`

### 10. Key Features

1. **Hierarchical Control:**
   - Category → Module → Feature
   - Toggle at any level

2. **Real-time Updates:**
   - Changes reflected immediately
   - Optimistic UI updates
   - Error handling with rollback

3. **Safety Features:**
   - Confirmation dialogs for critical operations
   - Prevents disabling Settings module without warning
   - Permission checks at multiple levels

4. **User Experience:**
   - Visual indicators (badges, colors)
   - Loading states
   - Success/error toasts
   - Expandable/collapsible sections

5. **Performance:**
   - Prefetch related features (reduces queries)
   - LocalStorage caching
   - Parallel API requests for batch operations

## Summary

The module settings system provides:
- **Granular Control**: Module and feature-level toggles
- **Security**: Super admin only modifications
- **Flexibility**: Category, module, and feature level control
- **User-Friendly**: Clear UI with visual feedback
- **Performance**: Efficient queries and caching
- **Safety**: Confirmation dialogs and permission checks
