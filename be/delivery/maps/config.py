"""Maps keys and public flags. Never send the server key to clients."""

PLACEHOLDER_MARKERS = (
    'REPLACE_WITH',
    'YOUR_KEY',
    'YOUR-KEY',
    'CHANGE-ME',
    'CHANGEME',
    'CHANGE_ME',
)

# Fallback shop pin (Nairobi CBD) until a branch depot is saved.
DEFAULT_DEPOT_LATITUDE = -1.2921
DEFAULT_DEPOT_LONGITUDE = 36.8219
DEFAULT_DEPOT_LABEL = 'Shop'


def configured_secret(raw: str) -> str:
    """Return a usable secret, or empty if missing / still a placeholder."""
    key = (raw or '').strip()
    if not key:
        return ''
    upper = key.upper().replace(' ', '')
    if any(marker in upper for marker in PLACEHOLDER_MARKERS):
        return ''
    return key.strip()


def maps_server_key() -> str:
    from django.conf import settings

    return configured_secret(getattr(settings, 'GOOGLE_MAPS_SERVER_KEY', ''))


def maps_public_config() -> dict:
    """Safe for GET /api/delivery/config/ — no secrets."""
    return {
        'routes_api_configured': bool(maps_server_key()),
        'live_tracking_enabled': False,
        'default_depot': {
            'latitude': DEFAULT_DEPOT_LATITUDE,
            'longitude': DEFAULT_DEPOT_LONGITUDE,
        },
    }
