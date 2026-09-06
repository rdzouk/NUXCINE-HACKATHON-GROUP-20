# VORA — Backend & Security Build Plan

**Owner of this document:** backend + security engineer (single owner).
**Format:** 48-hour hackathon, online. Clock starts Sat 5 Sep 2026, 09:00 WAT. Ends Mon 7 Sep 2026, 09:00 WAT.
**Scope of this document:** backend, data model, API contract, security, and any throwaway UI needed to *test or demo* backend behaviour. Mobile/frontend is owned by others and is out of scope except where this document defines the contract they consume.

---

## 0. How to use this document

*(This section is addressed to the AI agent executing the build.)*

**Read sections 1–6 fully before writing any code.** They contain invariants that later phases depend on. Do not start Phase 0 until you have read them.

**Rules of engagement:**

1. **Work one phase at a time.** Do not read ahead and pre-build. Each phase has an explicit hour budget, and the budget is the constraint that matters most. If a phase runs over budget, cut from that phase's `NICE TO HAVE` list, not from the next phase.
2. **Every phase ends with its Acceptance Check.** Run it. Paste the output. Do not declare a phase complete on the basis that the code looks right.
3. **Respect the `DO NOT BUILD` list in each phase.** These are things that look tempting and will eat the clock. They were considered and deliberately cut.
4. **The API contract in §6 is frozen after Phase 0.** If a later phase seems to need a contract change, stop and flag it explicitly with the reason — do not silently change a response shape. A mobile developer is coding against it in parallel.
5. **Security requirements are per-phase and are not optional.** They are listed inside each phase, not batched at the end, because batching them at the end means they don't happen. If you cannot implement one within the budget, write it into `THREAT_MODEL.md` as an accepted risk with a named mitigation — never silently skip it.
6. **Assume you are being asked to justify every choice to a jury.** Where you make a non-obvious decision, leave a one-line comment explaining the tradeoff. Not a paragraph.
7. **When requirements are ambiguous in a way that materially changes the schema or contract, ask.** Otherwise state your assumption inline and proceed.
8. **No placeholder logic in any path that appears in the demo script (§8).** No `TODO: handle this later` on ride creation, fare calculation, matching, or auth.

**What "glorified MVP" means here:** every feature that exists must work end-to-end against a real database with real constraints and real authorization. Breadth is sacrificed, never depth. A feature that half-works is worse than a feature that is absent, because it will fail live.

---

## 1. Project context

VORA is a smart-mobility application for the Cameroonian urban context (primary city: Yaoundé; secondary: Douala). It is not a market-agnostic ride-hailing clone. The evaluation criteria explicitly reward:

- innovation that solves a real, local problem
- ability of the team to explain and justify its architecture
- safety, accessibility, cost, service quality, UX
- adaptation to Cameroonian realities: neighbourhoods, landmarks, travel habits, road conditions

**Mandatory feature floor** (from the brief — these must all work):
user authentication · geolocation · interactive mapping · ride booking · automatic route calculation · ride cost estimation · real-time driver tracking · modern responsive interface.

**The two structural bets that differentiate this build** (both live in the backend, which is why they are in this document):

**Bet 1 — Landmark-first geocoding.** Street addressing is functionally absent for most trips in Cameroon. People navigate by carrefours, stations, markets, schools, and businesses: "Carrefour Warda", "Total Nsimeyong", "derrière la Poste Centrale". A backend whose primary geocoding path is a curated landmark gazetteer with fuzzy/multilingual matching works the way people actually speak. Competitors wiring raw Google Places will look imported.

**Bet 2 — Corridor (shared-seat) rides.** The dominant real transport mode is not exclusive hire — it is shared taxis running *ramassage* along corridors at a per-seat fare, plus motos. Supporting `seats_requested` against a route corridor lets VORA digitise the model that already exists, rather than importing carpooling as a retrofit. Exclusive hire is also supported (it satisfies the mandatory floor); corridor is the innovation layer on top.

**Framing for the jury:** "We did not add ride-sharing to a taxi app. We digitised the shared-corridor transport model Cameroonians already use, and added exclusive hire on top of it."

---

## 2. Non-negotiable invariants

These hold across every phase. Violating one is a build defect regardless of what phase you are in.

| # | Invariant | Why |
|---|---|---|
| I1 | **Every ride-scoped endpoint enforces object-level authorization.** A caller may touch a ride only if they are its passenger, its assigned driver, or an admin. Enforced in one shared dependency, never per-handler. | IDOR is *the* characteristic vulnerability of ride-hailing APIs. Per-handler checks miss one. |
| I2 | **Fare is computed server-side from a server-held GPS trace.** Client-reported distance is never an input to price. | A patched client otherwise inflates every fare. |
| I3 | **The API never returns a counterparty's phone number**, in any response, at any ride state. | Enables harassment, off-app leakage, doxxing. Also §4 legal exposure. |
| I4 | **Precise driver location is visible only to the assigned passenger, and only between `accepted` and `completed`.** | Location is the most sensitive field in the system. |
| I5 | **No secrets in any client.** Map keys, payment credentials, SMS credentials all live server-side and are proxied. | Free credibility; half the field will ship keys in the APK. |
| I6 | **All queries parameterised. All input validated at the boundary by schema, not by hand.** | Baseline. Use the framework's validation layer so it cannot be forgotten. |
| I7 | **Every state transition on a ride is written to an append-only `ride_events` table** with actor, timestamp, and reason. | This is the evidence layer that safety, disputes, and the audit story all depend on. Cheap if done from the start, impossible to retrofit at hour 40. |
| I8 | **`POST` endpoints that create or move money/state accept an `Idempotency-Key` header** and de-duplicate on it. | Mobile networks here drop and retry. Without this, one tap creates two rides. |
| I9 | **No health data, no biometrics, no ethnic/regional/political attributes are stored — ever.** Accessibility is modelled as *vehicle capability requirements*, never as a property of the person. | §4. This is a legal prohibition in Cameroon, not a preference. |
| I10 | **Never call a heuristic "AI" or "learning."** Describe what it does. | Judges reward a well-scoped heuristic and punish an overclaimed model. |

---

## 3. Tech stack

