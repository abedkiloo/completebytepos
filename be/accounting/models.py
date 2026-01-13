from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal


class AccountType(models.Model):
    """Account types (Asset, Liability, Equity, Revenue, Expense)"""
    TYPE_CHOICES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('expense', 'Expense'),
    ]

    name = models.CharField(max_length=50, choices=TYPE_CHOICES, unique=True)
    description = models.TextField(blank=True)
    normal_balance = models.CharField(
        max_length=10,
        choices=[('debit', 'Debit'), ('credit', 'Credit')],
        help_text='Normal balance side for this account type'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Set normal balance based on account type
        if not self.normal_balance:
            if self.name in ['asset', 'expense']:
                self.normal_balance = 'debit'
            else:  # liability, equity, revenue
                self.normal_balance = 'credit'
        super().save(*args, **kwargs)


class Account(models.Model):
    """Chart of Accounts"""
    account_code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    account_type = models.ForeignKey(
        AccountType,
        on_delete=models.PROTECT,
        related_name='accounts'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text='Parent account for sub-accounts'
    )
    description = models.TextField(blank=True)
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    current_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Current balance (calculated from transactions)'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['account_code']
        indexes = [
            models.Index(fields=['account_code']),
            models.Index(fields=['account_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.account_code} - {self.name}"

    @property
    def balance(self):
        """Get current balance"""
        return self.current_balance

    def update_balance(self):
        """Recalculate balance from journal entries"""
        from .models import JournalEntry
        debit_total = JournalEntry.objects.filter(
            account=self,
            entry_type='debit'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        credit_total = JournalEntry.objects.filter(
            account=self,
            entry_type='credit'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        if self.account_type.normal_balance == 'debit':
            self.current_balance = self.opening_balance + debit_total - credit_total
        else:
            self.current_balance = self.opening_balance + credit_total - debit_total
        
        self.save(update_fields=['current_balance'])


class JournalEntry(models.Model):
    """Double-entry journal entries"""
    ENTRY_TYPES = [
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ]

    entry_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    entry_date = models.DateField(db_index=True)
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='journal_entries'
    )
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True, help_text='Reference to source document')
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        help_text='Type of reference (sale, purchase, expense, etc.)'
    )
    reference_id = models.IntegerField(null=True, blank=True, help_text='ID of reference document')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='journal_entries_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-entry_date', '-created_at']
        verbose_name_plural = "Journal Entries"
        indexes = [
            models.Index(fields=['entry_date']),
            models.Index(fields=['account', 'entry_date']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]

    def __str__(self):
        return f"{self.entry_number} - {self.account.name} - {self.entry_type} {self.amount}"

    def save(self, *args, **kwargs):
        if not self.entry_number:
            import uuid
            self.entry_number = f"JE-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
        # Update account balance
        if self.account:
            self.account.update_balance()

    def delete(self, *args, **kwargs):
        account = self.account
        super().delete(*args, **kwargs)
        # Recalculate account balance after deletion
        if account:
            account.update_balance()


class Transaction(models.Model):
    """Transaction linking journal entries (double-entry)"""
    transaction_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    transaction_date = models.DateField(db_index=True)
    description = models.TextField()
    journal_entries = models.ManyToManyField(JournalEntry, related_name='transactions')
    reference = models.CharField(max_length=100, blank=True)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.IntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='transactions_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['transaction_date']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]

    def __str__(self):
        return f"{self.transaction_number} - {self.description}"

    def save(self, *args, **kwargs):
        if not self.transaction_number:
            import uuid
            self.transaction_number = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def validate_balance(self):
        """Validate that debits equal credits"""
        entries = self.journal_entries.all()
        debit_total = sum(entry.amount for entry in entries if entry.entry_type == 'debit')
        credit_total = sum(entry.amount for entry in entries if entry.entry_type == 'credit')
        return debit_total == credit_total
