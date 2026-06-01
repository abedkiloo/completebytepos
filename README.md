# CompleteBytePOS

A comprehensive, production-ready Point of Sale (POS) system designed for Kenyan businesses. Built with Django REST Framework and React, featuring a modern, touch-optimized interface.

![POS System](https://img.shields.io/badge/POS-System-blue)
![Django](https://img.shields.io/badge/Django-4.2-green)
![React](https://img.shields.io/badge/React-19-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 🚀 Quick Start

> **Full setup guide (Docker, VPS, tenant/branch, env vars, troubleshooting):** [docs/SETUP.md](docs/SETUP.md)

### Prerequisites

- **Python** 3.11 or higher
- **Node.js** 18 or higher
- **npm** or **yarn**
- **Docker** (recommended for production and team dev)

### Docker (recommended)

```bash
cp .env.example .env
./run_docker.sh              # development
# ./run_docker.sh --prod     # production VPS

docker exec completebytepos_backend python manage.py setup_new_organization
```

See [docs/SETUP.md](docs/SETUP.md) for remote server `REACT_APP_API_URL`, default users, and verification.

### First Time Setup (local script)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd CompleteBytePOS
   ```

2. **Run the setup script**
   ```bash
   python setup.py
   ```
   
   This automated script will:
   - ✅ Create Python virtual environment
   - ✅ Install all backend dependencies
   - ✅ Install all frontend dependencies
   - ✅ Set up SQLite database
   - ✅ Run Django migrations
   - ✅ Create default admin user
   - ✅ Generate `.env` configuration file

   **Setup time**: ~3-5 minutes

3. **Start the application**
   ```bash
   python run.py
   ```

4. **Access the application**
   - **Frontend**: http://localhost:3000
   - **Backend API**: http://localhost:8000/api
   - **Admin Panel**: http://localhost:8000/admin

5. **Login**
   - **Username**: `admin`
   - **Password**: `admin`

> ⚠️ **Important**: Change the default admin password after first login!

---

## ✨ Features

### 🛒 Point of Sale (POS)
- **Modern POS Interface** - Inspired by Dreams POS, touch-optimized design
- **Quick Product Search** - Search by name, SKU, or barcode
- **Category Navigation** - Browse products by category
- **Cart Management** - Add, remove, and adjust quantities
- **Multiple Payment Methods** - Cash, Card, Points, Deposit, Cheque, Gift Card, Scan, Pay Later
- **Real-time Calculations** - Automatic tax, discount, and shipping calculations
- **Receipt Generation** - Print receipts after sale completion

### 📦 Product Management
- **Complete CRUD Operations** - Create, read, update, delete products
- **Product Images** - Upload and manage product images
- **Advanced Search & Filtering** - Search by name, SKU, barcode, category
- **Bulk Operations** - Activate/deactivate, delete multiple products
- **Stock Tracking** - Real-time stock quantity monitoring
- **Low Stock Alerts** - Automatic alerts for products below threshold
- **Product Statistics** - View inventory value, profit margins, and more
- **CSV Import/Export** - Bulk import/export products

### 📁 Category Management
- **Dedicated Category Page** - Full category management interface
- **Hierarchical Categories** - Support for parent-child relationships
- **Category Statistics** - View product count per category
- **Active/Inactive Status** - Enable/disable categories
- **Search & Filter** - Find categories quickly

### 📊 Inventory Management
- **Stock Movements** - Track all inventory movements (purchases, sales, adjustments)
- **Stock Adjustments** - Manual stock corrections
- **Purchase Recording** - Record stock purchases with cost tracking
- **Stock Transfers** - Transfer stock between locations (future: multi-branch)
- **Low Stock Alerts** - Automatic alerts for products below threshold
- **Out of Stock Tracking** - Identify products with zero stock
- **Inventory Reports** - Comprehensive inventory statistics
- **Stock History** - Complete movement history per product
- **Cost Tracking** - Track unit costs and calculate average costs

### 🏷️ Barcode Management
- **Barcode Generation** - Auto-generate barcodes for products
- **Multiple Formats** - Code 128, EAN-13, EAN-8, QR Code
- **Barcode Preview** - Preview before printing
- **Label Printing** - Generate PDF labels for printing
- **Bulk Operations** - Generate barcodes for multiple products
- **Customizable Labels** - Include product name, price, and more

### 💰 Sales Management
- **Sales History** - Complete sales transaction history
- **Sale Details** - View detailed information for each sale
- **Receipt Printing** - Print receipts for completed sales
- **Payment Tracking** - Track payment methods and amounts
- **Sales Reports** - Comprehensive sales analytics

### 📈 Reports & Analytics
- **Dashboard** - Real-time statistics and overview
- **Sales Reports** - Daily, weekly, monthly sales reports
- **Product Reports** - Product performance analytics
- **Inventory Reports** - Stock levels and movements
- **Profit Analysis** - Calculate profit margins and amounts

### 👥 User Management
- **JWT Authentication** - Secure token-based authentication
- **User Roles** - Role-based access control (future)
- **Session Management** - Secure session handling

---

## 🏗️ Architecture

### Technology Stack

**Backend:**
- **Django** 4.2 - Web framework
- **Django REST Framework** 3.14+ - API framework
- **djangorestframework-simplejwt** - JWT authentication
- **Pillow** - Image processing
- **python-barcode** - Barcode generation
- **qrcode** - QR code generation
- **reportlab** - PDF generation
- **openpyxl** - Excel file handling

**Frontend:**
- **React** 19 - UI framework
- **React Router** 7 - Routing
- **Axios** - HTTP client
- **CSS3** - Styling

**Database:**
- **SQLite** (default) - For quick start and development
- **MySQL/PostgreSQL** - Supported for production

### Project Structure

```
CompleteBytePOS/
├── be/                          # Django Backend
│   ├── accounts/                # Authentication & User Management
│   ├── products/                # Product Management
│   ├── categories/              # Category Management
│   ├── sales/                   # Sales & Transactions
│   ├── inventory/               # Inventory & Stock Management
│   ├── barcodes/                # Barcode Generation & Printing
│   ├── reports/                 # Reports & Analytics
│   ├── config/                  # Django Settings
│   │   ├── settings.py          # Main configuration
│   │   ├── urls.py              # URL routing
│   │   └── wsgi.py              # WSGI config
│   ├── manage.py                # Django management script
│   ├── requirements.txt         # Python dependencies
│   ├── db.sqlite3               # SQLite database (gitignored)
│   ├── media/                   # User uploads (gitignored)
│   └── staticfiles/             # Collected static files (gitignored)
│
├── fe/                          # React Frontend
│   ├── public/                  # Static files
│   ├── src/
│   │   ├── components/          # React components
│   │   │   ├── Auth/           # Authentication
│   │   │   ├── Dashboard/      # Dashboard
│   │   │   ├── POS/            # Point of Sale
│   │   │   ├── Products/       # Product Management
│   │   │   ├── Categories/     # Category Management
│   │   │   ├── Sales/          # Sales Management
│   │   │   ├── Inventory/      # Inventory Management
│   │   │   ├── Barcodes/       # Barcode Management
│   │   │   └── Reports/        # Reports
│   │   ├── services/           # API services
│   │   ├── utils/              # Utility functions
│   │   └── App.js              # Main app component
│   ├── package.json            # Node dependencies
│   └── .gitignore              # Frontend gitignore
│
├── setup.py                     # Automated setup script
├── run.py                       # Run both servers
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

---

## 🔧 Configuration

### Environment Variables

The setup script automatically generates a `.env` file. You can customize it:

```env
# Database (SQLite by default)
DATABASE_URL=sqlite:///db.sqlite3

# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# API URL
REACT_APP_API_URL=http://localhost:8000/api
```

### Database Configuration

**SQLite (Default)** - No configuration needed, works out of the box.

**MySQL** - Update `be/config/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

**PostgreSQL** - Update `be/config/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

## 📚 API Documentation

### Authentication

All API endpoints require JWT authentication except login.

**Login:**
```http
POST /api/accounts/auth/login/
Content-Type: application/json

{
  "username": "admin",
  "password": "admin"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": { ... }
}
```

**Using the Token:**
```http
Authorization: Bearer <access_token>
```

### Main Endpoints

- **Products**: `/api/products/`
- **Categories**: `/api/products/categories/`
- **Sales**: `/api/sales/`
- **Inventory**: `/api/inventory/`
- **Barcodes**: `/api/barcodes/`
- **Reports**: `/api/reports/`

For detailed API documentation, visit `/api/` when the server is running.

---

## 🎯 Usage Guide

### 1. Setting Up Products

1. Navigate to **Products** from the main menu
2. Click **"Add Product"**
3. Fill in product details:
   - Name, SKU, Barcode
   - Category, Price, Cost
   - Stock quantity, Low stock threshold
   - Upload product image
4. Click **"Save"**

### 2. Processing a Sale

1. Go to **POS** from the main menu
2. Search or browse products
3. Click products to add to cart
4. Adjust quantities as needed
5. Add shipping, tax, or discount if applicable
6. Select payment method
7. Click **"Place Order"**
8. Complete payment and print receipt

### 3. Managing Inventory

1. Go to **Inventory** from the main menu
2. View stock movements, low stock alerts, or reports
3. Record purchases or adjust stock as needed
4. View product stock history

### 4. Generating Barcodes

1. Go to **Barcodes** from the main menu
2. Select products without barcodes
3. Click **"Generate Missing"** to auto-generate
4. Preview barcodes before printing
5. Print labels in bulk or individually

---

## 🛠️ Development

### Running Backend Only

```bash
cd be
source venv/bin/activate  # On Windows: venv\Scripts\activate
python manage.py runserver
```

### Running Frontend Only

```bash
cd fe
npm start
```

### Running Tests

**Backend:**
```bash
cd be
source venv/bin/activate
python manage.py test
```

**Frontend:**
```bash
cd fe
npm test
```

### Creating Migrations

```bash
cd be
source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
```

### Creating Superuser

```bash
cd be
source venv/bin/activate
python manage.py createsuperuser
```

---

## 🔒 Security

- **JWT Authentication** - Secure token-based authentication
- **CSRF Protection** - Enabled for all forms
- **CORS Configuration** - Properly configured for API access
- **Password Hashing** - Django's secure password hashing
- **SQL Injection Protection** - Django ORM prevents SQL injection
- **XSS Protection** - React automatically escapes content

> ⚠️ **Production Checklist:**
> - Change `DEBUG=False` in settings
> - Set a strong `SECRET_KEY`
> - Configure proper `ALLOWED_HOSTS`
> - Use HTTPS
> - Set up proper database (MySQL/PostgreSQL)
> - Configure static file serving
> - Set up proper logging
> - Enable rate limiting
> - Configure backup strategy

---

## 📦 Deployment

### Backend Deployment

1. Set `DEBUG=False` in `be/config/settings.py`
2. Configure production database
3. Run `python manage.py collectstatic`
4. Set up WSGI server (Gunicorn + Nginx)
5. Configure environment variables

### Frontend Deployment

1. Build the React app: `npm run build`
2. Serve the `build/` folder with a web server (Nginx, Apache)
3. Configure API URL in environment variables

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🆘 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the documentation files in the repository
- Review the code comments for implementation details

---

## 🙏 Acknowledgments

- Built with Django and React
- Inspired by modern POS systems like Dreams POS
- Designed for Kenyan businesses

---

## 📊 Project Status

✅ **Phase 1 Complete** - Core features implemented:
- POS Interface
- Product Management
- Category Management
- Inventory Management
- Barcode Generation & Printing
- Sales Management
- Basic Reports

🚧 **Future Enhancements**:
- Multi-branch support
- Advanced reporting with charts
- Customer management
- Supplier management
- Purchase orders
- Advanced user roles and permissions
- Receipt templates customization
- Mobile app

---

**Built with ❤️ for Kenyan businesses**

*CompleteBytePOS - Your Complete Point of Sale Solution*
