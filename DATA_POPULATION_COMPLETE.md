# Test Data Population - Complete ✅

## Summary

Successfully populated the database with comprehensive test data for end-to-end testing.

## Data Created

### Users: 101
- 1 superuser (admin)
- 100 regular users with profiles
- Roles distributed: cashier, manager, admin
- 75% active users
- 33% staff users

### Customers: 100
- Mix of individual and business customers
- Distributed across Kenyan cities (Nairobi, Mombasa, Kisumu, etc.)
- 75% active customers
- 50% assigned to headquarters branch

### Categories: 75
- **10 Main Categories:**
  - Electronics
  - Clothing & Apparel
  - Food & Beverages
  - Home & Kitchen
  - Sports & Outdoors
  - Beauty & Personal Care
  - Books & Media
  - Toys & Games
  - Automotive
  - Health & Wellness

- **66 Subcategories** distributed across main categories

### Products: 990
- Created across all subcategories
- Realistic pricing (cost + 20-200% markup)
- Stock quantities: 0-500 units
- Low stock thresholds: 10-100 units
- 66% have variants (sizes/colors)
- 75% active products
- Unique SKUs and barcodes

### Product Variants: 5,972
- Size + Color combinations
- Size-only variants
- Color-only variants
- Variant-specific pricing and stock
- Realistic variant data

### Sizes: 6
- Small (S)
- Medium (M)
- Large (L)
- Extra Large (XL)
- XXL
- One Size (OS)

### Colors: 15
- Red, Blue, Green, Yellow, Black, White
- Gray, Brown, Beige, Navy, Maroon
- Cream, Orange, Purple, Pink

## Command Usage

```bash
# Populate all data (default: 100 users, 100 customers, 1000 products)
python manage.py populate_test_data

# Custom amounts
python manage.py populate_test_data --users 200 --customers 150 --products 2000

# Skip specific data types
python manage.py populate_test_data --skip-users --skip-customers
python manage.py populate_test_data --skip-products
```

## Data Characteristics

### Users
- Usernames: `user001`, `user002`, etc.
- Email: `user1@example.com`, `user2@example.com`, etc.
- Password: `password123` (for all test users)
- Phone: Kenyan format (2547XXXXXXXX)
- Roles: Randomly assigned (cashier, manager, admin)

### Customers
- Names: `Customer 1`, `Business 1 Ltd`, etc.
- Types: Individual (50%) and Business (50%)
- Locations: Various Kenyan cities
- Contact info: Email, phone, address
- Tax IDs: Some have tax IDs

### Products
- Names: Based on category templates (e.g., "Smartphone 1", "T-Shirt Premium 5")
- SKUs: Format `PRD-{CAT}-{NUMBER}` (e.g., `PRD-ELE-000001`)
- Barcodes: 12-digit unique numbers
- Pricing: Realistic cost and selling prices
- Stock: Varied quantities with low stock alerts
- Variants: Most products have size/color variants

## Next Steps

1. **Test the System:**
   - Login with any user (password: `password123`)
   - Browse products with variants
   - Create sales
   - Manage inventory
   - Track customers

2. **Create Sales:**
   - Use POS to create sales
   - Create normal sales with invoices
   - Test payment plans

3. **Test Reports:**
   - View sales reports
   - Check inventory reports
   - Generate financial reports

## Notes

- All test users have the same password: `password123`
- Products are distributed across all categories
- Variants are created for products that support them
- Data is realistic but generated for testing purposes
- Can be regenerated anytime by running the command again
