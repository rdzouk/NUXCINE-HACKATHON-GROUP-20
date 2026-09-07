"""Accessibility: vehicle capabilities and arrival announcements.

**Read this before touching anything here.**

Every value in this module describes a *vehicle*, never a person. A wheelchair
user is not recorded as a wheelchair user; a trip is recorded as requiring a
ramp. That distinction is not delicacy, it is the law: Cameroon's Law
No. 2024/017 prohibits processing health data outright, and "this passenger
uses a wheelchair" is health data while "this trip needs a vehicle with a ramp"
is a logistics requirement (I9).

It also happens to be the more respectful framing, and it is the one that
survives contact with reality: the same passenger may need a ramp today and not
tomorrow, may be booking for a relative, or may simply have a lot of luggage.
A requirement attached to the journey handles all three; a flag attached to the
person handles none of them.

Consequences that fall out of this, and that are load-bearing:

  - the matcher compares `ride.accessibility_required` against vehicle columns,
    and never reads anything about the passenger
  - the driver sees "this trip needs a ramp", never why
  - nothing here is ever inferred from behaviour, and nothing is derived; the
    passenger writes these values and nobody else does
  - face-match driver verification is ruled out by the same law, which is why
    the PIN exists instead

**Arrival announcements** are spoken strings, returned by the API rather than
built in the client. That serves three groups at once: low-vision users, users
who cannot read comfortably, and anybody whose hands are full. Returning them
server-side means the wording can be corrected without shipping an app release,
and it means the French is written once rather than in three clients.
"""

from __future__ import annotations

from app.schemas.common import VehicleCapability
from app.schemas.driver import VehicleCapabilityInfo
from app.schemas.ride import RideStatus

# The vocabulary, with the wording the client shows. Served rather than
# hardcoded in the app so a bad translation can be fixed without a release.
#
# The descriptions are deliberately phrased as facts about the car. "Vehicule
# equipe d'une rampe", not "pour personnes en fauteuil roulant".
CAPABILITIES: list[VehicleCapabilityInfo] = [
    VehicleCapabilityInfo(
        key=VehicleCapability.RAMP,
        label_fr="Rampe d'acces",
        label_en="Access ramp",
        description_fr="Vehicule equipe d'une rampe ou d'un plancher surbaisse.",
        description_en="Vehicle fitted with a ramp or a low floor.",
    ),
    VehicleCapabilityInfo(
        key=VehicleCapability.BOOT_SPACE,
        label_fr="Grand coffre",
        label_en="Large boot",
        description_fr=(
            "Coffre pouvant accueillir un fauteuil plie, une poussette ou "
            "des bagages volumineux."
        ),
        description_en=(
            "Boot large enough for a folded chair, a pushchair or bulky luggage."
        ),
    ),
    VehicleCapabilityInfo(
        key=VehicleCapability.FRONT_SEAT,
        label_fr="Place avant disponible",
        label_en="Front seat available",
        description_fr="La place passager avant est libre et accessible.",
        description_en="The front passenger seat is free and reachable.",
    ),
    VehicleCapabilityInfo(
        key=VehicleCapability.DRIVER_ASSIST,
        label_fr="Chauffeur pouvant aider",
        label_en="Driver can assist",
        description_fr=(
            "Le chauffeur peut aider a monter, descendre et ranger les affaires."
        ),
        description_en="The driver can help with boarding, alighting and bags.",
    ),
    VehicleCapabilityInfo(
        key=VehicleCapability.GUIDE_ANIMAL,
        label_fr="Animal d'assistance accepte",
        label_en="Assistance animal welcome",
        description_fr="Les animaux d'assistance sont acceptes a bord.",
        description_en="Assistance animals are welcome in this vehicle.",
    ),
]


# Spoken announcements, keyed by ride status.
#
# Written to be *heard*, not read: short, front-loaded with the thing that
# matters, and free of the abbreviations and punctuation that a text-to-speech
# engine mangles. "CE 404 XY" is spelled out by the client, not here.
ANNOUNCEMENTS_FR: dict[RideStatus, str] = {
    RideStatus.ACCEPTED: (
        "Un chauffeur a accepte votre course. {vehicle}, immatriculation {plate}."
    ),
    RideStatus.ARRIVING: (
        "Votre chauffeur approche. {vehicle} de couleur {color}."
    ),
    RideStatus.ARRIVED: (
        "Votre chauffeur est arrive. {vehicle} de couleur {color}, "
        "immatriculation {plate}. Votre code est {pin}."
    ),
    RideStatus.IN_PROGRESS: "Votre course a commence. Bon voyage.",
    RideStatus.COMPLETED: "Vous etes arrive. Le montant est de {fare} francs.",
}

ANNOUNCEMENTS_EN: dict[RideStatus, str] = {
    RideStatus.ACCEPTED: (
        "A driver has accepted your ride. {vehicle}, registration {plate}."
    ),
    RideStatus.ARRIVING: "Your driver is approaching. A {color} {vehicle}.",
    RideStatus.ARRIVED: (
        "Your driver has arrived. A {color} {vehicle}, registration {plate}. "
        "Your code is {pin}."
    ),
    RideStatus.IN_PROGRESS: "Your ride has started. Have a good trip.",
    RideStatus.COMPLETED: "You have arrived. The fare is {fare} francs.",
}


def announcement(
    status: RideStatus,
    *,
    locale: str = "fr",
    vehicle: str | None = None,
    color: str | None = None,
    plate: str | None = None,
    pin: str | None = None,
    fare_xaf: int | None = None,
) -> str | None:
    """The spoken line for a ride status, or None if there is nothing to say.

    The PIN appears only in the `arrived` announcement, which is the one moment
    it is useful and the moment the passenger is about to say it aloud anyway.
    This function is only ever called for the passenger's own ride, so speaking
    it there discloses nothing the screen was not already showing them.
    """
    table = ANNOUNCEMENTS_EN if locale == "en" else ANNOUNCEMENTS_FR
    template = table.get(status)
    if template is None:
        return None

    return template.format(
        vehicle=vehicle or ("your vehicle" if locale == "en" else "votre vehicule"),
        color=color or "",
        plate=plate or "",
        pin=pin or "",
        fare=fare_xaf if fare_xaf is not None else "",
    ).replace("  ", " ").strip()


def required_from_profile(user) -> list[str]:
    """Turn a passenger's standing profile into per-trip vehicle requirements.

    The profile is the default; the ride carries the actual requirement, so a
    passenger booking for somebody else can override it for that trip without
    changing anything recorded about themselves.

    `prefers_text_contact` is deliberately absent. It is a communication
    preference, not a vehicle capability, and feeding it to the matcher would
    shrink the driver pool for no reason.
    """
    mapping = {
        VehicleCapability.RAMP: user.requires_ramp,
        VehicleCapability.BOOT_SPACE: user.requires_boot_space,
        VehicleCapability.FRONT_SEAT: user.requires_front_seat,
        VehicleCapability.DRIVER_ASSIST: user.requires_driver_assist,
        VehicleCapability.GUIDE_ANIMAL: user.allows_guide_animal,
    }
    return [cap.value for cap, needed in mapping.items() if needed]
