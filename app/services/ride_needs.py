"""What a passenger needs on a ride, and what the driver undertakes to do.

**Needs, never diagnoses.** Every entry below is something the driver does.
None of them is a condition anybody has, and the system deliberately cannot
tell why any of them was chosen: somebody tall, somebody who gets carsick and
somebody with a mobility impairment all select the same thing, and it is not
the platform's business which. Law No. 2024/017 prohibits processing health
data, and this is what compliance looks like in practice rather than in a
policy document (I9).

The vocabulary is served to the client with its wording, the same way vehicle
capabilities are, so a phrasing correction is a server change rather than an
app release.

Two of these change what the driver *says* rather than what the car *is*, and
they are the reason `driver_undertakings` exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RideNeed(StrEnum):
    """Stated by the passenger, carried on the ride, shown to the driver."""

    EXTRA_LEGROOM = "extra_legroom"
    CLIMATE_ADJUSTED = "climate_adjusted"
    WINDOWS_CLOSED = "windows_closed"
    SPOKEN_ITINERARY = "spoken_itinerary"
    GUIDED_TOUR = "guided_tour"
    QUIET_RIDE = "quiet_ride"
    OTHER = "other"


@dataclass(frozen=True)
class NeedInfo:
    key: RideNeed
    label_fr: str
    label_en: str
    # What the driver is actually asked to do. Written as an instruction
    # because that is how it appears on their screen.
    driver_action_fr: str
    driver_action_en: str
    # Whether it needs a vehicle with a matching capability, or only a driver
    # willing to do something. The distinction decides whether it shrinks the
    # pool of cars or not.
    vehicle_capability: str | None = None


NEEDS: list[NeedInfo] = [
    NeedInfo(
        key=RideNeed.EXTRA_LEGROOM,
        label_fr="Plus d'espace pour les jambes",
        label_en="More legroom",
        driver_action_fr=(
            "Avancez votre siege avant l'arrivee pour liberer de la place."
        ),
        driver_action_en=(
            "Move your seat forward before you arrive to free up space."
        ),
        vehicle_capability="extra_legroom",
    ),
    NeedInfo(
        key=RideNeed.CLIMATE_ADJUSTED,
        label_fr="Climatisation adaptee",
        label_en="Climate adjusted",
        driver_action_fr=(
            "Demandez la temperature souhaitee au depart, puis ajustez."
        ),
        driver_action_en="Ask what temperature suits them, then set it.",
    ),
    NeedInfo(
        key=RideNeed.WINDOWS_CLOSED,
        label_fr="Vitres fermees",
        label_en="Windows kept closed",
        driver_action_fr="Gardez les vitres fermees pendant tout le trajet.",
        driver_action_en="Keep the windows closed for the whole trip.",
    ),
    NeedInfo(
        key=RideNeed.SPOKEN_ITINERARY,
        label_fr="Itineraire annonce a voix haute",
        label_en="Spoken itinerary",
        # The reason this runs on the driver's phone rather than the
        # passenger's: a passenger who cannot see the route has no way to tell
        # a shortcut from a wrong turn unless somebody says it out loud, in
        # the car, as it happens.
        driver_action_fr=(
            "Votre telephone annonce chaque etape a voix haute. Signalez tout "
            "changement de route avant de le prendre."
        ),
        driver_action_en=(
            "Your phone announces each step aloud. Say any change of route "
            "before you take it."
        ),
    ),
    NeedInfo(
        key=RideNeed.GUIDED_TOUR,
        label_fr="Visite guidee",
        label_en="Guided tour",
        driver_action_fr=(
            "Presentez les lieux traverses. Utile pour un visiteur; cela "
            "compte dans votre note."
        ),
        driver_action_en=(
            "Talk about the places you pass. Useful to a visitor, and it "
            "counts toward your rating."
        ),
    ),
    NeedInfo(
        key=RideNeed.QUIET_RIDE,
        label_fr="Trajet silencieux",
        label_en="Quiet ride",
        driver_action_fr=(
            "Limitez la conversation a l'essentiel: la prise en charge et "
            "l'arrivee."
        ),
        driver_action_en=(
            "Keep conversation to the essentials: the pickup and the arrival."
        ),
    ),
    NeedInfo(
        key=RideNeed.OTHER,
        label_fr="Autre chose",
        label_en="Something else",
        driver_action_fr="Lisez la note du passager.",
        driver_action_en="Read the passenger's note.",
    ),
]

# Needs that require the driver to have signed the undertakings, because they
# are things a driver does rather than things a car has. Without the signature
# a passenger would be relying on behaviour nobody agreed to.
NEEDS_REQUIRING_UNDERTAKING = frozenset(
    {
        RideNeed.SPOKEN_ITINERARY,
        RideNeed.GUIDED_TOUR,
        RideNeed.QUIET_RIDE,
        RideNeed.CLIMATE_ADJUSTED,
        RideNeed.WINDOWS_CLOSED,
    }
)

# Bumped whenever the wording changes materially, so a driver who agreed to an
# older text is asked again rather than silently held to a new one.
UNDERTAKINGS_VERSION = "2026-09-1"

UNDERTAKINGS_FR = [
    "J'accepte les demandes du passager avec politesse et sans commentaire.",
    "Je ne facture aucun supplement pour ces demandes.",
    "Si je ne peux pas repondre a une demande, je refuse la course plutot que "
    "de l'accepter sans la respecter.",
    "J'annonce tout changement d'itineraire avant de le prendre.",
]

UNDERTAKINGS_EN = [
    "I will meet the passenger's requests politely and without comment.",
    "I will not charge anything extra for them.",
    "If I cannot meet a request, I will decline the ride rather than accept "
    "it and not honour it.",
    "I will say any change of route before I take it.",
]


def capability_for(need: str) -> str | None:
    """The vehicle capability a need implies, if any.

    Most needs imply none: keeping the windows closed is a thing a driver
    does, not a property of the car, and treating it as a capability would
    shrink the pool of vehicles for no reason.
    """
    for info in NEEDS:
        if info.key.value == need:
            return info.vehicle_capability
    return None


def requires_undertaking(needs: list[str]) -> bool:
    """Whether these needs may only be offered to a driver who has signed."""
    return any(n in NEEDS_REQUIRING_UNDERTAKING for n in needs)


def driver_instructions(needs: list[str], locale: str = "fr") -> list[str]:
    """What to show the driver, in their language.

    Instructions rather than labels. A driver reading "more legroom" has to
    work out what to do; a driver reading "move your seat forward before you
    arrive" already knows.
    """
    wanted = set(needs)
    return [
        info.driver_action_en if locale == "en" else info.driver_action_fr
        for info in NEEDS
        if info.key.value in wanted
    ]
