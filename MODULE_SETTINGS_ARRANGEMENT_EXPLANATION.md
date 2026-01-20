# Module Settings Arrangement Explanation

## How Modules Are Organized

### Step 1: Categorization (`getModuleCategory` function)
Modules are grouped into categories based on their `module_name`:

**Core Business Operations:**
- `products`, `sales`, `customers`, `invoicing`, `inventory`, `stock`

**Financial Management:**
- `expenses`, `income`, `bank_accounts`, `money_transfer`

**Accounting:**
- `accounting`, `balance_sheet`, `trial_balance`, `cash_flow`, `account_statement`

**Reporting:**
- `reports`

**Tools & Utilities:**
- `barcodes`

**System Administration:**
- `settings`

**Supplier Management:**
- `suppliers`

**Other:**
- Any module not matching above categories

---

### Step 2: Sorting Within Categories

**Accounting** (lines 376-387):
```javascript
Order: accounting → balance_sheet → trial_balance → cash_flow → account_statement
```

**Core Business Operations** (lines 389-403):
```javascript
Order: products → inventory → sales → customers → invoicing → stock
```
*Note: The comment says "3-column distribution" but the CSS shows vertical stacking*

**Financial Management** (lines 405-415):
```javascript
Order: expenses → income → bank_accounts → money_transfer
```

**Other categories:** No specific sorting (uses default alphabetical)

---

### Step 3: Display Layout (CSS)

**Main Container** (`.module-settings-content`):
- Uses `grid` with `repeat(auto-fit, minmax(400px, 1fr))`
- This creates responsive columns that auto-fit based on screen size
- On screens ≥1400px: 2 columns
- On screens <900px: 1 column
- Gap between categories: `0.875rem`

**Within Each Category** (`.modules-list`):
- Uses `flex-direction: column` (vertical stacking)
- Modules appear one below another
- Gap between modules: `0.625rem`

**Special Case - Accounting:**
- Spans full width: `grid-column: 1 / -1`
- Takes up all available columns

---

## Current Display Flow

```
┌─────────────────────────────────────────────────────────┐
│  Module Settings Header                                 │
└─────────────────────────────────────────────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌──────────┐
│ Core Business     │  │ Financial         │  │ Reporting │
│ Operations        │  │ Management       │  │           │
│                   │  │                  │  │           │
│ • Products        │  │ • Expenses       │  │ • Reports │
│ • Inventory       │  │ • Income         │  │           │
│ • Sales           │  │ • Bank Accounts  │  │           │
│ • Customers       │  │ • Money Transfer │  │           │
│ • Invoicing       │  │                  │  │           │
│ • Stock           │  │                  │  │           │
└──────────────────┘  └──────────────────┘  └──────────┘

┌─────────────────────────────────────────────────────────┐
│ Accounting (spans full width)                           │
│                                                          │
│ • Accounting                                             │
│ • Balance Sheet                                          │
│ • Trial Balance                                          │
│ • Cash Flow                                              │
│ • Account Statement                                      │
└─────────────────────────────────────────────────────────┘

┌──────────┐  ┌──────────┐  ┌──────────┐
│ Tools &  │  │ Supplier │  │ System   │
│ Utilities│  │ Mgmt     │  │ Admin    │
│          │  │          │  │          │
│ • Barcodes│  │ • Suppliers│ │ • Settings│
└──────────┘  └──────────┘  └──────────┘
```

---

## Issues You Might Be Seeing

1. **Core Business Operations order doesn't match comment:**
   - Comment says "Column 1: products, customers / Column 2: inventory, invoicing / Column 3: sales, stock"
   - But CSS uses vertical stacking, so it's just: products → inventory → sales → customers → invoicing → stock

2. **Accounting takes full width:**
   - This might make other categories look unbalanced

3. **No horizontal module layout:**
   - All modules stack vertically within categories
   - If you wanted side-by-side modules, you'd need to change `.modules-list` to use `grid` instead of `flex-direction: column`

---

## How to Rearrange

### To Change Module Order Within a Category:
Edit the sorting arrays in `ModuleSettings.js` (lines 376-415)

Example - Change Core Business Operations order:
```javascript
// Current:
const coreOrder = ['products', 'inventory', 'sales', 'customers', 'invoicing', 'stock'];

// Change to:
const coreOrder = ['products', 'customers', 'inventory', 'invoicing', 'sales', 'stock'];
```

### To Change Category Grouping:
Edit the `getModuleCategory` function (lines 335-365)

Example - Move 'invoicing' to Financial Management:
```javascript
// In Financial Management section, add:
if (['expenses', 'income', 'bank_accounts', 'money_transfer', 'invoicing'].includes(moduleName)) {
  return 'Financial Management';
}

// Remove 'invoicing' from Core Business Operations:
if (['products', 'sales', 'customers', 'inventory', 'stock'].includes(moduleName)) {
  return 'Core Business Operations';
}
```

### To Change Layout (Side-by-Side Modules):
Edit `ModuleSettings.css` - change `.modules-list`:
```css
.modules-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr); /* 2 columns */
  gap: 0.625rem;
}
```

### To Change Main Grid Layout:
Edit `.module-settings-content` in CSS:
```css
.module-settings-content {
  grid-template-columns: repeat(3, 1fr); /* Force 3 columns */
  /* or */
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); /* Smaller min width */
}
```

---

## Key Files

- **JavaScript Logic:** `fe/src/components/ModuleSettings/ModuleSettings.js`
  - Lines 335-365: Category assignment
  - Lines 376-415: Sorting within categories
  - Lines 533-539: Rendering categories

- **CSS Layout:** `fe/src/components/ModuleSettings/ModuleSettings.css`
  - Lines 35-52: Main grid layout
  - Lines 121-126: Module list layout (vertical)
  - Lines 133-136: Accounting special case
