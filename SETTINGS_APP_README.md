# Settings App - Complete Migration Guide

## ✅ Migration Complete

Module settings have been successfully migrated to a dedicated `settings` app without affecting system functionality.

## 📁 New Structure

```
be/settings/
├── __init__.py
├── admin.py          # Module settings admin
├── apps.py           # App configuration
├── models.py         # ModuleSettings & ModuleFeature models
├── serializers.py    # API serializers
├── urls.py           # API routes
├── views.py          # API ViewSets
├── management/
│   └── commands/
│       └── init_modules.py  # Initialization command
└── migrations/
    └── 0001_initial.py      # Migration (uses existing tables)
```

## 🔄 What Changed

### Backend
1. **New App**: `settings` app created
2. **Models Moved**: `ModuleSettings` and `ModuleFeature` → `settings/models.py`
3. **Views Moved**: ViewSets → `settings/views.py`
4. **Serializers Moved**: → `settings/serializers.py`
5. **Admin Moved**: → `settings/admin.py`
6. **Command Moved**: `init_modules` → `settings/management/commands/`

### API Endpoints
- **Old**: `/api/accounts/modules/` → **New**: `/api/settings/modules/`
- **Old**: `/api/accounts/module-features/` → **New**: `/api/settings/module-features/`

### Frontend
- Updated API paths in `fe/src/services/api.js`
- All functionality preserved

### Database
- **No data loss**: Tables remain (`accounts_modulesettings`, `accounts_modulefeature`)
- **Backward compatible**: Models use `db_table` to point to existing tables
- **No migration needed**: Existing data intact

## 🔗 Backward Compatibility

The `accounts` app maintains imports for compatibility:
```python
# accounts/models.py, views.py, etc.
from settings.models import ModuleSettings, ModuleFeature
```

This ensures existing code continues to work without changes.

## 🚀 Adding Future Settings

The settings app is designed to be extensible. Add new setting models:

### Example 1: System Configuration
```python
# In settings/models.py
class SystemConfiguration(models.Model):
    """System-wide configuration settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, default='general')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "System Configurations"
        ordering = ['category', 'key']
```

### Example 2: Notification Settings
```python
class NotificationSettings(models.Model):
    """User notification preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_settings')
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    low_stock_alerts = models.BooleanField(default=True)
    sales_alerts = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
```

### Example 3: Business Settings
```python
class BusinessSettings(models.Model):
    """Business-specific settings"""
    business_name = models.CharField(max_length=200)
    tax_id = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default='KES')
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    fiscal_year_start = models.DateField()
    # ... more fields
```

Then add corresponding:
- Serializers in `settings/serializers.py`
- ViewSets in `settings/views.py`
- Admin classes in `settings/admin.py`
- URL routes in `settings/urls.py`

## ✅ Testing Checklist

1. **API Endpoints**:
   ```bash
   # Test module listing
   curl http://localhost:8000/api/settings/modules/
   
   # Test module update (requires auth)
   curl -X PUT http://localhost:8000/api/settings/modules/1/ \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"is_enabled": true}'
   ```

2. **Frontend**:
   - Module Settings page loads
   - All modules visible
   - Toggle switches work
   - Features expandable
   - Category toggles work
   - No console errors

3. **Database**:
   - All existing modules present
   - All features intact
   - Settings persist after changes

## 📝 Configuration

### INSTALLED_APPS
```python
# config/settings.py
INSTALLED_APPS = [
    # ... other apps
    'settings',  # Settings app for module settings and future settings
]
```

### URLs
```python
# config/urls.py
urlpatterns = [
    # ... other patterns
    path('api/settings/', include('settings.urls')),
]
```

## 🎯 Benefits

1. **Better Organization**: Settings centralized in one app
2. **Extensibility**: Easy to add new setting types
3. **Maintainability**: Clear separation of concerns
4. **No Breaking Changes**: All functionality preserved
5. **Future-Proof**: Ready for additional settings
6. **Scalability**: Can grow without cluttering accounts app

## 🔧 Maintenance

### Adding New Modules
1. Add to `MODULE_CHOICES` in `settings/models.py`
2. Add features to `MODULE_FEATURES` dict
3. Run `python manage.py init_modules`

### Adding New Setting Types
1. Create model in `settings/models.py`
2. Create serializer in `settings/serializers.py`
3. Create ViewSet in `settings/views.py`
4. Register in admin in `settings/admin.py`
5. Add URL route in `settings/urls.py`
6. Create migrations: `python manage.py makemigrations settings`

## 📚 Related Files

- **Backend Models**: `be/settings/models.py`
- **Backend Views**: `be/settings/views.py`
- **Backend Serializers**: `be/settings/serializers.py`
- **Backend Admin**: `be/settings/admin.py`
- **Backend URLs**: `be/settings/urls.py`
- **Frontend API**: `fe/src/services/api.js`
- **Frontend Component**: `fe/src/components/ModuleSettings/ModuleSettings.js`

## 🎉 Success!

The settings app is now ready to manage all system settings, current and future!
