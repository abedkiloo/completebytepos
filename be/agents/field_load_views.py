"""
HTTP API for field loads.

Viewing requires ``agents.field_load`` and the sales ``field_load`` feature.
Issuing stock and accepting a return are narrower permissions checked in
the service. Error bodies do not include phone numbers.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePerm
from agents.field_load_service import (
    FieldLoadError,
    add_line,
    confirm_issue,
    decline_issue,
    issue_load,
    carrier_choices,
    loads_for_user,
    review_load,
    sell_from_load,
    serialize_load,
    serialize_loads,
    submit_return,
    user_may_approve,
    user_may_issue,
)
from agents.models import FieldLoad
from settings.feature_permissions import RequireModuleFeature

_HTTP = {
    'forbidden': status.HTTP_403_FORBIDDEN,
    'not_found': status.HTTP_404_NOT_FOUND,
    'no_stock': status.HTTP_400_BAD_REQUEST,
    'over_sold': status.HTTP_400_BAD_REQUEST,
    'open_load': status.HTTP_400_BAD_REQUEST,
    'not_open': status.HTTP_400_BAD_REQUEST,
    'not_pending': status.HTTP_400_BAD_REQUEST,
    'bad_qty': status.HTTP_400_BAD_REQUEST,
    'bad_lines': status.HTTP_400_BAD_REQUEST,
    'bad_product': status.HTTP_400_BAD_REQUEST,
    'bad_agent': status.HTTP_400_BAD_REQUEST,
    'bad_customer': status.HTTP_400_BAD_REQUEST,
    'bad_money': status.HTTP_400_BAD_REQUEST,
    'bad_note': status.HTTP_400_BAD_REQUEST,
}


class _FieldLoadFeature(RequireModuleFeature):
    """Gate field loads on the sales.field_load package toggle."""

    def __init__(self):
        """
        Bind this permission to the sales field load feature.

        Returns:
            None.
        """
        super().__init__('sales', 'field_load')


def _with_confirm(request, payload: dict) -> dict:
    """
    Mark whether this user may approve the written quantities.

    Args:
        request: Authenticated request. The user must not be the writer.
        payload: One serialized load.

    Returns:
        dict: The same payload plus ``can_confirm_issue``. No writes.
    """
    payload['can_confirm_issue'] = bool(
        user_may_approve(request.user)
        and payload.get('issued_by_id') != request.user.id
        and payload.get('status') == FieldLoad.STATUS_AWAITING
    )
    return payload


def _error(exc: FieldLoadError) -> Response:
    """
    Turn a field-load failure into a response without extra identifiers.

    Args:
        exc: Error with ``code`` and ``message``.

    Returns:
        Response: 400, 403, or 404. Body is ``{"error": message}`` only.
    """
    return Response({'error': exc.message}, status=_HTTP.get(exc.code, 400))


class FieldLoadViewSet(viewsets.ViewSet):
    """Issue, sell, return, and accept stock an agent carried out."""

    permission_classes = [IsAuthenticated, RequirePerm('agents', 'field_load'), _FieldLoadFeature]

    def list(self, request):
        """
        List loads this user may see, newest first.

        Args:
            request: Authenticated field-load user.

        Returns:
            Response: ``can_issue``, ``can_approve``, and up to 100 loads.
            Agents see their own. Issuers and approvers see all.
        """
        rows = serialize_loads(
            loads_for_user(request.user).order_by('-issued_at')[:100]
        )
        summary = {'active': 0, 'awaiting_approval': 0, 'shortage': 0, 'accepted': 0}
        for row in rows:
            shown = row['display_status']
            if shown == 'open':
                summary['active'] += 1
            elif shown == 'shortage':
                summary['shortage'] += 1
            elif shown in ('pending_review', 'awaiting_issue', 'issue_rejected'):
                summary['awaiting_approval'] += 1
            elif shown == 'accepted':
                summary['accepted'] += 1
        return Response({
            'can_issue': user_may_issue(request.user),
            'can_approve': user_may_approve(request.user),
            'summary': summary,
            'results': [_with_confirm(request, row) for row in rows],
        })

    @action(detail=False, methods=['get'], url_path='agents')
    def agents(self, request):
        """
        Active field agents for the issue form. The rows are sales
        employees from the staff roster who have a login.

        Args:
            request: User who may issue loads.

        Returns:
            Response: ``{"results": [{"id", "name"}]}``, at most 200 names.
            403 when the user cannot issue. Bodies do not include phone numbers.
        """
        if not user_may_issue(request.user):
            return Response(
                {'error': 'You cannot issue a field load.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(carrier_choices(request.user))

    def create(self, request):
        """
        Issue a new load.

        Args:
            request: JSON ``agent_id`` and ``lines`` (1–40).

        Returns:
            Response: 201 with the load, or 400/403 from the service.
        """
        try:
            load = issue_load(
                agent_id=request.data.get('agent_id'),
                lines=request.data.get('lines') or [],
                user=request.user,
            )
        except FieldLoadError as exc:
            return _error(exc)
        return Response(_with_confirm(request, serialize_load(load)), status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        """
        One load, if this user may see it.

        Args:
            request: Authenticated field-load user.
            pk: Load primary key.

        Returns:
            Response: 200 with the load, or 404 when it is missing or hidden.
        """
        load = loads_for_user(request.user).filter(pk=pk).first()
        if load is None:
            return Response({'error': 'Load not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_with_confirm(request, serialize_load(load)))

    @action(detail=True, methods=['post'], url_path='approve-issue')
    def approve_issue(self, request, pk=None):
        """
        Approve the written quantities. Shop stock leaves on this call.

        Args:
            request: Manager who did not write the load.
            pk: Load primary key.

        Returns:
            Response: The open load, or 403 when the writer tries to approve it.
        """
        try:
            load = confirm_issue(load_id=pk, user=request.user)
        except FieldLoadError as exc:
            return _error(exc)
        return Response(_with_confirm(request, serialize_load(load)))

    @action(detail=True, methods=['post'], url_path='decline-issue')
    def decline_issue(self, request, pk=None):
        """
        Send the written quantities back. Shop stock does not move.

        Args:
            request: Optional JSON ``note``, 0–500 characters.
            pk: Load primary key.

        Returns:
            Response: The load marked sent back.
        """
        try:
            load = decline_issue(
                load_id=pk,
                user=request.user,
                note=request.data.get('note') or '',
            )
        except FieldLoadError as exc:
            return _error(exc)
        return Response(_with_confirm(request, serialize_load(load)))

    @action(detail=True, methods=['post'], url_path='lines')
    def lines(self, request, pk=None):
        """
        Add quantity to an open load.

        Args:
            request: JSON ``product_id``, ``quantity``, optional ``variant_id``.
            pk: Load primary key.

        Returns:
            Response: Updated load, or an error from the service.
        """
        try:
            load = add_line(
                load_id=pk,
                product_id=request.data.get('product_id'),
                variant_id=request.data.get('variant_id'),
                quantity=request.data.get('quantity'),
                user=request.user,
            )
        except FieldLoadError as exc:
            return _error(exc)
        return Response(serialize_load(load))

    @action(detail=True, methods=['post'], url_path='sell')
    def sell(self, request, pk=None):
        """
        Sell units that are already on the load.

        Args:
            request: JSON ``product_id``, ``quantity``, ``amount_paid``,
                optional ``customer_id`` and ``variant_id``.
            pk: Load primary key.

        Returns:
            Response: Updated load including the new sale's money.
        """
        try:
            load = sell_from_load(
                load_id=pk,
                user=request.user,
                customer_id=request.data.get('customer_id'),
                product_id=request.data.get('product_id'),
                variant_id=request.data.get('variant_id'),
                quantity=request.data.get('quantity'),
                amount_paid=request.data.get('amount_paid', 0),
                payment_method=request.data.get('payment_method') or 'cash',
                tender=request.data.get('tender') or 'cash',
                notes=request.data.get('notes') or '',
                client_channel=request.data.get('client_channel') or 'web',
            )
        except FieldLoadError as exc:
            return _error(exc)
        return Response(serialize_load(FieldLoad.objects.get(pk=load.pk)))

    @action(detail=True, methods=['post'], url_path='return')
    def return_count(self, request, pk=None):
        """
        Submit what came back.

        Args:
            request: JSON ``lines`` of ``line_id`` and ``quantity_returned``.
            pk: Load primary key.

        Returns:
            Response: Load now waiting for a manager.
        """
        try:
            load = submit_return(
                load_id=pk,
                user=request.user,
                lines=request.data.get('lines') or [],
            )
        except FieldLoadError as exc:
            return _error(exc)
        return Response(serialize_load(load))

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        """
        Accept the count and restock what came back.

        Args:
            request: Optional JSON ``note``, 0–500 characters.
            pk: Load primary key.

        Returns:
            Response: Accepted load. Shop stock increases by the returned units.
        """
        try:
            load = review_load(
                load_id=pk,
                user=request.user,
                accept=True,
                note=request.data.get('note') or '',
            )
        except FieldLoadError as exc:
            return _error(exc)
        return Response(serialize_load(load))

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """
        Send the count back without moving stock.

        Args:
            request: Optional JSON ``note``.
            pk: Load primary key.

        Returns:
            Response: Load reopened. Existing sales stay sold.
        """
        try:
            load = review_load(
                load_id=pk,
                user=request.user,
                accept=False,
                note=request.data.get('note') or '',
            )
        except FieldLoadError as exc:
            return _error(exc)
        return Response(serialize_load(load))
