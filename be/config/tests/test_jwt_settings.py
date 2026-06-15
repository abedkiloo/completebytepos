import os
from datetime import timedelta

from django.conf import settings
from django.test import SimpleTestCase

from config.env import env_int


class JwtAccessTokenLifetimeTests(SimpleTestCase):
    def test_env_int_default_for_access_token_is_thirty(self):
        key = 'JWT_ACCESS_TOKEN_MINUTES'
        previous = os.environ.pop(key, None)
        try:
            self.assertEqual(env_int(key, 30), 30)
        finally:
            if previous is not None:
                os.environ[key] = previous

    def test_simple_jwt_access_token_lifetime_is_thirty_minutes(self):
        self.assertEqual(
            settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
            timedelta(minutes=30),
        )
