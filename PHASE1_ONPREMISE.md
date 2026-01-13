# Phase 1: On-Premise Basic Features

## 🎯 Overview

This document outlines the **basic features** for Phase 1, designed for **on-premise deployment on a local computer**. All data will be stored locally on the machine.

## 🏗️ Architecture Adjustments for On-Premise

### Simplified Tech Stack
- **Backend**: Django + SQLite (or PostgreSQL if preferred)
- **Frontend**: React (single-page application)
- **Database**: SQLite (simple, no setup) or PostgreSQL (if multi-tenant needed)
- **Deployment**: Single executable or local web server
- **No Cloud Services**: No Redis, Celery, or external services initially

### Key Differences from Cloud Version
- ✅ **Simpler**: No multi-tenancy complexity (single business per installation)
- ✅ **Faster Setup**: SQLite requires no database server
- ✅ **Offline by Default**: Always works offline
- ✅ **Lower Cost**: No cloud infrastructure needed
- ✅ **Privacy**: All data stays on local machine

---

## 📋 Phase 1: Basic Features (MVP)

### Core POS Functionality

#### 1. Product Management ✅
- [ ] Create Product model
- [ ] Add/Edit/Delete products
- [ ] Product search (by name, SKU)
- [ ] Product categories
- [ ] Product pricing
- [ ] Product images (optional)

#### 2. Sales Module ✅
- [ ] Create Sale model
- [ ] Create SaleItem model
- [ ] Add products to cart
- [ ] Remove products from cart
- [ ] Calculate subtotal
- [ ] Calculate total
- [ ] Process sale
- [ ] Sale history/view

#### 3. Basic Inventory ✅
- [ ] Track product stock
- [ ] Stock levels per product
- [ ] Reduce stock on sale
- [ ] Low stock alerts (optional)
- [ ] Stock adjustment (add/remove)

#### 4. Basic Receipts ✅
- [ ] Generate receipt on sale
- [ ] Print receipt (simple text/HTML)
- [ ] Receipt template
- [ ] Receipt history

#### 5. Basic Reporting ✅
- [ ] Daily sales report
- [ ] Sales by product
- [ ] Sales summary
- [ ] Export to CSV/Excel (optional)

#### 6. User Management ✅
- [ ] User login/logout
- [ ] User roles (Admin, Cashier)
- [ ] Basic permissions
- [ ] User activity tracking

---

## 🗄️ Database Schema (Simplified)

### Core Models

```python
# apps/core/models.py
class User(AbstractUser):
    """Extended user model"""
    role = models.CharField(max_length=20, choices=[
        ('admin', 'Admin'),
        ('cashier', 'Cashier'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)

class Category(models.Model):
    """Product categories"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Product(models.Model):
    """Products"""
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=50, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['name']),
        ]

class Sale(models.Model):
    """Sales transactions"""
    sale_number = models.CharField(max_length=50, unique=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=[
        ('cash', 'Cash'),
        ('mpesa', 'M-PESA'),
        ('card', 'Card'),
    ])
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    change = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['sale_number']),
        ]

class SaleItem(models.Model):
    """Items in a sale"""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

class StockMovement(models.Model):
    """Inventory movements"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=[
        ('sale', 'Sale'),
        ('purchase', 'Purchase'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
    ])
    quantity = models.IntegerField()  # Positive for add, negative for remove
    reference = models.CharField(max_length=100, blank=True)  # Sale number, PO number, etc.
    notes = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['product', 'created_at']),
        ]
```

---

## 🎨 Frontend Structure (Basic)

### POS Interface Components