| Layer | Choice | Tradeoff, one line |
|---|---|---|
| API | **Python 3.12 + FastAPI** | Pydantic gives schema validation (= I6) and auto-generated OpenAPI (= the Phase 0 artifact mobile needs) for free; iteration speed beats runtime speed at demo scale. |
| DB | **PostgreSQL 16 + PostGIS 3.4** | The entire app is geo queries; hand-rolled haversine filtering costs hours that `ST_DWithin` + a GiST index costs zero. |
| ORM | **SQLAlchemy 2.0 (async) + GeoAlchemy2**, Alembic for migrations | Typed models and real migrations; drop to raw SQL for the two or three corridor/matching queries where the ORM fights you. |
| Realtime | **Native FastAPI WebSockets**, single process, in-memory connection registry | Redis pub/sub is the horizontal answer and you say so to the jury; a demo does not need it. |
| Routing/ETA | **Self-hosted OSRM** (Docker, Cameroon OSM extract from Geofabrik) | No API key, no quota, no network dependency during a live demo — that alone justifies the 40-minute setup. Fallback: hosted directions API behind the same internal interface. |
| Cache / rate limit | **Redis** | Token buckets and OTP throttles want atomic ops with TTL. |
| Auth | **Phone + OTP → short-lived JWT access + rotating refresh token** | Email login is the wrong primitive for this market. |
| Deploy | **Docker Compose on a single VPS, HTTPS via Caddy** (auto-TLS) | One command, one host, TLS solved. |

### Why not Rust

Rust is the better production answer for the location-ingest path and would be a defensible long-term choice. It is the wrong choice for these 48 hours, for three specific reasons:

1. **Compile time under schema churn.** The data model will change perhaps fifteen times in the first day. `sqlx` compile-time query verification — the main reason to pick Rust here — turns every schema change into a rebuild-and-fix cycle. That is the exact cost you cannot afford.
2. **Validation is not free.** In FastAPI, request-schema validation *is* the framework. In axum you assemble it. Invariant I6 is cheaper to guarantee in Python.
3. **There is no hot path at demo scale.** You will have under twenty concurrent connections. Rust buys performance you will not be able to demonstrate, at a cost you will feel every hour.

**Do not build a Python/Rust hybrid.** Two toolchains, two deploy paths, two debugging contexts, one weekend. The correct place for Rust is a sentence in the architecture document: *"Location ingest is the component we would rewrite in Rust first — it is the only path where per-message cost matters at 10k concurrent drivers, and it is cleanly isolated behind the `LocationSink` interface."* That earns the credit without paying the cost.

---

## 4. Regulatory and threat context — Cameroon-specific

This section exists because it produces **hard design constraints**, not because it is nice framing. Almost no competing team will have it, and it is directly on the "adaptation to Cameroonian realities" criterion.

### 4.1 Law No. 2024/017 (personal data protection)

Cameroon enacted Law No. 2024/017 on 23 December 2024. The organisational compliance deadline was **23 June 2026 — already past**. This is live, enforceable law, not a future consideration. Provisions that bind this design:

- **Prohibited data categories.** The law expressly prohibits processing of data relating to religion, philosophy, trade-union or political opinions, racial or ethnic origin, linguistic or regional origin, genetics, and health/biometrics.
  → **Consequence (I9):** accessibility is stored as *vehicle capability requirements* (`requires_ramp`, `requires_boot_space`, `requires_front_seat`, `prefers_text_contact`), never as a medical condition or disability status. Also rules out face-match driver verification.
- **Cross-border transfer requires prior authorisation** from the data protection authority, which assesses whether the destination offers equivalent protection.
  → **Consequence:** data residency is an architectural decision, not an afterthought. Design for in-country or authorised-region hosting and say so. This single point will land with a jury.
- **Breach notification without delay**; annual security report to the authority.
  → **Consequence:** the `ride_events` audit table and structured security logging are compliance artifacts, not gold-plating.
- **Processing without prior authorisation is punishable by fines of 5–50 million FCFA.**
  → **Consequence:** the pitch says "designed for compliance," never "compliant." Do not claim a legal status you do not have.

### 4.2 SIM registration and the phone-as-identity question

**Correction to a common assumption:** in most markets, banning a phone number is weak because SIMs are disposable. **In Cameroon it is meaningfully stronger.** A Prime Ministerial decree of 3 September 2015 makes SIM registration compulsory, requires a national ID card (CNI) to register a SIM, prohibits street sale of SIMs, and caps an individual at **three SIMs per network**. With two major networks, that is roughly six legitimate numbers per person, not unlimited.

But do not over-rely on it:

- **Enforcement is leaky.** The regulator has found cases of 100–200 SIMs registered against a single national ID, and has fined operators for failing to identify subscribers. Treat phone as a *strong signal*, not a proof of uniqueness.
- **Hard ID-gating excludes real users.** Large numbers of Cameroonians lack a birth certificate and therefore lack a CNI. Gating passenger signup on national ID would exclude legitimate users and is the wrong tradeoff for the accessibility/inclusion story you are also telling.

**Resulting enforcement model — build this:**

| Party | Identity requirement | Ban surface |
|---|---|---|
| Passenger | Verified phone only | phone + device fingerprint + account; graduated (warn → restrict → suspend) |
| Driver | Full KYC: CNI, driving licence, vehicle registration | account + vehicle + CNI reference hash; permanent |

Rationale to state aloud: the driver is the higher-risk party and is already professionally licensed, so full KYC there costs nothing in inclusion. The passenger side stays low-friction because exclusion is a real harm.

### 4.3 Threat model summary (expand into `THREAT_MODEL.md`)

| Actor | Capability | Primary mitigation |
|---|---|---|
| Malicious passenger | Patched client, forged GPS, fake bookings, harassment | Server-side fare (I2), phone verification, cancellation ledger, no phone exposure (I3) |
| Malicious driver | Patched client, fare inflation, fee farming, impersonation | Server-side trace, movement-verified cancellation payout, ride PIN, KYC gate |
| Third party / impersonator | Poses as the assigned driver at pickup | Ride PIN + driver photo + vehicle photo |
| Credential attacker | OTP brute force, SMS pumping, token theft | OTP hashing + attempt caps + layered rate limits + short-lived JWT with rotating refresh |
| Curious insider | Reads location history or contact details | Field-level access control, audit log on admin reads, encrypted KYC fields |
| Network attacker | Intercept, replay | TLS everywhere, idempotency keys, no sensitive data in URLs |

