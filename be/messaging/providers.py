"""SMS provider adapter — Fake for tests; AfricasTalking stub for production wiring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


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
class AfricasTalkingSmsProvider:
    """
    Production adapter skeleton — requires AFRICASTALKING_* settings.
    Not called in unit tests; FakeSmsProvider is the default.
    """

    api_key: str
    username: str
    name: str = 'africastalking'

    def send(self, *, to: str, body: str) -> SmsSendResult:
        # Real HTTP call deferred — secrets must be present; raise if misconfigured.
        if not self.api_key or not self.username:
            return SmsSendResult(ok=False, error='Africa\'s Talking not configured')
        return SmsSendResult(ok=False, error='Live AT send not enabled in this build')


_provider: SmsProvider | None = None


def get_sms_provider() -> SmsProvider:
    global _provider
    if _provider is None:
        _provider = FakeSmsProvider()
    return _provider


def set_sms_provider(provider: SmsProvider | None) -> None:
    global _provider
    _provider = provider
