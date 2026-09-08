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
from collections import OrderedDict

from app.config import settings
from app.logging import get_logger
from app.security.phone import hash_phone

logger = get_logger("vora.sms")


class SmsSender(ABC):
    @abstractmethod
    async def send_otp(self, phone_e164: str, code: str) -> None: ...


class ConsoleSmsSender(SmsSender):
    """Logs the OTP so development and the mobile team can proceed without a
    gateway, a handset, or an SMS budget.

    It also keeps the last few codes in memory, so the dev router can show one
    on screen. Reading a code out of `docker compose logs` works, but it means
    alt-tabbing to a terminal in the middle of the first thirty seconds of a
    demo, and the demo is the thing this is for.

    In memory only, never written anywhere, and only ever populated by a class
    that refuses to construct in production. The bound is small so a long
    session cannot accumulate codes.
    """

    # Small on purpose. This is a demo convenience, not a store.
    _RECENT_LIMIT = 20

    def __init__(self) -> None:
        if settings.is_production:
            raise RuntimeError(
                "ConsoleSmsSender logs OTP codes in plaintext and must never "
                "run in production. Configure a real SmsSender."
            )
        # Hashed phone to the most recent code sent to it.
        self._recent: OrderedDict[str, str] = OrderedDict()

    async def send_otp(self, phone_e164: str, code: str) -> None:
        # The number is hashed even here. Development logs get pasted into
        # issues and chat, and a habit of printing real numbers survives into
        # production far more often than anyone intends.
        hashed = hash_phone(phone_e164)

        self._recent[hashed] = code
        self._recent.move_to_end(hashed)
        while len(self._recent) > self._RECENT_LIMIT:
            self._recent.popitem(last=False)

        logger.info(
            "otp_console_delivery",
            phone=hashed,
            code=code,
            note="development only",
        )

    def peek(self, phone_e164: str) -> str | None:
        """The last code sent to this number, if it was sent by this process.

        Keyed by the hashed number, so a caller has to already know the number
        to ask. That is not a security boundary and is not claimed as one: the
        boundary is that the dev router does not exist outside development.
        """
        return self._recent.get(hash_phone(phone_e164))


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
