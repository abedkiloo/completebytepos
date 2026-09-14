"""Daraja STK client — secrets stay server-side. Fake client for sandbox tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class StkInitiateResult:
    checkout_request_id: str
    merchant_request_id: str
    response_code: str = '0'
    customer_message: str = 'Success. Request accepted for processing'


@dataclass
class StkQueryResult:
    result_code: str
    result_desc: str
    mpesa_receipt: str = ''


class DarajaClient(Protocol):
    def initiate_stk(
        self,
        *,
        phone: str,
        amount: str,
        account_reference: str,
        transaction_desc: str,
    ) -> StkInitiateResult: ...

    def query_stk(self, checkout_request_id: str) -> StkQueryResult: ...


@dataclass
class FakeDarajaClient:
    """
    Sandbox stand-in: initiate always accepts; query/callback driven by
    ``force_result`` map keyed by checkout_request_id.
    """

    auto_succeed: bool = True
    force_result: dict[str, StkQueryResult] = field(default_factory=dict)
    initiated: list[dict] = field(default_factory=list)

    def initiate_stk(
        self,
        *,
        phone: str,
        amount: str,
        account_reference: str,
        transaction_desc: str,
    ) -> StkInitiateResult:
        checkout = f'ws_CO_{uuid.uuid4().hex[:12]}'
        merchant = f'ws_MR_{uuid.uuid4().hex[:12]}'
        self.initiated.append({
            'phone': phone,
            'amount': amount,
            'checkout_request_id': checkout,
            'merchant_request_id': merchant,
            'account_reference': account_reference,
        })
        if self.auto_succeed:
            self.force_result[checkout] = StkQueryResult(
                result_code='0',
                result_desc='The service request is processed successfully.',
                mpesa_receipt=f'SFH{uuid.uuid4().hex[:8].upper()}',
            )
        return StkInitiateResult(
            checkout_request_id=checkout,
            merchant_request_id=merchant,
        )

    def query_stk(self, checkout_request_id: str) -> StkQueryResult:
        if checkout_request_id in self.force_result:
            return self.force_result[checkout_request_id]
        return StkQueryResult(
            result_code='4999',
            result_desc='The transaction is being processed',
        )

    def mark_failed(self, checkout_request_id: str, desc: str = 'Failed') -> None:
        self.force_result[checkout_request_id] = StkQueryResult(
            result_code='1032',
            result_desc=desc,
        )


_client: DarajaClient | None = None


def get_daraja_client() -> DarajaClient:
    global _client
    if _client is None:
        _client = FakeDarajaClient()
    return _client


def set_daraja_client(client: DarajaClient | None) -> None:
    global _client
    _client = client
