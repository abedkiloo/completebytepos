# Multi-Branch Support Feature

## Overview

Branches are now **optional** and controlled by a module setting. Super admins can enable/disable multi-branch support through the Module Settings interface.

## How It Works

### 1. Module Feature

- **Location:** Settings Module → Multi-Branch Support feature
- **Default State:** **Disabled** (branches are optional)
- **Control:** Super admins can enable/disable via checkbox in Module Settings

### 2. When Disabled (Default)

- Branch selector is **hidden** in the UI
- Sales, inventory, expenses, income work **without branches**
- No branch filtering applied
- System operates at tenant level only

### 3. When Enabled

- Branch selector appears in the UI
- Branches can be created and managed
- Sales, inventory, expenses, income require branch selection
- Data is filtered by branch

## Enabling Multi-Branch Support

1. **Login as super admin** (`admin` / `admin123`)
2. **Navigate to:** Settings → Module Settings
3. **Find:** "System Settings" module
4. **Expand** the module to see features
5. **Check** the "Multi-Branch Support" checkbox
6. **Save** the changes
7. **Refresh** the page - branch selector will appear

## Backend Implementation

### Utility Function

```python
from settings.utils import is_branch_support_enabled

if is_branch_support_enabled():
    # Branch logic here
    branch = get_current_branch(request)
else:
    # No branch required
    branch = None
```

### Views Updated

All views now check `is_branch_support_enabled()` before requiring branches:
- `SaleViewSet` - Only requires branch if enabled
- `StockMovementViewSet` - Only filters by branch if enabled
- `ExpenseViewSet` - Only requires branch if enabled
- `IncomeViewSet` - Only requires branch if enabled
- `BranchViewSet` - Returns empty queryset if disabled

## Frontend Implementation

### BranchSelector Component

- Checks module settings on mount
- Only renders if `multi_branch_support` feature is enabled
- Returns `null` if disabled (component hidden)

### API Response

The modules API now includes branch support status:

```json
{
  "settings": {
    "features": {
      "multi_branch_support": {
        "is_enabled": false,
        "feature_name": "Multi-Branch Support",
        ...
      }
    }
  },
  "_meta": {
    "branch_support_enabled": false
  }
}
```

## Database

The feature is stored in:
- **Table:** `accounts_modulefeature`
- **Module:** `settings`
- **Feature Key:** `multi_branch_support`
- **Default:** `is_enabled = False`

## Testing

1. **With Branch Support Disabled (Default):**
   - Login → No branch selector visible
   - Create sale → Works without branch
   - All operations work at tenant level

2. **With Branch Support Enabled:**
   - Enable in Module Settings
   - Refresh page → Branch selector appears
   - Create branch → Works normally
   - Create sale → Requires branch selection

## Summary

✅ Branches are **optional** - controlled by module setting  
✅ **Disabled by default** - system works without branches  
✅ Super admin can **enable/disable** via checkbox  
✅ Frontend **automatically shows/hides** branch selector  
✅ Backend **conditionally requires** branches based on setting  
