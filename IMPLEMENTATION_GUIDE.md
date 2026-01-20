# Complete Implementation Guide: Service Layer & 90% Test Coverage

## Overview
This guide provides step-by-step instructions to refactor all 14 backend modules, extract business logic to services, and achieve 90%+ test coverage.

## Architecture

### Service Layer Pattern
```
be/services/
├── base.py              # BaseService, QueryService
├── products_service.py  # ✅ Complete
├── sales_service.py     # ✅ Started
└── {module}_service.py  # For each module
```

### Test Structure
```
be/{module}/tests/
├── test_services.py     # Unit tests for services
├── test_views.py        # Integration tests for views
├── test_models.py       # Model tests
└── test_serializers.py  # Serializer tests
```

## Step-by-Step Implementation

### For Each Module:

#### Step 1: Analyze Views
```bash
# Identify all business logic in views
grep -n "def\|@action\|\.objects\." be/{module}/views.py
```

#### Step 2: Create Service
```python
# be/services/{module}_service.py
from services.base import BaseService
from {module}.models import Model1, Model2

class Model1Service(BaseService):
    def __init__(self):
        super().__init__(Model1)
    
    # Extract methods from views
    def create_with_validation(self, data):
        # Validation logic
        # Business rules
        # Database operations
        return self.create(data)
    
    def complex_query(self, filters):
        # Complex query logic
        return self.list(filters)
```

#### Step 3: Refactor Views
```python
# be/{module}/views.py
from services.{module}_service import Model1Service

class Model1ViewSet(viewsets.ModelViewSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = Model1Service()
    
    def perform_create(self, serializer):
        # Use service instead of direct model operations
        validated_data = serializer.validated_data
        instance = self.service.create_with_validation(validated_data)
        serializer.instance = instance
```

#### Step 4: Write Tests

**Service Tests (test_services.py)**
```python
class Model1ServiceTestCase(TestCase):
    def setUp(self):
        self.service = Model1Service()
    
    def test_create_success(self):
        data = {...}
        instance = self.service.create(data)
        self.assertIsNotNone(instance.id)
    
    def test_create_validation_error(self):
        data = {...}  # Invalid data
        with self.assertRaises(ValidationError):
            self.service.create(data)
    
    def test_update_success(self):
        instance = Model1.objects.create(...)
        data = {...}
        updated = self.service.update(instance, data)
        self.assertEqual(updated.field, data['field'])
    
    def test_delete_success(self):
        instance = Model1.objects.create(...)
        result = self.service.delete(instance)
        self.assertTrue(result)
        self.assertFalse(Model1.objects.filter(id=instance.id).exists())
```

**View Tests (test_views.py)**
```python
class Model1ViewSetTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(...)
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
    
    def test_list_authenticated(self):
        response = self.client.get('/api/{module}/')
        self.assertEqual(response.status_code, 200)
    
    def test_create_success(self):
        data = {...}
        response = self.client.post('/api/{module}/', data, format='json')
        self.assertEqual(response.status_code, 201)
    
    def test_create_unauthorized(self):
        self.client.credentials()  # Remove auth
        response = self.client.post('/api/{module}/', {}, format='json')
        self.assertEqual(response.status_code, 401)
```

## Module-Specific Implementation

### Products Module ✅
- **Status**: Complete
- **Service**: ✅ ProductService, CategoryService, SizeService, ColorService, ProductVariantService
- **Tests**: ✅ 29+ service tests, 40+ view tests
- **Coverage**: ⏳ Run coverage analysis

### Sales Module (Next)
**Service Methods Needed:**
- `create_sale()` - Complex sale creation with items, stock updates, wallet handling
- `validate_sale_items()` - Stock validation
- `create_invoice_from_sale()` - Invoice creation
- `create_payment()` - Payment processing
- `get_sale_statistics()` - Statistics aggregation

**Test Coverage:**
- Sale creation (POS, Normal)
- Stock validation
- Wallet transactions
- Invoice creation
- Payment processing
- Error handling (insufficient stock, invalid data)
- Edge cases (empty cart, zero amounts, etc.)

