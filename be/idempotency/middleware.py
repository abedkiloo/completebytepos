"""
HTTP idempotency replay for mutating API requests.

Public entry points:
    - ``IdempotencyMiddleware`` — honors ``Idempotency-Key`` on POST/PUT/PATCH

Persists responses in ``IdempotencyRecord``. Replays set ``X-Idempotency-Replayed``.
401 responses are never cached. Mismatched body hash → 409 JSON error.
"""
import hashlib
import json

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .models import IdempotencyRecord

IDEMPOTENT_METHODS = {'POST', 'PUT', 'PATCH'}


def _request_hash(body: bytes) -> str:
    """
    Hash the raw request body for idempotency conflict detection.

    Args:
        body: Raw bytes; empty body hashes as SHA-256 of empty input.

    Returns:
        Lowercase hex digest (64 chars).
    """
    return hashlib.sha256(body or b'').hexdigest()


class IdempotencyMiddleware(MiddlewareMixin):
    """
    Replay prior responses for identical Idempotency-Key + user + method + path.

    Scope key: header ``Idempotency-Key`` (or ``HTTP_IDEMPOTENCY_KEY``), authenticated
    user (``None`` for anonymous), HTTP method, and request path (max 512 on model).
    Key max length 255 on ``IdempotencyRecord.key``.

    If the same key is reused with a different body hash → 409 Conflict JSON.
    """

    def process_request(self, request):
        """
        Short-circuit with a stored response when a matching record exists.

        Args:
            request: Incoming Django request.

        Returns:
            ``None`` to continue the stack, or ``HttpResponse`` when replaying or
            rejecting a body mismatch (409).
        """
        if request.method not in IDEMPOTENT_METHODS:
            return None
        key = request.headers.get('Idempotency-Key') or request.META.get('HTTP_IDEMPOTENCY_KEY')
        if not key:
            return None

        user = request.user if getattr(request.user, 'is_authenticated', False) else None
        body = request.body or b''
        path = request.path
        existing = IdempotencyRecord.objects.filter(
            key=key,
            user=user,
            method=request.method,
            path=path,
        ).first()
        if existing is None:
            request._idempotency_key = key  # noqa: SLF001
            request._idempotency_hash = _request_hash(body)  # noqa: SLF001
            return None

        if existing.request_hash and existing.request_hash != _request_hash(body):
            return HttpResponse(
                json.dumps({'error': 'Idempotency-Key reused with a different request body.'}),
                status=409,
                content_type='application/json',
            )

        response = HttpResponse(
            existing.response_body,
            status=existing.status_code,
            content_type=existing.response_content_type,
        )
        response['X-Idempotency-Replayed'] = 'true'
        return response

    def process_response(self, request, response):
        """
        Persist the first completed response for a new idempotency key.

        Args:
            request: Request that may carry ``_idempotency_key`` from ``process_request``.
            response: Downstream response to optionally store.

        Returns:
            The same ``response`` object (possibly after DB ``update_or_create``).
        """
        key = getattr(request, '_idempotency_key', None)
        if not key:
            return response
        if request.method not in IDEMPOTENT_METHODS:
            return response
        # Never cache auth challenges or server failures — a cached HTML/empty
        # 500 would stick the mobile client on a dead retry (same Idempotency-Key).
        if response.status_code == 401 or response.status_code >= 500:
            return response

        user = request.user if getattr(request.user, 'is_authenticated', False) else None
        body = response.content.decode('utf-8', errors='replace') if response.content else ''
        IdempotencyRecord.objects.update_or_create(
            key=key,
            user=user,
            method=request.method,
            path=request.path,
            defaults={
                'request_hash': getattr(request, '_idempotency_hash', ''),
                'status_code': response.status_code,
                'response_body': body,
                'response_content_type': response.get('Content-Type', 'application/json'),
            },
        )
        return response
