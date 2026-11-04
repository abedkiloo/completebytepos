"""
Employee roster queries and aggregate statistics.

Public entry points:
    - ``EmployeeService.build_queryset`` / ``get_employee_statistics``
    - HTTP under ``/api/employees/``

Does not mutate payroll runs or appraisal increments.
"""
from typing import Optional, Dict, Any
from decimal import Decimal

from django.db.models import Q, Count, Sum, QuerySet
from .models import Employee
from services.base import BaseService


class EmployeeService(BaseService):
    """
    List filters and roster aggregates for ``Employee``.

    Views stay thin and call these methods. Mutations (create/update/delete)
    go through the ViewSet + serializers; this service is read-oriented.
    """

    def __init__(self):
        super().__init__(Employee)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build a filtered employee listing queryset.

        Args:
            filters: Optional map of query params:
                - ``search`` (str): Case-insensitive match across name, codes,
                  email, phone, position. Empty/None = no search filter.
                - ``status`` (str): Exact status choice (e.g. ``active``).
                - ``department`` (str): Exact department choice.
                - ``role`` (int|str): ``custom_role`` id on the linked user's
                  profile. Invalid ids yield an empty match set via ORM.

        Returns:
            ``QuerySet[Employee]`` with ``user`` / profile / custom_role
            selected, ordered by ``-created_at``. No hard page-size cap here —
            pagination belongs to the ViewSet.
        """
        queryset = self.model.objects.select_related(
            'user', 'user__profile', 'user__profile__custom_role'
        )
        
        if not filters:
            return queryset.order_by('-created_at')
        
        search = filters.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(id_number__icontains=search) |
                Q(email__icontains=search) |
                Q(user__email__icontains=search) |
                Q(position__icontains=search) |
                Q(phone__icontains=search)
            )
        
        status_filter = filters.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        department = filters.get('department')
        if department:
            queryset = queryset.filter(department=department)

        role = filters.get('role')
        if role:
            queryset = queryset.filter(user__profile__custom_role_id=role)
        
        return queryset.order_by('-created_at')
    
    def get_employee_statistics(self, queryset: Optional[QuerySet] = None) -> Dict[str, Any]:
        """
        Aggregate headcount and salary totals for a (possibly filtered) set.

        Args:
            queryset: Employees to aggregate. ``None`` means all rows (unscoped
                by tenant). Salary sum ignores null salaries; counts include them.

        Returns:
            Dict with ``total_employees``, ``active_employees``,
            ``inactive_employees``, ``total_salary`` (str Decimal),
            ``employees_with_salary``, and breakdown lists by department,
            status, and custom role. Counts are unbounded by the full table size.
        """
        if queryset is None:
            queryset = self.model.objects.all()
        
        total_employees = queryset.count()
        active_employees = queryset.filter(status='active').count()
        inactive_employees = queryset.filter(status='inactive').count()
        salary_agg = queryset.aggregate(
            total_salary=Sum('salary'),
            with_salary=Count('id', filter=Q(salary__isnull=False)),
        )
        total_salary = salary_agg.get('total_salary') or Decimal('0.00')
        
        employees_by_department = list(
            queryset.values('department')
            .annotate(count=Count('id'), salary_total=Sum('salary'))
            .order_by('-count')
        )
        
        employees_by_status = list(
            queryset.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        employees_by_role = list(
            queryset.filter(user__profile__custom_role_id__isnull=False)
            .values(
                'user__profile__custom_role_id',
                'user__profile__custom_role__name',
            )
            .annotate(count=Count('id'), salary_total=Sum('salary'))
            .order_by('-count')
        )
        for row in employees_by_role:
            row['role_id'] = row.pop('user__profile__custom_role_id')
            row['role_name'] = row.pop('user__profile__custom_role__name')
        
        return {
            'total_employees': total_employees,
            'active_employees': active_employees,
            'inactive_employees': inactive_employees,
            'total_salary': str(total_salary),
            'employees_with_salary': salary_agg.get('with_salary') or 0,
            'employees_by_department': employees_by_department,
            'employees_by_status': employees_by_status,
            'employees_by_role': employees_by_role,
        }
