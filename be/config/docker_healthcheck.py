"""
Docker healthcheck: API must answer on the container's LAN IP, not only
127.0.0.1. A localhost-only Gunicorn bind passes curl-to-127 but nginx
(other containers) gets Connection refused → 502.
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


def main() -> int:
    ip = _lan_ip()
    url = f'http://{ip}:8000/api/healthz/'
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status != 200:
                print(f'healthz status {resp.status} via {ip}', file=sys.stderr)
                return 1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f'healthz failed via {ip}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
