"""Block API use until a temporary admin-set password is replaced."""

import re

from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication

from .password_policy import user_must_change_password

_SELF_CHANGE_PASSWORD = re.compile(
    r'^/api/accounts/users/(?P<user_id>\d+)/change_password/?$'
)

_ALWAYS_ALLOWED = (
    '/api/accounts/auth/login/',
    '/api/accounts/auth/logout/',
    '/api/accounts/auth/me/',
    '/api/token/',
    '/api/token/refresh/',
    '/api/token/verify/',
    '/api/settings/setup-status/',
    '/api/settings/fresh-install/',
    '/api/settings/store-settings/',
)


def _path_allowed(path: str, user_id: int) -> bool:
    normalized = path if path.endswith('/') else f'{path}/'
    if any(normalized == allowed or normalized.startswith(allowed) for allowed in _ALWAYS_ALLOWED):
        return True
    match = _SELF_CHANGE_PASSWORD.match(path) or _SELF_CHANGE_PASSWORD.match(normalized)
    return bool(match and int(match.group('user_id')) == user_id)


class PasswordChangeRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        if request.method == 'OPTIONS' or not request.path.startswith('/api/'):
            return self.get_response(request)

        user = self._authenticate(request)
        if user is None or not user_must_change_password(user):
            return self.get_response(request)

        if _path_allowed(request.path, user.id):
            return self.get_response(request)

        return JsonResponse(
            {
                'error': 'password_change_required',
                'must_change_password': True,
                'detail': 'You must choose a new password before continuing.',
            },
            status=403,
        )

    def _authenticate(self, request):
        try:
            result = self.jwt_auth.authenticate(request)
        except Exception:
            return None
        if not result:
            return None
        user, _token = result
        return user
