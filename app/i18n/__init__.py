"""Message resolution.

French is the default per §6. English is served when Accept-Language asks for
it. Unknown codes fall back to a generic string rather than leaking an
internal detail into a user-facing message.
"""

from __future__ import annotations

from app.errors.codes import ErrorCode
from app.i18n.en import MESSAGES as EN
from app.i18n.fr import MESSAGES as FR

_CATALOGUES: dict[str, dict[ErrorCode, str]] = {"fr": FR, "en": EN}
DEFAULT_LANG = "fr"


def negotiate_language(accept_language: str | None) -> str:
    """Pick a supported language from an Accept-Language header.

    Deliberately simple: the header is untrusted input and a full RFC 4647
    matcher is not worth the parsing surface here.
    """
    if not accept_language:
        return DEFAULT_LANG
    for part in accept_language.split(","):
        tag = part.split(";")[0].strip().lower()
        if not tag:
            continue
        primary = tag.split("-")[0]
        if primary in _CATALOGUES:
            return primary
    return DEFAULT_LANG


def message_for(code: ErrorCode, lang: str = DEFAULT_LANG) -> str:
    catalogue = _CATALOGUES.get(lang, FR)
    return catalogue.get(code) or FR.get(code) or "Une erreur est survenue."
