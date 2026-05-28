"""Format Django ValidationError instances for API responses."""

from django.core.exceptions import ValidationError


def validation_error_message(exc: BaseException) -> str:
    """Return a single human-readable string from a ValidationError."""
    if isinstance(exc, ValidationError):
        if hasattr(exc, 'message_dict') and exc.message_dict:
            parts = []
            for msgs in exc.message_dict.values():
                if isinstance(msgs, (list, tuple)):
                    parts.extend(str(m) for m in msgs)
                else:
                    parts.append(str(msgs))
            return '; '.join(parts)
        if hasattr(exc, 'messages'):
            return '; '.join(str(m) for m in exc.messages)
    return str(exc)
