from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from sales.models import Customer
from accounts.models import UserProfile
from django.contrib.auth.models import User


class NormalizePhoneNumbersCommandTests(TestCase):
    def test_dry_run_does_not_write(self):
        customer = Customer.objects.create(name='Jane', phone='0712345678')
        out = StringIO()
        call_command('normalize_phone_numbers', '--dry-run', stdout=out)
        customer.refresh_from_db()
        self.assertEqual(customer.phone, '0712345678')
        self.assertIn('1 updated', out.getvalue())

    def test_updates_local_kenyan_numbers(self):
        customer = Customer.objects.create(name='Jane', phone='0712345678')
        user = User.objects.create_user(username='phone_user', password='x')
        profile = UserProfile.objects.create(user=user, phone_number='712345679')
        already = Customer.objects.create(name='Ok', phone='254722000111')
        invalid = Customer.objects.create(name='Bad', phone='123')

        call_command('normalize_phone_numbers', stdout=StringIO())

        customer.refresh_from_db()
        profile.refresh_from_db()
        already.refresh_from_db()
        invalid.refresh_from_db()
        self.assertEqual(customer.phone, '254712345678')
        self.assertEqual(profile.phone_number, '254712345679')
        self.assertEqual(already.phone, '254722000111')
        self.assertEqual(invalid.phone, '123')
