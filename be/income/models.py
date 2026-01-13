from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


class IncomeCategory(models.Model):
    """Categories for income"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Income Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Income(models.Model):
    """Income records"""
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
        ('received', 'Received'),
    ]

    income_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    branch = models.ForeignKey(
        'settings.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='incomes',
        help_text='Branch where income was received'
    )
    category = models.ForeignKey(
        IncomeCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incomes'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.TextField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payer = models.CharField(max_length=200, blank=True, help_text='Payer name')
    reference_number = models.CharField(max_length=100, blank=True)
    income_date = models.DateField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='incomes_created'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incomes_approved'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-income_date', '-created_at']
        indexes = [
            models.Index(fields=['income_date']),
            models.Index(fields=['status']),
            models.Index(fields=['category', 'income_date']),
        ]

    def __str__(self):
        return f"{self.income_number} - {self.amount} KES"

    def save(self, *args, **kwargs):
        if not self.income_number:
            self.income_number = f"INC-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
