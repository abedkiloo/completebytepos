"""Auth-related and expensive-read DRF throttles."""

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


class ReportRateThrottle(ScopedRateThrottle):
    """
    Cap authenticated report reads (aggregates / trends / exports).

    Scope ``reports`` defaults to ``120/min``. Checkout and sale writes are
    not covered — apply only on report viewsets. Shared Redis cache makes
    the counter correct across Gunicorn workers.
    """

    scope = 'reports'


class HeavyReadRateThrottle(ScopedRateThrottle):
    """
    Cap heavy list builders (call book, large catalogue dumps).

    Scope ``heavy_read`` defaults to ``60/min``. Keeps business flow usable
    for a desk while blocking accidental or hostile stampede traffic.
    """

    scope = 'heavy_read'
