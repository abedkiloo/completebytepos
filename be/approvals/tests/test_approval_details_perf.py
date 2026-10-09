"""Query-budget checks for approval queues (no per-row N+1 on details)."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import (
    ACTION_DEBT_COLLECTION,
    ACTION_PRODUCT_PRICE,
    ACTION_SALE_COMPLETE,
    ACTION_STOCK_PURCHASE,
)
from products.models import Category, Product
from sales.models import Customer, Sale, SaleItem
from utils.tests.api_test_base import SalesAPITestCase


class ApprovalDetailsPerfTests(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ensure_permissions()
        sync_default_roles()
        cls.manager = User.objects.create_user('appr_perf_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        cls.category = Category.objects.create(name='Appr Perf', is_active=True)
        cls.product = Product.objects.create(
            name='Appr Perf SKU',
            sku='APPR-PERF-1',
            category=cls.category,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=500,
            track_stock=True,
            is_active=True,
        )
        cls.customers = []
        for i in range(12):
            cls.customers.append(
                Customer.objects.create(
                    name=f'Debtor {i}',
                    phone=f'07000000{i:02d}',
                    wallet_balance=Decimal('-200.00'),
                    is_active=True,
                )
            )
        cls.pending_sales = []
        for i in range(12):
            sale = Sale.objects.create(
                sale_number=f'APPR-S-{i}',
                cashier=cls.sales_user,
                status='pending_approval',
                sale_type='pos',
                customer=cls.customers[i % len(cls.customers)],
                subtotal=Decimal('100.00'),
                total=Decimal('100.00'),
                amount_paid=Decimal('100.00'),
                payment_method='cash',
            )
            SaleItem.objects.create(
                sale=sale,
                product=cls.product,
                quantity=1,
                unit_price=Decimal('100.00'),
                subtotal=Decimal('100.00'),
            )
            PendingChange.objects.create(
                action_type=ACTION_SALE_COMPLETE,
                entity_type='sales.Sale',
                entity_id=str(sale.pk),
                entity_repr=sale.sale_number,
                reason='Till sale awaiting approval',
                status=PendingChange.STATUS_PENDING,
                made_by=cls.sales_user,
                apply_payload={
                    'amount_paid': '100.00',
                    'payment_method': 'cash',
                },
            )
            cls.pending_sales.append(sale)

        for i, customer in enumerate(cls.customers):
            PendingChange.objects.create(
                action_type=ACTION_DEBT_COLLECTION,
                entity_type='sales.Customer',
                entity_id=str(customer.pk),
                entity_repr=customer.name,
                reason='Field collection',
                status=PendingChange.STATUS_PENDING,
                made_by=cls.sales_user,
                original_values={'wallet_balance': str(customer.wallet_balance)},
                proposed_values={'amount': '50.00'},
                apply_payload={
                    'amount': '50.00',
                    'payment_method': 'cash',
                    'notes': f'Visit {i}',
                },
            )

        for i in range(8):
            PendingChange.objects.create(
                action_type=ACTION_PRODUCT_PRICE,
                entity_type='products.Product',
                entity_id=str(cls.product.pk),
                entity_repr=cls.product.name,
                reason=f'Price bump {i}',
                status=PendingChange.STATUS_PENDING,
                made_by=cls.sales_user,
                original_values={'price': '100.00'},
                proposed_values={'price': str(100 + i)},
            )
            PendingChange.objects.create(
                action_type=ACTION_STOCK_PURCHASE,
                entity_type='inventory.StockMovement',
                entity_id='new',
                entity_repr=cls.product.name,
                reason=f'Restock {i}',
                status=PendingChange.STATUS_PENDING,
                made_by=cls.sales_user,
                apply_payload={
                    'product_id': cls.product.pk,
                    'quantity': 5 + i,
                    'unit_cost': '40.00',
                    'notes': f'PO-{i}',
                },
            )

    def _manager_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.manager)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_pending_sales_list_query_count_does_not_grow_with_rows(self):
        client = self._manager_client()
        with CaptureQueriesContext(connection) as ctx_full:
            full = client.get('/api/sales/', {'status': 'pending_approval', 'page_size': 100})
        self.assertEqual(full.status_code, 200, full.data)
        rows = full.data.get('results', full.data)
        self.assertGreaterEqual(len(rows), 12)
        for row in rows:
            self.assertIsNotNone(row.get('approval_details'))
            self.assertTrue(row['approval_details']['sections'])

        with CaptureQueriesContext(connection) as ctx_page:
            page = client.get('/api/sales/', {'status': 'pending_approval', 'page_size': 5})
        self.assertEqual(page.status_code, 200, page.data)
        page_rows = page.data.get('results', page.data)
        self.assertEqual(len(page_rows), 5)

        self.assertLessEqual(
            len(ctx_full),
            30,
            msg=f'Pending sales list used {len(ctx_full)} queries (likely N+1):\n'
            + '\n'.join(q['sql'][:160] for q in ctx_full.captured_queries[-12:]),
        )
        self.assertLessEqual(
            abs(len(ctx_full) - len(ctx_page)),
            4,
            msg=(
                f'Query count grew with page size '
                f'({len(ctx_page)} for 5 vs {len(ctx_full)} for {len(rows)}).'
            ),
        )

    def test_pending_changes_list_query_count_does_not_grow_with_rows(self):
        client = self._manager_client()
        with CaptureQueriesContext(connection) as ctx_full:
            full = client.get('/api/approvals/pending-changes/pending/')
        self.assertEqual(full.status_code, 200, full.data)
        rows = full.data if isinstance(full.data, list) else full.data.get('results', [])
        self.assertGreaterEqual(len(rows), 20)
        with_details = [r for r in rows if r.get('details')]
        self.assertGreaterEqual(len(with_details), 20)

        # Slice mentally: same endpoint always returns full pending set; compare
        # serializing many vs few via action_type filters instead.
        with CaptureQueriesContext(connection) as ctx_debt:
            debt = client.get(
                '/api/approvals/pending-changes/pending/',
                {'action_type': ACTION_DEBT_COLLECTION},
            )
        self.assertEqual(debt.status_code, 200, debt.data)
        debt_rows = debt.data if isinstance(debt.data, list) else debt.data.get('results', [])
        self.assertEqual(len(debt_rows), 12)

        with CaptureQueriesContext(connection) as ctx_stock:
            stock = client.get(
                '/api/approvals/pending-changes/pending/',
                {'action_type': ACTION_STOCK_PURCHASE},
            )
        self.assertEqual(stock.status_code, 200, stock.data)
        stock_rows = stock.data if isinstance(stock.data, list) else stock.data.get('results', [])
        self.assertEqual(len(stock_rows), 8)

        self.assertLessEqual(
            len(ctx_full),
            55,
            msg=f'Pending changes used {len(ctx_full)} queries (likely N+1):\n'
            + '\n'.join(q['sql'][:160] for q in ctx_full.captured_queries[-15:]),
        )
        # Debt (12) vs stock (8) should stay nearly flat — not +1 query per extra row.
        self.assertLessEqual(
            abs(len(ctx_debt) - len(ctx_stock)),
            8,
            msg=(
                f'Query count grew with row mix '
                f'({len(ctx_debt)} debt vs {len(ctx_stock)} stock).'
            ),
        )
