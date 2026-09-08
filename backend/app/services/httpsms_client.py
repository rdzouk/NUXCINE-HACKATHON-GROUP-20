"""Draft HTTPSMS client for the SMS backend proposal.

This module owns outbound SMS delivery. It is intentionally isolated from the
ride workflow until the backend owner approves the integration contract.
"""

import os

import httpx

HTTPSMS_API_URL = "https://api.httpsms.com/v1/messages/send"


async def send_sms(to: str, content: str) -> dict:
    """Send one SMS through HTTPSMS using deployment-provided credentials."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            HTTPSMS_API_URL,
            headers={"x-api-key": os.environ["HTTPSMS_API_KEY"]},
            json={
                "from": os.environ["HTTPSMS_FROM_NUMBER"],
                "to": to,
                "content": content,
            },
        )
        response.raise_for_status()
        return response.json()
