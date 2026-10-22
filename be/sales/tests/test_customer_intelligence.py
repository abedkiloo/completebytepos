"""Customer purchase intelligence — tiers, RFM-lite segments, list filters."""

from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from products.models import Category, Product
from sales.customer_intelligence import (
    ENGAGEMENT_BUYER,
    ENGAGEMENT_PROSPECT,
    SEGMENT_ACTIVE,
    SEGMENT_AT_RISK,
    SEGMENT_CHAMPION,
    SEGMENT_DORMANT,
    SEGMENT_NEW,
    SEGMENT_NONE,
    backfill_customer_intelligence,
    classify_buyer_segment,
    on_sale_completed,
    refresh_customer_purchase_intelligence,
    segment_label,
    tier_label,
)
from sales.models import Customer, Sale, SaleItem
from sales.services import SaleService


class ClassifyBuyerSegmentTests(TestCase):
    def test_prospect_and_new_and_active(self):
        now = timezone.now()
        self.assertEqual(
            classify_buyer_segment(
                purchase_count=0,
                lifetime_sales_value=Decimal('0'),
                last_purchased_at=None,
                now=now,
            ),
            SEGMENT_NONE,
        )
        self.assertEqual(
            classify_buyer_segment(
                purchase_count=1,
                lifetime_sales_value=Decimal('100'),
                last_purchased_at=now - timedelta(days=2),
                now=now,
            ),
            SEGMENT_NEW,
        )
        self.assertEqual(
            classify_buyer_segment(
                purchase_count=3,
                lifetime_sales_value=Decimal('500'),
                last_purchased_at=now - timedelta(days=5),
                now=now,
            ),
            SEGMENT_ACTIVE,
        )

    def test_at_risk_dormant_champion(self):
        now = timezone.now()
        self.assertEqual(
            classify_buyer_segment(
                purchase_count=2,
                lifetime_sales_value=Decimal('200'),
                last_purchased_at=now - timedelta(days=45),
                now=now,
            ),
            SEGMENT_AT_RISK,
        )
        self.assertEqual(
            classify_buyer_segment(
                purchase_count=2,
                lifetime_sales_value=Decimal('200'),
                last_purchased_at=now - timedelta(days=120),
                now=now,
            ),
            SEGMENT_DORMANT,
        )
        self.assertEqual(
            classify_buyer_segment(
                purchase_count=5,
                lifetime_sales_value=Decimal('15000'),
                last_purchased_at=now - timedelta(days=3),
                now=now,
            ),
            SEGMENT_CHAMPION,
        )

    def test_labels(self):
        self.assertIn('Omuwenga', tier_label(ENGAGEMENT_BUYER))
        self.assertIn('Registered', tier_label(ENGAGEMENT_PROSPECT))
        self.assertEqual(segment_label(SEGMENT_NEW), 'New buyer')


class RefreshCustomerIntelligenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('intel', password='x')
        self.cat = Category.objects.create(name='Intel Cat', is_active=True)
        self.product = Product.objects.create(
            name='Intel Item',
            sku='INT-1',
            category=self.cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )
        self.prospect = Customer.objects.create(name='Never Bought', phone='0700111001')
        self.buyer = Customer.objects.create(name='Has Bought', phone='0700111002')

    def _complete_sale(self, customer, *, total='100', days_ago=0):
        sale = Sale.objects.create(
            sale_number=f'S-INT-{customer.id}-{Sale.objects.count()}',
            status='completed',
            sale_type='pos',
            customer=customer,
            subtotal=Decimal(total),
            total=Decimal(total),
            tax_amount=Decimal('0'),
            payment_method='cash',
            amount_paid=Decimal(total),
            cashier=self.user,
            occurred_at=timezone.now() - timedelta(days=days_ago),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal(total),
            unit_cost=Decimal('40'),
            subtotal=Decimal(total),
        )
        on_sale_completed(sale)
        return sale

    def test_prospect_stays_prospect_without_sales(self):
        stats = refresh_customer_purchase_intelligence(self.prospect.id)
        self.prospect.refresh_from_db()
        self.assertEqual(stats['engagement_tier'], ENGAGEMENT_PROSPECT)
        self.assertEqual(self.prospect.engagement_tier, ENGAGEMENT_PROSPECT)
        self.assertEqual(self.prospect.buyer_segment, SEGMENT_NONE)
        self.assertEqual(self.prospect.purchase_count, 0)

    def test_first_sale_promotes_to_buyer_new(self):
        self._complete_sale(self.buyer)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.engagement_tier, ENGAGEMENT_BUYER)
        self.assertEqual(self.buyer.buyer_segment, SEGMENT_NEW)
        self.assertEqual(self.buyer.purchase_count, 1)
        self.assertEqual(self.buyer.lifetime_sales_value, Decimal('100.00'))
        self.assertIsNotNone(self.buyer.first_purchased_at)
        self.assertIsNotNone(self.buyer.intelligence_updated_at)

    def test_second_sale_moves_to_active(self):
        self._complete_sale(self.buyer, days_ago=1)
        self._complete_sale(self.buyer, total='50')
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.purchase_count, 2)
        self.assertEqual(self.buyer.lifetime_sales_value, Decimal('150.00'))
        self.assertEqual(self.buyer.buyer_segment, SEGMENT_ACTIVE)

    def test_on_sale_completed_noop_without_customer(self):
        sale = Sale.objects.create(
            sale_number='S-NO-CUST',
            status='completed',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            amount_paid=Decimal('10'),
            cashier=self.user,
            occurred_at=timezone.now(),
        )
        self.assertIsNone(on_sale_completed(sale))

    def test_backfill_classifies_existing_sales(self):
        Sale.objects.create(
            sale_number='S-BF-1',
            status='completed',
            customer=self.buyer,
            subtotal=Decimal('80'),
            total=Decimal('80'),
            amount_paid=Decimal('80'),
            cashier=self.user,
            occurred_at=timezone.now(),
        )
        result = backfill_customer_intelligence(batch_size=10)
        self.buyer.refresh_from_db()
        self.prospect.refresh_from_db()
        self.assertEqual(result['processed'], 2)
        self.assertEqual(result['buyers'], 1)
        self.assertEqual(result['prospects'], 1)
        self.assertEqual(self.buyer.engagement_tier, ENGAGEMENT_BUYER)
        self.assertEqual(self.prospect.engagement_tier, ENGAGEMENT_PROSPECT)

    def test_sale_service_create_refreshes_tier(self):
        service = SaleService()
        sale = service.create_sale(
            {
                'sale_type': 'pos',
                'customer': self.prospect,
                'payment_method': 'cash',
                'amount_paid': Decimal('100'),
            },
            [
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'unit_price': Decimal('100'),
                }
            ],
            self.user,
            complete=True,
        )
        self.assertEqual(sale.status, 'completed')
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.engagement_tier, ENGAGEMENT_BUYER)
        self.assertGreaterEqual(self.prospect.purchase_count, 1)


