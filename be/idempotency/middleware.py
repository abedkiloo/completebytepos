import hashlib
import json

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .models import IdempotencyRecord

IDEMPOTENT_METHODS = {'POST', 'PUT', 'PATCH'}


def _request_hash(body: bytes) -> str:
    return hashlib.sha256(body or b'').hexdigest()


class IdempotencyMiddleware(MiddlewareMixin):
    """
    Replay prior responses for identical Idempotency-Key + user + method + path.

    If the same key is reused with a different body → 409 Conflict.
    """

    def process_request(self, request):
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
        key = getattr(request, '_idempotency_key', None)
        if not key:
            return response
        if request.method not in IDEMPOTENT_METHODS:
            return response
        # Only cache completed responses (not 401 auth challenges).
        if response.status_code == 401:
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