### Accounting Module (Critical)
**Service Methods Needed:**
- `create_sale_journal_entry()` - Extract from views
- `create_expense_journal_entry()` - Extract from views
- `create_payment_journal_entry()` - Extract from views
- `generate_balance_sheet()` - Report generation
- `generate_trial_balance()` - Report generation
- `generate_income_statement()` - Report generation
- `validate_transaction_balance()` - Validation

**Test Coverage:**
- Journal entry creation
- Transaction balancing (debits = credits)
- Report generation
- Account balance calculations
- Error handling

### Expenses Module
**Service Methods Needed:**
- `create_expense()` - Expense creation
- `validate_expense()` - Validation
- `get_expense_statistics()` - Statistics

**Test Coverage:**
- Expense creation
- Category validation
- Amount validation
- Payment method handling
- Status transitions

### Inventory Module
**Service Methods Needed:**
- `create_stock_movement()` - Stock movement creation
- `update_stock()` - Stock updates
- `get_stock_history()` - Stock history
- `validate_stock_availability()` - Stock validation

**Test Coverage:**
- Stock movements (sale, purchase, adjustment, etc.)
- Stock updates
- Low stock detection
- Out of stock detection

## Test Coverage Checklist

For each module, ensure tests cover:

### Database Operations
- [ ] INSERT (create operations)
- [ ] SELECT (read, list, filter, search)
- [ ] UPDATE (update, partial_update, bulk_update)
- [ ] DELETE (delete, bulk_delete)
- [ ] Foreign key relationships
- [ ] Unique constraints
- [ ] Index usage
- [ ] Transaction rollback

### Error Handling
- [ ] ValidationError
- [ ] DoesNotExist (404)
- [ ] PermissionDenied (403)
- [ ] AuthenticationRequired (401)
- [ ] Database errors
- [ ] Business logic errors

### Edge Cases
- [ ] Empty data
- [ ] Null values
- [ ] Invalid types
- [ ] Boundary values
- [ ] Large datasets
- [ ] Concurrent operations

### View Navigation
- [ ] List endpoint
- [ ] Detail endpoint
- [ ] Create endpoint
- [ ] Update endpoint
- [ ] Delete endpoint
- [ ] Custom actions
- [ ] Filtering
- [ ] Pagination
- [ ] Ordering
- [ ] Search

## Running Coverage Analysis

```bash
# Install coverage
docker-compose exec backend pip install coverage

# Run tests with coverage
docker-compose exec backend coverage run --source='.' manage.py test

# Generate report
docker-compose exec backend coverage report

# Generate HTML report
docker-compose exec backend coverage html
# View: htmlcov/index.html

# Check specific module
docker-compose exec backend coverage run --source='products' manage.py test products
docker-compose exec backend coverage report
```

## Quick Start Commands

```bash
# Test products module
docker-compose exec backend python manage.py test products --verbosity=2

# Test with coverage
docker-compose exec backend coverage run --source='products' manage.py test products
docker-compose exec backend coverage report -m

# Test specific test class
docker-compose exec backend python manage.py test products.tests.test_services.ProductServiceTestCase

# Test specific test method
docker-compose exec backend python manage.py test products.tests.test_services.ProductServiceTestCase.test_create_product_success
```

## Priority Order

1. ✅ **Products** - Complete (template)
2. **Sales** - Critical (core business)
3. **Accounting** - Critical (financial integrity)
4. **Expenses** - Important
5. **Inventory** - Important
6. **Accounts** - Important
7. **Suppliers** - Medium
8. **Employees** - Medium
9. **Settings** - Medium
10. **Income** - Low
11. **Bank Accounts** - Low
12. **Transfers** - Low
13. **Barcodes** - Low
14. **Reports** - Low

## Notes

- Services are stateless (no instance state)
- Views are thin (HTTP handling only)
- Tests are independent (no shared state)
- Use factories for test data
- Mock external dependencies
- Test both success and failure paths
- Cover all code paths (branches, conditions)
