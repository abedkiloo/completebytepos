# Settings App Migration Guide

## Overview
Module settings have been migrated from the `accounts` app to a dedicated `settings` app for better organization and extensibility.

## What Changed

### New App Structure
- **New App**: `be/settings/` - Dedicated app for all system settings
- **Models**: `ModuleSettings` and `ModuleFeature` moved to `settings/models.py`
- **Views**: `ModuleSettingsViewSet` and `ModuleFeatureViewSet` moved to `settings/views.py`
- **Serializers**: Moved to `settings/serializers.py`
- **Admin**: Moved to `settings/admin.py`
- **Management Command**: `init_modules` moved to `settings/management/commands/`

### API Endpoints Changed
**Old endpoints:**
- `/api/accounts/modules/`
- `/api/accounts/module-features/`

**New endpoints:**
- `/api/settings/modules/`
- `/api/settings/module-features/`

### Database Tables
- **No data loss**: Tables remain the same (`accounts_modulesettings`, `accounts_modulefeature`)
- **Backward compatibility**: Models use `db_table` to point to existing tables
- **No migration needed**: Existing data is preserved

## Backward Compatibility

### Import Compatibility
The `accounts` app still imports models for backward compatibility:
```python
# In accounts/models.py, views.py, etc.
from settings.models import ModuleSettings, ModuleFeature
```

### Frontend Updated
- API endpoints updated in `fe/src/services/api.js`
- All module settings functionality continues to work

## Future Settings

The settings app is designed to be extensible. Future settings can be added:

### Example: System Configuration
```python
# In settings/models.py
class SystemConfiguration(models.Model):
    """System-wide configuration settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Example: Notification Settings
```python
class NotificationSettings(models.Model):
    """Notification preferences"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    # ... more fields
```

## Testing

1. **Verify API endpoints work:**
   ```bash
   curl http://localhost:8000/api/settings/modules/
   ```

2. **Check frontend:**
   - Module Settings page should load
   - All toggles should work
   - No errors in console

3. **Verify data integrity:**
   - All existing modules should be visible
   - All features should be intact
   - Settings should persist

## Rollback (if needed)

If you need to rollback:
1. Revert frontend API paths in `fe/src/services/api.js`
2. Move models back to `accounts/models.py`
3. Move views back to `accounts/views.py`
4. Update `config/urls.py` to use accounts URLs

## Benefits

1. **Better Organization**: Settings are now in a dedicated app
2. **Extensibility**: Easy to add new setting types
3. **Maintainability**: Clear separation of concerns
4. **No Breaking Changes**: All existing functionality preserved
5. **Future-Proof**: Ready for additional settings types
