"""Draft parser for the SMS ride-request format.

This parser only validates and separates text. It does not authenticate the
sender, resolve places, or create a ride.
"""

import re


def parse_ride_request(content: str) -> dict | None:
    """Parse `RIDE origin;destination`, returning None for other messages."""
    match = re.match(r"^RIDE\s+(.+?);(.+)$", content.strip(), re.IGNORECASE)
    if not match:
        return None
    return {
        "origin": match.group(1).strip(),
        "destination": match.group(2).strip(),
    }
