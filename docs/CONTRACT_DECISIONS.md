# Contract decisions

Resolutions to places where the build plan's §5 data model and §6 API contract
contradicted each other or were underspecified. Decided at Phase 0. **The
contract is frozen from here.** A later phase that seems to need a change stops
and flags it rather than changing a response shape silently.

Read this alongside `openapi.json`. Where the two disagree, `openapi.json` wins,
because it is generated from the code that actually runs.

---

## 1. The `ride` object was never defined

§6 returns `{ ride }` from eight endpoints and never says what is in it.

**Decision.** One schema, `app/schemas/ride.py:Ride`, with role-dependent
population. Not three schemas. The wire shape is identical for every caller; the
serializer decides which optional fields are filled. The client parses one thing.

| Field | Passenger | Assigned driver | Admin |
|---|---|---|---|
| `pin` | the 4 digits | `null` | `null` |
| `driver`, `vehicle` | from `accepted` | `null` | populated |
| `passenger` | `null` | populated | populated |
| `driver_location` | only in `accepted`..`in_progress` | `null` | `null` |
| everything else | populated | populated | populated |

A phone number appears in no branch of that table, in any state. A caller who
is none of those three gets `404 RIDE_NOT_FOUND`, not a filtered ride.

## 2. The `user` object was never defined

**Decision.** `app/schemas/user.py:User`. `phone_e164` is present only on the
caller's own object and never on a nested driver or passenger summary.
`accessibility` is a `AccessibilityProfile` of six booleans. `outstanding_xaf`
is on the user object so the client always knows whether booking will be
refused.

## 3. `offer_id` had no referent

§6 addresses `POST /driver/offers/{id}/accept`; §5 has no offers table.

**Decision.** An offer is a first-class object with its own id, backed by a
`ride_offers(ride_id, driver_id, wave, state, expires_at)` table added in
Phase 3. Reusing the ride id would have made `decline` a no-op and let wave 2
re-offer a ride to a driver who already refused it in wave 1.

The offer payload is not a `Ride`. Before acceptance the driver has no
relationship to the passenger, so they get pickup, dropoff, distances, fare and
capability requirements, and nothing that identifies anyone.

## 4. The PIN could not be re-shown

§5 stores `pin_hash` only, but the passenger has to read the PIN aloud at pickup.

**Decision.** The plaintext PIN is stored alongside the hash and returned to the
passenger on **every** read of their own ride, not just in the 201. A passenger
who backgrounds the app, loses signal or reinstalls must still be able to start
their trip; a PIN shown once is a live-demo failure waiting to happen. The hash
remains the thing the driver's input is compared against, and the plaintext is
never serialised for the driver or an admin.

## 5. `accessibility_required[]` had nowhere to live

`POST /rides` accepted it; `rides` had no column; Phase 6.1 matched
`users.requires_*` instead, ignoring the per-ride value.

**Decision.** Keep it and add the column. Booking for a relative, or travelling
with a wheelchair only today, are real cases. A per-trip vehicle requirement is
also a better fit for I9 than a permanent flag on a person: it records what this
journey needs, not what someone is.

The array defaults from the passenger's standing profile when omitted.

## 6. `vehicles` could not satisfy every `users.requires_*`

`users` has six flags; `vehicles` has four. Two of the six could not be matched.

**Decision.** Split them by kind.

**Vehicle capabilities** (matched in the query, `VehicleCapability` enum):
`ramp`, `boot_space`, `front_seat`, `driver_assist`, `guide_animal`.

**Communication preference** (never a matching predicate): `prefers_text_contact`.
It selects canned messages over a call and has nothing to do with the vehicle.

Phase 1's `vehicles` migration must therefore add `front_seat_available`, which
§5 omitted.

## 7. The cancellation debt was invisible and unclearable

Phase 5.3 blocks booking on an unsettled fee. §6 gave the client no way to see
the balance and no error code for the refusal.

**Decision.** Two additions, made now rather than at H28 so the contract can
stay frozen:

* `GET /me/balance` returning `outstanding_xaf` and the ledger entries behind it
* error code `OUTSTANDING_BALANCE` (409) on `POST /rides`

## 8. `seats` is passed twice and could disagree

**Decision.** The signed quote is authoritative for `seats` and `mode`. A body
`seats` that disagrees with the quote is rejected `422`, never silently
repriced. `seats` stays in the body so the client can confirm what it thinks it
booked.

## 9. Nothing prevented quote replay

`quote_id` is a signed blob with no backing row, so one quote could create N
rides under N different idempotency keys.

