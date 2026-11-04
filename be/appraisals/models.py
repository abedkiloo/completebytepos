"""Persisted salary-increment decisions. Daily/monthly stars still rebuild from sales."""

from django.conf import settings
from django.db import models


class AppraisalSalaryIncrement(models.Model):
    """
    Year-end salary increment decision for one ``(user, year)``.

    Stars/bonus math rebuild from posted sales on read; this row persists
    eligibility amounts and approve/reject. On approve, ``Employee.salary`` is
    set to ``new_basic`` when an employee record exists.

    Bounds:
        - ``year``: positive calendar year (API typically clamps [2000, 2100]).
        - Money fields: Decimal max_digits=12, 2 dp, default 0.
        - ``four_star_months_required`` default 8 (policy may override at calc).
        - ``reason`` truncated to 500 chars on decide.
    """

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_NOT_ELIGIBLE = 'not_eligible'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_NOT_ELIGIBLE, 'Not eligible'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appraisal_increments',
    )
    year = models.PositiveIntegerField()
    role_name = models.CharField(max_length=120, blank=True)
    previous_basic = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    increment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    new_basic = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_average = models.FloatField(default=0)
    four_star_months = models.PositiveSmallIntegerField(default=0)
    four_star_months_required = models.PositiveSmallIntegerField(default=8)
    qualifies = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    effective_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appraisal_increments_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'year')
        ordering = ['-year', 'user_id']

    def __str__(self):
        return f'{self.user_id}:{self.year}:{self.status}'
