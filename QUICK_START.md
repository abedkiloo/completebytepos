# CompleteBytePOS - Quick Start Guide

## 🚀 First Time Setup (One Command!)

### Step 1: Run Setup

```bash
python setup.py
```

This single command will:
- ✅ Create Python virtual environment
- ✅ Install all Python dependencies
- ✅ Create React app (if needed)
- ✅ Install all Node dependencies
- ✅ Create database migrations
- ✅ Run database migrations
- ✅ Create default admin user
- ✅ Configure environment files

**Time**: ~3-5 minutes (depending on internet speed)

### Step 2: Start the Application

```bash
python run.py
```

This will start:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000

### Step 3: Login

Open http://localhost:3000 in your browser and login with:

- **Username**: `admin`
- **Password**: `admin`

---

## ✅ That's It!

You're ready to use the POS system!

---

## 📋 What You Get

After setup, you have:

1. **Working POS Interface** - Search products, add to cart, process sales
2. **Product Management** - Add/edit products via Django admin
3. **Sales Tracking** - All sales are recorded
4. **Inventory Management** - Stock tracking and movements
5. **Reports** - Dashboard with sales statistics

---

## 🎯 First Steps After Setup

1. **Add Products**:
   - Go to http://localhost:8000/admin
   - Login with admin/admin
   - Add some products under "Products"

2. **Use POS**:
   - Go to http://localhost:3000/pos
   - Search for products
   - Add to cart and process sales

3. **View Dashboard**:
   - See sales statistics
   - Check low stock items

---

## 🔧 Troubleshooting

### Setup Fails

**Error**: "Command not found: python"
- **Solution**: Use `python3` instead of `python`

**Error**: "npm not found"
- **Solution**: Install Node.js from https://nodejs.org/

**Error**: "Virtual environment creation failed"
- **Solution**: Make sure you have Python 3.11+ installed

### Run Fails

**Error**: "Database not found"
- **Solution**: Run `python setup.py` again

**Error**: "Port already in use"
- **Solution**: Stop other services on ports 8000 or 3000

**Error**: "Migrations needed"
- **Solution**: The run script will auto-run migrations, or run `python setup.py` again

---

## 📝 System Requirements

- **Python 3.11+**
- **Node.js 18+** and npm
- **4GB RAM** (minimum)
- **500MB disk space**

---

## 🎉 You're All Set!

The system is designed to work out-of-the-box with minimal configuration.

**Happy selling!** 🚀

