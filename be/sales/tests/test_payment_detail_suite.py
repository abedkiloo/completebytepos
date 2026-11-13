"""
Payment detail suite: unit, integration, module gate, and stress tests.

Covers GET wallet settlement detail, pay-later labeling, till/bank fields,
and receipt-aware settlement payloads used by the payment detail dialog.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image
from rest_framework import status

from sales.customer_detail import serialize_ledger_entry
from sales.models import Customer, CustomerWalletTransaction
from sales.payments_trail import get_wallet_settlement_detail
from sales.sale_payment_method import (
    normalize_sale_payment_method,
    sale_payment_method_label,
)
from sales.sale_payment_receipt import require_sale_payment_receipt_image
from sales.services import CustomerService
from utils.tests.api_test_base import ManagerAPITestCase


def _jpeg_bytes(color=(20, 120, 80)) -> bytes:
    buf = BytesIO()
    Image.new('RGB', (32, 32), color=color).save(buf, format='JPEG')
    return buf.getvalue()


class PaymentDetailUnitTests(SimpleTestCase):
    """Pure unit checks — no database."""

    def test_normalize_pay_later_never_stays_cash(self):
        self.assertEqual(
            normalize_sale_payment_method(
                payment_method='cash',
                amount_paid=0,
                allow_partial=True,
            ),
            'on_account',
        )

    def test_sale_label_pay_later_and_mpesa_destination(self):
        self.assertEqual(
            sale_payment_method_label('cash', amount_paid=0, total=250),
            'Debt',
        )
        self.assertEqual(
            sale_payment_method_label(
                'mpesa',
                amount_paid=100,
                total=100,
                mpesa_destination='bank',
            ),
            'M-Pesa · Bank',
        )

    def test_require_receipt_for_mpesa_collection(self):
        with self.assertRaises(Exception):
            require_sale_payment_receipt_image(
                None,
                payment_method='mpesa',
                amount_paid=Decimal('50.00'),
            )
        require_sale_payment_receipt_image(
            None,
            payment_method='on_account',
            amount_paid=Decimal('0'),
        )


class PaymentDetailCorrectedFunctionalityTests(SimpleTestCase):
    """Corrected-functionality regressions for the payment UX fixes."""

    def test_pay_later_never_listed_as_cash(self):
        self.assertEqual(
            normalize_sale_payment_method(
                payment_method='cash',
                amount_paid=0,
                allow_partial=True,
            ),
            'on_account',
        )
        self.assertEqual(
            sale_payment_method_label('cash', amount_paid=0, total=99),
            'Debt',
        )
        self.assertEqual(
            sale_payment_method_label(
                'on_account',
                amount_paid=99,
                total=99,
            ),
            'Debt repaid',
        )
        self.assertNotEqual(
            sale_payment_method_label('on_account', amount_paid=0, total=99),
            'Cash',
        )

    def test_till_and_bank_appear_in_detail_labels(self):
        self.assertEqual(
            sale_payment_method_label(
                'mpesa',
                amount_paid=1,
                total=1,
                mpesa_destination='till',
            ),
            'M-Pesa · Till',
        )
        self.assertEqual(
            sale_payment_method_label(
                'mpesa',
                amount_paid=1,
                total=1,
                mpesa_destination='bank',
            ),
            'M-Pesa · Bank',
        )


class PaymentDetailStressUnitTests(SimpleTestCase):
    """Stress pure helpers with many iterations / threads."""

    def test_label_stress_batch(self):
        for i in range(2000):
            unpaid = sale_payment_method_label(
                'cash',
                amount_paid=0,
                total=100 + (i % 50),
            )
            self.assertEqual(unpaid, 'Debt')
            dest = 'till' if i % 2 == 0 else 'bank'
            labeled = sale_payment_method_label(
                'mpesa',
                amount_paid=10,
                total=10,
                mpesa_destination=dest,
            )
            self.assertIn(dest.title(), labeled)

    def test_concurrent_normalize_calls(self):
        def work(i: int) -> str:
            return normalize_sale_payment_method(
                payment_method='cash' if i % 3 else 'mpesa',
                amount_paid=0 if i % 2 == 0 else Decimal('5'),
                allow_partial=True,
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(400)]
            results = [f.result() for f in as_completed(futures)]
        self.assertEqual(len(results), 400)
        self.assertTrue(all(r in ('on_account', 'cash', 'mpesa') for r in results))


class PaymentDetailIntegrationTests(ManagerAPITestCase):
    """API integration: create settlement → open detail → ledger fields."""

    def setUp(self):
        super().setUp()
        self._media_tmpdir = TemporaryDirectory()
        self._media_override = override_settings(
            MEDIA_ROOT=self._media_tmpdir.name,
        )
        self._media_override.enable()
        self.addCleanup(self._media_override.disable)
        self.addCleanup(self._media_tmpdir.cleanup)
        Path(self._media_tmpdir.name).mkdir(parents=True, exist_ok=True)
        self.customer = Customer.objects.create(
            name='Detail Customer',
            phone='0711000001',
            wallet_balance=Decimal('-500.00'),
            is_active=True,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('500.00'),
            balance_after=Decimal('-500.00'),
            created_by=self.manager_user,
        )

    @patch(
        'sales.customer_module_settings.customers_collection_payer_details_enabled',
        return_value=True,
    )
    def test_receive_then_get_settlement_detail(self, _payer_on):
        receipt = SimpleUploadedFile(
            'pay.jpg',
            _jpeg_bytes(),
            content_type='image/jpeg',
        )
        create = self.client.post(
            f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
            {
                'amount': '120.00',
                'payment_method': 'mpesa',
                'reference': 'QHXDETAIL01',
                'payer_name': 'Detail Payer',
                'payer_phone': '0700999888',
                'mpesa_destination': 'till',
                'receipt_image': receipt,
            },
            format='multipart',
        )
        self.assertIn(
            create.status_code,
            (status.HTTP_200_OK, status.HTTP_201_CREATED),
            create.data,
        )
        txn_id = create.data['transaction']['id']

        detail = self.client.get(
            f'/api/sales/customers/wallet-settlements/{txn_id}/',
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.data)
        self.assertEqual(detail.data['kind'], 'debt_settlement')
        self.assertEqual(detail.data['payer_name'], 'Detail Payer')
        self.assertEqual(detail.data['mpesa_destination'], 'till')
        self.assertEqual(detail.data['reference'], 'QHXDETAIL01')
        self.assertTrue(detail.data.get('receipt_image_url'))
        self.assertIn('paid_towards', detail.data)

        helper = get_wallet_settlement_detail(txn_id, user=self.manager_user)
        self.assertEqual(helper['id'], txn_id)
        self.assertEqual(helper['mpesa_destination_label'], 'Till')

    def test_ledger_entry_includes_payer_and_till(self):
        txn = CustomerService().record_wallet_payment(
            self.customer,
            Decimal('30.00'),
            payment_method='mpesa',
            reference='QHXLEDGER01',
            user=self.manager_user,
            payer_name='Ledger Payer',
            payer_phone='0700555444',
            mpesa_destination='bank',
        )
        row = serialize_ledger_entry(txn)
        self.assertEqual(row['kind'], 'debt_settlement')
        self.assertEqual(row['payer_name'], 'Ledger Payer')
        self.assertEqual(row['mpesa_destination'], 'bank')
        self.assertEqual(row['mpesa_destination_label'], 'Bank')
        self.assertTrue(row.get('received_by') or row.get('created_by_name'))

    def test_settlement_detail_404_for_missing(self):
        res = self.client.get('/api/sales/customers/wallet-settlements/999999/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_settlement_detail_rejects_non_settlement(self):
        debt_row = CustomerWalletTransaction.objects.filter(
            customer=self.customer,
            source_type='debt',
        ).first()
        res = self.client.get(
            f'/api/sales/customers/wallet-settlements/{debt_row.id}/',
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class PaymentDetailModuleGateTests(ManagerAPITestCase):
    """Module packaging: wallet feature off blocks settlement detail."""

    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Module Gate Customer',
            phone='0711000002',
            wallet_balance=Decimal('-50.00'),
            is_active=True,
        )
        self.txn = CustomerService().record_wallet_payment(
            self.customer,
            Decimal('10.00'),
            payment_method='cash',
            user=self.manager_user,
        )

    @patch(
        'sales.customer_module_settings.customers_show_wallet_balance',
        return_value=False,
    )
    def test_detail_disabled_when_wallet_module_off(self, _off):
        res = self.client.get(
            f'/api/sales/customers/wallet-settlements/{self.txn.id}/',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_open_detail(self):
        self.client.credentials()
        res = self.client.get(
            f'/api/sales/customers/wallet-settlements/{self.txn.id}/',
        )
        self.assertIn(
            res.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            getattr(res, 'data', res.content),
        )


class PaymentDetailApiStressTests(ManagerAPITestCase):
    """Stress: many settlements + concurrent detail GETs."""

    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Stress Customer',
            phone='0711000003',
            wallet_balance=Decimal('-5000.00'),
            is_active=True,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('5000.00'),
            balance_after=Decimal('-5000.00'),
            created_by=self.manager_user,
        )
        self.txn_ids = []
        for i in range(40):
            txn = CustomerService().record_wallet_payment(
                self.customer,
                Decimal('5.00'),
                payment_method='mpesa' if i % 2 == 0 else 'cash',
                reference=f'QHXSTRESS{i:03d}A1' if i % 2 == 0 else f'CASH{i}',
                user=self.manager_user,
                payer_name=f'Payer {i}' if i % 2 == 0 else '',
                payer_phone='0700111222' if i % 2 == 0 else '',
                mpesa_destination='till' if i % 2 == 0 else '',
            )
            self.txn_ids.append(txn.id)

    def test_sequential_detail_reads(self):
        for txn_id in self.txn_ids:
            res = self.client.get(
                f'/api/sales/customers/wallet-settlements/{txn_id}/',
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
            self.assertEqual(res.data['id'], txn_id)
            self.assertEqual(res.data['kind'], 'debt_settlement')

    def test_burst_detail_reads(self):
        """Stress: many sequential detail reads (SQLite-safe; concurrent unit stress covers threads)."""
        seen = []
        for _ in range(5):
            for txn_id in self.txn_ids:
                row = get_wallet_settlement_detail(txn_id, user=self.manager_user)
                self.assertEqual(row['id'], txn_id)
                self.assertEqual(row['kind'], 'debt_settlement')
                seen.append(txn_id)
        self.assertEqual(len(seen), 5 * len(self.txn_ids))
