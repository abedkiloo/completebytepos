from rest_framework import serializers

from payroll.models import (
    EmployeePayAssignment,
    PayComponent,
    PayrollRun,
    PayrollSettings,
    Payslip,
    PayslipLine,
    StatutoryRule,
)


class PayrollSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollSettings
        fields = [
            'id',
            'tenant',
            'currency',
            'pay_day',
            'statutory_enabled',
            'include_appraisal_bonus',
            'letterhead_line',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PayComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayComponent
        fields = [
            'id',
            'code',
            'name',
            'kind',
            'calculation_type',
            'default_amount',
            'default_rate',
            'is_taxable',
            'is_statutory',
            'is_active',
            'sort_order',
            'description',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeePayAssignmentSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source='component.code', read_only=True)
    component_name = serializers.CharField(source='component.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_id', read_only=True)

    class Meta:
        model = EmployeePayAssignment
        fields = [
            'id',
            'employee',
            'employee_code',
            'employee_name',
            'component',
            'component_code',
            'component_name',
            'amount',
            'rate',
            'is_active',
            'effective_from',
            'effective_to',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StatutoryRuleSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(
        source='component.code', read_only=True, allow_null=True
    )

    class Meta:
        model = StatutoryRule
        fields = [
            'id',
            'code',
            'name',
            'component',
            'component_code',
            'is_active',
            'config',
            'description',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PayslipLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipLine
        fields = [
            'id',
            'code',
            'name',
            'kind',
            'amount',
            'is_taxable',
            'sort_order',
            'meta',
        ]


class PayslipSerializer(serializers.ModelSerializer):
    lines = PayslipLineSerializer(many=True, read_only=True)
    period = serializers.CharField(source='run.period_label', read_only=True)
    run_status = serializers.CharField(source='run.status', read_only=True)
    year = serializers.IntegerField(source='run.year', read_only=True)
    month = serializers.IntegerField(source='run.month', read_only=True)

    class Meta:
        model = Payslip
        fields = [
            'id',
            'run',
            'employee',
            'period',
            'year',
            'month',
            'run_status',
            'employee_id_snapshot',
            'employee_name_snapshot',
            'position_snapshot',
            'department_snapshot',
            'bank_name_snapshot',
            'bank_account_snapshot',
            'basic_salary',
            'gross_pay',
            'total_deductions',
            'net_pay',
            'currency',
            'bonus_snapshot',
            'calculation_meta',
            'lines',
            'created_at',
        ]


class PayslipListSerializer(serializers.ModelSerializer):
    period = serializers.CharField(source='run.period_label', read_only=True)
    run_status = serializers.CharField(source='run.status', read_only=True)

    class Meta:
        model = Payslip
        fields = [
            'id',
            'run',
            'employee',
            'period',
            'run_status',
            'employee_id_snapshot',
            'employee_name_snapshot',
            'gross_pay',
            'total_deductions',
            'net_pay',
            'currency',
            'bonus_snapshot',
        ]


class PayrollRunSerializer(serializers.ModelSerializer):
    period = serializers.CharField(source='period_label', read_only=True)
    can_calculate = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = PayrollRun
        fields = [
            'id',
            'tenant',
            'year',
            'month',
            'period',
            'status',
            'period_start',
            'period_end',
            'notes',
            'gross_total',
            'deduction_total',
            'net_total',
            'employee_count',
            'calculated_at',
            'submitted_at',
            'locked_at',
            'created_at',
            'updated_at',
            'can_calculate',
            'can_submit',
            'can_approve',
            'can_cancel',
        ]
        read_only_fields = [
            'id',
            'status',
            'period_start',
            'period_end',
            'gross_total',
            'deduction_total',
            'net_total',
            'employee_count',
            'calculated_at',
            'submitted_at',
            'locked_at',
            'created_at',
            'updated_at',
        ]

    def get_can_calculate(self, obj):
        return obj.status in (
            PayrollRun.STATUS_DRAFT,
            PayrollRun.STATUS_CALCULATED,
        )

    def get_can_submit(self, obj):
        return obj.status == PayrollRun.STATUS_CALCULATED and obj.employee_count > 0

    def get_can_approve(self, obj):
        return obj.status == PayrollRun.STATUS_PENDING_APPROVAL

    def get_can_cancel(self, obj):
        return obj.status not in (
            PayrollRun.STATUS_LOCKED,
            PayrollRun.STATUS_CANCELLED,
        )


class PayrollRunCreateSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
