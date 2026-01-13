from django.contrib import admin
from .models import ModuleSettings, ModuleFeature, Branch


class ModuleFeatureInline(admin.TabularInline):
    model = ModuleFeature
    extra = 0
    fields = ['feature_key', 'feature_name', 'is_enabled', 'description', 'display_order']
    readonly_fields = ['feature_key', 'feature_name']


@admin.register(ModuleSettings)
class ModuleSettingsAdmin(admin.ModelAdmin):
    list_display = ['module_name', 'is_enabled', 'features_count', 'updated_by', 'updated_at']
    list_filter = ['is_enabled', 'updated_at']
    search_fields = ['module_name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'features_count']
    ordering = ['module_name']
    inlines = [ModuleFeatureInline]
    
    fieldsets = (
        ('Module Information', {
            'fields': ('module_name', 'description', 'is_enabled')
        }),
        ('Features', {
            'fields': ('features_count',),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('updated_by', 'created_at', 'updated_at')
        }),
    )
    
    def features_count(self, obj):
        return obj.features.count()
    features_count.short_description = 'Features'
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        # Only super admins can add modules
        return request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_super_admin)
    
    def has_change_permission(self, request, obj=None):
        # Only super admins can change modules
        return request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_super_admin)
    
    def has_delete_permission(self, request, obj=None):
        # Only super admins can delete modules
        return request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_super_admin)


@admin.register(ModuleFeature)
class ModuleFeatureAdmin(admin.ModelAdmin):
    list_display = ['feature_name', 'module', 'is_enabled', 'display_order', 'updated_by', 'updated_at']
    list_filter = ['is_enabled', 'module', 'updated_at']
    search_fields = ['feature_name', 'feature_key', 'module__module_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['module', 'display_order', 'feature_name']
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        return request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_super_admin)
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_super_admin)
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_super_admin)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['branch_code', 'name', 'city', 'country', 'is_active', 'is_headquarters', 'manager', 'created_at']
    list_filter = ['is_active', 'is_headquarters', 'country', 'created_at']
    search_fields = ['branch_code', 'name', 'city', 'address', 'phone', 'email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Branch Information', {
            'fields': ('branch_code', 'name', 'is_active', 'is_headquarters')
        }),
        ('Location', {
            'fields': ('address', 'city', 'country')
        }),
        ('Contact', {
            'fields': ('phone', 'email')
        }),
        ('Management', {
            'fields': ('manager', 'created_by')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
