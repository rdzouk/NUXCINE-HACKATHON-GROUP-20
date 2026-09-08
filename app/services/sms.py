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


class RoutingSmsSender(SmsSender):
    """Real SMS to real handsets, console for the reserved test numbers.

    Turning on a real gateway must not lock the seeded accounts out. A test
    number has no handset behind it, so sending it an SMS delivers nothing and
    the code becomes unreadable: the demo passengers and the entire seeded
    fleet stop being able to log in the moment credentials are configured.

    Routing on the number rather than on an environment flag keeps both true at
    once. A real phone gets a real message; +23760000000xxxx keeps logging to
    the console, where the dev endpoint can read it back.

    The split is the same one `normalise_phone` already makes, so there is one
    definition of "test number" rather than two that can drift.
    """

    def __init__(self, real: SmsSender, console: ConsoleSmsSender) -> None:
        self._real = real
        self._console = console

    def _is_test_number(self, phone_e164: str) -> bool:
        prefix = settings.test_number_prefix
        return bool(
            settings.allow_test_numbers
            and prefix
            and phone_e164.startswith(prefix)
        )

    async def send_otp(self, phone_e164: str, code: str) -> None:
        if self._is_test_number(phone_e164):
            await self._console.send_otp(phone_e164, code)
            return
        await self._real.send_otp(phone_e164, code)

    def peek(self, phone_e164: str) -> str | None:
        """Read back a console-delivered code, for the dev endpoint."""
        return self._console.peek(phone_e164)


def get_sms_sender() -> SmsSender:
    """The active sender.

    Real delivery when credentials are configured, the console otherwise, and
    both at once when a real gateway is wired: see RoutingSmsSender.

    Chosen by whether the credentials exist rather than by an environment flag,
    because a flag can say "production" while the credentials are absent, and
    the failure mode there is an app that believes it sent an SMS.
    """
    global _sender

    if _sender is None:
        if settings.httpsms_api_key and settings.httpsms_from_number:
            from app.services.sms_httpsms import HttpSmsSender

            _sender = RoutingSmsSender(HttpSmsSender(), ConsoleSmsSender())
            logger.info(
                "sms_sender_selected",
                sender="httpsms",
                note="test numbers still log to the console",
            )
        else:
            _sender = ConsoleSmsSender()
            logger.info(
                "sms_sender_selected",
                sender="console",
                note="no HTTPSMS credentials; codes are logged, not sent",
            )

    return _sender


def set_sms_sender(sender: SmsSender) -> None:
    """Injection point for tests and for wiring a real gateway at startup."""
    global _sender
    _sender = sender
