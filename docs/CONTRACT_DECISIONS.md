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

## Phase 3 additions

One new error code. Additive: no existing code changed meaning, and no response
shape moved.

```
KYC_DOCUMENT_ALREADY_REGISTERED   409
```

Submitting a CNI that is already registered to another driver previously
surfaced as a raw database integrity error, so the client saw a 500. The unique
constraint is deliberate (§4.2 makes the CNI hash the ban surface, so a
suspended driver cannot re-register under a new phone number), but a driver who
mistypes a digit deserves to be told that rather than shown a server fault.

`ride_offers` landed as specified in decision 3, with one addition: a unique
constraint on `(ride_id, driver_id)`, so a driver who declines in wave 1 is
never re-offered the same ride in wave 2.

Two partial unique indexes carry the concurrency guarantees, rather than
application logic alone:

```
uq_rides_one_live_per_passenger   ON rides (passenger_id) WHERE status IN (live)
uq_rides_one_live_per_driver      ON rides (driver_id)    WHERE status IN (live)
```

Two concurrent ride creations both pass a handler check and both insert; only
the database can serialise them. `scripts/race_test.py` fires ten simultaneous
accepts and asserts exactly one 200 and nine 409s.

## Phase 4 additions

Two development-only routes, registered **only** when `DEBUG` is on and the
environment is not production:

```
POST /dev/simulate-driver     { ride_id, speed_kmh?, polyline? }  -> 202
GET  /dev/realtime-stats                                          -> 200
```

They are absent from `openapi.json` on a production build because the router is
never included, not because a handler checks a flag. An endpoint that fabricates
GPS positions for arbitrary rides must not exist on a real deployment, and a
per-handler guard is the version somebody eventually forgets.

### WebSocket authentication, settled

§6 said "`Authorization` header or first-frame token, never a query string" and
left the choice open. It is now settled, because the browser has no choice:
the WebSocket API cannot set headers.

```js
ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token }));
```

The server replies `{type:"ready", ride_id, ride_status, heartbeat_s}` and
closes with 1008 if the first frame is anything else. Reconnect resumes from
that ready frame rather than from nothing, so a dropped connection does not
blank the passenger's screen.

The socket is **accepted before authentication** so a refusal can be explained.
Rejecting the handshake gives a browser no way to tell an expired token from a
network failure.

### `driver_location` stays nested

`features/map/hooks/useDriverLocation.js` reads `msg.lat`. The frame nests it:

```json
{"type": "driver_location", "ride_id": "...",
 "location": {"lat": 3.87, "lng": 11.51, "heading": 145,
              "updated_at": "2026-09-07T02:31:00Z"},
 "eta_s": 240}
```

Flattening was considered and rejected. `updated_at` is what lets a client show
a stale-fix warning rather than a marker frozen at a position the driver left
four minutes ago, and `ride_id` lets one socket carry more than one ride
unambiguously. The client change is one line. See `docs/INTEGRATION.md`.

## Phase 5 additions

No new routes. Every Phase 5 endpoint was already in §6 and stubbed at Phase 0;
this phase replaced the stubs. Two response fields gained real values:

* `GET /me/balance` now returns the ledger instead of 501.
* `POST /rides/{id}/cancel` now returns a real `fee_xaf` and `fee_reason`.

`POST /rides` can now return **409 OUTSTANDING_BALANCE**, with
`details.outstanding_xaf` naming the amount so the client can say what is owed
rather than only that something is. That code was reserved at Phase 0 for
exactly this; nothing about the contract changed.

### The cancellation policy, as implemented

| When | Who | Driver moved | Passenger pays | Driver receives |
|---|---|---|---|---|
| before a driver is assigned | passenger | n/a | 0 | 0 |
| within 30 s of acceptance | either | n/a | 0 | 0 |
| after acceptance | passenger | yes | 500 | 300 |
| after acceptance | passenger | **no** | 500 | **0** |
| after acceptance | driver | n/a | 0 | pays 500 |

The fourth row is the anti-abuse case. A driver could accept and idle to farm
compensation, so the payout is conditional on the server-held trace showing
real movement **toward the pickup**, measured as the reduction in distance to
the pickup rather than distance travelled: a driver circling their own street
covers ground without approaching anybody. Rejected trace points are excluded,
so a forged approach earns nothing.

`scripts/cancel_matrix.py` asserts every cell.

### Share tokens

