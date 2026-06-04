"""Maker-checker hooks for inventory @action endpoints."""

from __future__ import annotations

from typing import Any, Optional

from rest_framework import status
from rest_framework.response import Response

from approvals.permissions import is_maker_checker_enabled
from approvals.serializers import PendingChangeSerializer
from approvals.service import route_stock_movement


def try_pending_stock_response(
    request,
    *,
    action_type: str,
    apply_payload: dict[str, Any],
    reason: str,
) -> Optional[Response]:
    """
    If maker-checker is on, queue the movement and return 202.
    Returns None when the caller should apply the movement immediately.
    """
    if not is_maker_checker_enabled():
        return None
    if not str(reason).strip():
        from rest_framework.exceptions import ValidationError

        raise ValidationError({'reason': 'A reason is required for stock changes.'})
    pending = route_stock_movement(
        request,
        action_type=action_type,
        apply_payload=apply_payload,
        reason=str(reason).strip(),
    )
    if pending is None:
        return None
    return Response(
        {
            'message': 'Change submitted for approval, not yet active.',
            'pending_change': PendingChangeSerializer(pending).data,
        },
        status=status.HTTP_202_ACCEPTED,
    )
