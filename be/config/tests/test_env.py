import os

from django.test import SimpleTestCase

from config.env import (
    env_bool,
    env_list,
    is_ip_like_host,
    normalize_public_host,
    public_host_origins,
)


class EnvHelpersTests(SimpleTestCase):
    def test_env_list_comma_separated(self):
        os.environ['TEST_LIST'] = 'a,b, c'
        self.assertEqual(env_list('TEST_LIST'), ['a', 'b', 'c'])
        del os.environ['TEST_LIST']

    def test_env_bool(self):
        os.environ['TEST_FLAG'] = 'yes'
        self.assertTrue(env_bool('TEST_FLAG'))
        del os.environ['TEST_FLAG']

    def test_normalize_public_host_strips_scheme(self):
        self.assertEqual(
            normalize_public_host('https://shop.omuwenga.com/'),
            'shop.omuwenga.com',
        )
        self.assertEqual(normalize_public_host('193.37.213.177'), '193.37.213.177')

    def test_is_ip_like_host(self):
        self.assertTrue(is_ip_like_host('193.37.213.177'))
        self.assertTrue(is_ip_like_host('10.0.0.1:3000'))
        self.assertFalse(is_ip_like_host('shop.omuwenga.com'))

    def test_public_host_origins_include_https(self):
        origins = public_host_origins('shop.omuwenga.com')
        self.assertIn('https://shop.omuwenga.com', origins)
        self.assertIn('http://shop.omuwenga.com', origins)
        self.assertIn('https://shop.omuwenga.com:3000', origins)

    def test_allowed_hosts_style_entries_strip_scheme(self):
        """People often put https://domain in ALLOWED_HOSTS; Django needs bare host."""
        self.assertEqual(
            normalize_public_host('https://shop.omuwenga.com'),
            'shop.omuwenga.com',
        )
        hosts = [
            normalize_public_host(h)
            for h in [
                'https://shop.omuwenga.com',
                '193.37.213.177',
                'localhost',
                'backend',
            ]
        ]
        self.assertEqual(
            hosts,
            ['shop.omuwenga.com', '193.37.213.177', 'localhost', 'backend'],
        )
