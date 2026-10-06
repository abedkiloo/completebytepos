"""SMS provider adapters — Fake (tests), Mobile Sasa (live), Africa's Talking stub."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol, Sequence

from django.conf import settings

logger = logging.getLogger(__name__)

MOBILESASA_SEND_URL = 'https://api.mobilesasa.com/v1/send/message'
MOBILESASA_BULK_URL = 'https://api.mobilesasa.com/v1/send/bulk'
MOBILESASA_BULK_PERSONALIZED_URL = 'https://api.mobilesasa.com/v1/send/bulk-personalized'
BULK_CHUNK_SIZE = 500


@dataclass
class SmsSendResult:
    ok: bool
    provider_ref: str = ''
    error: str = ''


@dataclass
class SmsBulkResult:
    ok: bool
    provider_ref: str = ''
    error: str = ''
    accepted_count: int = 0


class SmsProvider(Protocol):
    name: str

    def send(self, *, to: str, body: str) -> SmsSendResult: ...

    def send_bulk_personalized(
        self, *, messages: Sequence[dict],
    ) -> SmsBulkResult: ...


@dataclass
class FakeSmsProvider:
    name: str = 'fake'
    sent: list[dict] = field(default_factory=list)
    bulk_sent: list[list[dict]] = field(default_factory=list)
    fail_next: bool = False
    fail_bulk_next: bool = False

    def send(self, *, to: str, body: str) -> SmsSendResult:
        if self.fail_next:
            self.fail_next = False
            return SmsSendResult(ok=False, error='Simulated SMS failure')
        ref = f'fake-{len(self.sent) + 1}'
        self.sent.append({'to': to, 'body': body, 'ref': ref})
        return SmsSendResult(ok=True, provider_ref=ref)

    def send_bulk_personalized(self, *, messages: Sequence[dict]) -> SmsBulkResult:
        rows = [dict(m) for m in messages if (m.get('phone') or '').strip()]
        if self.fail_bulk_next:
            self.fail_bulk_next = False
            return SmsBulkResult(ok=False, error='Simulated bulk SMS failure')
        ref = f'fake-bulk-{len(self.bulk_sent) + 1}'
        self.bulk_sent.append(rows)
        for row in rows:
            self.sent.append({
                'to': row.get('phone', ''),
                'body': row.get('message', ''),
                'ref': ref,
            })
        return SmsBulkResult(ok=True, provider_ref=ref, accepted_count=len(rows))


def _mobilesasa_post(url: str, token: str, payload: dict, timeout: float) -> tuple[dict | None, str]:
    data = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=data,
        method='POST',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode('utf-8', errors='replace')
            return (json.loads(raw) if raw else {}), ''
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', errors='replace')[:300]
        except Exception:
            detail = str(exc)
        logger.warning('Mobile Sasa HTTP %s: %s', exc.code, detail)
        return None, f'HTTP {exc.code}: {detail or exc.reason}'
    except Exception as exc:
        logger.warning('Mobile Sasa request failed: %s', exc)
        return None, str(exc)[:300]


@dataclass
class MobileSasaSmsProvider:
    """
    Live SMS via Mobile Sasa:
    - single: https://docs.mobilesasa.com/sms/send
    - bulk same text: https://docs.mobilesasa.com/sms/bulk
    - bulk personalized: https://docs.mobilesasa.com/sms/personalized
    """

    api_token: str
    sender_id: str
    name: str = 'mobilesasa'
    timeout_seconds: float = 30.0

    def send(self, *, to: str, body: str) -> SmsSendResult:
        token = (self.api_token or '').strip()
        sender = (self.sender_id or '').strip()
        phone = (to or '').strip()
        if not token:
            return SmsSendResult(ok=False, error='Mobile Sasa token not configured')
        if not sender:
            return SmsSendResult(ok=False, error='Mobile Sasa sender ID not configured')
        if not phone:
            return SmsSendResult(ok=False, error='Missing phone number')

        data, err = _mobilesasa_post(
            MOBILESASA_SEND_URL,
            token,
            {'senderID': sender, 'phone': phone, 'message': body},
            self.timeout_seconds,
        )
        if err:
            return SmsSendResult(ok=False, error=err)
        if data.get('status') is True or str(data.get('responseCode', '')) == '0200':
            ref = str(data.get('messageId') or data.get('message_id') or '')[:128]
            return SmsSendResult(ok=True, provider_ref=ref)
        message = str(data.get('message') or data.get('error') or 'Mobile Sasa rejected send')
        code = data.get('responseCode', '')
        return SmsSendResult(ok=False, error=f'{code} {message}'.strip()[:300])

    def send_bulk(self, *, phones: Sequence[str], body: str) -> SmsBulkResult:
        """Same message to many numbers — POST /v1/send/bulk."""
        token = (self.api_token or '').strip()
        sender = (self.sender_id or '').strip()
        cleaned = [str(p).strip() for p in phones if str(p or '').strip()]
        if not token:
            return SmsBulkResult(ok=False, error='Mobile Sasa token not configured')
        if not sender:
            return SmsBulkResult(ok=False, error='Mobile Sasa sender ID not configured')
        if not cleaned:
            return SmsBulkResult(ok=False, error='No phone numbers')
        if not (body or '').strip():
            return SmsBulkResult(ok=False, error='Empty message')

        refs: list[str] = []
        total = 0
        for i in range(0, len(cleaned), BULK_CHUNK_SIZE):
            chunk = cleaned[i:i + BULK_CHUNK_SIZE]
            data, err = _mobilesasa_post(
                MOBILESASA_BULK_URL,
                token,
                {
                    'senderID': sender,
                    'phones': ','.join(chunk),
                    'message': body,
                },
                self.timeout_seconds,
            )
            if err:
                return SmsBulkResult(
                    ok=False, error=err, provider_ref=','.join(refs)[:128],
                    accepted_count=total,
                )
            if not (data.get('status') is True or str(data.get('responseCode', '')) == '0200'):
                message = str(data.get('message') or data.get('error') or 'Bulk rejected')
                code = data.get('responseCode', '')
                return SmsBulkResult(
                    ok=False,
                    error=f'{code} {message}'.strip()[:300],
                    provider_ref=','.join(refs)[:128],
                    accepted_count=total,
                )
            refs.append(str(data.get('bulkId') or '')[:64])
            total += len(chunk)
        return SmsBulkResult(
            ok=True, provider_ref=','.join(r for r in refs if r)[:128], accepted_count=total,
        )

    def send_bulk_personalized(self, *, messages: Sequence[dict]) -> SmsBulkResult:
        """Different text per number — POST /v1/send/bulk-personalized."""
        token = (self.api_token or '').strip()
        sender = (self.sender_id or '').strip()
        rows = []
        for item in messages:
            phone = str(item.get('phone') or '').strip()
            message = str(item.get('message') or '').strip()
            if phone and message:
                rows.append({'phone': phone, 'message': message})
        if not token:
            return SmsBulkResult(ok=False, error='Mobile Sasa token not configured')
        if not sender:
            return SmsBulkResult(ok=False, error='Mobile Sasa sender ID not configured')
        if not rows:
            return SmsBulkResult(ok=False, error='No personalized messages')

        refs: list[str] = []
        total = 0
        for i in range(0, len(rows), BULK_CHUNK_SIZE):
            chunk = rows[i:i + BULK_CHUNK_SIZE]
            data, err = _mobilesasa_post(
                MOBILESASA_BULK_PERSONALIZED_URL,
                token,
                {'senderID': sender, 'messageBody': chunk},
                self.timeout_seconds,
            )
            if err:
                return SmsBulkResult(
                    ok=False, error=err, provider_ref=','.join(refs)[:128],
                    accepted_count=total,
                )
            if not (data.get('status') is True or str(data.get('responseCode', '')) == '0200'):
                message = str(data.get('message') or data.get('error') or 'Bulk rejected')
                code = data.get('responseCode', '')
                return SmsBulkResult(
                    ok=False,
                    error=f'{code} {message}'.strip()[:300],
                    provider_ref=','.join(refs)[:128],
                    accepted_count=total,
                )
            refs.append(str(data.get('bulkId') or '')[:64])
            total += len(chunk)
        return SmsBulkResult(
            ok=True, provider_ref=','.join(r for r in refs if r)[:128], accepted_count=total,
        )


@dataclass
class AfricasTalkingSmsProvider:
    """Legacy stub — prefer Mobile Sasa for production."""

    api_key: str
    username: str
    name: str = 'africastalking'

    def send(self, *, to: str, body: str) -> SmsSendResult:
        if not self.api_key or not self.username:
            return SmsSendResult(ok=False, error="Africa's Talking not configured")
        return SmsSendResult(ok=False, error='Live AT send not enabled; use Mobile Sasa')

    def send_bulk_personalized(self, *, messages: Sequence[dict]) -> SmsBulkResult:
        return SmsBulkResult(ok=False, error='Live AT send not enabled; use Mobile Sasa')


_provider: SmsProvider | None = None


def build_sms_provider_from_settings() -> SmsProvider:
    """Pick provider from Django settings (used when no test override is set)."""
    choice = (getattr(settings, 'SMS_PROVIDER', '') or '').strip().lower()
    mobilesasa_token = (getattr(settings, 'MOBILESASA_API_TOKEN', '') or '').strip()
    mobilesasa_sender = (getattr(settings, 'MOBILESASA_SENDER_ID', '') or '').strip()

    if choice in ('mobilesasa', 'mobile_sasa', 'ms') or (
        not choice and mobilesasa_token and mobilesasa_sender
    ):
        return MobileSasaSmsProvider(
            api_token=mobilesasa_token,
            sender_id=mobilesasa_sender,
        )

    if choice in ('africastalking', 'at'):
        return AfricasTalkingSmsProvider(
            api_key=getattr(settings, 'AFRICASTALKING_API_KEY', '') or '',
            username=getattr(settings, 'AFRICASTALKING_USERNAME', '') or '',
        )

    if choice in ('fake', 'test', 'none'):
        return FakeSmsProvider()

    return FakeSmsProvider()


def get_sms_provider() -> SmsProvider:
    global _provider
    if _provider is None:
        _provider = build_sms_provider_from_settings()
    return _provider


def set_sms_provider(provider: SmsProvider | None) -> None:
    global _provider
    _provider = provider
