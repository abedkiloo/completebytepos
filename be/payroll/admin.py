from django.contrib import admin

from payroll.models import (
    EmployeePayAssignment,
    PayComponent,
    PayrollRun,
    PayrollSettings,
    Payslip,
    PayslipLine,
    StatutoryRule,
)


@admin.register(PayrollSettings)
class PayrollSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'tenant',
        'currency',
        'pay_day',
        'statutory_enabled',
        'include_appraisal_bonus',
    )


@admin.register(PayComponent)
class PayComponentAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'kind',
        'calculation_type',
        'is_statutory',
        'is_active',
        'sort_order',
    )
    list_filter = ('kind', 'is_active', 'is_statutory')
    search_fields = ('code', 'name')


@admin.register(EmployeePayAssignment)
class EmployeePayAssignmentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'component', 'amount', 'rate', 'is_active')
    list_filter = ('is_active',)


@admin.register(StatutoryRule)
class StatutoryRuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'component')


class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0
    readonly_fields = (
        'code',
        'name',
        'kind',
        'amount',
        'is_taxable',
        'sort_order',
    )


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id_snapshot',
        'employee_name_snapshot',
        'run',
        'gross_pay',
        'net_pay',
    )
    inlines = [PayslipLineInline]
    search_fields = ('employee_id_snapshot', 'employee_name_snapshot')


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = (
        'year',
        'month',
        'status',
        'employee_count',
        'gross_total',
        'net_total',
        'locked_at',
    )
    list_filter = ('status', 'year')