```
src/
├── components/
│   ├── POS/
│   │   ├── ProductGrid.jsx       # Product display grid
│   │   ├── ProductSearch.jsx     # Search bar
│   │   ├── Cart.jsx              # Shopping cart
│   │   ├── PaymentModal.jsx      # Payment processing
│   │   └── ReceiptPreview.jsx    # Receipt display
│   ├── Products/
│   │   ├── ProductList.jsx       # Product management
│   │   ├── ProductForm.jsx       # Add/Edit product
│   │   └── CategoryManager.jsx   # Category management
│   ├── Sales/
│   │   ├── SaleList.jsx          # Sales history
│   │   └── SaleDetail.jsx        # Sale details
│   ├── Inventory/
│   │   ├── StockList.jsx         # Stock levels
│   │   └── StockAdjustment.jsx   # Adjust stock
│   ├── Reports/
│   │   ├── SalesReport.jsx       # Sales reports
│   │   └── Dashboard.jsx        # Dashboard
│   └── Auth/
│       ├── Login.jsx             # Login page
│       └── ProtectedRoute.jsx    # Route protection
├── services/
│   ├── api.js                    # API client
│   └── auth.js                   # Authentication
└── App.jsx                       # Main app
```

---

## 🔌 API Endpoints (Basic)

### Products
```
GET    /api/products/              # List products
POST   /api/products/              # Create product
GET    /api/products/:id/          # Get product
PUT    /api/products/:id/          # Update product
DELETE /api/products/:id/          # Delete product
GET    /api/products/search/?q=    # Search products
```

### Sales
```
GET    /api/sales/                 # List sales
POST   /api/sales/                 # Create sale
GET    /api/sales/:id/             # Get sale
GET    /api/sales/:id/receipt/    # Get receipt
```

### Inventory
```
GET    /api/inventory/             # List stock levels
POST   /api/inventory/adjust/      # Adjust stock
GET    /api/inventory/low-stock/   # Low stock alerts
```

### Reports
```
GET    /api/reports/sales/         # Sales report
GET    /api/reports/products/      # Product sales
GET    /api/reports/dashboard/     # Dashboard data
```

---

## 🚀 Implementation Steps

### Step 1: Project Setup (Week 1)
- [ ] Initialize Django project
- [ ] Initialize React project
- [ ] Set up SQLite database
- [ ] Configure Django REST Framework
- [ ] Set up authentication (JWT or Session)
- [ ] Create basic folder structure

### Step 2: Core Models (Week 1)
- [ ] Create User model (extend AbstractUser)
- [ ] Create Category model
- [ ] Create Product model
- [ ] Create Sale model
- [ ] Create SaleItem model
- [ ] Create StockMovement model
- [ ] Run migrations

### Step 3: Basic API (Week 2)
- [ ] Product CRUD endpoints
- [ ] Sale creation endpoint
- [ ] Sale list endpoint
- [ ] Stock management endpoints
- [ ] Authentication endpoints
- [ ] Test all endpoints

### Step 4: POS Interface (Week 3)
- [ ] Product search component
- [ ] Product grid display
- [ ] Shopping cart component
- [ ] Payment modal
- [ ] Receipt preview
- [ ] Connect to API

### Step 5: Product Management (Week 3)
- [ ] Product list page
- [ ] Add/Edit product form
- [ ] Category management
- [ ] Image upload (optional)
- [ ] Connect to API

### Step 6: Sales History (Week 4)
- [ ] Sales list page
- [ ] Sale detail page
- [ ] Receipt reprint
- [ ] Sales filtering
- [ ] Connect to API

### Step 7: Inventory (Week 4)
- [ ] Stock levels display
- [ ] Stock adjustment form
- [ ] Low stock alerts
- [ ] Stock movement history
- [ ] Connect to API

### Step 8: Reports (Week 5)
- [ ] Dashboard component
- [ ] Sales report
- [ ] Product sales report
- [ ] Export functionality (optional)
- [ ] Connect to API

### Step 9: Testing & Polish (Week 5-6)
- [ ] Test all features
- [ ] Fix bugs
- [ ] UI/UX improvements
- [ ] Performance optimization
- [ ] User documentation

---

## 💾 Database Configuration

### SQLite (Recommended for Phase 1)

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

**Advantages:**
- No database server needed
- Single file, easy backup
- Perfect for single-computer deployment
- Zero configuration

