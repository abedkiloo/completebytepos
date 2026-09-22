from django.test import TestCase, override_settings

from utils.phone import PhoneNumberError, default_country_code, normalize_phone_number


class NormalizePhoneNumberTests(TestCase):
    def test_default_country_is_254(self):
        self.assertEqual(default_country_code(), '254')

    def test_blank_allowed(self):
        self.assertEqual(normalize_phone_number(''), '')
        self.assertEqual(normalize_phone_number(None), '')
        self.assertEqual(normalize_phone_number('   '), '')

    def test_blank_required_raises(self):
        with self.assertRaises(PhoneNumberError) as ctx:
            normalize_phone_number('', required=True)
        self.assertIn('0712 345 678', str(ctx.exception))

    def test_letters_explain_expected_format(self):
        with self.assertRaises(PhoneNumberError) as ctx:
            normalize_phone_number('not-a-phone')
        self.assertIn('Letters are not allowed', str(ctx.exception))

    def test_local_zero_prefix_becomes_254(self):
        self.assertEqual(normalize_phone_number('0712345678'), '254712345678')
        self.assertEqual(normalize_phone_number('07 123 45678'), '254712345678')

    def test_nine_digit_mobile_gets_254(self):
        self.assertEqual(normalize_phone_number('712345678'), '254712345678')

    def test_plus_254_and_existing_prefix(self):
        self.assertEqual(normalize_phone_number('+254712345678'), '254712345678')
        self.assertEqual(normalize_phone_number('254712345678'), '254712345678')
        self.assertEqual(normalize_phone_number('2540712345678'), '254712345678')

    def test_invalid_too_short(self):
        with self.assertRaises(PhoneNumberError):
            normalize_phone_number('123')
        with self.assertRaises(PhoneNumberError):
            normalize_phone_number('07123')

    @override_settings(DEFAULT_PHONE_COUNTRY_CODE='254')
    def test_settings_override_still_254(self):
        self.assertEqual(normalize_phone_number('0712345678'), '254712345678')
