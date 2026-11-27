"""Cover FieldLoad* __str__ and order line total helper."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from agents.models import FieldLoad, FieldLoadLine, FieldLoadSale, FieldOrder, FieldOrderLine
from agents.order_services import field_order_total
from products.models import Category, Product
from sales.models import Customer, Sale


class AgentsModelStrGapTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user('str_agent', password='x')
        cat = Category.objects.create(name='Str Cat', is_active=True)
        self.product = Product.objects.create(
            name='Str Prod',
            sku='STR-1',
            category=cat,
            price=Decimal('10'),
            cost=Decimal('4'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        self.customer = Customer.objects.create(
            name='Str Cust', phone='0700111222', created_by=self.agent,
        )

    def test_field_load_strs_and_order_total(self):
        from agents.models import CustomerSite

        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1',
            longitude='36',
            created_by=self.agent,
            status=CustomerSite.STATUS_FINALIZED,
        )
        order = FieldOrder.objects.create(site=site, created_by=self.agent)
        FieldOrderLine.objects.create(
            order=order,
            product=self.product,
            quantity=Decimal('2'),
            unit_price=Decimal('5.00'),
            product_name='Str Prod',
        )
        FieldOrderLine.objects.create(
            order=order,
            product=self.product,
            quantity=Decimal('0'),
            unit_price=Decimal('0'),
            product_name='Zero',
        )
        self.assertEqual(field_order_total(order), Decimal('10.00'))

        load = FieldLoad.objects.create(agent=self.agent)
        self.assertIn('Field load', str(load))
        line = FieldLoadLine.objects.create(
            load=load, product=self.product, quantity_taken=3,
        )
        self.assertIn('Load line', str(line))
        sale = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('10'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('10'),
            amount_paid=Decimal('10'),
            cashier=self.agent,
        )
        link = FieldLoadSale.objects.create(load=load, sale=sale)
        self.assertIn(str(load.pk), str(link))
        self.assertIn(str(sale.pk), str(link))

        from rest_framework.exceptions import ValidationError

        from agents.serializers import SiteMediaUploadSerializer

        with self.assertRaises(ValidationError):
            SiteMediaUploadSerializer().validate_image(None)
