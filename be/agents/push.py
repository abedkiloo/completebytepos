"""Push notification stub — real FCM/APNs deferred to BACKLOG."""


class PushNotifier:
    """Interface for order/dispatch lifecycle alerts."""

    def notify(self, *, user_id: int | None, title: str, body: str, data: dict | None = None) -> bool:
        raise NotImplementedError


class FakePushNotifier(PushNotifier):
    """In-memory recorder for tests and environments without a provider."""

    def __init__(self):
        self.sent: list[dict] = []

    def notify(self, *, user_id: int | None, title: str, body: str, data: dict | None = None) -> bool:
        self.sent.append({
            'user_id': user_id,
            'title': title,
            'body': body,
            'data': data or {},
        })
        return True


class NoOpPushNotifier(PushNotifier):
    def notify(self, *, user_id: int | None, title: str, body: str, data: dict | None = None) -> bool:
        return False


_default_notifier: PushNotifier = NoOpPushNotifier()


def get_push_notifier() -> PushNotifier:
    return _default_notifier


def set_push_notifier(notifier: PushNotifier) -> None:
    global _default_notifier
    _default_notifier = notifier
