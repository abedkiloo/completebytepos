from datetime import date, datetime
from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from utils.field_types import (
    AMOUNT_EXAMPLE,
    DATE_EXAMPLE,
    EMAIL_EXAMPLE,
    NAME_EXAMPLE,
    date_error,
    date_error_messages,
    email_error,
    integer_error,
    money_error,
    money_error_messages,
    raise_field_error,
    required_text_error,
)


class RequiredTextErrorTests(SimpleTestCase):
    def test_empty_and_short(self):
        self.assertIn(NAME_EXAMPLE, required_text_error('', label='customer name', example=NAME_EXAMPLE, min_length=2))
        self.assertIn('at least 2', required_text_error('A', label='customer name', example=NAME_EXAMPLE, min_length=2))
        self.assertIsNone(required_text_error('Jane Wambua', label='customer name', example=NAME_EXAMPLE, min_length=2))


class EmailErrorTests(SimpleTestCase):
    def test_optional_blank_ok(self):
        self.assertIsNone(email_error(''))
        self.assertIsNone(email_error(None))

    def test_required_and_invalid(self):
        self.assertIn(EMAIL_EXAMPLE, email_error('', required=True))
        msg = email_error('not-an-email')
        self.assertIn(EMAIL_EXAMPLE, msg)
        self.assertIn('not-an-email', msg)
        self.assertIsNone(email_error('name@example.com'))


class DateErrorTests(SimpleTestCase):
    def test_formats(self):
        self.assertIn(DATE_EXAMPLE, date_error(''))
        self.assertIn('YYYY-MM-DD', date_error('22-09-2026'))
        self.assertIn('real calendar', date_error('2026-02-30'))
        self.assertIsNone(date_error('2026-09-22'))
        self.assertIsNone(date_error(date(2026, 9, 22)))
        self.assertIsNone(date_error(datetime(2026, 9, 22, 8, 0)))
        self.assertIsNone(date_error('2026-09-22T08:00:00'))
        self.assertIsNone(date_error(None, required=False))


class MoneyErrorTests(SimpleTestCase):
    def test_empty_invalid_zero(self):
        self.assertIn(AMOUNT_EXAMPLE, money_error(''))
        self.assertIn('numbers only', money_error('abc'))
        self.assertIn('2 decimal', money_error('12.345'))
        self.assertIn('greater than zero', money_error('0'))
        self.assertIsNone(money_error('250.00'))
        self.assertIsNone(money_error(Decimal('10.5')))
        self.assertIsNone(money_error(250))
        self.assertIsNone(money_error(12.5))
        self.assertIn('note', required_text_error(None, label='note', example='Closing count'))
        self.assertIsNone(money_error('0', allow_zero=True))
        self.assertIsNone(money_error('', required=False))
        self.assertIn('negative', money_error('-1'))

    def test_drf_error_messages(self):
        msgs = money_error_messages(allow_zero=False)
        self.assertIn(AMOUNT_EXAMPLE, msgs['invalid'])
        self.assertIn('greater than zero', msgs['min_value'])
        self.assertIn('cannot be negative', money_error_messages(allow_zero=True)['min_value'])
        self.assertIn(DATE_EXAMPLE, date_error_messages()['invalid'])


class IntegerErrorTests(SimpleTestCase):
    def test_whole_numbers(self):
        self.assertIsNone(integer_error(''))
        self.assertIn('e.g. 3', integer_error('', required=True))
        self.assertIn('whole number', integer_error('1.5'))
        self.assertIn('at least 1', integer_error(0, min_value=1, label='quantity'))
        self.assertIsNone(integer_error(3, min_value=1))
        self.assertIsNone(integer_error('5'))
        self.assertIn('whole number', integer_error(True))


class RaiseFieldErrorTests(SimpleTestCase):
    def test_raises_only_when_message_set(self):
        raise_field_error(None)
        with self.assertRaises(ValidationError):
            raise_field_error('Enter customer name, e.g. Jane Wambua')
