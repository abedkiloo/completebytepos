from rest_framework import serializers
from .models import MoneyTransfer


class MoneyTransferSerializer(serializers.ModelSerializer):
    from_account_name = serializers.CharField(source='from_account.account_name', read_only=True)
    to_account_name = serializers.CharField(source='to_account.account_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    
    class Meta:
        model = MoneyTransfer
        fields = [
            'id', 'transfer_number', 'transfer_type', 'from_account', 'from_account_name',
            'to_account', 'to_account_name', 'amount', 'currency', 'transfer_date',
            'status', 'description', 'reference', 'fees', 'exchange_rate',
            'created_by', 'created_by_name', 'approved_by', 'approved_by_name',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['transfer_number', 'created_at', 'updated_at']