---

## 5. Data model

PostGIS geometry columns are `geography(Point, 4326)` unless noted. Every table has `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `created_at`, `updated_at`.

### Core identity

```
users
  phone_e164        TEXT UNIQUE NOT NULL      -- +237...
  display_name      TEXT NOT NULL
  role              ENUM(passenger, driver, admin) NOT NULL
  status            ENUM(active, restricted, suspended) NOT NULL DEFAULT 'active'
  locale            TEXT NOT NULL DEFAULT 'fr'
  -- accessibility: vehicle CAPABILITY REQUIREMENTS only. See I9.
  requires_ramp             BOOLEAN NOT NULL DEFAULT false
  requires_boot_space       BOOLEAN NOT NULL DEFAULT false
  requires_front_seat       BOOLEAN NOT NULL DEFAULT false
  requires_driver_assist    BOOLEAN NOT NULL DEFAULT false
  prefers_text_contact      BOOLEAN NOT NULL DEFAULT false
  allows_guide_animal       BOOLEAN NOT NULL DEFAULT false

otp_challenges
  phone_e164   TEXT NOT NULL
  code_hash    TEXT NOT NULL          -- bcrypt/argon2. NEVER the plaintext code.
  attempts     SMALLINT NOT NULL DEFAULT 0
  max_attempts SMALLINT NOT NULL DEFAULT 5
  expires_at   TIMESTAMPTZ NOT NULL
  consumed_at  TIMESTAMPTZ
  request_ip   INET
  INDEX (phone_e164, expires_at)

refresh_tokens
  user_id      UUID REFERENCES users
  token_hash   TEXT UNIQUE NOT NULL   -- store hash, not token
  family_id    UUID NOT NULL          -- rotation family; reuse of a rotated token kills the family
  expires_at   TIMESTAMPTZ NOT NULL
  revoked_at   TIMESTAMPTZ
```

### Driver and vehicle

```
drivers
  user_id           UUID UNIQUE REFERENCES users
  kyc_status        ENUM(pending, verified, rejected, suspended) NOT NULL DEFAULT 'pending'
  kyc_reviewed_at   TIMESTAMPTZ
  cni_ref_hash      TEXT              -- hash, not the number. Dedupe + ban surface.
  licence_ref_enc   BYTEA             -- encrypted at rest
  rating_avg        NUMERIC(3,2)
  CHECK (kyc_status = 'verified' OR NOT is_online)

vehicles
  driver_id         UUID REFERENCES drivers
  plate             TEXT NOT NULL
  make, model, color TEXT NOT NULL
  seats             SMALLINT NOT NULL CHECK (seats BETWEEN 1 AND 8)
  photo_url         TEXT
  -- capability flags, matched against user requirements
  has_ramp          BOOLEAN NOT NULL DEFAULT false
  has_boot_space    BOOLEAN NOT NULL DEFAULT false
  driver_assists    BOOLEAN NOT NULL DEFAULT false
  accepts_guide_animal BOOLEAN NOT NULL DEFAULT false

driver_presence
  driver_id    UUID PRIMARY KEY REFERENCES drivers
  geom         geography(Point,4326) NOT NULL
  heading      SMALLINT
  is_online    BOOLEAN NOT NULL DEFAULT false
  seats_free   SMALLINT NOT NULL DEFAULT 0
  updated_at   TIMESTAMPTZ NOT NULL
  INDEX USING GIST (geom)              -- the single most important index in the system
```

### Geocoding

```
landmarks
  name          TEXT NOT NULL
  aliases       TEXT[] NOT NULL DEFAULT '{}'   -- 'Warda', 'Carrefour Warda', 'Rond-point Warda'
  kind          ENUM(carrefour, station, market, school, hospital, admin, business, quartier)
  city          TEXT NOT NULL
  quartier      TEXT
  geom          geography(Point,4326) NOT NULL
  popularity    INT NOT NULL DEFAULT 0
  search_vec    tsvector GENERATED ALWAYS AS (...) STORED
  INDEX USING GIN (search_vec), INDEX USING GIN (aliases), INDEX USING GIST (geom)
```

### Rides

```
rides
  passenger_id     UUID REFERENCES users
  driver_id        UUID REFERENCES drivers            -- null until accepted
  vehicle_id       UUID REFERENCES vehicles
  mode             ENUM(exclusive, corridor) NOT NULL
  status           ENUM(requested, matching, accepted, arriving, arrived,
                        in_progress, completed, cancelled_passenger,
                        cancelled_driver, expired) NOT NULL
  seats            SMALLINT NOT NULL DEFAULT 1
  pickup_geom      geography(Point,4326) NOT NULL
  dropoff_geom     geography(Point,4326) NOT NULL
  pickup_label     TEXT NOT NULL       -- what the user actually said: 'Carrefour Warda'
  dropoff_label    TEXT NOT NULL
  route_polyline   TEXT                -- encoded, from OSRM
  route_geom       geography(LineString,4326)
  quoted_fare_xaf  INT NOT NULL
  final_fare_xaf   INT
  quoted_distance_m INT NOT NULL
  actual_distance_m INT
  pin_hash         TEXT NOT NULL       -- 4-digit pickup PIN, hashed
  accepted_at, arrived_at, started_at, ended_at TIMESTAMPTZ
  idempotency_key  TEXT
  UNIQUE (passenger_id, idempotency_key)
  INDEX USING GIST (route_geom)        -- corridor containment queries
  -- partial index: only one live ride per passenger
  UNIQUE INDEX ON (passenger_id) WHERE status IN ('requested','matching','accepted','arriving','arrived','in_progress')

ride_events                            -- APPEND ONLY. No UPDATE, no DELETE. (I7)
  ride_id      UUID REFERENCES rides
  seq          BIGSERIAL
  event_type   TEXT NOT NULL
  actor_type   ENUM(passenger, driver, system, admin)
  actor_id     UUID
  from_status, to_status TEXT
  reason       TEXT
  metadata     JSONB
  occurred_at  TIMESTAMPTZ NOT NULL

