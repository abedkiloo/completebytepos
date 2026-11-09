from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal


class ExpenseCategory(models.Model):
    """
    Expense taxonomy row.

    ``name`` is unique (max 100). When ``include_in_trading_profit`` is False,
    approved expenses in this category are excluded from trading P&L.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    include_in_trading_profit = models.BooleanField(
        default=True,
        help_text=(
            'When true (default), approved expenses in this category are subtracted '
            'in trading profit. Turn off for categories that should not affect trading P&L '
            '(e.g. owner drawings).'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Expense Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Expense(models.Model):
    """
    Operating expense voucher.

    Bounds:
        - ``amount``: Decimal ≥ 0.01, max_digits=10, 2 dp.
        - ``expense_number``: auto ``EXP-`` + 8 hex chars; unique.
        - ``status``: pending → approved|rejected|paid|voided (via services).

    ``expense_date`` is the business day the cost occurred (not create time).
    """

    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-PESA'),
        ('bank', 'Bank Transfer'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
        ('voided', 'Voided'),
    ]

    expense_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    branch = models.ForeignKey(
        'settings.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='expenses',
        help_text='Branch where expense was incurred'
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.TextField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    vendor = models.CharField(max_length=200, blank=True, help_text='Vendor/Supplier name')
    receipt_number = models.CharField(max_length=100, blank=True)
    image = models.ImageField(
        upload_to='expenses/',
        blank=True,
        null=True,
        help_text='Optional photo of the expense receipt or proof of payment.',
    )
    expense_date = models.DateField(
        help_text='The day this expense occurred, not the day it was recorded.',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='expenses_created'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses_approved'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['expense_date']),
            models.Index(fields=['status']),
            models.Index(fields=['category', 'expense_date']),
        ]

    def __str__(self):
        return f"{self.expense_number} - {self.amount} KES"

    def save(self, *args, **kwargs):
        if not self.expense_number:
            import uuid
            self.expense_number = f"EXP-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
