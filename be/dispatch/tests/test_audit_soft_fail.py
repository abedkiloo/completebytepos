"""Dispatch pack/assign/create-driver keep working when audit logging fails."""

from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from agents.models import FieldOrder, FieldOrderLine
from agents.order_services import submit_order
from delivery.tests.test_claim_and_drivers import ClaimAndDriversAPITestCase


class DispatchAuditSoftFailTests(ClaimAndDriversAPITestCase):
    def test_create_driver_survives_audit_failure(self):
        self._auth(self.dispatch)
        with patch(
            'utils.audit_events.log_simple_action',
            side_effect=RuntimeError('audit down'),
        ):
            res = self.client.post(
                '/api/dispatch/drivers/',
                {'display_name': 'Audit Soft', 'phone': '0712555666'},
                format='json',
            )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

    def test_pack_survives_audit_failure(self):
        order = FieldOrder.objects.create(
            site=self.site,
            customer=self.customer,
            created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order,
            product=self.product,
            quantity=Decimal('1'),
            unit_price=Decimal('50'),
            product_name='Tiles',
        )
        submit_order(order)
        self._auth(self.dispatch)
        with patch(
            'utils.audit_events.log_simple_action',
            side_effect=RuntimeError('audit down'),
        ):
            packed = self.client.post(f'/api/dispatch/field-orders/{order.id}/pack/')
        self.assertEqual(packed.status_code, status.HTTP_200_OK, packed.data)

    def test_assign_survives_audit_failure(self):
        order = self._ready_unassigned()
        self._auth(self.dispatch)
        with patch(
            'utils.audit_events.log_simple_action',
            side_effect=RuntimeError('audit down'),
        ):
            assigned = self.client.post(
                f'/api/dispatch/field-orders/{order.id}/assign/',
                {'delivery_agent_id': self.driver.id},
                format='json',
            )
        self.assertEqual(assigned.status_code, status.HTTP_200_OK, assigned.data)