ride_traces                            -- server-held GPS trace. Source of truth for fare. (I2)
  ride_id      UUID REFERENCES rides
  seq          INT NOT NULL
  geom         geography(Point,4326) NOT NULL
  speed_mps    REAL
  accuracy_m   REAL
  recorded_at  TIMESTAMPTZ NOT NULL
  rejected     BOOLEAN NOT NULL DEFAULT false   -- failed plausibility check, kept for forensics
  PRIMARY KEY (ride_id, seq)

ride_share_tokens                      -- family/friend live-tracking links
  ride_id      UUID REFERENCES rides
  token_hash   TEXT UNIQUE NOT NULL
  expires_at   TIMESTAMPTZ NOT NULL
  revoked_at   TIMESTAMPTZ

corridor_legs                          -- a corridor ride's per-passenger segment
  parent_ride_id  UUID REFERENCES rides
  ride_id         UUID REFERENCES rides
  boarding_order  SMALLINT NOT NULL
  seats           SMALLINT NOT NULL
  leg_distance_m  INT NOT NULL
  leg_fare_xaf    INT NOT NULL
```

### Money and trust

```
ledger_entries                         -- double-entry-ish. Cancellation debt lives here.
  user_id      UUID REFERENCES users
  ride_id      UUID REFERENCES rides
  kind         ENUM(fare_charge, fare_payout, cancel_fee, cancel_compensation,
                    pass_purchase, pass_redemption, adjustment)
  amount_xaf   INT NOT NULL           -- signed
  settled_at   TIMESTAMPTZ            -- null = outstanding
  note         TEXT

incident_reports
  ride_id, reporter_id, reported_id
  category     ENUM(safety, harassment, fare_dispute, no_show, vehicle_condition, other)
  description  TEXT
  snapshot     JSONB NOT NULL          -- sealed: trace summary, driver+vehicle ids, timestamps
  status       ENUM(open, reviewing, resolved)

canned_messages                        -- replaces phone contact (I3)
  ride_id, sender_id
  template_key TEXT NOT NULL           -- 'at_gate', 'two_min', 'cant_find_you', 'please_wait_5'
```

**Explicit N+1 and locking notes:**
- Matching selects candidate drivers with a single `ST_DWithin` query joined to `vehicles` — never loop-and-fetch per driver.
- Driver claim must be atomic: `UPDATE driver_presence SET ... WHERE driver_id = $1 AND is_online AND NOT EXISTS (live ride)` inside the transaction that sets `rides.driver_id`. Two passengers must never claim one driver.
- `ride_traces` writes are append-only and batched; do not hold a transaction open across a WebSocket read.

---

## 6. API contract (frozen after Phase 0)

Base: `/api/v1`. All responses JSON. All timestamps RFC 3339 UTC.

### Error envelope — identical on every failure

```json
{
  "error": {
    "code": "RIDE_NOT_FOUND",
    "message": "No ride with that identifier is visible to you.",
    "details": {},
    "request_id": "018f3c2e-..."
  }
}
```

Codes are SCREAMING_SNAKE and stable. `message` is human-readable French by default (`Accept-Language` honoured). **Authorization failures return `404 RIDE_NOT_FOUND`, never `403`** — do not leak the existence of rides the caller cannot see.

| Status | Used for |
|---|---|
| 400 | Malformed request / schema failure |
| 401 | Missing or invalid access token |
| 403 | Authenticated but role-forbidden (e.g. passenger hitting a driver endpoint) |
| 404 | Not found **or** not visible to caller |
| 409 | State conflict (ride already accepted, driver already claimed) |
| 422 | Semantically invalid (dropoff outside service area) |
| 429 | Rate limited. Always includes `Retry-After`. |
| 503 | Dependency down (OSRM, SMS) — includes `retry_after_s` |

### Endpoints

**Auth**
```
POST /auth/otp/request      { phone }                      → 202 { challenge_id, expires_at, resend_after_s }
POST /auth/otp/verify       { challenge_id, code }         → 200 { access_token, refresh_token, user }
POST /auth/refresh          { refresh_token }              → 200 { access_token, refresh_token }
POST /auth/logout                                          → 204
GET  /me                                                   → 200 { user }
PATCH /me                   { display_name?, locale?, accessibility{} } → 200 { user }
```
`otp/request` returns 202 with the same body shape whether or not the phone is registered. Do not leak registration state.

**Geocoding**
```
GET  /places/search?q=warda&near=3.848,11.502&limit=8
     → 200 { results: [ { id, name, kind, quartier, lat, lng, distance_m, match_type } ] }
     match_type ∈ exact_alias | fuzzy_landmark | quartier | street_fallback
GET  /places/reverse?lat=&lng=  → 200 { label, nearest_landmark, quartier }
```

**Quoting**
```
POST /rides/quote  { pickup{lat,lng,label}, dropoff{lat,lng,label}, seats, mode }
     → 200 { quote_id, distance_m, duration_s, fare_xaf,
             corridor_fare_xaf?, route_polyline, expires_at,
             breakdown: { base_xaf, per_km_xaf, per_min_xaf, surge_multiplier } }
```
`quote_id` is signed and short-lived (5 min). Ride creation references it; the server re-derives the fare and never trusts a client-supplied price.

**Rides**
```
POST   /rides                { quote_id, seats, accessibility_required[] }
       Header: Idempotency-Key                        → 201 { ride }
GET    /rides/{id}                                    → 200 { ride }
GET    /rides?status=&limit=&cursor=                  → 200 { items, next_cursor }
POST   /rides/{id}/cancel    { reason }               → 200 { ride, fee_xaf, fee_reason }
POST   /rides/{id}/share                              → 201 { url, expires_at }
DELETE /rides/{id}/share                              → 204
POST   /rides/{id}/messages  { template_key }         → 201 { message }
POST   /rides/{id}/sos                                → 201 { incident_id }
POST   /rides/{id}/report    { category, description } → 201 { incident_id }
```

**Driver**
```
POST /driver/online          { lat, lng, seats_free }  → 200   (409 if kyc_status != verified)
POST /driver/offline                                   → 200
GET  /driver/offers                                    → 200 { offers: [...] }
POST /driver/offers/{id}/accept                        → 200 { ride }   (409 if taken)
POST /driver/offers/{id}/decline                       → 204
POST /rides/{id}/arrived                               → 200 { ride }
POST /rides/{id}/start       { pin }                   → 200 { ride }   (403 on wrong pin, capped)
POST /rides/{id}/complete                              → 200 { ride, final_fare_xaf }
```

**Public (unauthenticated, token-scoped)**
```
GET /share/{token}            → 200 { ride_status, driver_first_name, vehicle{make,model,color,plate},
                                      current_location{lat,lng}, eta_s, dropoff_label }
