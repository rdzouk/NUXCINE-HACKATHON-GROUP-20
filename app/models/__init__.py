"""Model package.

Importing every model here means Base.metadata is complete for anything that
inspects it, including Alembic's autogenerate comparison. A model that is only
imported by the module that uses it is invisible to that comparison, and the
generated migration then proposes dropping its table.
"""

from app.models.base import Base, TimestampMixin, UuidPkMixin
from app.models.user import (
    Driver,
    KycDocument,
    OtpChallenge,
    RefreshToken,
    User,
    Vehicle,
)

__all__ = [
    "Base",
    "Driver",
    "KycDocument",
    "OtpChallenge",
    "RefreshToken",
    "TimestampMixin",
    "User",
    "UuidPkMixin",
    "Vehicle",
]
