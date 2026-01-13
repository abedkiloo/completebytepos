from rest_framework import serializers
from .models import BankAccount, BankTransaction


class BankAccountSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    transaction_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = BankAccount
        fields = [
            'id', 'account_name', 'account_number', 'bank_name',
            'account_type', 'branch', 'swift_code',
            'opening_balance', 'current_balance', 'currency',
            'is_active', 'notes', 'created_by', 'created_by_name',
            'transaction_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['current_balance', 'created_at', 'updated_at']


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(source='bank_account.account_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = BankTransaction
        fields = [
            'id', 'transaction_number', 'bank_account', 'bank_account_name',
            'transaction_type', 'amount', 'description', 'reference',
            'transaction_date', 'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['transaction_number', 'created_at']

