from rest_framework import serializers
from .models import IncomeCategory, Income


class IncomeCategorySerializer(serializers.ModelSerializer):
    income_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = IncomeCategory
        fields = [
            'id', 'name', 'description', 'is_active',
            'income_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class IncomeSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    
    class Meta:
        model = Income
        fields = [
            'id', 'income_number', 'category', 'category_name',
            'amount', 'description', 'payment_method', 'status',
            'payer', 'reference_number', 'income_date',
            'created_by', 'created_by_name', 'approved_by', 'approved_by_name',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['income_number', 'created_at', 'updated_at']

