"""
Docker healthcheck.

Gunicorn must listen on 0.0.0.0 (so nginx on another container can connect).
Django ALLOWED_HOSTS must NOT include Docker bridge IPs (172.18.x.x) — those
are not public hosts. Probe HTTP with Host: 127.0.0.1, which is already allowed.
"""
from __future__ import annotations

import socket
import sys
import urllib.error
import urllib.request


def _lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('10.255.255.255', 1))
        return sock.getsockname()[0]
    finally:
        sock.close()


def gunicorn_accepts_on_lan(timeout: float = 5) -> None:
    """Fails if Gunicorn is bound to 127.0.0.1 only."""
    sock = socket.create_connection((_lan_ip(), 8000), timeout)
    sock.close()


def healthz_ok(timeout: float = 5) -> None:
    request = urllib.request.Request(
        'http://127.0.0.1:8000/api/healthz/',
        headers={'Host': '127.0.0.1'},
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f'healthz status {resp.status}')


def main() -> int:
    try:
        gunicorn_accepts_on_lan()
        healthz_ok()
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f'healthcheck failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
