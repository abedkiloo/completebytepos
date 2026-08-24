from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from config.docker_healthcheck import healthz_ok


class DockerHealthcheckTests(SimpleTestCase):
    def test_healthz_sends_localhost_host_header(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with patch('config.docker_healthcheck.urllib.request.urlopen', return_value=response) as urlopen:
            healthz_ok()

        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:8000/api/healthz/')
        self.assertEqual(request.get_header('Host'), '127.0.0.1')
