"""Payroll models — monthly runs, components, payslips, and tenant settings."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class PayrollSettings(models.Model):
    """Per-tenant payroll configuration (config-over-code)."""

    tenant = models.OneToOneField(
        'settings.Tenant',
        on_delete=models.CASCADE,
        related_name='payroll_settings',
        null=True,
        blank=True,
        help_text='Null = default / single-tenant store settings',
    )
    currency = models.CharField(max_length=8, default='KES')
    pay_day = models.PositiveSmallIntegerField(
        default=28,
        help_text='Day of month payroll typically runs (1–28)',
    )
    statutory_enabled = models.BooleanField(
        default=False,
        help_text='When off, statutory deduction rules stay dormant (no calculation)',
    )
    include_appraisal_bonus = models.BooleanField(
        default=True,
        help_text='Pull monthly target-delivery bonus into earnings when calculating',
    )
    letterhead_line = models.CharField(
        max_length=255,
        blank=True,
        help_text='Optional extra letterhead line under the store brand on payslips',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payroll settings'
        verbose_name_plural = 'Payroll settings'

    def __str__(self):
        label = self.tenant.code if self.tenant_id else 'default'
        return f'PayrollSettings({label})'

    @classmethod
    def load(cls, tenant=None):
        if tenant is not None:
            obj, _ = cls.objects.get_or_create(tenant=tenant)
            return obj
        obj = cls.objects.filter(tenant__isnull=True).first()
        if obj:
            return obj
        default_tenant = None
        try:
            from settings.models import Tenant

            default_tenant = Tenant.get_default_tenant()
        except Exception:
            default_tenant = None
        if default_tenant is not None:
            obj, _ = cls.objects.get_or_create(tenant=default_tenant)
            return obj
        obj, _ = cls.objects.get_or_create(tenant=None)
        return obj


class PayComponent(models.Model):
    """Catalog of earnings / deductions / employer contributions."""

    KIND_EARNING = 'earning'
    KIND_DEDUCTION = 'deduction'
    KIND_EMPLOYER = 'employer'
    KIND_CHOICES = [
        (KIND_EARNING, 'Earning'),
        (KIND_DEDUCTION, 'Deduction'),
        (KIND_EMPLOYER, 'Employer contribution'),
    ]

    CALC_FIXED = 'fixed'
    CALC_PERCENT_BASIC = 'percent_basic'
    CALC_PERCENT_GROSS = 'percent_gross'
    CALC_FORMULA = 'formula'
    CALC_CHOICES = [
        (CALC_FIXED, 'Fixed amount'),
        (CALC_PERCENT_BASIC, '% of basic'),
        (CALC_PERCENT_GROSS, '% of gross'),
        (CALC_FORMULA, 'Formula / adapter'),
    ]

    code = models.CharField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_EARNING)
    calculation_type = models.CharField(
        max_length=20, choices=CALC_CHOICES, default=CALC_FIXED
    )
    default_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    default_rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text='Rate when calculation is percent_* (e.g. 0.05 = 5%)',
    )
    is_taxable = models.BooleanField(default=True)
    is_statutory = models.BooleanField(
        default=False,
        help_text='Statutory components only apply when PayrollSettings.statutory_enabled',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Pay component'
        verbose_name_plural = 'Pay components'

    def __str__(self):
        return f'{self.code} — {self.name}'


class RolePayPackage(models.Model):
    """
    Default pay package for a job role (e.g. Sales Personnel, Manager).

    Applied at calculate time; EmployeePayAssignment overrides per person.
    """

    role = models.OneToOneField(
        'accounts.Role',
        on_delete=models.CASCADE,
        related_name='pay_package',
    )
    name = models.CharField(
        max_length=120,
        blank=True,
        help_text='Display name; defaults to role name + “ package”',
    )
    default_basic = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Used when the employee has no salary set and no BASIC override',
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role__name']
        verbose_name = 'Role pay package'
        verbose_name_plural = 'Role pay packages'

    def __str__(self):
        return self.name or f'{self.role.name} package'

    def display_name(self):
        return (self.name or '').strip() or f'{self.role.name} package'


class RolePayPackageLine(models.Model):
    """One earning/deduction line in a role package."""

    package = models.ForeignKey(
        RolePayPackage,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    component = models.ForeignKey(
        PayComponent,
        on_delete=models.PROTECT,
        related_name='role_package_lines',
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Fixed amount for this role; null = component default / %',
    )
    rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Percent override for this role',
    )
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['sort_order', 'id']
        unique_together = [['package', 'component']]
        verbose_name = 'Role pay package line'
        verbose_name_plural = 'Role pay package lines'

    def __str__(self):
        return f'{self.package_id}:{self.component.code}'


class EmployeePayAssignment(models.Model):
    """Per-employee override or extra component for a period."""

    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='pay_assignments',
    )
    component = models.ForeignKey(
        PayComponent,
        on_delete=models.PROTECT,
        related_name='assignments',
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Override fixed amount; null = use component default',
    )
    rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Override percent rate; null = use component default',
    )
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_id', 'component__sort_order']
        unique_together = [['employee', 'component']]
        verbose_name = 'Employee pay assignment'
        verbose_name_plural = 'Employee pay assignments'

    def __str__(self):
        return f'{self.employee_id}:{self.component.code}'


class StatutoryRule(models.Model):
    """Dormant statutory deduction definitions (NHIF/NSSF/PAYE etc.)."""

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    component = models.ForeignKey(
        PayComponent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='statutory_rules',
    )
    is_active = models.BooleanField(
        default=False,
        help_text='Must be active AND PayrollSettings.statutory_enabled to apply',
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Bands / rates — unused while statutory is off',
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'Statutory rule'
        verbose_name_plural = 'Statutory rules'

    def __str__(self):
        return self.code


class PayrollRun(models.Model):
    """One monthly payroll cycle for a company/tenant."""

    STATUS_DRAFT = 'draft'
    STATUS_CALCULATED = 'calculated'
    STATUS_PENDING_APPROVAL = 'pending_approval'
    STATUS_LOCKED = 'locked'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_CALCULATED, 'Calculated'),
        (STATUS_PENDING_APPROVAL, 'Pending approval'),
        (STATUS_LOCKED, 'Locked'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    tenant = models.ForeignKey(
        'settings.Tenant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payroll_runs',
    )
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True
    )
    period_start = models.DateField()
    period_end = models.DateField()
    notes = models.TextField(blank=True)

    gross_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    deduction_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    net_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    employee_count = models.PositiveIntegerField(default=0)

    calculated_at = models.DateTimeField(null=True, blank=True)
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payroll_runs_calculated',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payroll_runs_submitted',
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payroll_runs_locked',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payroll_runs_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month']
        unique_together = [['tenant', 'year', 'month']]
        verbose_name = 'Payroll run'
        verbose_name_plural = 'Payroll runs'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['year', 'month']),
        ]

    def __str__(self):
        return f'Payroll {self.year}-{self.month:02d} ({self.status})'

    @property
    def period_label(self):
        return f'{self.year}-{self.month:02d}'

    @property
    def is_immutable(self):
        return self.status == self.STATUS_LOCKED


class Payslip(models.Model):
    """Immutable snapshot of one employee's pay for a run (once run is locked)."""

    run = models.ForeignKey(
        PayrollRun, on_delete=models.CASCADE, related_name='payslips'
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
        related_name='payslips',
    )
    # Snapshot fields — frozen at calculate time
    employee_id_snapshot = models.CharField(max_length=50)
    employee_name_snapshot = models.CharField(max_length=200)
    position_snapshot = models.CharField(max_length=100, blank=True)
    department_snapshot = models.CharField(max_length=50, blank=True)
    bank_name_snapshot = models.CharField(max_length=120, blank=True)
    bank_account_snapshot = models.CharField(max_length=60, blank=True)

    basic_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    gross_pay = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    total_deductions = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    net_pay = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    currency = models.CharField(max_length=8, default='KES')
    bonus_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Appraisal bonus frozen at calculate time',
    )
    calculation_meta = models.JSONField(
        default=dict,
        blank=True,
        help_text='Adapter notes, attendance/loan stubs, etc.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_name_snapshot']
        unique_together = [['run', 'employee']]
        verbose_name = 'Payslip'
        verbose_name_plural = 'Payslips'
        indexes = [
            models.Index(fields=['employee', 'run']),
        ]

    def __str__(self):
        return f'{self.employee_id_snapshot} {self.run.period_label}'


class PayslipLine(models.Model):
    """One earning or deduction line on a payslip."""

    payslip = models.ForeignKey(
        Payslip, on_delete=models.CASCADE, related_name='lines'
    )
    component = models.ForeignKey(
        PayComponent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payslip_lines',
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_taxable = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Payslip line'
        verbose_name_plural = 'Payslip lines'

    def __str__(self):
        return f'{self.code}: {self.amount}'
