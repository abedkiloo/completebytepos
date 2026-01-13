from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models import Sum
from decimal import Decimal
import uuid


class BankAccount(models.Model):
    """Bank accounts"""
    ACCOUNT_TYPES = [
        ('savings', 'Savings'),
        ('current', 'Current'),
        ('checking', 'Checking'),
        ('fixed_deposit', 'Fixed Deposit'),
    ]

    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=100, unique=True, db_index=True)
    bank_name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='current')
    branch = models.CharField(max_length=200, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    current_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Current balance (calculated from transactions)'
    )
    currency = models.CharField(max_length=3, default='KES', help_text='Currency code (KES, USD, etc.)')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='bank_accounts_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['bank_name', 'account_name']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.bank_name} - {self.account_name} ({self.account_number})"

    def update_balance(self):
        """Recalculate balance from transactions"""
        # Calculate from bank transactions
        deposits = self.transactions.filter(
            transaction_type__in=['deposit', 'transfer_in', 'interest']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        withdrawals = self.transactions.filter(
            transaction_type__in=['withdrawal', 'transfer_out', 'fee']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Also calculate from transfers
        try:
            from transfers.models import MoneyTransfer
            transfer_deposits = MoneyTransfer.objects.filter(
                to_account=self,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            transfer_withdrawals = MoneyTransfer.objects.filter(
                from_account=self,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            deposits += transfer_deposits
            withdrawals += transfer_withdrawals
        except:
            pass
        
        self.current_balance = self.opening_balance + deposits - withdrawals
        self.save(update_fields=['current_balance'])


class BankTransaction(models.Model):
    """Bank account transactions"""
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('fee', 'Bank Fee'),
        ('interest', 'Interest'),
    ]

    transaction_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True)
    transaction_date = models.DateField(db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='bank_transactions_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['transaction_date']),
            models.Index(fields=['bank_account', 'transaction_date']),
        ]

    def __str__(self):
        return f"{self.transaction_number} - {self.amount} {self.bank_account.currency}"

    def save(self, *args, **kwargs):
        if not self.transaction_number:
            self.transaction_number = f"BTXN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
        # Update bank account balance
        if self.bank_account:
            self.bank_account.update_balance()
