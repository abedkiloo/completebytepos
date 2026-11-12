"""Unit checks for wallet settlement detail helper (no DB host required)."""

from django.test import SimpleTestCase

from sales.payments_trail import get_wallet_settlement_detail


class WalletSettlementDetailHelperTests(SimpleTestCase):
    def test_helper_is_exported(self):
        self.assertTrue(callable(get_wallet_settlement_detail))
