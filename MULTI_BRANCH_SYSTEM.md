# Multi-Branch System Implementation

## Overview
The CompleteByte POS system now supports multiple branches/locations. All transactions, sales, inventory, expenses, and income are attached to specific branches, while maintaining an overall view that contains all branches.

## Backend Implementation

### 1. Branch Model (`be/settings/models.py`)
- **Branch** model with fields:
  - `branch_code`: Unique identifier
  - `name`: Branch name
  - `address`, `city`, `country`: Location details
  - `phone`, `email`: Contact information
  - `is_active`: Active status
  - `is_headquarters`: Mark one branch as HQ
  - `manager`: Branch manager (User FK)
  - `created_by`: Creator tracking

### 2. Branch Integration in Models
Branch foreign keys added to:
- **Sale**: `branch` field (required for sales)
- **Invoice**: `branch` field (required for invoices)
- **Customer**: `branch` field (optional - customers can be shared)
- **StockMovement**: `branch` field (required for inventory movements)
- **Expense**: `branch` field (required for expenses)
- **Income**: `branch` field (required for income)

### 3. Branch Management API (`be/settings/views.py`)
- **BranchViewSet**: Full CRUD operations
- Endpoints:
  - `GET /api/settings/branches/` - List all branches
  - `GET /api/settings/branches/active/` - Get active branches
  - `GET /api/settings/branches/headquarters/` - Get HQ branch
  - `POST /api/settings/branches/{id}/set_current/` - Set current branch
  - `POST /api/settings/branches/clear_current/` - Clear current (show all)

### 4. Branch Filtering in Viewsets
All viewsets now filter by branch:
- **SaleViewSet**: Filters sales by branch
- **InvoiceViewSet**: Filters invoices by branch
- **ExpenseViewSet**: Filters expenses by branch
- **IncomeViewSet**: Filters income by branch
- **StockMovementViewSet**: Filters stock movements by branch
- **CustomerViewSet**: Optional branch filtering (customers can be shared)

### 5. Branch Utility Functions (`be/settings/utils.py`)
- `get_current_branch(request)`: Gets current branch from session/header/query
- `set_current_branch(request, branch)`: Sets branch in session

## Frontend Implementation

### 1. Branch Selector Component (`fe/src/components/BranchSelector/`)
- Dropdown component for branch selection
- Shows current branch in header/navbar
- Supports "All Branches" view for super admins
- Automatically loads and sets default branch (HQ or first active)

### 2. Branch Management UI (`fe/src/components/Branches/`)
- Full CRUD interface for branch management
- Accessible from Settings menu (super admins only)
- Features:
  - Create/Edit/Delete branches
  - Set branch as headquarters
  - Assign branch managers
  - Search and filter branches

### 3. Integration Points
- **Layout Header**: Branch selector in top right
- **POS Topbar**: Branch selector in center navigation
- **Settings Menu**: Branch Management link (super admins)

## Features

### Branch Selection
1. **Automatic Selection**: System defaults to headquarters or first active branch
2. **Session Persistence**: Selected branch stored in session and localStorage
3. **Header Integration**: Branch selector visible in all views
4. **Global View**: Super admins can select "All Branches" to see everything

### Data Filtering
- All data automatically filtered by selected branch
- Sales, invoices, expenses, income, and inventory movements are branch-specific
- Customers can be shared across branches (optional)
- Products are shared but stock is branch-specific

### Branch Management
- Create unlimited branches
- Mark one branch as headquarters
- Assign managers to branches
- Activate/deactivate branches
- Search and filter branches

## API Usage

### Setting Current Branch
```javascript
// Set specific branch
await branchesAPI.setCurrent(branchId);

// Clear to show all branches
await branchesAPI.clearCurrent();
```

### Branch in Requests
The branch ID is automatically included in request headers:
- Header: `X-Branch-ID: {branch_id}`
- Session: `current_branch_id` stored in Django session

## Database Migrations

Run migrations to add branch fields:
```bash
python manage.py migrate
```

Migrations created:
- `settings/migrations/0002_branch.py` - Branch model
- `sales/migrations/0006_*.py` - Branch fields in sales models
- `expenses/migrations/0002_*.py` - Branch field in expenses
- `income/migrations/0002_*.py` - Branch field in income
- `inventory/migrations/0004_*.py` - Branch field in stock movements

## Usage Flow

1. **Initial Setup**: Create branches via Branch Management UI
2. **Set Headquarters**: Mark one branch as HQ (default branch)
3. **Branch Selection**: Users select branch from header dropdown
4. **Data Entry**: All new transactions automatically assigned to current branch
5. **Viewing Data**: Data filtered by selected branch automatically
6. **Global View**: Super admins can select "All Branches" to see everything

## Notes

- **Backward Compatibility**: Existing data without branches will work (branch can be null)
- **Default Behavior**: If no branch selected, defaults to headquarters
- **Session Management**: Branch selection persists across page reloads
- **Multi-Branch Reports**: Use "All Branches" view for consolidated reporting
