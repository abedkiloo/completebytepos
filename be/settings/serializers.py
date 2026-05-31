from rest_framework import serializers
from .models import ModuleSettings, ModuleFeature, ModuleSetting, Branch, Tenant, StoreSettings
from .module_settings_registry import MODULE_SETTING_DEFINITIONS
from .store_settings_helpers import normalize_payment_methods, VALID_PAYMENT_METHODS


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


class StoreSettingsSerializer(serializers.ModelSerializer):
    receipt_logo_url = serializers.SerializerMethodField()

    class Meta:
        model = StoreSettings
        fields = [
            'allow_sales_add_products',
            'sales_catalog_skip_pricing',
            'hide_entity_status_toggles',
            'enabled_payment_methods',
            'receipt_logo',
            'receipt_logo_url',
            'receipt_header_text',
            'receipt_footer_text',
            'receipt_show_logo',
            'receipt_show_sku',
            'receipt_auto_print',
            'updated_at',
        ]
        read_only_fields = ['updated_at']
        extra_kwargs = {
            'receipt_logo': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def to_internal_value(self, data):
        # Build a plain dict — QueryDict coerces non-string values (e.g. parsed
        # JSON lists) to invalid Python repr strings like "['cash']".
        if hasattr(data, 'keys'):
            ret = {key: data.get(key) for key in data.keys()}
        else:
            ret = dict(data)

        methods = ret.get('enabled_payment_methods')
        if isinstance(methods, str):
            import json
            try:
                ret['enabled_payment_methods'] = json.loads(methods)
            except json.JSONDecodeError:
                ret['enabled_payment_methods'] = [
                    m.strip() for m in methods.split(',') if m.strip()
                ]
        return super().to_internal_value(ret)

    def get_receipt_logo_url(self, obj):
        if not obj.receipt_logo:
            return None
        request = self.context.get('request')
        url = obj.receipt_logo.url
        if request:
            return request.build_absolute_uri(url)
        return url

    def validate_enabled_payment_methods(self, value):
        if value is not None and len(value) == 0:
            raise serializers.ValidationError('Select at least one payment method.')
        normalized = normalize_payment_methods(value)
        if not normalized:
            raise serializers.ValidationError('Select at least one payment method.')
        invalid = [m for m in (value or []) if str(m).strip().lower() not in VALID_PAYMENT_METHODS]
        if invalid:
            raise serializers.ValidationError(
                f'Unknown payment method(s): {", ".join(invalid)}'
            )
        return normalized

    def update(self, instance, validated_data):
        if validated_data.get('receipt_logo') is None and self.context.get('clear_receipt_logo'):
            if instance.receipt_logo:
                instance.receipt_logo.delete(save=False)
            validated_data['receipt_logo'] = None
        return super().update(instance, validated_data)


class ModuleSettingEntrySerializer(serializers.Serializer):
    """One keyed setting with metadata for the Settings UI."""

    value = serializers.JSONField()
    default_value = serializers.JSONField()
    label = serializers.CharField()
    description = serializers.CharField()
    display_order = serializers.IntegerField()
    impact = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ModuleSettingsModuleSerializer(serializers.Serializer):
    module = serializers.CharField()
    settings = serializers.DictField(child=ModuleSettingEntrySerializer())


def build_module_settings_response(module: str) -> dict:
    """Structured payload for GET /api/settings/{module}/."""
    from .settings_service import SettingsService

    rows = {r.key: r for r in ModuleSetting.objects.filter(module=module)}
    settings_out = {}

    definitions = MODULE_SETTING_DEFINITIONS.get(module, [])
    seen = set()
    for definition in sorted(definitions, key=lambda d: d.get('display_order', 0)):
        key = definition['key']
        seen.add(key)
        row = rows.get(key)
        settings_out[key] = {
            'value': SettingsService.get(module, key, definition['default_value']),
            'default_value': row.default_value if row else definition['default_value'],
            'label': row.label if row else definition['label'],
            'description': row.description if row else definition.get('description', ''),
            'display_order': row.display_order if row else definition.get('display_order', 0),
            'impact': definition.get('impact'),
        }

    for key, row in rows.items():
        if key in seen:
            continue
        settings_out[key] = {
            'value': row.value if row.value is not None else row.default_value,
            'default_value': row.default_value,
            'label': row.label,
            'description': row.description,
            'display_order': row.display_order,
        }

    return {'module': module, 'settings': settings_out}