class CustomerIntelligenceAPITests(TestCase):
    def setUp(self):
        ensure_permissions()
        sync_default_roles()
        self.admin = User.objects.create_user('intel-admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=self.admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.buyer = Customer.objects.create(
            name='API Buyer',
            phone='0700222001',
            engagement_tier=ENGAGEMENT_BUYER,
            buyer_segment=SEGMENT_ACTIVE,
            purchase_count=2,
            lifetime_sales_value=Decimal('200'),
        )
        self.prospect = Customer.objects.create(
            name='API Prospect',
            phone='0700222002',
            engagement_tier=ENGAGEMENT_PROSPECT,
            buyer_segment=SEGMENT_NONE,
        )

    def test_filter_buyers_and_prospects(self):
        buyers = self.client.get('/api/sales/customers/', {'engagement_tier': 'buyer'})
        self.assertEqual(buyers.status_code, 200, buyers.data)
        buyer_ids = {row['id'] for row in (buyers.data.get('results') or buyers.data)}
        self.assertIn(self.buyer.id, buyer_ids)
        self.assertNotIn(self.prospect.id, buyer_ids)

        prospects = self.client.get('/api/sales/customers/', {'engagement_tier': 'prospect'})
        self.assertEqual(prospects.status_code, 200, prospects.data)
        prospect_ids = {row['id'] for row in (prospects.data.get('results') or prospects.data)}
        self.assertIn(self.prospect.id, prospect_ids)
        self.assertNotIn(self.buyer.id, prospect_ids)

    def test_list_includes_intelligence_fields(self):
        resp = self.client.get('/api/sales/customers/', {'search': 'API Buyer'})
        self.assertEqual(resp.status_code, 200)
        rows = resp.data.get('results') or resp.data
        row = next(r for r in rows if r['id'] == self.buyer.id)
        self.assertEqual(row['engagement_tier'], ENGAGEMENT_BUYER)
        self.assertEqual(row['buyer_segment'], SEGMENT_ACTIVE)
        self.assertEqual(row['purchase_count'], 2)

    def test_filter_buyer_segment(self):
        resp = self.client.get('/api/sales/customers/', {'buyer_segment': 'active'})
        self.assertEqual(resp.status_code, 200)
        ids = {row['id'] for row in (resp.data.get('results') or resp.data)}
        self.assertIn(self.buyer.id, ids)
        self.assertNotIn(self.prospect.id, ids)


class CustomerIntelligenceEdgeTests(TestCase):
    def test_refresh_missing_customer_and_holding_sale(self):
        self.assertIsNone(refresh_customer_purchase_intelligence(None))
        self.assertIsNone(refresh_customer_purchase_intelligence(99999999))
        user = User.objects.create_user('edge', password='x')
        cust = Customer.objects.create(name='Holding Only', phone='0700333001')
        sale = Sale.objects.create(
            sale_number='S-HOLD',
            status='holding',
            customer=cust,
            subtotal=Decimal('10'),
            total=Decimal('10'),
            amount_paid=Decimal('0'),
            cashier=user,
            occurred_at=timezone.now(),
        )
        self.assertIsNone(on_sale_completed(sale))

    def test_backfill_batches(self):
        user = User.objects.create_user('batchu', password='x')
        # Buyer first so a full mid-loop batch (size 2) includes a buyer hit.
        buyer = Customer.objects.create(name='Batch Buyer', phone='0700444999')
        Sale.objects.create(
            sale_number='S-BATCH-BUY',
            status='completed',
            customer=buyer,
            subtotal=Decimal('20'),
            total=Decimal('20'),
            amount_paid=Decimal('20'),
            cashier=user,
            occurred_at=timezone.now(),
        )
        for i in range(3):
            Customer.objects.create(name=f'Batch {i}', phone=f'0700444{i:03d}')
        result = backfill_customer_intelligence(batch_size=2)
        self.assertEqual(result['processed'], 4)
        self.assertEqual(result['buyers'], 1)
        buyer.refresh_from_db()
        self.assertEqual(buyer.engagement_tier, ENGAGEMENT_BUYER)

    def test_naive_last_purchased_at(self):
        naive = timezone.now().replace(tzinfo=None)
        seg = classify_buyer_segment(
            purchase_count=2,
            lifetime_sales_value=Decimal('100'),
            last_purchased_at=naive,
            now=timezone.now(),
        )
        self.assertIn(seg, (SEGMENT_NEW, SEGMENT_ACTIVE, SEGMENT_AT_RISK, SEGMENT_DORMANT, SEGMENT_CHAMPION))
