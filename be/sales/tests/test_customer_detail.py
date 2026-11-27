"""Customer lifetime detail + debt trail API."""

from decimal import Decimal
from datetime import date

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from sales.customer_detail import (
    balance_before_from_txn,
    debt_flow_for_txn,
    get_customer_detail,
    serialize_ledger_entry,
)
from sales.models import Customer, CustomerCall, CustomerWalletTransaction, Sale
from settings.models import ModuleFeature, ModuleSetting, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


def _seed_customer_settings():
    cache.clear()
    for key, default in (
        ('show_wallet_balance', True),
        ('enable_wallet_payment', True),
        ('show_outstanding_balance', True),
        ('enable_customer_create', True),
        ('enable_customer_edit', True),
        ('enable_customer_delete', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='customers',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class CustomerDetailMathTests(ManagerAPITestCase):
    def test_balance_before_debit_and_credit(self):
        self.assertEqual(
            balance_before_from_txn('debit', Decimal('250.00'), Decimal('-600.00')),
            Decimal('-350.00'),
        )
        self.assertEqual(
            balance_before_from_txn('credit', Decimal('300.00'), Decimal('-300.00')),
            Decimal('-600.00'),
        )

    def test_settlement_flow_previous_paid_new_debt(self):
        """Paid 300 against previous debt 600 → new debt 300."""
        flow = debt_flow_for_txn(
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('300.00'),
            balance_after=Decimal('-300.00'),
        )
        self.assertEqual(flow['previous_debt'], '600.00')
        self.assertEqual(flow['payment_amount'], '300.00')
        self.assertEqual(flow['new_debt'], '300.00')
        self.assertEqual(flow['balance_before'], '-600.00')
        self.assertEqual(flow['delta_debt'], '-300.00')

    def test_sale_debt_flow_with_partial_payment(self):
        """Sale total 630 paid 330 → debt added 300; wallet was clean."""
        customer = Customer.objects.create(name='Flow Cust', wallet_balance=Decimal('-300.00'))
        sale = Sale.objects.create(
            sale_number='S-FLOW-1',
            customer=customer,
            subtotal=Decimal('630.00'),
            total=Decimal('630.00'),
            amount_paid=Decimal('330.00'),
            status='completed',
            sale_type='pos',
            payment_method='cash',
        )
        flow = debt_flow_for_txn(
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('300.00'),
            balance_after=Decimal('-300.00'),
            sale=sale,
        )
        self.assertEqual(flow['previous_debt'], '0.00')
        self.assertEqual(flow['debt_added'], '300.00')
        self.assertEqual(flow['sale_total'], '630.00')
        self.assertEqual(flow['sale_paid'], '330.00')
        self.assertEqual(flow['new_debt'], '300.00')

    def test_serialize_ledger_entry_includes_trail(self):
        customer = Customer.objects.create(
            name='Ledger Cust',
            wallet_balance=Decimal('-300.00'),
        )
        txn = CustomerWalletTransaction.objects.create(
            customer=customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('300.00'),
            balance_after=Decimal('-300.00'),
            notes='Debt payment received via Cash',
        )
        row = serialize_ledger_entry(txn)
        self.assertEqual(row['previous_debt'], '600.00')
        self.assertEqual(row['payment_amount'], '300.00')
        self.assertEqual(row['new_debt'], '300.00')
        self.assertEqual(row['source_type'], 'debt_settlement')

    def test_wallet_payment_and_generic_credit_flows(self):
        wallet_use = debt_flow_for_txn(
            transaction_type='debit',
            source_type='payment',
            amount=Decimal('50.00'),
            balance_after=Decimal('50.00'),
        )
        self.assertEqual(wallet_use['payment_amount'], '50.00')
        self.assertEqual(wallet_use['balance_before'], '100.00')

        overpay = debt_flow_for_txn(
            transaction_type='credit',
            source_type='overpayment',
            amount=Decimal('20.00'),
            balance_after=Decimal('20.00'),
        )
        self.assertEqual(overpay['payment_amount'], '20.00')
        self.assertEqual(overpay['previous_debt'], '0.00')

    def test_other_credit_is_not_labelled_as_a_payment(self):
        """Correction reverses must not look like debt repayments on the ledger."""
        flow = debt_flow_for_txn(
            transaction_type='credit',
            source_type='other',
            amount=Decimal('8100.00'),
            balance_after=Decimal('-18700.00'),
        )
        self.assertEqual(flow['previous_debt'], '26800.00')
        self.assertEqual(flow['new_debt'], '18700.00')
        self.assertIsNone(flow['payment_amount'])

    def test_credit_standing_when_wallet_positive(self):
        customer = Customer.objects.create(
            name='Credit Cust',
            wallet_balance=Decimal('75.00'),
        )
        payload = get_customer_detail(customer_id=customer.id)
        self.assertEqual(payload['customer']['standing'], 'credit')
        self.assertEqual(payload['customer']['wallet_credit'], '75.00')

    def test_get_customer_detail_raises_for_missing(self):
        with self.assertRaises(LookupError):
            get_customer_detail(customer_id=999999)

    def test_get_customer_detail_accepts_base_sales_queryset(self):
        customer = Customer.objects.create(name='Scoped Cust', wallet_balance=Decimal('0'))
        Sale.objects.create(
            sale_number='S-SCOPE-1',
            customer=customer,
            subtotal=Decimal('40.00'),
            total=Decimal('40.00'),
            amount_paid=Decimal('40.00'),
            status='completed',
            sale_type='pos',
            payment_method='cash',
        )
        base = Sale.objects.filter(sale_number='S-SCOPE-1')
        payload = get_customer_detail(
            customer_id=customer.id,
            base_sales_queryset=base,
        )
        self.assertEqual(len(payload['orders']), 1)
        self.assertEqual(payload['orders'][0]['sale_number'], 'S-SCOPE-1')


class CustomerDetailAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_customer_settings()
        self.customer = Customer.objects.create(
            name='Detail Customer',
            phone='0700111222',
            email='detail@example.com',
            wallet_balance=Decimal('-300.00'),
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='S-DET-1',
            customer=self.customer,
            subtotal=Decimal('630.00'),
            total=Decimal('630.00'),
            amount_paid=Decimal('330.00'),
            status='completed',
            sale_type='pos',
            payment_method='cash',
            cashier=self.manager_user,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('300.00'),
            balance_after=Decimal('-300.00'),
            sale=self.sale,
            reference=self.sale.sale_number,
            notes='Unpaid balance from sale',
            created_by=self.manager_user,
        )

    def test_detail_endpoint_returns_profile_orders_ledger(self):
        # Rebuild: previous debt 600 → paid 300 → new debt 300
        CustomerWalletTransaction.objects.filter(customer=self.customer).delete()
        self.customer.wallet_balance = Decimal('-300.00')
        self.customer.save(update_fields=['wallet_balance'])
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('600.00'),
            balance_after=Decimal('-600.00'),
            sale=self.sale,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('300.00'),
            balance_after=Decimal('-300.00'),
            notes='Debt payment received via Cash',
        )

        response = self.client.get(f'/api/sales/customers/{self.customer.id}/detail/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['customer']['name'], 'Detail Customer')
        self.assertIn('owner_name', response.data['customer'])
        self.assertIn('typical_goods', response.data['customer'])
        self.assertEqual(response.data['customer']['wallet_debt'], '300.00')
        self.assertEqual(response.data['standing_summary']['lifetime_orders'], 1)
        self.assertEqual(len(response.data['orders']), 1)
        self.assertEqual(response.data['orders'][0]['paid_amount'], '330.00')
        self.assertEqual(response.data['orders'][0]['debt_amount'], '300.00')

        settlement = next(
            row for row in response.data['ledger'] if row['source_type'] == 'debt_settlement'
        )
        self.assertEqual(settlement['previous_debt'], '600.00')
        self.assertEqual(settlement['payment_amount'], '300.00')
        self.assertEqual(settlement['new_debt'], '300.00')

    def test_detail_not_found(self):
        response = self.client.get('/api/sales/customers/999999/detail/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_tolerates_invalid_pagination_params(self):
        response = self.client.get(
            f'/api/sales/customers/{self.customer.id}/detail/',
            {
                'orders_page': 'x',
                'orders_page_size': 'y',
                'ledger_page': 'z',
                'ledger_page_size': 'q',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('orders', response.data)
        self.assertIn('ledger', response.data)

    def test_get_customer_detail_service_paginates(self):
        for i in range(3):
            Sale.objects.create(
                sale_number=f'S-PAGE-{i}',
                customer=self.customer,
                subtotal=Decimal('10.00'),
                total=Decimal('10.00'),
                amount_paid=Decimal('10.00'),
                status='completed',
                sale_type='pos',
                payment_method='cash',
            )
        payload = get_customer_detail(
            customer_id=self.customer.id,
            orders_page=1,
            orders_page_size=2,
            ledger_page=1,
            ledger_page_size=1,
        )
        self.assertEqual(len(payload['orders']), 2)
        self.assertTrue(payload['orders_pagination']['has_next'])
        self.assertEqual(len(payload['ledger']), 1)

    def test_wallet_transactions_include_debt_trail_fields(self):
        CustomerWalletTransaction.objects.filter(customer=self.customer).delete()
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('300.00'),
            balance_after=Decimal('-300.00'),
        )
        response = self.client.get(
            f'/api/sales/customers/{self.customer.id}/wallet-transactions/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['previous_debt'], '600.00')
        self.assertEqual(response.data[0]['new_debt'], '300.00')


class CustomerDetailSalesPersonaTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_customer_settings()
        self.customer = Customer.objects.create(
            name='Sales View Cust',
            wallet_balance=Decimal('0.00'),
            is_active=True,
        )

    def test_sales_can_view_customer_detail(self):
        response = self.client.get(f'/api/sales/customers/{self.customer.id}/detail/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['customer']['name'], 'Sales View Cust')
        self.assertEqual(response.data['orders'], [])
        self.assertEqual(response.data['ledger'], [])
        self.assertIsNone(response.data['customer'].get('latitude'))
        self.assertIsNone(response.data['customer'].get('longitude'))

    def test_detail_includes_snapped_location_ping(self):
        """Corrected functionality: detail profile exposes the field-picked GPS pin."""
        self.customer.latitude = Decimal('-1.2921000')
        self.customer.longitude = Decimal('36.8219000')
        self.customer.location_accuracy = 14.5
        self.customer.address = 'Near stage'
        self.customer.county = 'Nairobi'
        self.customer.save(
            update_fields=[
                'latitude',
                'longitude',
                'location_accuracy',
                'address',
                'county',
            ]
        )
        response = self.client.get(f'/api/sales/customers/{self.customer.id}/detail/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile = response.data['customer']
        self.assertAlmostEqual(profile['latitude'], -1.2921, places=4)
        self.assertAlmostEqual(profile['longitude'], 36.8219, places=4)
        self.assertAlmostEqual(profile['location_accuracy'], 14.5, places=1)
        self.assertEqual(profile['address'], 'Near stage')
        self.assertEqual(profile['county'], 'Nairobi')

    def test_detail_location_ping_stress_and_idor(self):
        """Stress + security: many detail reads stay stable; unknown id is not leaked."""
        self.customer.latitude = Decimal('-1.3000000')
        self.customer.longitude = Decimal('36.8000000')
        self.customer.save(update_fields=['latitude', 'longitude'])
        for _ in range(20):
            response = self.client.get(f'/api/sales/customers/{self.customer.id}/detail/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertAlmostEqual(response.data['customer']['latitude'], -1.3, places=4)
        missing = self.client.get('/api/sales/customers/999999991/detail/')
        self.assertIn(missing.status_code, (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN))
        self.assertNotIn('-1.3', str(missing.data))


class CustomerCallHistoryTests(ManagerAPITestCase):
    """Call history on the customer detail screen."""

    def setUp(self):
        super().setUp()
        _seed_customer_settings()
        self.customer = Customer.objects.create(
            name='Called Duka',
            phone='0712000001',
            county='Nairobi',
            typical_goods=['Sofa legs'],
            buyer_segment='active',
            engagement_tier='buyer',
            is_active=True,
        )
        self.other = Customer.objects.create(
            name='Other Duka',
            phone='0799000111',
            is_active=True,
        )

    def _call(self, customer, outcome, note, week=date(2026, 11, 16)):
        return CustomerCall.objects.create(
            customer=customer,
            called_by=self.manager_user,
            week_start=week,
            outcome=outcome,
            request_summary=note,
        )

    def test_newest_calls_are_listed_without_another_customers_phone(self):
        self._call(self.customer, 'no_answer', 'No response')
        latest = self._call(self.customer, 'called', 'Discussed sofa legs')
        self._call(self.other, 'called', 'Do not show this shop')
        response = self.client.get(f'/api/sales/customers/{self.customer.id}/detail/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.content.decode()
        self.assertNotIn('0799000111', body)
        self.assertNotIn('Do not show this shop', body)
        calls = response.data['calls']
        self.assertEqual(response.data['calls_count'], 2)
        self.assertTrue(response.data['calls_enabled'])
        self.assertEqual(calls[0]['id'], latest.id)
        self.assertEqual(calls[0]['outcome_label'], 'Called')
        self.assertEqual(calls[0]['request_summary'], 'Discussed sofa legs')
        self.assertNotIn('phone', calls[0])

    def test_feature_off_hides_the_history(self):
        self._call(self.customer, 'called', 'Spoke')
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='customers',
            defaults={'is_enabled': True, 'description': 'customers'},
        )
        feature, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='call_book',
            defaults={'feature_name': 'Weekly call book', 'is_enabled': True},
        )
        feature.is_enabled = False
        feature.save(update_fields=['is_enabled'])
        try:
            response = self.client.get(f'/api/sales/customers/{self.customer.id}/detail/')
        finally:
            feature.is_enabled = True
            feature.save(update_fields=['is_enabled'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['calls_enabled'])
        self.assertEqual(response.data['calls'], [])
        self.assertEqual(response.data['calls_count'], 0)
        self.assertNotIn('Spoke', response.content.decode())

    def test_anonymous_detail_does_not_return_the_phone(self):
        client = APIClient()
        response = client.get(f'/api/sales/customers/{self.customer.id}/detail/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('0712000001', response.content.decode())

    def test_more_than_fifty_calls_keep_the_newest_page(self):
        CustomerCall.objects.bulk_create([
            CustomerCall(
                customer=self.customer,
                called_by=self.manager_user,
                week_start=date(2026, 11, 16),
                outcome='called',
                request_summary=f'Note {index:02d}',
            )
            for index in range(60)
        ])
        payload = get_customer_detail(customer_id=self.customer.id)
        self.assertEqual(payload['calls_count'], 60)
        self.assertEqual(len(payload['calls']), 50)
        self.assertNotIn('0712000001', str(payload['calls']))

