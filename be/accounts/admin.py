from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Permission, Role
# Module settings models moved to settings app - import for backward compatibility
from settings.models import ModuleSettings, ModuleFeature


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = ('role', 'custom_role', 'phone_number', 'is_active')


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'module', 'action', 'description', 'created_at']
    list_filter = ['module', 'action', 'created_at']
    search_fields = ['name', 'module', 'action', 'description']
    readonly_fields = ['created_at']
    ordering = ['module', 'action']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_system_role', 'is_active', 'permissions_count', 'users_count', 'created_at']
    list_filter = ['is_system_role', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['permissions']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    fieldsets = (
        ('Role Information', {
            'fields': ('name', 'description', 'is_system_role', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def permissions_count(self, obj):
        return obj.permissions.count()
    permissions_count.short_description = 'Permissions'
    
    def users_count(self, obj):
        return obj.users.count()
    users_count.short_description = 'Users'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system_role:
            return False
        return super().has_delete_permission(request, obj)


# Module settings admin classes moved to settings app
# See settings/admin.py for ModuleSettingsAdmin and ModuleFeatureAdmin
