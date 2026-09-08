"""Real SMS delivery through HTTPSMS.

HTTPSMS turns an ordinary Android handset into the gateway: the phone holds a
SIM, the app polls for queued messages, and the handset sends them. No telco
contract, no sender-ID approval, no per-message billing beyond the SIM's own
tariff.

That matters here for a reason beyond convenience. Every commercial gateway
wants a registered business and a sender ID approved by the operator, which is
a procurement exercise. A team that can put a SIM in a phone can send OTPs
today, which is the same constraint a small operator in Yaounde faces.

**What this costs, said plainly.** Throughput is one handset, so this is a
pilot mechanism and not a national rollout. If the phone is off, flat, or out
of credit, delivery stops. That is why `send_otp` raising is important: the
auth service treats a failed send as a failed OTP request rather than
pretending a code was delivered, so a passenger sees an error instead of
waiting for a message that is never coming.

Credentials come from the environment and are never logged. The API key is a
bearer credential for an account that can send SMS from a real number.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.logging import get_logger
from app.security.phone import hash_phone
from app.services.sms import SmsSender

logger = get_logger("vora.sms.httpsms")

API_URL = "https://api.httpsms.com/v1/messages/send"

# Short. An OTP that arrives after the passenger has given up is worse than a
# clean failure, and the request itself is bounded by the API's own timeout.
TIMEOUT_S = 12.0


class HttpSmsSender(SmsSender):
    """Sends through an Android handset running the HTTPSMS app."""

    def __init__(self) -> None:
        key = settings.httpsms_api_key
        sender = settings.httpsms_from_number

        if not key or not sender:
            raise RuntimeError(
                "HttpSmsSender needs HTTPSMS_API_KEY and HTTPSMS_FROM_NUMBER. "
                "Without both, configure the console sender instead of "
                "silently failing to deliver."
            )

        self._key = key.get_secret_value()
        self._from = sender

    async def send_otp(self, phone_e164: str, code: str) -> None:
        # The message is deliberately dull. A recipient who has not requested a
        # code should be able to tell instantly that they are being phished,
        # and a template full of urgency makes that harder rather than easier.
        content = (
            f"VORA: votre code de verification est {code}. "
            f"Il expire dans 5 minutes. Ne le partagez avec personne."
        )

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                response = await client.post(
                    API_URL,
                    headers={"x-api-key": self._key},
                    json={
                        "from": self._from,
                        "to": phone_e164,
                        "content": content,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            # The number is hashed and the body is never included. A provider's
            # error response routinely echoes the request, which here would put
            # both a real phone number and the OTP into the logs.
            logger.warning(
                "sms_delivery_failed",
                to=hash_phone(phone_e164),
                error=type(exc).__name__,
            )
            # Raised, not swallowed. The caller must not tell a passenger a
            # code is on its way when it is not.
            raise

        logger.info("sms_delivered", to=hash_phone(phone_e164), via="httpsms")