```
Returns a **strict subset**. No passenger identity, no phone, no fare, no full trace history.

### WebSockets

```
WS /ws/driver     (driver JWT)     ↑ {type:'location', lat, lng, heading, speed, ts}
                                   ↓ {type:'offer'|'ride_update'|'ping'}
WS /ws/passenger  (passenger JWT)  ↓ {type:'ride_update'|'driver_location'|'message'|'ping'}
WS /ws/share/{token} (no auth)     ↓ {type:'share_update'}   — throttled, coarse until in_progress
```

Rules: authenticate on connect via `Authorization` header or first-frame token, **never a query string** (query strings land in logs). Server-side heartbeat every 20 s; drop dead connections. Driver location fan-out goes only to the one subscribed passenger of the active ride (I4). Rate-limit inbound location frames to 1 per 2 s per connection.

---

## PHASE 0 — Contract, skeleton, deploy
**Budget: H0 → H3 (3 hours). Do not exceed. This is the highest-leverage block in the build.**

**Objective:** a deployed, HTTPS-reachable skeleton and a frozen OpenAPI document, so that mobile can mock and work in parallel from hour three instead of integrating at hour forty.

**Deliverables**
1. Repo with `README.md` (architecture diagram), `ARCHITECTURE.md`, `THREAT_MODEL.md` (stub with §4.3 table).
2. `docker-compose.yml`: api, postgres+postgis, redis, osrm, caddy.
3. FastAPI app with the **full §6 route surface stubbed** — every endpoint present, correct request/response Pydantic models, returning `501 NOT_IMPLEMENTED` in the standard error envelope.
4. Exported `openapi.json` committed to the repo and handed to mobile.
5. Global error handler emitting the §6 envelope with `request_id`.
6. Structured JSON logging with request ID propagation.
7. `GET /health` returning db/redis/osrm status.
8. **Deployed to the VPS with real TLS.** Not localhost.

**Security requirements**
- Security headers via middleware: HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY`, restrictive CSP on any HTML surface.
- CORS allow-list, not `*`.
- Request body size cap (1 MB) and global request timeout.
- All configuration via environment variables; `.env` gitignored; `.env.example` committed with placeholder values.
- Confirm no secret is present in git history before the first push.

**Test harness to build**
- `scripts/smoke.sh` — curls `/health` and three stub endpoints against the deployed URL, asserts the error envelope shape.

**Acceptance check**
```
curl -sS https://<deployed>/api/v1/health | jq .
curl -sS https://<deployed>/api/v1/rides/00000000-0000-0000-0000-000000000000 | jq .error.code
# expect: 501 with a well-formed envelope, over real TLS, from a machine that is not yours
```

**DO NOT BUILD:** business logic, database tables beyond an initial empty migration, authentication. This phase is scaffolding and a contract, nothing else.

---

## PHASE 1 — Identity, auth, KYC gate
**Budget: H3 → H9 (6 hours).**

**Objective:** phone-OTP authentication that an attacker cannot brute-force and cannot use to burn your SMS budget, plus the driver KYC state machine that gates going online.

**Deliverables**
1. Alembic migration: `users`, `otp_challenges`, `refresh_tokens`, `drivers`, `vehicles`.
2. OTP request/verify with **hashed codes** (argon2), 5-minute TTL, 5-attempt cap then burn the challenge.
3. JWT access token (15 min) + rotating refresh token (30 days) with **reuse detection**: presenting an already-rotated refresh token revokes the whole family.
4. `get_current_user` dependency; `require_role(...)` dependency.
5. Driver KYC: document upload endpoints, `pending → verified → rejected/suspended`, admin approval stub. `POST /driver/online` returns **409** unless `kyc_status = 'verified'`.
6. Pluggable `SmsSender` interface with a `ConsoleSmsSender` that logs the code in dev.

**Security requirements — this is the phase where these matter most**
- **Layered OTP rate limits (Redis token buckets):** per-phone 3/hour and 10/day; per-IP 20/hour; **global circuit breaker** that halts OTP sending and alerts if the system-wide rate exceeds a threshold. An unrated OTP endpoint is an SMS-pumping ATM that bills *you* and routes revenue to premium numbers. This is a real, actively exploited attack, not a theoretical one.
- Constant-time comparison on OTP verification.
- Identical response shape and timing regardless of whether the phone is registered.
- E.164 normalisation and validation on every phone input; reject non-`+237` numbers unless a config flag allows test numbers.
- KYC documents stored encrypted at rest; `cni_ref_hash` stored as a hash for dedupe/ban, never the plaintext number.
- Log auth failures with phone **hashed**, never in plaintext.

**Test harness to build**
- `scripts/auth_smoke.py` — full signup→login→refresh→reuse-detection cycle; asserts the family revocation actually fires.
- Rate limit test: fire 10 OTP requests for one phone, assert 429 with `Retry-After` after the third.

**Acceptance check**
```
python scripts/auth_smoke.py --base https://<deployed>/api/v1
# expect: all green, including reuse-detection revocation and 429 on the 4th OTP request
```

**DO NOT BUILD:** social login, password fallback, email verification, real SMS gateway integration (console sender is correct until you have credentials in hand and time to spare).

---

## PHASE 2 — Geo core, landmark gazetteer, fare quoting
**Budget: H9 → H15 (6 hours). This is Bet 1. Protect this budget.**

**Objective:** a geocoder that resolves how Cameroonians actually name places, plus deterministic server-side fare quoting.

