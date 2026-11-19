"""
HTTP API for one-day leave and sick days.

Signed-in staff with ``employees.leave_request`` may ask. A manager or
director with ``employees.leave_approve`` may decide the requests they
are allowed to see. The employees.leave_requests feature must be on.
"""

from datetime import datetime

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import RequirePerm
from employees.leave import (
    allowance_payload,
    allowance_people,
    decide_leave,
    file_leave,
    leave_rows,
    row_payload,
    set_person_leave_days,
    set_shop_leave_days,
    user_may_configure_leave,
)
from employees.models import LeaveRequest
from employees.module_settings import employees_monthly_leave_days
from settings.feature_permissions import RequireModuleFeature


class _LeaveFeature(RequireModuleFeature):
    """Gate leave on the employees.leave_requests package toggle."""

    def __init__(self):
        """
        Bind this permission to the leave feature.

        Returns:
            None.
        """
        super().__init__('employees', 'leave_requests')


class LeaveRequestListView(APIView):
    """List the signed-in person's leave and file a new day."""

    permission_classes = [IsAuthenticated, _LeaveFeature, RequirePerm('employees', 'leave_request')]

    def get(self, request):
        """
        Return up to 100 requests this person may see.

        Args:
            request: Authenticated request.

        Returns:
            Response: ``{"results": [...]}``. No phone numbers.
        """
        raw_day = str(request.query_params.get('day') or '').strip()[:10]
        try:
            day = datetime.strptime(raw_day, '%Y-%m-%d').date() if raw_day else timezone.localdate()
        except ValueError:
            day = timezone.localdate()
        rows = [row_payload(row, request.user) for row in leave_rows(request.user)]
        return Response({
            'results': rows,
            'allowance': allowance_payload(request.user, day),
            'can_configure': user_may_configure_leave(request.user),
        })

    def post(self, request):
        """
        File one day off or one sick day.

        Args:
            request: JSON ``kind`` (``leave`` or ``sick``), ``day``
                (``YYYY-MM-DD``), and optional ``note`` of 0–300 characters.

        Returns:
            Response 201 with the pending row.

        Raises:
            ValidationError: The day, kind, or note is not allowed.
        """
        kind = str(request.data.get('kind') or '').strip()[:8]
        raw_day = str(request.data.get('day') or '').strip()[:10]
        try:
            day = datetime.strptime(raw_day, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError({'day': 'Use a date like 2026-11-20.'})
        leave = file_leave(
            request.user,
            kind=kind,
            day=day,
            note=str(request.data.get('note') or '')[:400],
        )
        return Response(row_payload(leave, request.user), status=201)


class LeaveDecisionView(APIView):
    """Approve or reject one pending request."""

    permission_classes = [IsAuthenticated, _LeaveFeature, RequirePerm('employees', 'leave_approve')]

    def post(self, request, pk):
        """
        Decide one request.

        Args:
            request: JSON ``decision`` (``approved`` or ``rejected``) and
                optional ``note`` of 0–300 characters.
            pk: Leave request id, a positive integer.

        Returns:
            Response 200 with the updated row.

        Raises:
            ValidationError: Unknown id, or the request is already decided.
            PermissionDenied: This person cannot decide this employee.
        """
        try:
            leave = LeaveRequest.objects.select_related('user', 'user__profile').get(pk=pk)
        except (LeaveRequest.DoesNotExist, ValueError, TypeError):
            raise ValidationError({'id': 'That request was not found.'})
        try:
            updated = decide_leave(
                request.user,
                leave,
                decision=str(request.data.get('decision') or '').strip()[:12],
                note=str(request.data.get('note') or '')[:400],
            )
        except PermissionDenied:
            raise
        return Response(row_payload(updated, request.user))


class LeaveAllowanceView(APIView):
    """Read and change the monthly day-off number."""

    permission_classes = [IsAuthenticated, _LeaveFeature, RequirePerm('employees', 'leave_approve')]

    def get(self, request):
        """
        Return the shop number and up to 200 people.

        Args:
            request: Authenticated approver.

        Returns:
            Response: ``shop_days`` 0–31 and ``people``. No phone numbers.
        """
        return Response({
            'shop_days': employees_monthly_leave_days(),
            'people': allowance_people(),
        })

    def patch(self, request):
        """
        Change the shop number, or one person's number.

        Args:
            request: JSON ``monthly_leave_days`` 0–31. Include ``user_id``
                to change one person. Send ``monthly_leave_days`` as null
                with ``user_id`` to use the shop number again.

        Returns:
            Response 200 with the saved shop number or the person's row.

        Raises:
            ValidationError: The number is outside 0–31 or the person is unknown.
        """
        if request.data.get('user_id') not in (None, ''):
            row = set_person_leave_days(
                request.user,
                request.data.get('user_id'),
                request.data.get('monthly_leave_days', None),
            )
            return Response(row)
        saved = set_shop_leave_days(request.user, request.data.get('monthly_leave_days'))
        return Response({'shop_days': saved})
