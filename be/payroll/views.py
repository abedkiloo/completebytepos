from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasPermission
from payroll.models import (
    EmployeePayAssignment,
    PayComponent,
    PayrollRun,
    PayrollSettings,
    Payslip,
    RolePayPackage,
    RolePayPackageLine,
    StatutoryRule,
)
from payroll.pdf import build_payslip_pdf
from payroll.reports import run_summary, year_overview
from payroll.serializers import (
    EmployeePayAssignmentSerializer,
    PayComponentSerializer,
    PayrollRunCreateSerializer,
    PayrollRunSerializer,
    PayrollSettingsSerializer,
    PayslipListSerializer,
    PayslipSerializer,
    RolePayPackageLineSerializer,
    RolePayPackageSerializer,
    RolePayPackageWriteSerializer,
    StatutoryRuleSerializer,
)
from payroll.services import (
    PayrollError,
    approve_and_lock,
    calculate_run,
    cancel_run,
    create_run,
    employee_for_user,
    reject_to_calculated,
    submit_run,
)
from payroll.starters import seed_starter_components
from settings.models import Tenant


def _perm(module, action):
    return [IsAuthenticated(), HasPermission(module, action)]


class PayrollSettingsView(APIView):
    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH'):
            return [IsAuthenticated(), HasPermission('payroll', 'manage')]
        return [IsAuthenticated(), HasPermission('payroll', 'view')]

    def get(self, request):
        settings = PayrollSettings.load()
        return Response(PayrollSettingsSerializer(settings).data)

    def put(self, request):
        return self._update(request)

    def patch(self, request):
        return self._update(request)

    def _update(self, request):
        settings = PayrollSettings.load()
        ser = PayrollSettingsSerializer(settings, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class PayComponentViewSet(viewsets.ModelViewSet):
    queryset = PayComponent.objects.all()
    serializer_class = PayComponentSerializer
    lookup_field = 'pk'

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return _perm('payroll', 'view')
        return _perm('payroll', 'manage')

    def get_queryset(self):
        qs = super().get_queryset()
        kind = self.request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        active = self.request.query_params.get('is_active')
        if active is not None:
            qs = qs.filter(is_active=active.lower() in ('1', 'true', 'yes'))
        return qs

    @action(detail=False, methods=['post'], url_path='seed-starters')
    def seed_starters(self, request):
        created = seed_starter_components()
        return Response({'created': created})


class EmployeePayAssignmentViewSet(viewsets.ModelViewSet):
    queryset = EmployeePayAssignment.objects.select_related(
        'employee', 'component'
    ).all()
    serializer_class = EmployeePayAssignmentSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return _perm('payroll', 'view')
        return _perm('payroll', 'manage')

    def get_queryset(self):
        qs = super().get_queryset()
        emp = self.request.query_params.get('employee')
        if emp:
            qs = qs.filter(employee_id=emp)
        return qs


class RolePayPackageViewSet(viewsets.ModelViewSet):
    queryset = RolePayPackage.objects.select_related('role').prefetch_related(
        'lines__component'
    )
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RolePayPackageWriteSerializer
        return RolePayPackageSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return _perm('payroll', 'view')
        return _perm('payroll', 'manage')

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role_id=role)
        return qs

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(RolePayPackageSerializer(instance).data)

    def create(self, request, *args, **kwargs):
        ser = RolePayPackageWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        package = ser.save()
        if not package.name:
            package.name = f'{package.role.name} package'
            package.save(update_fields=['name'])
        return Response(
            RolePayPackageSerializer(
                RolePayPackage.objects.prefetch_related('lines__component').get(
                    pk=package.pk
                )
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        ser = RolePayPackageWriteSerializer(
            instance, data=request.data, partial=partial
        )
        ser.is_valid(raise_exception=True)
        package = ser.save()
        return Response(
            RolePayPackageSerializer(
                RolePayPackage.objects.prefetch_related('lines__component').get(
                    pk=package.pk
                )
            ).data
        )

    @action(detail=True, methods=['post'], url_path='lines')
    def add_line(self, request, pk=None):
        package = self.get_object()
        data = {**request.data, 'package': package.id}
        ser = RolePayPackageLineSerializer(data=data)
        ser.is_valid(raise_exception=True)
        ser.save()
        package = RolePayPackage.objects.prefetch_related('lines__component').get(
            pk=package.pk
        )
        return Response(
            RolePayPackageSerializer(package).data, status=status.HTTP_201_CREATED
        )


class RolePayPackageLineViewSet(viewsets.ModelViewSet):
    queryset = RolePayPackageLine.objects.select_related('component', 'package')
    serializer_class = RolePayPackageLineSerializer
    http_method_names = ['get', 'patch', 'put', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return _perm('payroll', 'view')
        return _perm('payroll', 'manage')

    def get_queryset(self):
        qs = super().get_queryset()
        package = self.request.query_params.get('package')
        if package:
            qs = qs.filter(package_id=package)
        return qs


class StatutoryRuleViewSet(viewsets.ModelViewSet):
    queryset = StatutoryRule.objects.select_related('component').all()
    serializer_class = StatutoryRuleSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return _perm('payroll', 'view')
        return _perm('payroll', 'manage')


class PayrollRunViewSet(viewsets.ModelViewSet):
    queryset = PayrollRun.objects.all()
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return PayrollRunCreateSerializer
        return PayrollRunSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'payslips', 'summary'):
            return _perm('payroll', 'view')
        if self.action == 'create':
            return _perm('payroll', 'create')
        if self.action == 'calculate':
            return _perm('payroll', 'update')
        if self.action == 'submit':
            return _perm('payroll', 'update')
        if self.action in ('approve', 'reject'):
            return _perm('payroll', 'approve')
        if self.action == 'cancel':
            return _perm('payroll', 'update')
        return _perm('payroll', 'view')

    def get_queryset(self):
        qs = super().get_queryset()
        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        st = self.request.query_params.get('status')
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)
        if st:
            qs = qs.filter(status=st)
        return qs

    def create(self, request, *args, **kwargs):
        ser = PayrollRunCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tenant = Tenant.get_default_tenant()
        try:
            run = create_run(
                year=ser.validated_data['year'],
                month=ser.validated_data['month'],
                notes=ser.validated_data.get('notes') or '',
                user=request.user,
                tenant=tenant,
                request=request,
            )
        except PayrollError as exc:
            return Response({'detail': exc.message}, status=exc.status)
        return Response(
            PayrollRunSerializer(run).data, status=status.HTTP_201_CREATED
        )

    def _run_action(self, request, fn, **kwargs):
        run = self.get_object()
        try:
            run = fn(run, user=request.user, request=request, **kwargs)
        except PayrollError as exc:
            return Response({'detail': exc.message}, status=exc.status)
        return Response(PayrollRunSerializer(run).data)

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        return self._run_action(request, calculate_run)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return self._run_action(request, submit_run)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._run_action(request, approve_and_lock)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        reason = (request.data or {}).get('reason') or ''
        return self._run_action(request, reject_to_calculated, reason=reason)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return self._run_action(request, cancel_run)

    @action(detail=True, methods=['get'])
    def payslips(self, request, pk=None):
        run = self.get_object()
        qs = run.payslips.select_related('employee').prefetch_related('lines')
        return Response(PayslipListSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        run = self.get_object()
        return Response(run_summary(run))


class PayslipViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payslip.objects.select_related('run', 'employee').prefetch_related(
        'lines'
    )

    def get_serializer_class(self):
        if self.action == 'list':
            return PayslipListSerializer
        return PayslipSerializer

    def get_permissions(self):
        return _perm('payroll', 'view')

    def get_queryset(self):
        qs = super().get_queryset()
        run = self.request.query_params.get('run')
        employee = self.request.query_params.get('employee')
        if run:
            qs = qs.filter(run_id=run)
        if employee:
            qs = qs.filter(employee_id=employee)
        return qs

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        payslip = self.get_object()
        pdf_bytes = build_payslip_pdf(payslip)
        filename = (
            f'payslip_{payslip.employee_id_snapshot}_'
            f'{payslip.run.period_label}.pdf'
        )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class MyPayslipsView(APIView):
    """Employee self-service — locked payslips matched by user email."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        emp = employee_for_user(request.user)
        # Admins with payroll.view can also pass ?employee=
        if emp is None:
            profile = getattr(request.user, 'profile', None)
            can_view = False
            if profile and hasattr(profile, 'has_permission'):
                can_view = profile.has_permission('payroll', 'view')
            if request.user.is_superuser:
                can_view = True
            emp_id = request.query_params.get('employee')
            if can_view and emp_id:
                qs = Payslip.objects.filter(
                    employee_id=emp_id, run__status=PayrollRun.STATUS_LOCKED
                )
            else:
                return Response(
                    {
                        'detail': 'No employee record linked to your account email.',
                        'results': [],
                    },
                    status=status.HTTP_200_OK,
                )
        else:
            qs = Payslip.objects.filter(
                employee=emp, run__status=PayrollRun.STATUS_LOCKED
            )
        qs = qs.select_related('run').order_by('-run__year', '-run__month')
        return Response(PayslipListSerializer(qs, many=True).data)


class MyPayslipPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        emp = employee_for_user(request.user)
        payslip = (
            Payslip.objects.select_related('run')
            .prefetch_related('lines')
            .filter(pk=pk, run__status=PayrollRun.STATUS_LOCKED)
            .first()
        )
        if payslip is None:
            return Response({'detail': 'Not found'}, status=404)

        profile = getattr(request.user, 'profile', None)
        can_view_all = request.user.is_superuser or (
            profile and profile.has_permission('payroll', 'view')
        )
        if emp is None and not can_view_all:
            return Response({'detail': 'Forbidden'}, status=403)
        if emp is not None and payslip.employee_id != emp.id and not can_view_all:
            return Response({'detail': 'Forbidden'}, status=403)

        pdf_bytes = build_payslip_pdf(payslip)
        filename = (
            f'payslip_{payslip.employee_id_snapshot}_'
            f'{payslip.run.period_label}.pdf'
        )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class PayrollYearReportView(APIView):
    def get_permissions(self):
        return _perm('payroll', 'view')

    def get(self, request):
        try:
            year = int(request.query_params.get('year') or timezone_year())
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid year'}, status=400)
        return Response(year_overview(year=year, tenant=Tenant.get_default_tenant()))


def timezone_year():
    from django.utils import timezone

    return timezone.localdate().year
