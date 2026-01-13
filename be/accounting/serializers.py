from rest_framework import serializers
from .models import AccountType, Account, JournalEntry, Transaction


class AccountTypeSerializer(serializers.ModelSerializer):
    account_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = AccountType
        fields = [
            'id', 'name', 'description', 'normal_balance',
            'is_active', 'account_count'
        ]


class AccountSerializer(serializers.ModelSerializer):
    account_type_name = serializers.CharField(source='account_type.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Account
        fields = [
            'id', 'account_code', 'name', 'account_type', 'account_type_name',
            'parent', 'parent_name', 'description',
            'opening_balance', 'current_balance', 'balance',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['current_balance', 'created_at', 'updated_at']


class AccountListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for account lists"""
    account_type_name = serializers.CharField(source='account_type.name', read_only=True)
    
    class Meta:
        model = Account
        fields = [
            'id', 'account_code', 'name', 'account_type_name',
            'current_balance', 'is_active'
        ]


class JournalEntrySerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.account_code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_number', 'entry_date', 'account', 'account_name', 'account_code',
            'entry_type', 'amount', 'description', 'reference', 'reference_type', 'reference_id',
            'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['entry_number', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    journal_entries = JournalEntrySerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    is_balanced = serializers.SerializerMethodField()
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_number', 'transaction_date', 'description',
            'journal_entries', 'reference', 'reference_type', 'reference_id',
            'created_by', 'created_by_name', 'created_at', 'is_balanced'
        ]
        read_only_fields = ['transaction_number', 'created_at']
    
    def get_is_balanced(self, obj):
        return obj.validate_balance()


class BalanceSheetSerializer(serializers.Serializer):
    """Serializer for balance sheet data"""
    assets = serializers.DictField()
    liabilities = serializers.DictField()
    equity = serializers.DictField()
    total_assets = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_liabilities = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_equity = serializers.DecimalField(max_digits=12, decimal_places=2)
    date = serializers.DateField()


class IncomeStatementSerializer(serializers.Serializer):
    """Serializer for income statement (P&L) data"""
    revenue = serializers.DictField()
    expenses = serializers.DictField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    period_start = serializers.DateField()
    period_end = serializers.DateField()


class TrialBalanceSerializer(serializers.Serializer):
    """Serializer for trial balance data"""
    accounts = serializers.ListField(child=serializers.DictField())
    total_debits = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_credits = serializers.DecimalField(max_digits=12, decimal_places=2)
    date = serializers.DateField()

