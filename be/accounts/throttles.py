"""Auth-related DRF throttles (login / JWT token obtain)."""

from rest_framework.throttling import ScopedRateThrottle


class LoginRateThrottle(ScopedRateThrottle):
    """
    Rate-limit password guessing on custom login and ``/api/token/``.

    Scope ``login`` is configured in ``REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``
    (default ``10/min`` per cache key / IP).
    """

    scope = 'login'


class SmsBlastRateThrottle(ScopedRateThrottle):
    """
    Cap bulk customer SMS send endpoints to limit cost abuse.

    Scope ``sms_blast`` defaults to ``5/hour`` per authenticated user/IP.
    """

    scope = 'sms_blast'