**Deliverables**
1. Migration: `landmarks`, `driver_presence` (both with their GIST/GIN indexes).
2. **Seed the gazetteer: 300–500 Yaoundé landmarks minimum.** Source from the Geofabrik Cameroon OSM extract (`amenity`, `shop`, `highway=junction`, `place=suburb`), then hand-add the carrefours and quartiers that matter and that OSM misses. Commit the seed file. *This dataset is a deliverable in its own right — say so to the jury.*
3. `GET /places/search` with a **layered resolution cascade**, returning `match_type` so the client can show provenance:
   - exact alias match → fuzzy landmark match (trigram + `tsvector`, accent-insensitive, tolerant of FR/EN/pidgin mixing) → quartier match → street fallback.
4. OSRM integration behind a `RoutingProvider` interface (`route()`, `distance_matrix()`), with a timeout, a retry, and a haversine × 1.35 fallback if OSRM is down. **The demo must not die because a container fell over.**
5. `POST /rides/quote`: signed, 5-minute `quote_id` encoding pickup, dropoff, distance, fare, and mode. Returns both exclusive and corridor prices.
6. Fare engine, deterministic and explainable in one sentence:
   ```
   exclusive = base + (per_km × km) + (per_min × min), clamped to [minimum_fare, ceiling]
   corridor  = 0.62 × exclusive_rate applied to that passenger's own travelled distance
   ```
   Configuration in one table/config object. Round to the nearest 50 XAF — people pay in coins.

**Security requirements**
- Sign `quote_id` (HMAC) and verify on ride creation; a client-supplied fare is never accepted (I2).
- Service-area polygon check: reject dropoffs outside the served bounding region with 422.
- Rate-limit `/places/search` (it is a database-heavy unauthenticated-adjacent endpoint).
- Cap `limit`; paginate; never allow an unbounded result set.
- Sanitise the search term before it reaches `to_tsquery` — parameterise, never interpolate.

**Test harness to build**
- `scripts/geo_eval.py` — a fixture file of ~40 realistic queries ("warda", "carefour warda", "total nsimeyong", "poste centrale", "mokolo market", "obili") with expected landmark IDs; prints a hit-rate. **This number is a slide.**
- A one-page HTML map (Leaflet, single file) that shows the gazetteer and lets you type a query and see what resolves. Testing tool, not product.

**Acceptance check**
```
python scripts/geo_eval.py     # expect ≥ 85% top-3 hit rate on the fixture set
curl -X POST .../rides/quote -d '{...}' | jq '.fare_xaf, .corridor_fare_xaf'
# expect: stable, sane XAF values; corridor < exclusive; ends in 00 or 50
```

**DO NOT BUILD:** traffic prediction (you have no historical data — faking it will be caught), surge pricing beyond a config multiplier, isochrones, multi-city support beyond Yaoundé.

---

## PHASE 3 — Ride lifecycle and matching
**Budget: H15 → H23 (8 hours). Largest block. This is the spine.**

**Objective:** the complete ride state machine with atomic driver claiming and object-level authorization everywhere.

**Deliverables**
1. Migration: `rides`, `ride_events`, `ride_traces` with all constraints from §5, including the partial unique index preventing two live rides per passenger.
2. `POST /rides` — validates `quote_id`, re-derives the fare server-side, generates a 4-digit PIN, stores `pin_hash`, honours `Idempotency-Key` (I8).
3. Matching service, wave-based:
   - wave 1: `ST_DWithin` 2 km, filtered by seat count and capability requirements, ordered by distance
   - wave 2 at +15 s: 4 km
   - wave 3 at +30 s: 6 km
   - no match by +60 s → `expired`
   - Single query per wave. **No per-driver loop.**
4. **Atomic driver claim.** Accept is a transaction: verify the offer is still open, verify no live ride for that driver, set `rides.driver_id`, update presence. Race must resolve to exactly one winner; the loser gets `409 OFFER_TAKEN`.
5. Full state machine with transitions validated by a table, not by scattered `if` statements. Illegal transitions → `409`.
6. **`ride_events` written on every transition** (I7).
7. `require_ride_participant` dependency — **one implementation, applied to every ride-scoped route** (I1).

**Security requirements**
- I1 enforced by dependency. Write a test that enumerates every ride-scoped route and asserts a third-party token gets 404 on each. Automate it — this is exactly the check that gets skipped manually.
- PIN: hashed, 5 attempts then the ride requires support intervention, never returned to the driver.
- Idempotency keys scoped per-user and expired after 24 h.
- `SELECT ... FOR UPDATE` on the claim path; keep the transaction short.

**Test harness to build**
- `scripts/ride_flow.py` — drives a full lifecycle end to end via HTTP.
- `scripts/race_test.py` — fires N concurrent accepts on one offer; **asserts exactly one 200 and N−1 409s.** Run it; paste the output.
- `scripts/idor_sweep.py` — enumerates ride routes with a foreign token; asserts 404 on all.

**Acceptance check**
```
python scripts/ride_flow.py    # requested → completed, all events logged
python scripts/race_test.py -n 20   # expect exactly 1 success
python scripts/idor_sweep.py   # expect 0 leaks
```

**DO NOT BUILD:** corridor matching (Phase 6), driver preference learning, surge zones, scheduled rides.

---

## PHASE 4 — Realtime tracking and the driver simulator
**Budget: H23 → H28 (5 hours).**

**Objective:** live tracking that survives a demo on a bad network, and the simulator that makes a solo live demo possible at all.

**Deliverables**
1. `WS /ws/driver` and `WS /ws/passenger` with an in-memory connection registry behind a `LocationSink` interface (the Redis-pub/sub seam you name to the jury).
2. Driver location ingest: validate, plausibility-check, persist to `ride_traces`, fan out to the one subscribed passenger.
3. **Plausibility filter** — the trace is the fare's source of truth, so it must be defended: reject implied speed > 150 km/h, reject accuracy > 100 m, reject non-monotonic timestamps, reject teleport jumps. **Persist rejected points with `rejected = true`** — deleting them destroys forensic value.
4. Heartbeat every 20 s; drop dead connections; reconnect resumes from last known state.
5. **`POST /dev/simulate-driver`** (dev-only, behind an env flag): walks a synthetic driver along a polyline at a configurable speed, emitting realistic location frames. **Without this, you cannot demo tracking without two phones and a second person.**
6. Seeder: 8–12 drivers with varied vehicles and capability flags placed around Yaoundé.