**Limitations:**
- Not ideal for high concurrency (but fine for single user/small team)
- File size limit (but fine for Phase 1)

### PostgreSQL (If Needed Later)

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'completebytepos',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

## 🔐 Authentication (Simplified)

### Option 1: Session Authentication (Simplest)
```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

### Option 2: JWT (If Needed)
```python
# Install: pip install djangorestframework-simplejwt
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}
```

---

## 📦 Deployment Options

### Option 1: Local Web Server
```bash
# Backend
python manage.py runserver 0.0.0.0:8000

# Frontend
npm start
# Or build and serve:
npm run build
npx serve -s build
```

### Option 2: Single Executable (Future)
- Use PyInstaller for Django backend
- Use Electron for React frontend
- Package as single application

### Option 3: Docker (Optional)
```dockerfile
# Simple Docker setup for easy deployment
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

---

## 🎯 Success Criteria

### Functional Requirements
- ✅ Can add products
- ✅ Can process sales
- ✅ Can view sales history
- ✅ Can manage inventory
- ✅ Can generate receipts
- ✅ Can view basic reports
- ✅ User authentication works

### Performance Requirements
- ✅ Product search < 100ms
- ✅ Sale processing < 500ms
- ✅ UI responsive (< 16ms render)
- ✅ Can handle 1000+ products

### Quality Requirements
- ✅ No critical bugs
- ✅ Data integrity maintained
- ✅ User-friendly interface
- ✅ Works offline (always, since on-premise)

---

## 🔄 Future Enhancements (After Phase 1)

Once basic features work, consider adding:

1. **VAT Support** - Add VAT calculation
2. **M-PESA Integration** - Payment processing
3. **eTIMS Integration** - Tax compliance
4. **Barcode Scanning** - Hardware integration
5. **Customer Management** - CRM features
6. **Advanced Reports** - More analytics
7. **Multi-user** - Better role management
8. **Backup System** - Automated backups

---

## 📝 Development Checklist

### Week 1: Setup & Models
- [ ] Django project setup
- [ ] React project setup
- [ ] Database models created
- [ ] Migrations run
- [ ] Admin interface working

### Week 2: API Development
- [ ] Product API complete
- [ ] Sale API complete
- [ ] Inventory API complete
- [ ] Authentication working
- [ ] API tested with Postman/curl

### Week 3: Frontend - POS
- [ ] Product search working
- [ ] Product grid displaying
- [ ] Cart functionality
- [ ] Payment processing
- [ ] Receipt generation

### Week 4: Frontend - Management
- [ ] Product management UI
- [ ] Sales history UI
- [ ] Inventory management UI
- [ ] User management UI

### Week 5: Reports & Polish
- [ ] Dashboard implemented
- [ ] Reports working
- [ ] UI/UX improvements
- [ ] Bug fixes
- [ ] Testing complete

### Week 6: Final Polish
- [ ] Performance optimization
- [ ] Documentation
- [ ] User training materials
- [ ] Deployment preparation

---

## 🛠️ Tech Stack Summary

### Backend
- Django 4.2+
- Django REST Framework
- SQLite (or PostgreSQL)
- Python 3.11+

### Frontend
- React 18+
- React Router
- Axios (for API calls)
- CSS/SCSS (or Tailwind)

### Development Tools
- Git (version control)
- Virtual environment (venv)
- npm/yarn (package manager)

### No Need For (Phase 1)
- ❌ Redis (caching)
- ❌ Celery (task queue)
- ❌ Cloud services
- ❌ Docker (optional)
- ❌ CI/CD (optional)

---

## 📚 Next Steps

1. **Start with Step 1**: Project setup
2. **Follow the checklist**: Week by week
3. **Test frequently**: After each feature
4. **Keep it simple**: Don't over-engineer
5. **Focus on core**: POS functionality first

---

**Remember**: This is Phase 1 - keep it simple, get it working, then enhance!

