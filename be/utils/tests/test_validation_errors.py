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
