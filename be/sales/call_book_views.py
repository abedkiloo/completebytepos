"""
HTTP API for the weekly call book.

Every signed-in role with ``customers.call_book`` may read the book, hold a
customer, and mark a call while the ``customers.call_book`` feature is on.
Replacing the day plan is limited to Manager and Super Admin. Error bodies
do not include phone numbers.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import RequirePerm
from datetime import datetime

from sales.call_book import (
    build_call_book,
    build_day_call_log,
    hold_customer,
    mark_called,
    nairobi_today,
    plan_payload,
    replace_plan,
    user_may_edit_call_plan,
)
from settings.feature_permissions import RequireModuleFeature

class _CallBookFeature(RequireModuleFeature):
    """Gate the call book on the customers.call_book package toggle."""

    def __init__(self):
        """
        Bind this permission to the customers call book feature.

        Returns:
            None.
        """
        super().__init__('customers', 'call_book')


_PERM = RequirePerm('customers', 'call_book')


def _query_weekday(raw):
    """
    Read the optional weekday query.

    Args:
        raw: Query value. Blank means every day. A number is passed through
            and clamped by the book builder to 0–4.

    Returns:
        int | None: Parsed day, or None when the query is blank or not a number.

    Raises:
        None.
    """
    if raw is None or str(raw).strip() == '':
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


_STATUS = {
    'ok': status.HTTP_200_OK,
    'weekend': status.HTTP_400_BAD_REQUEST,
    'not_found': status.HTTP_404_NOT_FOUND,
    'no_phone': status.HTTP_400_BAD_REQUEST,
    'bad_outcome': status.HTTP_400_BAD_REQUEST,
    'too_long': status.HTTP_400_BAD_REQUEST,
    'bad_date': status.HTTP_400_BAD_REQUEST,
    'bad_time': status.HTTP_400_BAD_REQUEST,
    'held': status.HTTP_409_CONFLICT,
    'called_today': status.HTTP_409_CONFLICT,
    'bad_plan': status.HTTP_400_BAD_REQUEST,
}


def _query_date(raw):
    """
    Read an optional YYYY-MM-DD query for the day call log.

    Args:
        raw: Query value. Blank means Nairobi today. Invalid text is ignored
            and treated as today.

    Returns:
        date: Parsed calendar day, or ``nairobi_today`` when blank/invalid.

    Raises:
        None.
    """
    if raw is None or str(raw).strip() == '':
        return nairobi_today()
    text = str(raw).strip()
    if len(text) != 10:
        return nairobi_today()
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        return nairobi_today()


class CallBookView(APIView):
    """Shared Monday–Friday book. Not-called customers are listed first."""

    permission_classes = [IsAuthenticated, _PERM, _CallBookFeature]

    def get(self, request):
        """
        List this week's book.

        Args:
            request: Query ``scope`` (today|week), ``status``
              (not_called|called|all), ``page`` (1+), ``page_size`` (1–1000),
            optional ``weekday`` (0–4), and optional ``search`` (name, code,
            place, or phone, 0–100 characters). A search looks through the
            whole week. Week totals stay the full book.

        Returns:
            Response: Summary counts and one page of rows. Weekend requests
            are forced to the week view. Phone numbers appear only on rows
            the caller is allowed to dial.

        Raises:
            None. Missing feature or permission is a 403 from the permission
            classes. Anonymous callers receive 401.
        """
        try:
            page = int(request.query_params.get('page') or 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.query_params.get('page_size') or 100)
        except (TypeError, ValueError):
            page_size = 100
        payload = build_call_book(
            scope=request.query_params.get('scope') or 'today',
            status=request.query_params.get('status') or 'all',
            page=page,
            page_size=page_size,
            viewer_id=request.user.id,
            weekday=_query_weekday(request.query_params.get('weekday')),
            search=request.query_params.get('search') or '',
        )
        return Response(payload)


class CallBookMarkView(APIView):
    """Mark one customer called for the current Monday–Friday week."""

    permission_classes = [IsAuthenticated, _PERM, _CallBookFeature]

    def post(self, request, customer_id: int):
        """
        Record or update an outcome and call notes.

        When this user already marked the customer this week, the existing
        row is updated (same endpoint) so notes can be corrected on web and
        mobile without a second call history row.

        Args:
            request: JSON ``outcome``, ``request_summary`` (0–500 chars), and
            optional ``follow_up_on`` (blank or YYYY-MM-DD within 90 days) and
            ``follow_up_time`` (HH:MM, required for call later).
            customer_id: Customer primary key, positive integer.

        Returns:
            Response: 200 on success with ``updated`` true when an existing
            week row was edited. 400 on the weekend, a bad outcome, a
            summary over 500 characters, a bad follow-up date, a missing or
            invalid call-later time, or no usable phone. 404 when the
            customer is missing. 409 when another staff member holds the
            customer or already called them today. Bodies do not include the
            phone number.

        Raises:
            None.
        """
        try:
            code, payload = mark_called(
                customer_id=customer_id,
                user=request.user,
                outcome=(request.data.get('outcome') or ''),
                request_summary=request.data.get('request_summary') or '',
                follow_up_on=request.data.get('follow_up_on') or '',
                follow_up_time=request.data.get('follow_up_time') or '',
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                'call-book mark failed for customer_id=%s', customer_id,
            )
            return Response(
                {'error': 'Could not save this call. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if code == 'ok':
            from sales.models import Customer
            from utils.audit_events import log_call_write
            customer = Customer.objects.filter(pk=customer_id).only(
                'id', 'name', 'customer_code',
            ).first()
            log_call_write(
                request,
                customer,
                kind='updated' if payload.get('updated') else 'marked',
                detail={
                    'outcome': payload.get('outcome') or '',
                    'request_summary': payload.get('request_summary') or '',
                    'follow_up_on': payload.get('follow_up_on') or '',
                    'updated': bool(payload.get('updated')),
                },
            )
        http = status.HTTP_200_OK if code == 'ok' else _STATUS.get(code, 400)
        # Always expose a string ``error`` for non-OK so web/mobile toasts
        # never fall back to a generic "Could not save" when DRF would only
        # have put the message under another key.
        if code != 'ok' and isinstance(payload, dict) and not payload.get('error'):
            payload = {**payload, 'error': 'Could not save this call.'}
        return Response(payload, status=http)


class CallBookHoldView(APIView):
    """Claim one customer for the rest of the Nairobi day while dialing."""

    permission_classes = [IsAuthenticated, _PERM, _CallBookFeature]

    def post(self, request, customer_id: int):
        """
        Claim the customer until end of day so only this person can call them.

        Args:
            request: Authenticated call. Body is ignored.
            customer_id: Customer primary key.

        Returns:
            Response: 200 with expiry and ``day_claim``, 409 if someone else
            already claimed or called them today, 400 on the weekend or when
            there is no number. No phone in the body.

        Raises:
            None.
        """
        code, payload = hold_customer(customer_id=customer_id, user=request.user)
        if code == 'ok':
            from sales.models import Customer
            from utils.audit_events import log_call_write
            customer = Customer.objects.filter(pk=customer_id).only(
                'id', 'name', 'customer_code',
            ).first()
            log_call_write(
                request,
                customer,
                kind='held',
                detail={
                    'day_claim': True,
                    'expires_at': payload.get('expires_at'),
                },
            )
        http = status.HTTP_200_OK if code == 'ok' else _STATUS.get(code, 400)
        return Response(payload, status=http)


class CallBookDayLogView(APIView):
    """Who called which customers on one Nairobi calendar day."""

    permission_classes = [IsAuthenticated, _PERM, _CallBookFeature]

    def get(self, request):
        """
        List call records for one day.

        Args:
            request: Query ``date`` (YYYY-MM-DD, optional), ``page`` (1+),
            and ``page_size`` (1–1000). Blank date uses Nairobi today.

        Returns:
            Response: Day ISO date, unique caller names, and one page of
            call rows without phone numbers. Anonymous callers get 401.
            Missing feature or permission is 403.

        Raises:
            None.
        """
        try:
            page = int(request.query_params.get('page') or 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.query_params.get('page_size') or 100)
        except (TypeError, ValueError):
            page_size = 100
        payload = build_day_call_log(
            day=_query_date(request.query_params.get('date')),
            page=page,
            page_size=page_size,
        )
        return Response(payload)


class CallBookPlanView(APIView):
    """Read the day plan, or replace it when the user is a manager."""

    permission_classes = [IsAuthenticated, _PERM, _CallBookFeature]

    def get(self, request):
        """
        Return the current plan.

        Args:
            request: Authenticated call-book user.

        Returns:
            Response: Unlocated weekday, hold minutes, and location rows.
        """
        return Response(plan_payload())

    def put(self, request):
        """
        Replace the plan.

        Args:
            request: JSON ``unlocated_weekday`` (0–4), ``hold_minutes``
            (1–30), and ``rows`` (at most 200).

        Returns:
            Response: 200 with the saved plan, 400 when the plan is invalid,
            403 when the user is not a manager or super admin.

        Raises:
            None.
        """
        if not user_may_edit_call_plan(request.user):
            return Response(
                {'error': 'Only a manager can change the call plan.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        code, payload = replace_plan(
            unlocated_weekday=request.data.get('unlocated_weekday', 0),
            hold_minutes=request.data.get('hold_minutes', 5),
            rows=request.data.get('rows') or [],
        )
        if code == 'ok':
            from utils.audit_events import log_call_write
            log_call_write(
                request,
                None,
                kind='plan',
                detail={
                    'unlocated_weekday': payload.get('unlocated_weekday'),
                    'hold_minutes': payload.get('hold_minutes'),
                    'locations': len(payload.get('rows') or []),
                },
            )
        http = status.HTTP_200_OK if code == 'ok' else _STATUS.get(code, 400)
        return Response(payload, status=http)
