from django.urls import include, path
from rest_framework.routers import DefaultRouter

from payroll.views import (
    EmployeePayAssignmentViewSet,
    MyPayView,
    MyPayslipPdfView,
    MyPayslipsView,
    PayComponentViewSet,
    PayrollRunViewSet,
    PayrollSettingsView,
    PayrollYearReportView,
    PayslipViewSet,
    RolePayPackageLineViewSet,
    RolePayPackageViewSet,
    StatutoryRuleViewSet,
)

router = DefaultRouter()
router.register(r'components', PayComponentViewSet, basename='payroll-component')
router.register(r'assignments', EmployeePayAssignmentViewSet, basename='payroll-assignment')
router.register(r'packages', RolePayPackageViewSet, basename='payroll-package')
router.register(
    r'package-lines', RolePayPackageLineViewSet, basename='payroll-package-line'
)
router.register(r'statutory', StatutoryRuleViewSet, basename='payroll-statutory')
router.register(r'runs', PayrollRunViewSet, basename='payroll-run')
router.register(r'payslips', PayslipViewSet, basename='payroll-payslip')

urlpatterns = [
    path('settings/', PayrollSettingsView.as_view(), name='payroll-settings'),
    path('me/pay/', MyPayView.as_view(), name='payroll-my-pay'),
    path('me/payslips/', MyPayslipsView.as_view(), name='payroll-my-payslips'),
    path(
        'me/payslips/<int:pk>/pdf/',
        MyPayslipPdfView.as_view(),
        name='payroll-my-payslip-pdf',
    ),
    path('reports/year/', PayrollYearReportView.as_view(), name='payroll-year-report'),
    path('', include(router.urls)),
]
