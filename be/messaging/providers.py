"""SMS provider adapters — Fake (tests), Mobile Sasa (live), Africa's Talking stub."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from django.conf import settings

logger = logging.getLogger(__name__)

MOBILESASA_SEND_URL = 'https://api.mobilesasa.com/v1/send/message'


@dataclass
class SmsSendResult:
    ok: bool
    provider_ref: str = ''
    error: str = ''


class SmsProvider(Protocol):
    name: str

    def send(self, *, to: str, body: str) -> SmsSendResult: ...


@dataclass
class FakeSmsProvider:
    name: str = 'fake'
    sent: list[dict] = field(default_factory=list)
    fail_next: bool = False

    def send(self, *, to: str, body: str) -> SmsSendResult:
        if self.fail_next:
            self.fail_next = False
            return SmsSendResult(ok=False, error='Simulated SMS failure')
        ref = f'fake-{len(self.sent) + 1}'
        self.sent.append({'to': to, 'body': body, 'ref': ref})
        return SmsSendResult(ok=True, provider_ref=ref)


@dataclass
class MobileSasaSmsProvider:
    """
    Live SMS via Mobile Sasa: https://docs.mobilesasa.com/sms/send

    POST /v1/send/message with Bearer token (mbs_…) and senderID + phone + message.
    """

    api_token: str
    sender_id: str
    name: str = 'mobilesasa'
    timeout_seconds: float = 15.0

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

        payload = json.dumps({
            'senderID': sender,
            'phone': phone,
            'message': body,
        }).encode('utf-8')
        request = urllib.request.Request(
            MOBILESASA_SEND_URL,
            data=payload,
            method='POST',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode('utf-8', errors='replace')
                data = json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = ''
            try:
                detail = exc.read().decode('utf-8', errors='replace')[:300]
            except Exception:
                detail = str(exc)
            logger.warning('Mobile Sasa HTTP %s: %s', exc.code, detail)
            return SmsSendResult(ok=False, error=f'HTTP {exc.code}: {detail or exc.reason}')
        except Exception as exc:
            logger.warning('Mobile Sasa send failed: %s', exc)
            return SmsSendResult(ok=False, error=str(exc)[:300])

        if data.get('status') is True or str(data.get('responseCode', '')) == '0200':
            ref = str(data.get('messageId') or data.get('message_id') or '')[:128]
            return SmsSendResult(ok=True, provider_ref=ref)

        message = str(data.get('message') or data.get('error') or 'Mobile Sasa rejected send')
        code = data.get('responseCode', '')
        return SmsSendResult(ok=False, error=f'{code} {message}'.strip()[:300])


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

    # Dev/test default when nothing configured
    return FakeSmsProvider()


def get_sms_provider() -> SmsProvider:
    global _provider
    if _provider is None:
        _provider = build_sms_provider_from_settings()
    return _provider


def set_sms_provider(provider: SmsProvider | None) -> None:
    global _provider
    _provider = provider