**Security requirements**
- Authenticate WebSockets on connect; **never accept the token in the query string.**
- Reject a location frame from a driver with no active ride.
- Enforce I4 in the fan-out layer: a passenger receives driver location only for their own ride, only between `accepted` and `completed`.
- Inbound frame rate limit: 1 per 2 s per connection; disconnect abusers.
- Cap WebSocket message size.

**Test harness to build**
- `tools/tracking_dashboard.html` — a single-file Leaflet page that connects to the passenger socket and renders the moving driver. **This is your demo surface for tracking if the mobile app is not ready.** Build it deliberately; it may end up on screen in front of the jury.
- `scripts/spoof_test.py` — sends teleporting and impossible-speed points; asserts they are rejected and flagged.

**Acceptance check**
```
POST /dev/simulate-driver  → open tools/tracking_dashboard.html → the marker moves smoothly
python scripts/spoof_test.py   # expect all impossible points rejected=true, fare unaffected
```

**DO NOT BUILD:** Redis pub/sub, horizontal scaling, push notifications, background location on the client.

---

## PHASE 5 — Trust and safety
**Budget: H28 → H36 (8 hours). This is where the jury story is won.**

**Objective:** the safety layer, built as real enforcement rather than as UI claims.

**Deliverables**

**5.1 Ride PIN verification (~1 h)** — `POST /rides/{id}/start` requires the 4-digit PIN. Passenger reads it aloud; driver enters it. Solves impersonation at pickup. *Note in `ARCHITECTURE.md`: BLE phone-to-phone proximity was evaluated and rejected — proximity is not identity (a raw broadcast can be relayed or replayed), and doing it properly requires a short-lived HMAC over `ride_id + timestamp` under a per-ride key. The PIN delivers the same security property today; the HMAC beacon is the documented next step.*

**5.2 Trip share link (~1.5 h)** — `POST /rides/{id}/share` mints a signed, short-lived, revocable token. `GET /share/{token}` and `WS /ws/share/{token}` expose the strict subset from §6. **Highest safety value per hour of work in the entire build.**

**5.3 Cancellation ledger (~3 h)** — the economically real feature.
- Free cancel before `accepted`, or within 30 s of `accepted`.
- After that, a fee accrues as a `ledger_entries` row and **must be settled before the next booking** — a debt ledger, not a wallet. Wallet pre-load kills conversion in a cash market; a debt ledger needs no money movement to demo.
- **Anti-abuse, and say this out loud in the pitch:** a driver could accept and idle to farm compensation. So driver compensation only pays out if `ride_traces` shows the driver actually moved toward the pickup. *Stating that you modelled who attacks your own incentive system is the single most differentiating thing you can say to a jury — almost no hackathon team does it.*
- Symmetric: drivers incur fees for late cancellation too, or they will cherry-pick and dump cheap fares.
- Graduated enforcement tied to §4.2: warn → restrict → suspend.

**5.4 SOS and incident reports (~1.5 h)** — `POST /rides/{id}/sos` seals an immutable snapshot: trace summary, driver and vehicle identifiers, timestamps, both parties. This is the evidence layer that audio recording would later plug into.

**5.5 Canned messages (~1 h)** — `POST /rides/{id}/messages` with a fixed template set, delivered over the existing WebSocket. Replaces phone contact entirely (I3), works on bad networks, translates trivially, and serves deaf and hard-of-hearing users.

**Security requirements**
- Share tokens: single-purpose, expiring, revocable, and rate-limited on the public endpoint. Location in the share view is coarse until `in_progress`.
- SOS must succeed even under partial system degradation — it is the one path that gets its own error handling and its own alert.
- Incident snapshots are immutable once written.
- Message templates are an enum; free text is never accepted on that endpoint.
- Ledger writes are transactional and append-only; corrections are new `adjustment` rows, never mutations.

**Test harness to build**
- `scripts/cancel_matrix.py` — cancellation at every state × both actors × moved/not-moved; asserts the correct fee and payout in every cell. This is the table you show a judge.
- `tools/share_view.html` — renders the public share link. Doubles as a demo asset.

**Acceptance check**
```
python scripts/cancel_matrix.py    # every cell matches the documented policy
# open a share link in a private window: shows location, hides identity/fare/phone
```

**DO NOT BUILD:** continuous audio/video recording. *The correct design — recorded on-device, encrypted with a random data key, that key wrapped with a server-held public key, uploaded only when a report is filed, auto-purged after N days, so that nobody at the company can casually listen — belongs in `ARCHITECTURE.md` as designed-not-built. Describing it earns most of the credit at none of the cost, and it is what separates trust infrastructure from surveillance.*

---

## PHASE 6 — Accessibility, corridor rides, payment abstraction
**Budget: H36 → H42 (6 hours). Cut from the bottom of this list first if you are behind.**

**6.1 Accessibility matching (~1.5 h) — do this one first; it is on the rubric and most teams will skip it entirely.**
- Match `users.requires_*` against `vehicles.has_*` in the Phase 3 matching query. One extra `WHERE` clause.
- `GET /vehicles/capabilities` for client filter UI.
- **French TTS arrival announcement strings** returned by the API — satisfies "intelligent voice announcements" from the brief and serves low-literacy and low-vision users at the same time.
- **Restate I9 in code comments at the model:** these are vehicle capability requirements, not medical facts about a person. That is both the legally required framing under Law 2024/017 and the more respectful one.

**6.2 Corridor rides (~3 h) — Bet 2. Cut this before accessibility, not after.**
- `POST /rides` with `mode=corridor` and `seats`.
- Matching: find an in-progress corridor ride whose `route_geom` contains both the new pickup and dropoff within a tolerance (`ST_DWithin` against the route line), with `seats_free >= seats`.
- **Detour cap: reject if the added distance exceeds 8% or 4 minutes.** Without a cap, the first passenger gets a tour of the city.
- **Driver consent required** for each additional pickup — never auto-append.
- Fare: each passenger pays their own travelled leg at 0.62× the exclusive per-km rate. Sum exceeds a single exclusive fare. Defensible in one sentence; do not get clever.
- Write `corridor_legs` rows for the audit trail.