**Decision.** The quote carries a `jti`, burned in Redis on first use with a TTL
matching the quote lifetime. Second use returns `409 QUOTE_ALREADY_USED`. Redis
rather than a `quotes` table: TTL is native and it costs no migration.

## 10. Schema failure returns 400, not 422

FastAPI answers a schema failure with 422. §6 reserves 422 for semantically
invalid requests, such as a dropoff outside the service area, and assigns schema
failure to 400.

**Decision.** `RequestValidationError` is remapped to `400 VALIDATION_FAILED`,
with the offending fields in `details.fields`. Without this, "bad JSON" and
"outside Yaounde" are indistinguishable to the client.

## 11. Retry semantics were inconsistent

§6 says 429 carries a `Retry-After` header and 503 carries a `retry_after_s`
body field.

**Decision.** Both statuses emit both forms. The client implements one path.

## 12. Smaller resolutions

* `distance_m` in `/places/search` is `null` when `near` is omitted.
* `GET /rides` `cursor` is an opaque base64 keyset cursor. Pass it back verbatim;
  do not parse it.
* `rides.vehicle_id` is null until `accepted`, exactly like `driver_id`.
* `ride_events` append-only is enforced by revoking UPDATE and DELETE from the
  API's database role, not by convention.
* WebSocket frame models are injected into `openapi.json` by
  `scripts/export_openapi.py`, since FastAPI cannot describe socket routes.
* `/health` component status is one of `ok`, `degraded`, `down`,
  `not_configured`. OSRM reports `not_configured` until Phase 2.

---

## Phase 1 additions

Three routes that §6 does not list. Phase 1 deliverable 5 requires "document
upload endpoints" and an "admin approval stub", and §6 specified no admin
surface at all. Added rather than skipped, and recorded here rather than
introduced quietly. None of them changes an existing response shape.

```
POST /driver/kyc/documents          { kind, reference }  -> 201
GET  /admin/drivers?kyc_status=     -> 200 [DriverAdminView]
POST /admin/drivers/{id}/kyc        { status, reason? }  -> 200
```

`POST /auth/logout` gained an **optional** body carrying `refresh_token`. §6
specifies a bodyless logout and that still works unchanged: with no body every
family for the caller is revoked, with a token only that device is signed out.
Optional, so the frozen contract holds.

## Phase 1 data model changes

`drivers.is_online` and `drivers.seats_free` moved onto `drivers`, where §5 put
them on `driver_presence`. This is what makes the constraint §5 itself asks for,
`CHECK (kyc_status = 'verified' OR NOT is_online)`, creatable at all: Postgres
CHECK constraints cannot reference another table. Phase 2's `driver_presence`
still holds the geometry, heading and freshness. The result is that the KYC gate
is enforced by the database, not only by the handler, and `kyc_smoke.py` proves
it by trying the UPDATE directly in psql and being refused.

`vehicles.front_seat_available` added, per decision 6 above.

`drivers.kyc_rejection_reason` and `refresh_tokens.rotated_at` added. The
latter is the reuse-detection signal: a token with `rotated_at` set that is
presented again revokes its whole family.

`kyc_documents` added. §5 mentioned `licence_ref_enc BYTEA` on `drivers` but
had nowhere to put the other four required documents.

---

## Defects found in the build plan

Two things in §5 cannot be built as written. Both are corrected above and noted
here so nobody re-implements them from the original text.

**§5 `drivers` CHECK constraint.** `CHECK (kyc_status = 'verified' OR NOT
is_online)` references `is_online`, which lives on `driver_presence`. A Postgres
CHECK constraint cannot reference another table. Enforced instead in the
`POST /driver/online` handler, which returns 409 per §6, plus a trigger on
`driver_presence` for defence in depth.

**§5 `landmarks.search_vec`.** A `GENERATED ALWAYS AS ... STORED` column
requires an IMMUTABLE expression. `unaccent()` is STABLE, because it depends on
a dictionary, so the column as sketched will fail to create. Phase 2's migration
wraps it in an IMMUTABLE SQL function first.

---

## Open, deferred to the phase that needs it

**The corridor parent ride and the one-live-ride index.** `corridor_legs` has
both `parent_ride_id` and `ride_id`. If the parent is a `rides` row owned by the
first passenger and that passenger also has a leg row, they hold two live rides
and trip the partial unique index. The index predicate needs
`AND parent_ride_id IS NULL`, or the first passenger's leg has to be the parent
itself. Decided in Phase 3, before that index is written, because the index
shape depends on the answer.
