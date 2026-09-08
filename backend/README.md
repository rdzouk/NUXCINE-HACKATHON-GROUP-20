> **This is not the VORA backend.** It is a draft SMS gateway proposal,
> kept for history. The application runs from the repository root: see
> [../README.md](../README.md) and [../DEMARRAGE.md](../DEMARRAGE.md).

# VORA local backend

## Run the local API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The local API exposes `/health`, `/places/search`, `/places/reverse`, and
`/rides/quote` for testing the map booking flow. It uses seeded Yaounde
landmarks and does not require SMS credentials or a database.

The SMS webhook below remains a draft and is not registered by this local app.

Status: DRAFT. This folder is a proposal for the FastAPI backend owner and is not approved for production integration.

## Ownership and use

- `app/services/httpsms_client.py`: outbound HTTP SMS client. It reads the HTTPSMS API key and sender number from environment variables.
- `app/services/sms_parser.py`: parses the draft `RIDE origin;destination` message format without creating a ride.
- `app/routers/sms_webhook.py`: proposed inbound webhook endpoint. It currently acknowledges the request and sends a reply, but it does not persist a ride or register itself with the application.

## Required backend-owner decisions

1. Confirm the real FastAPI application layout, dependency injection, database session, and ride model before wiring the router.
2. Decide how an SMS sender satisfies Phase 1 OTP authentication. An SMS sender does not pass through `/auth/otp/verify`; this must be designed and approved rather than bypassed in the webhook.
3. Confirm HTTPSMS webhook authentication/signature verification before exposing the endpoint publicly.
4. Resolve origin and destination through the existing landmark gazetteer and `/places/search` behavior, not as untrusted raw text.
5. Agree on the `channel='sms'` ride field and the response/idempotency behavior for repeated webhook events.

## Integration checklist

- [ ] Backend owner signs off on the proposal.
- [ ] Add the project's actual database session dependency.
- [ ] Add the router to the FastAPI application only after review.
- [ ] Implement webhook authentication and replay protection.
- [ ] Create a ride using the approved schema and SMS identity mapping.
- [ ] Add parser, client, endpoint, and integration tests.
- [ ] Configure `HTTPSMS_API_KEY` and `HTTPSMS_FROM_NUMBER` through the deployment secret manager.
