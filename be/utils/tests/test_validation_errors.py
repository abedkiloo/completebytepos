from django.core.exceptions import ValidationError
from django.test import TestCase

from utils.validation_errors import validation_error_message


class ValidationErrorMessageTestCase(TestCase):
    def test_list_messages(self):
        exc = ValidationError(['Insufficient stock for Sofa. Available: 0'])
        self.assertEqual(
            validation_error_message(exc),
            'Insufficient stock for Sofa. Available: 0',
        )

    def test_message_dict(self):
        exc = ValidationError({'items': ['Quantity too high']})
        self.assertEqual(validation_error_message(exc), 'Quantity too high')

    def test_message_dict_scalar_value(self):
        exc = ValidationError({'amount': 'Must be positive'})
        self.assertEqual(validation_error_message(exc), 'Must be positive')

    def test_non_validation_error_falls_back_to_str(self):
        self.assertEqual(validation_error_message(RuntimeError('boom')), 'boom')

    def test_message_dict_mixed_list_and_scalar(self):
        # Django normalizes dict values to lists; poke scalar branch via error_dict
        exc = ValidationError({'items': ['Too many']})
        exc.error_dict['amount'] = 'Must be positive'
        text = validation_error_message(exc)
        self.assertIn('Too many', text)
        self.assertIn('Must be positive', text)
