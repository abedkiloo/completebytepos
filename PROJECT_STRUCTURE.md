# CompleteBytePOS - Project Structure

## Recommended Folder Structure (Phase 1)

```
CompleteBytePOS/
├── backend/                          # Django backend
│   ├── config/                      # Django project settings
│   │   ├── __init__.py
│   │   ├── settings.py             # Main settings
│   │   ├── urls.py                 # Root URL configuration
│   │   └── wsgi.py                 # WSGI config
│   │
│   ├── products/                   # Products app
│   │   ├── __init__.py
│   │   ├── models.py               # Product, Category models
│   │   ├── serializers.py          # Product serializers
│   │   ├── views.py                # Product views/viewsets
│   │   ├── urls.py                 # Product URLs
│   │   ├── admin.py                # Admin interface
│   │   └── migrations/             # Database migrations
│   │
│   ├── sales/                      # Sales app
│   │   ├── __init__.py
│   │   ├── models.py               # Sale, SaleItem models
│   │   ├── serializers.py          # Sale serializers
│   │   ├── views.py                # Sale views/viewsets
│   │   ├── urls.py                 # Sale URLs
│   │   ├── admin.py
│   │   └── migrations/
│   │
│   ├── inventory/                  # Inventory app
│   │   ├── __init__.py
│   │   ├── models.py               # StockMovement model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── migrations/
│   │
│   ├── accounts/                    # Authentication app
│   │   ├── __init__.py
│   │   ├── models.py               # Extended User model (if needed)
│   │   ├── serializers.py
│   │   ├── views.py                # Login, logout views
│   │   ├── urls.py
│   │   └── migrations/
│   │
│   ├── reports/                     # Reports app (optional)
│   │   ├── __init__.py
│   │   ├── views.py                # Report generation
│   │   └── urls.py
│   │
│   ├── manage.py                    # Django management script
│   ├── requirements.txt             # Python dependencies
│   ├── db.sqlite3                   # SQLite database (created after migrate)
│   └── .env                         # Environment variables (optional)
│
├── frontend/                        # React frontend
│   ├── public/
│   │   ├── index.html
│   │   └── favicon.ico
│   │
│   ├── src/
│   │   ├── components/
│   │   │   ├── POS/
│   │   │   │   ├── ProductGrid.jsx
│   │   │   │   ├── ProductSearch.jsx
│   │   │   │   ├── Cart.jsx
│   │   │   │   ├── PaymentModal.jsx
│   │   │   │   └── ReceiptPreview.jsx
│   │   │   │
│   │   │   ├── Products/
│   │   │   │   ├── ProductList.jsx
│   │   │   │   ├── ProductForm.jsx
│   │   │   │   └── CategoryManager.jsx
│   │   │   │
│   │   │   ├── Sales/
│   │   │   │   ├── SaleList.jsx
│   │   │   │   └── SaleDetail.jsx
│   │   │   │
│   │   │   ├── Inventory/
│   │   │   │   ├── StockList.jsx
│   │   │   │   └── StockAdjustment.jsx
│   │   │   │
│   │   │   ├── Reports/
│   │   │   │   ├── Dashboard.jsx
│   │   │   │   └── SalesReport.jsx
│   │   │   │
│   │   │   └── Auth/
│   │   │       ├── Login.jsx
│   │   │       └── ProtectedRoute.jsx
│   │   │
│   │   ├── services/
│   │   │   ├── api.js               # API client configuration
│   │   │   └── auth.js              # Authentication service
│   │   │
│   │   ├── utils/
│   │   │   ├── formatters.js       # Currency, date formatters
│   │   │   └── validators.js       # Form validators
│   │   │
│   │   ├── App.jsx                  # Main app component
│   │   ├── index.js                 # Entry point
│   │   └── index.css                # Global styles
│   │
│   ├── package.json                 # Node dependencies
│   └── .env                         # Frontend environment variables
│
├── docs/                            # Documentation
│   ├── README.md
│   ├── QUICKSTART.md
│   ├── PHASE1_ONPREMISE.md
│   ├── SUMMARY.md
│   └── MARKET_EVALUATION.md
│
├── .gitignore                       # Git ignore file
└── README.md                        # Main project README
```

## Key Files to Create First

### Backend Priority Order:
1. `backend/config/settings.py` - Configure Django
2. `backend/products/models.py` - Product model
3. `backend/sales/models.py` - Sale model
4. `backend/products/serializers.py` - API serializers
5. `backend/products/views.py` - API views
6. `backend/config/urls.py` - URL routing

### Frontend Priority Order:
1. `frontend/src/services/api.js` - API client
2. `frontend/src/components/Auth/Login.jsx` - Login page
3. `frontend/src/components/POS/ProductSearch.jsx` - Product search
4. `frontend/src/components/POS/Cart.jsx` - Shopping cart
5. `frontend/src/components/POS/PaymentModal.jsx` - Payment processing

## Database Models Relationship

```
User (Django built-in)
  └── Sale (cashier)
      └── SaleItem (items in sale)
          └── Product

Product
  ├── Category
  └── StockMovement

StockMovement
  └── Product
```

## API Endpoint Structure

```
/api/
├── auth/
│   ├── login/
│   └── logout/
│
├── products/
│   ├── categories/
│   ├── search/?q=query
│   └── {id}/
│
├── sales/
│   ├── {id}/
│   └── {id}/receipt/
│
└── inventory/
    ├── low-stock/
    └── adjust/
```

## Component Hierarchy (Frontend)

```
App
├── Router
│   ├── Login (public)
│   └── Protected Routes
│       ├── POS
│       │   ├── ProductSearch
│       │   ├── ProductGrid
│       │   ├── Cart
│       │   ├── PaymentModal
│       │   └── ReceiptPreview
│       │
│       ├── Products
│       │   ├── ProductList
│       │   └── ProductForm
│       │
│       ├── Sales
│       │   ├── SaleList
│       │   └── SaleDetail
│       │
│       ├── Inventory
│       │   ├── StockList
│       │   └── StockAdjustment
│       │
│       └── Reports
│           ├── Dashboard
│           └── SalesReport
```

## Development Workflow

1. **Backend First**: Create models → serializers → views → URLs
2. **Test API**: Use Postman or curl to test endpoints
3. **Frontend**: Create components → Connect to API → Test flow
4. **Integration**: Test complete user flows

## File Naming Conventions

- **Models**: `models.py` (singular: Product, Sale)
- **Serializers**: `serializers.py` (ProductSerializer, SaleSerializer)
- **Views**: `views.py` (ProductViewSet, SaleViewSet)
- **URLs**: `urls.py`
- **React Components**: PascalCase (ProductGrid.jsx, Cart.jsx)
- **Services**: camelCase (api.js, auth.js)

## Important Notes

- **SQLite Database**: `db.sqlite3` is created automatically after first migration
- **Migrations**: Run `python manage.py makemigrations` after model changes
- **Static Files**: Django serves static files in development automatically
- **CORS**: Configured in `settings.py` for React frontend
- **Environment**: Use `.env` files for sensitive data (not committed to git)

