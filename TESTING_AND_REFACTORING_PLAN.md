# Comprehensive Testing and Refactoring Plan

## Overview
This document outlines the systematic approach to refactor all backend modules, extract business logic to services, and achieve 90%+ test coverage.

## Architecture Changes

### Service Layer Structure
```
be/services/
├── __init__.py
├── base.py                    # Base service classes
├── products_service.py        # Product business logic
├── sales_service.py           # Sales business logic
├── accounting_service.py      # Accounting business logic
├── expenses_service.py        # Expenses business logic
├── inventory_service.py       # Inventory business logic
├── accounts_service.py         # Accounts/Users business logic
├── suppliers_service.py        # Suppliers business logic
├── employees_service.py        # Employees business logic
└── settings_service.py         # Settings business logic
```

### Test Structure
```
be/{module}/tests/
├── __init__.py
├── test_services.py          # Unit tests for services
├── test_views.py             # Integration tests for views
├── test_models.py            # Model tests
└── test_serializers.py       # Serializer tests
```

## Modules to Refactor (14 modules)

1. ✅ **products** - In progress
2. **sales** - Next
3. **accounting** - Critical
4. **expenses** - Critical
5. **inventory** - Critical
6. **accounts** - Critical
7. **suppliers** - Medium
8. **employees** - Medium
9. **settings** - Medium
10. **income** - Low
11. **bankaccounts** - Low
12. **transfers** - Low
13. **barcodes** - Low
14. **reports** - Low

## Refactoring Pattern

### Step 1: Create Service Layer
- Extract business logic from views
- Create service classes inheriting from BaseService
- Implement all CRUD operations
- Add complex query methods
- Add validation logic

### Step 2: Update Views
- Inject service instances in ViewSet __init__
- Delegate business logic to services
- Keep views thin (only HTTP handling)
- Maintain serializer usage for validation

### Step 3: Write Comprehensive Tests

#### Service Tests (Unit Tests)
- Test all service methods
- Test edge cases
- Test error handling
- Test validation logic
- Test database operations (inserts, selects, updates, deletes)

#### View Tests (Integration Tests)
- Test all API endpoints
- Test authentication/authorization
- Test request/response formats
- Test error responses
- Test pagination, filtering, ordering
- Test bulk operations

#### Model Tests
- Test model properties
- Test model methods
- Test model validation
- Test relationships

#### Serializer Tests
- Test serialization
- Test deserialization
- Test validation
- Test field transformations

## Test Coverage Goals

### Minimum Coverage per Module: 90%

#### Critical Paths (100% coverage):
- Create operations
- Update operations
- Delete operations
- Validation logic
- Error handling
- Database transactions

#### Important Paths (95% coverage):
- List/retrieve operations
- Filtering and search
- Bulk operations
- Statistics/aggregations

#### Standard Paths (90% coverage):
- Helper methods
- Utility functions
- Edge cases

## Testing Checklist per Module

### Database Operations
- [ ] Insert operations (create)
- [ ] Select operations (read, list, filter)
- [ ] Update operations (update, partial_update)
- [ ] Delete operations (delete, bulk_delete)
- [ ] Transaction rollback on errors
- [ ] Foreign key constraints
- [ ] Unique constraints
- [ ] Index usage

### Error Handling
- [ ] Validation errors
- [ ] Not found errors (404)
- [ ] Permission errors (403)
- [ ] Authentication errors (401)
- [ ] Database errors
- [ ] Business logic errors

### Edge Cases
- [ ] Empty data
- [ ] Null values
- [ ] Invalid data types
- [ ] Boundary values
- [ ] Large datasets
- [ ] Concurrent operations
- [ ] Race conditions

### View Navigation
- [ ] List endpoint
- [ ] Detail endpoint
- [ ] Create endpoint
- [ ] Update endpoint
- [ ] Delete endpoint
- [ ] Custom actions (@action)
- [ ] Filtering
- [ ] Pagination
- [ ] Ordering
- [ ] Search

## Implementation Status

### Products Module
- [x] Service layer created
- [x] Views refactored to use services
- [x] Service tests created
- [x] View tests created
- [ ] Run coverage analysis
- [ ] Achieve 90%+ coverage

### Next: Sales Module
- [ ] Create sales_service.py
- [ ] Extract sale creation logic
- [ ] Extract payment logic
- [ ] Extract invoice logic
- [ ] Extract stock movement logic
- [ ] Refactor SaleViewSet
- [ ] Write comprehensive tests
- [ ] Achieve 90%+ coverage

## Running Tests

```bash
# Run all tests
docker-compose exec backend python manage.py test

# Run specific module tests
docker-compose exec backend python manage.py test products

# Run with coverage
docker-compose exec backend coverage run --source='.' manage.py test
docker-compose exec backend coverage report
docker-compose exec backend coverage html
```

## Coverage Analysis

After each module:
1. Run coverage analysis
2. Identify gaps
3. Add missing tests
4. Verify 90%+ coverage
5. Document any exceptions

## Notes

- Services should be stateless where possible
- Use dependency injection for services in views
- Keep services focused on single responsibility
- Tests should be independent and isolated
- Use factories/fixtures for test data
- Mock external dependencies
