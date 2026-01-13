# Quick Start Guide - On-Premise Phase 1

This guide will help you set up the basic on-premise POS system quickly.

## 🚀 Quick Setup (30 minutes)

### Prerequisites
- Python 3.11+ installed
- Node.js 18+ installed
- Git (optional)

### Step 1: Create Project Structure

```bash
# Create main project directory
mkdir CompleteBytePOS
cd CompleteBytePOS

# Create backend directory
mkdir backend
cd backend

# Create frontend directory (from project root)
cd ..
mkdir frontend
```

### Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install Django and dependencies
pip install django djangorestframework django-cors-headers pillow

# Create Django project
django-admin startproject config .

# Create apps
python manage.py startapp products
python manage.py startapp sales
python manage.py startapp inventory
python manage.py startapp accounts
```

### Step 3: Frontend Setup

```bash
cd ../frontend

# Create React app
npx create-react-app . --yes

# Install additional dependencies
npm install axios react-router-dom

# Optional: Install UI library
npm install @mui/material @emotion/react @emotion/styled
# or
npm install bootstrap react-bootstrap
```

### Step 4: Basic Configuration

#### Backend Settings (`backend/config/settings.py`)

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'products',
    'sales',
    'inventory',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS settings (for local development)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOW_CREDENTIALS = True

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
}

# Database (SQLite for Phase 1)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### Step 5: Create Basic Models

#### Products App (`backend/products/models.py`)

```python
from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=50, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name
```

#### Sales App (`backend/sales/models.py`)

```python
from django.db import models
from django.contrib.auth.models import User
from products.models import Product
import uuid

class Sale(models.Model):
    sale_number = models.CharField(max_length=50, unique=True, editable=False)
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

    def save(self, *args, **kwargs):
        if not self.sale_number:
            self.sale_number = f"SALE-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sale_number

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
```

#### Inventory App (`backend/inventory/models.py`)

```python
from django.db import models
from django.contrib.auth.models import User
from products.models import Product

class StockMovement(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=[
        ('sale', 'Sale'),
        ('purchase', 'Purchase'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
    ])
    quantity = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['product', 'created_at']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.movement_type} - {self.quantity}"
```

### Step 6: Create Serializers

#### Products (`backend/products/serializers.py`)

```python
from rest_framework import serializers
from .models import Category, Product

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'created_at']

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'barcode', 'category', 'category_name',
                  'price', 'cost', 'stock_quantity', 'low_stock_threshold',
                  'is_active', 'created_at', 'updated_at']
```

#### Sales (`backend/sales/serializers.py`)

```python
from rest_framework import serializers
from .models import Sale, SaleItem
from products.serializers import ProductSerializer

class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product = ProductSerializer(read_only=True)
    
    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'quantity', 
                  'unit_price', 'subtotal']

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source='cashier.username', read_only=True)
    
    class Meta:
        model = Sale
        fields = ['id', 'sale_number', 'cashier', 'cashier_name',
                  'subtotal', 'total', 'payment_method', 'amount_paid',
                  'change', 'items', 'created_at']
```

### Step 7: Create Views

#### Products (`backend/products/views.py`)

```python
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sku', 'barcode']
    ordering_fields = ['name', 'price', 'created_at']
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        products = self.queryset.filter(
            models.Q(name__icontains=query) |
            models.Q(sku__icontains=query) |
            models.Q(barcode__icontains=query)
        )[:20]
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
```

#### Sales (`backend/sales/views.py`)

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Sale, SaleItem
from .serializers import SaleSerializer, SaleItemSerializer
from products.models import Product
from inventory.models import StockMovement

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().order_by('-created_at')
    serializer_class = SaleSerializer
    
    def create(self, request, *args, **kwargs):
        # Process sale creation
        items_data = request.data.pop('items', [])
        
        # Calculate totals
        subtotal = sum(item['quantity'] * item['unit_price'] for item in items_data)
        total = subtotal  # Add VAT/tax later
        
        # Create sale
        sale_data = {
            **request.data,
            'cashier': request.user.id,
            'subtotal': subtotal,
            'total': total,
        }
        serializer = self.get_serializer(data=sale_data)
        serializer.is_valid(raise_exception=True)
        sale = serializer.save(cashier=request.user)
        
        # Create sale items and update stock
        for item_data in items_data:
            product = Product.objects.get(id=item_data['product_id'])
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['quantity'] * item_data['unit_price']
            )
            
            # Update stock
            product.stock_quantity -= item_data['quantity']
            product.save()
            
            # Create stock movement
            StockMovement.objects.create(
                product=product,
                movement_type='sale',
                quantity=-item_data['quantity'],
                reference=sale.sale_number,
                user=request.user
            )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

### Step 8: URL Configuration

#### Main URLs (`backend/config/urls.py`)

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/products/', include('products.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/auth/', include('accounts.urls')),
]
```

#### Products URLs (`backend/products/urls.py`)

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'', ProductViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
```

### Step 9: Run Migrations

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### Step 10: Run Servers

#### Terminal 1 - Backend
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python manage.py runserver
```

#### Terminal 2 - Frontend
```bash
cd frontend
npm start
```

### Step 11: Test API

Visit: http://localhost:8000/api/products/

You should see the API response!

---

## 📝 Next Steps

1. **Create React components** for POS interface
2. **Connect frontend to backend** API
3. **Test the complete flow**: Add product → Create sale → View receipt
4. **Add more features** as needed

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Change Django port
python manage.py runserver 8001

# Change React port
PORT=3001 npm start
```

### CORS Issues
Make sure `corsheaders` is in `INSTALLED_APPS` and `MIDDLEWARE`

### Database Issues
```bash
# Delete database and recreate
rm db.sqlite3
python manage.py migrate
```

---

## 📚 Resources

- [Django REST Framework Docs](https://www.django-rest-framework.org/)
- [React Docs](https://react.dev/)
- [SQLite Docs](https://www.sqlite.org/docs.html)

---

**You're ready to start building!** 🚀

