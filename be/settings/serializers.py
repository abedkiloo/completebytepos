from rest_framework import serializers
from .models import ModuleSettings, ModuleFeature, Branch, Tenant


class ModuleFeatureSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source='module.module_name', read_only=True)
    module_name_display = serializers.CharField(source='module.get_module_name_display', read_only=True)
    
    class Meta:
        model = ModuleFeature
        fields = [
            'id', 'module', 'module_name', 'module_name_display',
            'feature_key', 'feature_name', 'is_enabled', 'description',
            'display_order', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'id', 'module', 'feature_key', 'feature_name', 'module_name', 'module_name_display']


class ModuleSettingsSerializer(serializers.ModelSerializer):
    module_name_display = serializers.CharField(source='get_module_name_display', read_only=True)
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True)
    features = ModuleFeatureSerializer(many=True, read_only=True)
    
    class Meta:
        model = ModuleSettings
        fields = [
            'id', 'module_name', 'module_name_display', 'is_enabled', 'description',
            'updated_by', 'updated_by_username', 'features',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TenantSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    branch_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'code', 'registration_number', 'tax_id',
            'address', 'city', 'country', 'phone', 'email', 'website',
            'is_active', 'owner', 'owner_name', 'created_by', 'created_by_name',
            'branch_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_branch_count(self, obj):
        """Get count of active branches for this tenant"""
        return obj.branches.filter(is_active=True).count()
    
    def validate_code(self, value):
        """Ensure tenant code is unique"""
        if self.instance and self.instance.code == value:
            return value
        if Tenant.objects.filter(code=value).exists():
            raise serializers.ValidationError("Tenant code already exists")
        return value


class TenantListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for tenant lists"""
    branch_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'code', 'city', 'country',
            'is_active', 'branch_count'
        ]
    
    def get_branch_count(self, obj):
        return obj.branches.filter(is_active=True).count()


class BranchSerializer(serializers.ModelSerializer):
    tenant = TenantListSerializer(read_only=True)
    tenant_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = Branch
        fields = [
            'id', 'tenant', 'tenant_id', 'branch_code', 'name', 'address', 'city', 'country',
            'phone', 'email', 'is_active', 'is_headquarters',
            'manager', 'manager_name', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_branch_code(self, value):
        """Ensure branch code is unique within tenant"""
        # Get tenant_id from initial_data, instance, or context
        tenant_id = (
            self.initial_data.get('tenant_id') or 
            (self.instance.tenant.id if self.instance else None) or
            (self.context.get('tenant_id') if hasattr(self, 'context') and self.context else None)
        )
        
        # If tenant_id is not available yet (will be set in perform_create), skip validation
        # The tenant will be set automatically in perform_create
        if not tenant_id:
            # For new instances, tenant will be set in perform_create, so allow this
            if not self.instance:
                return value
            # For existing instances, tenant should be available
            raise serializers.ValidationError("Tenant is required")
        
        queryset = Branch.objects.filter(tenant_id=tenant_id, branch_code=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Branch code already exists for this tenant")
        return value


class BranchListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for branch lists"""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = Branch
        fields = [
            'id', 'tenant_name', 'branch_code', 'name', 'city', 'country',
            'is_active', 'is_headquarters'
        ]