Signed with `itsdangerous`, not as JWTs: these are one-off, single-purpose,
revocable blobs, and a JWT would add claims and an algorithm surface for
nothing while being indistinguishable from an access token in a log.

Two independent expiries, deliberately. The signature carries a max age, so a
token is refused even if its row is gone; the row carries `expires_at` and
`revoked_at`, so a link can be killed before its signature lapses. Either alone
leaves a gap.

Invalid, expired and revoked all answer **404 alike**. Telling them apart would
reveal which links were ever real, and a share link is precisely the kind of
URL that gets forwarded and guessed at.

Position is **coarse (about 300 m) until the ride is `in_progress`**. A link
shared while waiting should not reveal which doorway somebody is standing in.


## Phase 6 additions

No response shape changed. Everything below either fills a field the contract
already declared or corrects an index, which is what the freeze permits.

### `GET /vehicles/capabilities` was the last 501

It now serves the five capabilities with French and English labels. Served
rather than hardcoded in the client so a bad translation is a server fix, not
an app release.

Every capability is worded as a fact about the **vehicle**: "Vehicule equipe
d'une rampe", never "pour personnes handicapees". Law No. 2024/017 prohibits
processing health data, and "this passenger uses a wheelchair" is health data
while "this trip needs a ramp" is a logistics requirement (I9). A unit test
asserts the wording, because that distinction is exactly what a well-meaning
copy edit erases.

`accessibility_required` on a ride defaults from the passenger's profile and is
overridden per trip by the request body. Booking for a relative, or needing a
ramp today and not tomorrow, are both ordinary; a requirement attached to the
journey handles them and a flag attached to the person does not.

### The one-live-ride-per-driver index had to change

Flagged at Phase 0 as decision 7 and settled in migration 0006. A corridor
driver carries several live rides at once, which is the entire point of the
mode, so `uq_rides_one_live_per_driver` is replaced by
`uq_rides_one_live_exclusive_per_driver`, which covers `mode = 'exclusive'`
only. Corridor capacity is enforced by seat count instead.

The passenger rule is unchanged. Somebody riding in two cars at once is a bug
in every mode.

### A corridor join is a targeted offer, not a matching wave

The normal matching wave excludes any driver already on a live ride, which is
every corridor driver by definition. Routing a join through it would guarantee
that the one driver who can help never hears about it, so `offer_join` creates
a single offer for that driver.

Consent stays mandatory. Declining releases the held seats and falls back to an
ordinary wave, so a driver saying no costs the joiner a wait and nothing else.

### The joiner's fare is the leg, measured along the driven route

`ST_LineSubstring` between the two projected positions, priced per seat. A
fresh direct route between the joiner's endpoints would be a different journey,
usually shorter, and charging for it would underprice every seat.

The fare is still derived entirely on the server from server-held geometry, so
I2 holds for corridor exactly as it does for exclusive hire. `quoted_fare_xaf`
is rewritten at consent, which is the first moment the leg is real.

### `route_geom` is now populated

Declared in Phase 3 and left null because nothing needed a line. Corridor
containment is `ST_DWithin` against it, so it is written at ride creation with
`ST_LineFromEncodedPolyline`. `route_polyline` is still what a client draws;
`route_geom` is what Postgres can answer questions about.

### `WS /ws/share/{token}` was still a stub

Phase 5 built the share link, the token lifecycle and the HTTP view, but left
the socket returning 501, so `tools/share_view.html` polls over HTTP. The
socket is implemented now, and both it and the HTTP route assemble their
payload with one function, `sharing.build_share_view`. They built the same
view twice before, which is the arrangement where a field added carefully to
one is forgotten in the other.

The token stays in the path. The share link *is* the URL, it gets forwarded in
WhatsApp, and there is nowhere else for it to live; what makes that acceptable
is that the token is signed, expiring, revocable, and reveals a view that
cannot contain passenger identity, fare, PIN or phone number.

### Payments are behind an interface, and cash is the default

`PaymentProvider` with `initiate`, `status` and `refund`. `CashProvider` is
the default and that is a decision, not a limitation: most trips here are paid
in cash and a build that made mobile money mandatory would be describing a
different country.

MTN MoMo and Orange Money are stubs that **raise** rather than returning a
plausible-looking decline, so nobody spends an hour debugging a provider that
was never contacted. `initiate` is idempotent by key, which is I8 applied to
money, where charging twice is worse than creating a duplicate ride.
