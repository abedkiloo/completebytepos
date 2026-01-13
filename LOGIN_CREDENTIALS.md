# Login Credentials

## Super Admin (Superuser)

**Username:** `admin`  
**Email:** `admin@example.com`  
**Password:** `admin123`

This user has full system access and can:
- Manage all modules
- Create/edit/delete users and roles
- Access all settings
- Manage branches
- Full administrative privileges

---

## Admin User (if created via `create_users` command)

**Username:** `manager`  
**Email:** `manager@example.com`  
**Password:** `manager123`

This user has admin role with:
- Full access except user/role management
- Can manage products, sales, inventory
- Can view reports
- Cannot manage users, roles, or system settings

---

## Regular Admin Users (from `populate_test_data`)

Multiple admin users were created with the following pattern:

**Usernames:** `user002`, `user004`, `user007`, `user009`, `user015`, etc.  
**Password:** `password123` (for all test users)

These users have the `admin` role assigned randomly during data population.

---

## Manager Users (from `populate_test_data`)

**Usernames:** Various (e.g., `user001`, `user003`, `user005`, etc.)  
**Password:** `password123`

These users have the `manager` role with view/create/update permissions.

---

## Cashier Users (from `populate_test_data`)

**Usernames:** Various (e.g., `user001`, `user003`, `user005`, etc.)  
**Password:** `password123`

These users have the `cashier` role with limited POS and sales permissions.

---

## Quick Reference

| Role | Username | Password | Access Level |
|------|----------|----------|--------------|
| Super Admin | `admin` | `admin123` | Full system access |
| Admin (if created) | `manager` | `manager123` | Admin role (no user management) |
| Admin (test users) | `user002`, `user004`, etc. | `password123` | Admin role |
| Manager (test users) | `user001`, `user003`, etc. | `password123` | Manager role |
| Cashier (test users) | `user001`, `user003`, etc. | `password123` | Cashier role |

---

## Notes

- All test users created by `populate_test_data` use the password: `password123`
- The super admin (`admin`) is created automatically by the populate command if it doesn't exist
- You can create additional users using: `python manage.py create_users`
- To change passwords, use Django admin or the user management interface
