"""SMS delivery, behind an interface.

One interface, one implementation today. The interface is not speculative
abstraction: it is the seam that lets a real gateway drop in during Phase 7
without touching the auth service, and it is what makes the console sender
safe to ship in the repository.

The console sender logs the code. That is fine in development and would be a
full account-takeover primitive in production, so `ConsoleSmsSender` refuses to
start when APP_ENV is production rather than trusting a config flag to have
been set correctly. A guard that fails loudly at boot beats a comment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import settings
from app.logging import get_logger
from app.security.phone import hash_phone

logger = get_logger("vora.sms")


class SmsSender(ABC):
    @abstractmethod
    async def send_otp(self, phone_e164: str, code: str) -> None: ...


class ConsoleSmsSender(SmsSender):
    """Logs the OTP so development and the mobile team can proceed without a
    gateway, a handset, or an SMS budget."""

    def __init__(self) -> None:
        if settings.is_production:
            raise RuntimeError(
                "ConsoleSmsSender logs OTP codes in plaintext and must never "
                "run in production. Configure a real SmsSender."
            )

    async def send_otp(self, phone_e164: str, code: str) -> None:
        # The number is hashed even here. Development logs get pasted into
        # issues and chat, and a habit of printing real numbers survives into
        # production far more often than anyone intends.
        logger.info(
            "otp_console_delivery",
            phone=hash_phone(phone_e164),
            code=code,
            note="development only",
        )


class NullSmsSender(SmsSender):
    """Accepts and discards. Used by tests that assert on rate limiting rather
    than on delivery."""

    async def send_otp(self, phone_e164: str, code: str) -> None:
        return None


_sender: SmsSender | None = None


def get_sms_sender() -> SmsSender:
    global _sender
    if _sender is None:
        _sender = ConsoleSmsSender()
    return _sender


def set_sms_sender(sender: SmsSender) -> None:
    """Injection point for tests and for wiring a real gateway at startup."""
    global _sender
    _sender = sender
