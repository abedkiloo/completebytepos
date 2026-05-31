from rest_framework import serializers
from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    """Full supplier serializer with all fields"""
    full_address = serializers.ReadOnlyField()
    primary_contact = serializers.ReadOnlyField()
    is_credit_available = serializers.ReadOnlyField()
    created_by_username = serializers.SerializerMethodField()
    
    def get_created_by_username(self, obj):
        """Safely get created_by username"""
        return obj.created_by.username if obj.created_by else None

    def validate(self, attrs):
        from suppliers.module_settings import validate_supplier_write

        return validate_supplier_write(attrs)

    def to_representation(self, instance):
        from suppliers.module_settings import apply_supplier_representation_flags

        return apply_supplier_representation_flags(super().to_representation(instance))
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'supplier_code', 'supplier_type', 'contact_person',
            'email', 'phone', 'alternate_phone', 'address', 'city', 'state',
            'country', 'postal_code', 'tax_id', 'registration_number', 'website',
            'payment_terms', 'credit_limit', 'account_balance', 'notes', 'rating',
            'is_preferred', 'is_active', 'full_address', 'primary_contact',
            'is_credit_available', 'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['supplier_code', 'created_at', 'updated_at', 'created_by']


class SupplierListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for supplier lists"""

    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'supplier_code', 'supplier_type', 'contact_person',
            'email', 'phone', 'city', 'country', 'is_preferred', 'is_active',
            'rating', 'payment_terms', 'credit_limit', 'account_balance',
        ]

    def to_representation(self, instance):
        from suppliers.module_settings import apply_supplier_representation_flags

        return apply_supplier_representation_flags(super().to_representation(instance))
