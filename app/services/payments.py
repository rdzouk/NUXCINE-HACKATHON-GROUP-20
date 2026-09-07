"""Payment providers, behind an interface.

**Cash on completion is the default, and that is a decision rather than a
limitation.** Most trips here are paid in cash, the driver has change, and
nobody needs an account balance to take a taxi. A build that made mobile money
mandatory would be describing a different country. It is worth saying that out
loud rather than apologising for it.

The interface exists so MTN MoMo and Orange Money can drop in without any
caller changing. Both are **stubs**: the build plan is explicit that real
sandbox credentials are a Phase 7 task only if we are ahead, and it names the
failure mode precisely, which is that sandbox onboarding silently blocks and
eats a day. Nothing here pretends otherwise, and `MockPaymentProvider` is what
the demo actually runs.

Three things every implementation must honour:

**Idempotency on `initiate`.** Mobile networks here drop and retry. A second
call with the same key returns the first transaction rather than charging
again. This is the same reasoning as I8 on ride creation, applied to money,
where the consequence of getting it wrong is worse.

**Never log a payload.** Not the phone number, not the token, not the provider
response. A payment log is the highest-value thing in an incident, and a
provider's error body routinely contains the credential that failed.

**Verify webhook signatures.** No webhook is wired today. If one ever is, an
unsigned callback endpoint is an open instruction to mark any transaction paid.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.logging import get_logger

logger = get_logger("vora.payments")


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    # The provider accepted the request but the payer has not yet approved it
    # on their handset. Distinct from pending because the client should be
    # telling the user to check their phone, not to wait.
    AWAITING_PAYER = "awaiting_payer"


class PaymentMethod(StrEnum):
    CASH = "cash"
    MTN_MOMO = "mtn_momo"
    ORANGE_MONEY = "orange_money"


@dataclass(frozen=True)
class PaymentResult:
    transaction_id: str
    status: PaymentStatus
    method: PaymentMethod
    amount_xaf: int
    # Safe to show a user and safe to put in a log. Never the provider's raw
    # body, which routinely carries the credential that failed.
    message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PaymentProvider(ABC):
    """Three methods. Any provider that satisfies them can be swapped in."""

    method: PaymentMethod

    @abstractmethod
    async def initiate(
        self, *, amount_xaf: int, payer_msisdn: str, idempotency_key: str
    ) -> PaymentResult: ...

    @abstractmethod
    async def status(self, transaction_id: str) -> PaymentResult: ...

    @abstractmethod
    async def refund(
        self, transaction_id: str, *, amount_xaf: int | None = None
    ) -> PaymentResult: ...


class CashProvider(PaymentProvider):
    """The default. Money changes hands in the car; the server records it.

    This is not a null implementation dressed up. Cash settlement is a real
    path with a real record: the fare is charged to the ledger at completion
    and cleared when the driver confirms collection, which is what makes the
    cancellation debt from Phase 5 enforceable without any payment rails.
    """

    method = PaymentMethod.CASH

    async def initiate(
        self, *, amount_xaf: int, payer_msisdn: str, idempotency_key: str
    ) -> PaymentResult:
        # Nothing to contact. The transaction is a record, not a request.
        return PaymentResult(
            transaction_id=f"cash_{uuid.uuid4().hex[:16]}",
            status=PaymentStatus.PENDING,
            method=self.method,
            amount_xaf=amount_xaf,
            message="A regler en especes a la fin de la course.",
        )

    async def status(self, transaction_id: str) -> PaymentResult:
        return PaymentResult(
            transaction_id=transaction_id,
            status=PaymentStatus.PENDING,
            method=self.method,
            amount_xaf=0,
            message="Reglement en especes.",
        )

    async def refund(
        self, transaction_id: str, *, amount_xaf: int | None = None
    ) -> PaymentResult:
        # A cash refund happens between two people. The system records that it
        # is owed; it cannot move the money.
        return PaymentResult(
            transaction_id=transaction_id,
            status=PaymentStatus.REFUNDED,
            method=self.method,
            amount_xaf=amount_xaf or 0,
            message="Remboursement a effectuer en especes.",
        )


class MockPaymentProvider(PaymentProvider):
    """Works end to end, in memory. What the demo runs.

    Deliberately succeeds immediately rather than simulating a delay: a demo
    that waits ten seconds for a fake confirmation spends its budget on
    theatre. The `awaiting_payer` state is still modelled in the enum so the
    client is built against the real shape.
    """

    method = PaymentMethod.MTN_MOMO

    def __init__(self) -> None:
        self._transactions: dict[str, PaymentResult] = {}
        # Idempotency key to transaction id. Same reasoning as I8: a retry on a
        # dropped connection must not charge twice.
        self._by_key: dict[str, str] = {}

    async def initiate(
        self, *, amount_xaf: int, payer_msisdn: str, idempotency_key: str
    ) -> PaymentResult:
        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            logger.info("payment_idempotent_replay", transaction_id=existing)
            return self._transactions[existing]

        transaction_id = f"mock_{uuid.uuid4().hex[:16]}"
        result = PaymentResult(
            transaction_id=transaction_id,
            status=PaymentStatus.SUCCEEDED,
            method=self.method,
            amount_xaf=amount_xaf,
            message="Paiement confirme.",
        )
        self._transactions[transaction_id] = result
        self._by_key[idempotency_key] = transaction_id

        # The amount and the id, never the payer's number and never a payload.
        logger.info(
            "payment_initiated",
            transaction_id=transaction_id,
            amount_xaf=amount_xaf,
            method=self.method.value,
        )
        return result

    async def status(self, transaction_id: str) -> PaymentResult:
        result = self._transactions.get(transaction_id)
        if result is None:
            return PaymentResult(
                transaction_id=transaction_id,
                status=PaymentStatus.FAILED,
                method=self.method,
                amount_xaf=0,
                message="Transaction inconnue.",
            )
        return result

    async def refund(
        self, transaction_id: str, *, amount_xaf: int | None = None
    ) -> PaymentResult:
        original = self._transactions.get(transaction_id)
        amount = amount_xaf if amount_xaf is not None else (
            original.amount_xaf if original else 0
        )
        result = PaymentResult(
            transaction_id=transaction_id,
            status=PaymentStatus.REFUNDED,
            method=self.method,
            amount_xaf=amount,
            message="Remboursement effectue.",
        )
        self._transactions[transaction_id] = result
        logger.info(
            "payment_refunded", transaction_id=transaction_id, amount_xaf=amount
        )
        return result


class _UnconfiguredProvider(PaymentProvider):
    """Shared behaviour for the two real providers, which are not wired.

    Raises rather than returning a plausible-looking failure. A stub that
    quietly answers "declined" is worse than one that refuses to run: the first
    looks like a payment problem and sends somebody debugging a provider that
    was never contacted.
    """

    provider_name = "unconfigured"

    async def initiate(
        self, *, amount_xaf: int, payer_msisdn: str, idempotency_key: str
    ) -> PaymentResult:
        raise NotImplementedError(
            f"{self.provider_name} is a stub. Sandbox credentials were not in "
            f"hand, and the build plan puts wiring them behind everything else. "
            f"Cash on completion is the default settlement path."
        )

    async def status(self, transaction_id: str) -> PaymentResult:
        raise NotImplementedError(f"{self.provider_name} is a stub.")

    async def refund(
        self, transaction_id: str, *, amount_xaf: int | None = None
    ) -> PaymentResult:
        raise NotImplementedError(f"{self.provider_name} is a stub.")


class MtnMoMoProvider(_UnconfiguredProvider):
    """MTN Mobile Money. Stub.

    Wiring this needs a sandbox subscription key, an API user and an API key,
    and the onboarding is the part that silently blocks. Verify credentials can
    actually be issued *before* budgeting time to integrate.
    """

    method = PaymentMethod.MTN_MOMO
    provider_name = "MTN MoMo"


class OrangeMoneyProvider(_UnconfiguredProvider):
    """Orange Money. Stub. Same reasoning as MTN MoMo."""

    method = PaymentMethod.ORANGE_MONEY
    provider_name = "Orange Money"


_provider: PaymentProvider | None = None


def get_payment_provider() -> PaymentProvider:
    """The active provider. Cash unless something else is configured."""
    global _provider
    if _provider is None:
        _provider = CashProvider()
    return _provider


def set_payment_provider(provider: PaymentProvider) -> None:
    """Injection point for tests and for wiring a real provider at startup."""
    global _provider
    _provider = provider
