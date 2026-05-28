import os

from django.test import SimpleTestCase

from config.env import env_bool, env_list


class EnvHelpersTests(SimpleTestCase):
    def test_env_list_comma_separated(self):
        os.environ['TEST_LIST'] = 'a,b, c'
        self.assertEqual(env_list('TEST_LIST'), ['a', 'b', 'c'])
        del os.environ['TEST_LIST']

    def test_env_bool(self):
        import os
        os.environ['TEST_FLAG'] = 'yes'
        self.assertTrue(env_bool('TEST_FLAG'))
        del os.environ['TEST_FLAG']