**6.3 Payment abstraction (~1.5 h)**
- `PaymentProvider` interface: `initiate()`, `status()`, `refund()`.
- `MockPaymentProvider` that works end to end and is the demo default.
- `MtnMoMoProvider` / `OrangeMoneyProvider` **stubs only.** Wire real sandbox credentials only if you are ahead at H40. Verify early whether the sandbox will actually issue credentials in time — that is the part that silently blocks and eats eight hours.
- Cash-on-completion is the default settlement path. **It is the honest default for this market** and should be presented as a deliberate choice, not a limitation.
- If you want the subscription story: a **prepaid weekly commuter pass** (N trips on a fixed home↔work corridor at a discount) is the right monetisation. It is predictable revenue, it has obvious perceived value, it locks in the corridor feature, and its prepaid balance solves cancellation-fee enforcement from 5.3. *Do not build a "pay 500 XAF/week for personalisation" subscription: it has no training data at demo time, and charging users to remove friction does not sell in a price-sensitive market. Preferences are free to store and should be given away.*

**Security requirements**
- Corridor: verify the joining passenger cannot read the existing passengers' identities or destinations. A shared ride must not become a data leak.
- Payment: idempotency on `initiate()`; never log provider credentials or full transaction payloads; verify webhook signatures if any webhook is wired.
- Accessibility flags are user-writable but never derived, inferred, or exposed to the driver as anything other than a vehicle requirement.

**Acceptance check**
```
python scripts/corridor_flow.py
# passenger A books corridor → B joins mid-route → both fares < exclusive,
# sum > single exclusive fare, detour within cap, B cannot read A's dropoff
```

**DO NOT BUILD:** dynamic corridor re-optimisation, more than 3 legs per corridor ride, real MoMo integration unless demonstrably ahead of schedule.

---

## PHASE 7 — Harden, seed, document, rehearse
**Budget: H42 → H48 (6 hours). Code freeze at H46. The last two hours are rehearsal, not coding.**

**Deliverables**
1. **Full seed script**: 500 landmarks, 12 drivers with varied capability flags, 5 passengers, 20 historical rides for a plausible-looking history screen. One command, idempotent.
2. **`THREAT_MODEL.md` completed** — assets, actors, trust boundaries, the §4.3 mitigation table, accepted risks, and what you would do with more time. *One page. Thirty minutes. It is the artifact that makes "security engineer" credible to a jury rather than a claim.*
3. **`ARCHITECTURE.md` completed** — diagram, the §3 tradeoff table, the state machine, the designed-not-built list (BLE HMAC beacon, encrypted incident audio, Redis fan-out, Rust location ingest), and the Law 2024/017 compliance posture from §4.1.
4. Rate limits applied to **every** endpoint, not just auth.
5. Dependency audit (`pip-audit`), secret scan of git history, `DEBUG=false`, verbose errors off in production.
6. Postman/Bruno collection exported for the jury to poke at.
7. **Network degradation rehearsal**: throttle to 3G, kill OSRM mid-ride, drop the WebSocket mid-trip. Every one of these must degrade visibly and recover — never an infinite spinner. *The brief says "Cameroonian realities" four times; a demo that survives you toggling the network is a stronger statement than any slide.*
8. **Rehearse the §8 demo script end to end at least twice.** Time it.

**Acceptance check**
```
docker compose down -v && docker compose up -d && ./scripts/seed.sh && ./scripts/smoke.sh
# a cold machine reaches a fully seeded, demo-ready system with one sequence
```

---

## 8. Demo script (rehearse this; build backwards from it)

The hackathon is online, so this is a screen share or a recording. Rehearse for 5 minutes.

1. **The problem.** "Ask anyone in Yaoundé for an address. They will name a carrefour." Type `warda` → landmarks resolve with `match_type: exact_alias`. *(Bet 1)*
2. **Book exclusive.** Quote appears with a transparent breakdown. Ride created with an idempotency key.
3. **Match.** Wave-based matching claims a driver. Show `race_test.py` output: 20 concurrent accepts, exactly one winner.
4. **Track.** Driver simulator moves; passenger view updates live.
5. **Safety.** Share the trip link, open it in a private window — location visible, identity and fare and phone not. Then the PIN at pickup.
6. **Trust economics.** Cancel after the driver has moved: fee accrues to the ledger. Then show the anti-abuse case — a driver who accepted and idled gets no payout, because the trace proves no movement. *This is the moment. Say the word "attacker" out loud.*
7. **Corridor.** Second passenger joins a live route. Both pay less; driver earns more. "This is the transport model that already exists here." *(Bet 2)*
8. **Accessibility.** Book with `requires_ramp` — the matching pool shrinks to capable vehicles only. Note that no medical data is stored, and why that is a legal requirement under Law 2024/017 and not just a preference.
9. **Close on architecture.** `ARCHITECTURE.md`, `THREAT_MODEL.md`, the data-residency posture, and the designed-not-built list.

---

## 9. Cut order if you fall behind

Cut strictly from the bottom up. Do not cut out of order.

```
8. Corridor rides                  ← cut first
7. Payment provider stubs
6. Canned messages
5. Incident reports (keep SOS)
4. Cancellation ledger
3. Trip share link
2. Accessibility matching
1. Ride PIN
─────────────────────────────────
   NEVER CUT: auth, landmark search, quote, ride lifecycle,
   matching, realtime tracking, driver simulator,
   THREAT_MODEL.md, ARCHITECTURE.md
```

The two documents stay above the cut line. They cost thirty minutes each and they are what make the rest of it legible to a jury.

---

## 10. Repo hygiene (graded, whether or not anyone says so)

The brief requires every team member to explain the architecture. That means the repository is evidence.

- Real commits from real accounts, throughout the 48 hours. Four commits titled "update" from one account is a visible red flag.
- Conventional commit messages (`feat:`, `fix:`, `sec:`).
- `sec:` prefix for security work — it makes the security contribution greppable and visible.
- `README.md` with the architecture diagram at the top, quickstart below.
- `openapi.json` committed and current.
- No secrets, ever, including in history.
