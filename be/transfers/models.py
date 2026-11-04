"""
Inter-account and cash money transfers with approval status.

Public entry points:
    - ``MoneyTransfer`` ORM model
    - ``MoneyTransferService`` in ``be.transfers.services``

Side effects: when ``status`` is ``completed``, ``save`` refreshes
``from_account`` / ``to_account`` balances via ``BankAccount.update_balance``.
Pending or cancelled transfers do not change bank balances on save alone.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from bankaccounts.models import BankAccount
import uuid


class MoneyTransfer(models.Model):
    """
    Documented movement of funds between bank accounts and/or cash.

    ``from_account`` / ``to_account`` may be null for cash legs. Balance impact
    is tied to ``completed`` status (see ``save`` and approve service).

    Attributes:
        amount: Transfer principal ≥ 0.01 (12,2 decimals).
        fees: Additional fees ≥ 0.00; not auto-deducted from amount in model.
        status: pending, processing, completed, failed, cancelled.
        transfer_type: bank_to_bank, bank_to_cash, cash_to_bank, cash_to_cash.
    """

    TRANSFER_TYPES = [
        ('bank_to_bank', 'Bank to Bank'),
        ('bank_to_cash', 'Bank to Cash'),
        ('cash_to_bank', 'Cash to Bank'),
        ('cash_to_cash', 'Cash to Cash'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    transfer_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPES)
    from_account = models.ForeignKey(
        'bankaccounts.BankAccount',
        on_delete=models.PROTECT,
        related_name='transfers_out',
        null=True,
        blank=True,
        help_text='Source account (null for cash)'
    )
    to_account = models.ForeignKey(
        'bankaccounts.BankAccount',
        on_delete=models.PROTECT,
        related_name='transfers_in',
        null=True,
        blank=True,
        help_text='Destination account (null for cash)'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='KES')
    transfer_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True)
    fees = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Transfer fees'
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('1.0000'),
        help_text='Exchange rate if different currencies'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='transfers_created'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfers_approved'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transfer_date', '-created_at']
        indexes = [
            models.Index(fields=['transfer_date']),
            models.Index(fields=['status']),
            models.Index(fields=['from_account', 'to_account']),
        ]

    def __str__(self):
        return f"{self.transfer_number} - {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        """
        Persist transfer and refresh bank balances when completed.

        Assigns ``TRF-{8 hex upper}`` when ``transfer_number`` is empty.

        Side effects:
            When ``status == 'completed'``, calls ``update_balance`` on non-null
            ``from_account`` and ``to_account``.
        """
        if not self.transfer_number:
            self.transfer_number = f"TRF-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

        # Update account balances when completed
        if self.status == 'completed':
            if self.from_account:
                self.from_account.update_balance()
            if self.to_account:
                self.to_account.update_balance()
