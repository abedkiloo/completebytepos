"""
Senior financial audit: sale corrections (qty change / line remove) must cascade
through stock, FIFO layers, COGS stamps, journals, debt, and trading-profit reports.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN
from agents.push import FakePushNotifier, set_push_notifier
from inventory.models import StockLayer, StockMovement
from products.models import Category, Product
from reports.trading_profit import _cogs_for_sales, compute_trading_profit
from reports.views import sale_report_queryset
from sales.models import Sale, SaleItemLayerAllocation
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from settings.test_utils import enable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


def _enable_layers():
    cache.clear()
    ModuleSetting.objects.update_or_create(
        module='inventory',
        key='enable_stock_layers',
        defaults={
            'label': 'enable_stock_layers',
            'description': '',
            'default_value': True,
            'value': True,
        },
    )
    SettingsService.set('inventory', 'enable_stock_layers', True)
    cache.clear()


class SaleCorrectionCascadeAuditTests(SalesAPITestCase):
    """Books must match the corrected cart after admin return → edit → re-approve."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.manager_user = User.objects.create_user('cascade_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager_user,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        cls.admin = User.objects.create_superuser(
            'cascade_admin', email='cascade@test.com', password='x'
        )
        UserProfile.objects.create(
            user=cls.admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.category = Category.objects.create(name='Cascade Cat', is_active=True)
        cls.product_a = Product.objects.create(
            name='Cascade A',
            sku='CASCADE-A',
            category=cls.category,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        cls.product_b = Product.objects.create(
            name='Cascade B',
            sku='CASCADE-B',
            category=cls.category,
            price=Decimal('50.00'),
            cost=Decimal('20.00'),
            stock_quantity=15,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        enable_maker_checker()
        _enable_layers()
        self.notifier = FakePushNotifier()
        set_push_notifier(self.notifier)
        self.tenant, self.branch, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.sales_user
        )
        self.set_session_branch(self.tenant, self.branch)
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        # Reset stock between tests (setUpTestData shares rows).
        Product.objects.filter(pk=self.product_a.pk).update(
            stock_quantity=20, cost=Decimal('40.00')
        )
        Product.objects.filter(pk=self.product_b.pk).update(
            stock_quantity=15, cost=Decimal('20.00')
        )
        StockLayer.objects.filter(product__in=[self.product_a, self.product_b]).delete()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()

    def tearDown(self):
        set_push_notifier(FakePushNotifier())
        super().tearDown()

    def set_session_branch(self, tenant, branch):
        session = self.client.session
        session['current_tenant_id'] = tenant.id
        session['current_branch_id'] = branch.id
        session.save()

    def _client_for(self, user):
        client = self.client.__class__()
        token = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        session = client.session
        session['current_tenant_id'] = self.tenant.id
        session['current_branch_id'] = self.branch.id
        session.save()
        return client

    def _manager(self):
        return self._client_for(self.manager_user)

    def _admin(self):
        return self._client_for(self.admin)

    def _complete_sale(self, items, *, amount_paid=None):
        api_items = []
        total = Decimal('0')
        for row in items:
            qty = Decimal(str(row['quantity']))
            price = Decimal(str(row['unit_price']))
            total += qty * price
            api_items.append({
                'product_id': row['product_id'],
                'quantity': str(row['quantity']),
                'unit_price': str(row['unit_price']),
            })
        payload = {
            'items': api_items,
            'payment_method': 'cash',
            'amount_paid': str(amount_paid if amount_paid is not None else total),
            'sale_type': 'pos',
            'allow_partial_payment': False,
        }
        created = self.client.post('/api/sales/', payload, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        sale_id = created.data['id']
        approve = self._manager().post(f'/api/sales/{sale_id}/complete/', {}, format='json')
        self.assertEqual(approve.status_code, status.HTTP_200_OK, approve.data)
        sale = Sale.objects.get(pk=sale_id)
        self.assertEqual(sale.status, 'completed')
        return sale

    def _admin_return(self, sale_id, reason='Audit correction'):
        response = self._admin().post(
            f'/api/sales/{sale_id}/reject-complete/',
            {'rejection_reason': reason},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        sale = Sale.objects.get(pk=sale_id)
        self.assertEqual(sale.status, 'holding')
        return sale

    def _edit_and_reapprove(self, sale_id, items, *, amount_paid=None):
        total = sum(
            Decimal(str(r['quantity'])) * Decimal(str(r['unit_price']))
            for r in items
        )
        edited = self.client.post(
            '/api/sales/holding/',
            {
                'holding_id': sale_id,
                'items': [
                    {
                        'product_id': r['product_id'],
                        'quantity': str(r['quantity']),
                        'unit_price': str(r['unit_price']),
                    }
                    for r in items
                ],
                'client_channel': 'web',
            },
            format='json',
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK, edited.data)
        queued = self.client.post(
            f'/api/sales/{sale_id}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': str(amount_paid if amount_paid is not None else total),
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(queued.status_code, status.HTTP_201_CREATED, queued.data)
        approve = self._manager().post(f'/api/sales/{sale_id}/complete/', {}, format='json')
        self.assertEqual(approve.status_code, status.HTTP_200_OK, approve.data)
        return Sale.objects.get(pk=sale_id)

    def _active_sale_movements(self, sale_number):
        return StockMovement.objects.filter(
            movement_type='sale',
            reference=sale_number,
        )

    def _superseded_sale_movements(self, sale_number):
        return StockMovement.objects.filter(
            movement_type='sale',
            reference__startswith=f'{sale_number}#corrected-',
        )

    def test_qty_reduction_cascades_stock_cogs_layers_and_reports(self):
        sale = self._complete_sale([
            {'product_id': self.product_a.id, 'quantity': 5, 'unit_price': '100.00'},
        ])
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 15)
        original_cogs = _cogs_for_sales(Sale.objects.filter(pk=sale.pk))
        self.assertEqual(original_cogs, Decimal('200.00'))  # 5 × 40
        self.assertTrue(sale_report_queryset().filter(pk=sale.pk).exists())
        layer_before_return = list(
            StockLayer.objects.filter(product=self.product_a).values_list(
                'qty_remaining', flat=True
            )
        )

        self._admin_return(sale.pk, reason='Wrong quantity')
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 20)
        self.assertFalse(sale_report_queryset().filter(pk=sale.pk).exists())
        self.assertFalse(self._active_sale_movements(sale.sale_number).exists())
        self.assertTrue(self._superseded_sale_movements(sale.sale_number).exists())
        self.assertFalse(
            SaleItemLayerAllocation.objects.filter(sale_item__sale=sale).exists()
        )
        # Layers fully restored after unpost.
        restored = sum(
            StockLayer.objects.filter(product=self.product_a).values_list(
                'qty_remaining', flat=True
            )
        )
        self.assertGreaterEqual(restored, 20)

        corrected = self._edit_and_reapprove(
            sale.pk,
            [{'product_id': self.product_a.id, 'quantity': 2, 'unit_price': '100.00'}],
        )
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 18)
        self.assertEqual(corrected.status, 'completed')
        self.assertEqual(corrected.total, Decimal('200.00'))
        self.assertEqual(corrected.items.count(), 1)
        self.assertEqual(int(corrected.items.get().quantity), 2)

        line = corrected.items.get()
        self.assertEqual(Decimal(str(line.unit_cost)), Decimal('40.00'))
        cogs = _cogs_for_sales(Sale.objects.filter(pk=corrected.pk))
        self.assertEqual(cogs, Decimal('80.00'))  # 2 × 40 — not 5×40 leftover

        active_sale_qty = self._active_sale_movements(corrected.sale_number).aggregate(
            t=Sum('quantity')
        )['t']
        self.assertEqual(int(active_sale_qty or 0), 2)
        # Prior drains remain as audit trail under corrected tags only.
        self.assertTrue(self._superseded_sale_movements(corrected.sale_number).exists())

        now = timezone.now()
        profit = compute_trading_profit(
            start=now - timedelta(days=1),
            end=now + timedelta(days=1),
        )
        self.assertEqual(Decimal(str(profit['cogs_sold'])), Decimal('80.00'))
        self.assertEqual(Decimal(str(profit['gross_sales'])), Decimal('200.00'))
        self.assertTrue(sale_report_queryset().filter(pk=corrected.pk).exists())
        self.assertIsNotNone(layer_before_return)

    def test_line_remove_cascades_out_of_stock_cogs_and_reports(self):
        sale = self._complete_sale([
            {'product_id': self.product_a.id, 'quantity': 3, 'unit_price': '100.00'},
            {'product_id': self.product_b.id, 'quantity': 4, 'unit_price': '50.00'},
        ])
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 17)
        self.assertEqual(self.product_b.stock_quantity, 11)
        self.assertEqual(
            _cogs_for_sales(Sale.objects.filter(pk=sale.pk)),
            Decimal('200.00'),  # 3×40 + 4×20
        )

        self._admin_return(sale.pk, reason='Remove product B')
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 20)
        self.assertEqual(self.product_b.stock_quantity, 15)

        corrected = self._edit_and_reapprove(
            sale.pk,
            [{'product_id': self.product_a.id, 'quantity': 3, 'unit_price': '100.00'}],
        )
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 17)
        self.assertEqual(self.product_b.stock_quantity, 15)  # fully restored, not re-sold
        self.assertEqual(corrected.items.count(), 1)
        self.assertEqual(corrected.items.get().product_id, self.product_a.id)
        self.assertEqual(corrected.total, Decimal('300.00'))
        self.assertEqual(
            _cogs_for_sales(Sale.objects.filter(pk=corrected.pk)),
            Decimal('120.00'),  # 3×40 only
        )
        # No live sale movement for the removed product under the sale number.
        self.assertFalse(
            self._active_sale_movements(corrected.sale_number)
            .filter(product=self.product_b)
            .exists()
        )
        now = timezone.now()
        profit = compute_trading_profit(
            start=now - timedelta(days=1),
            end=now + timedelta(days=1),
        )
        self.assertEqual(Decimal(str(profit['cogs_sold'])), Decimal('120.00'))
        self.assertEqual(Decimal(str(profit['gross_sales'])), Decimal('300.00'))

    def test_unpost_return_uses_stamped_unit_cost_not_catalog(self):
        """Catalog cost drift must not rewrite the correction return valuation."""
        sale = self._complete_sale([
            {'product_id': self.product_a.id, 'quantity': 2, 'unit_price': '100.00'},
        ])
        line = sale.items.get()
        self.assertEqual(Decimal(str(line.unit_cost)), Decimal('40.00'))
        # Drift catalog after posting (simulates later purchase / price change).
        Product.objects.filter(pk=self.product_a.pk).update(cost=Decimal('99.00'))

        self._admin_return(sale.pk, reason='Cost stamp check')
        ret = StockMovement.objects.filter(
            movement_type='return',
            reference=sale.sale_number,
        ).order_by('-id').first()
        self.assertIsNotNone(ret)
        self.assertEqual(Decimal(str(ret.unit_cost)), Decimal('40.00'))
        self.assertEqual(Decimal(str(ret.total_cost)), Decimal('80.00'))
