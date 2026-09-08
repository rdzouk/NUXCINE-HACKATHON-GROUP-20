# Threat model

Status: Phases 0 and 1. The actor and mitigation tables are complete; the
accepted-risk register grows as phases land and is finalised in Phase 7.

## Assets, in the order an attacker would want them

1. **Live location of a specific person.** The most sensitive field in the
   system. A passenger's pickup point plus a timestamp is enough to know where
   someone lives and when they leave.
2. **Trip history.** Where somebody habitually goes, and with whom.
3. **Phone numbers.** The identity primitive here, and the vector for
   harassment and off-app coercion.
4. **KYC documents.** CNI and licence references for drivers.
5. **Fare and ledger integrity.** Money, and the trust that the price is real.
6. **The audit trail.** `ride_events` and `ride_traces` are the evidence layer
   that safety claims, disputes and breach notification all rest on.

## Trust boundaries

| Boundary | Crossed by | Assumption |
|---|---|---|
| Public internet to edge | anyone | nothing is trusted |
| Edge to API | cloudflared, one hop | `X-Forwarded-*` trusted from this hop only |
| API to database | app role | app role holds no UPDATE or DELETE on `ride_events` |
| Authenticated caller to a ride | JWT | authorization is per object, not per role |
| Share-link holder to a ride | signed token | strict subset, its own schema, expiring |

Both clients are assumed hostile. Every field a client sends is attacker
controlled, including GPS.

## Actors and mitigations

| Actor | Capability | Primary mitigation | Lands |
|---|---|---|---|
| Malicious passenger | Patched client, forged GPS, fake bookings, harassment | Server-side fare from a server-held trace (I2); phone verification; cancellation ledger; no phone exposure (I3) | 1, 3, 5 |
| Malicious driver | Patched client, fare inflation, fee farming, impersonation | Server-held trace; cancellation payout gated on proven movement toward pickup; ride PIN; KYC gate on going online | 1, 3, 5 |
| Third party at pickup | Poses as the assigned driver | Ride PIN, driver photo, vehicle photo and plate shown before arrival | 5 |
| Credential attacker | OTP brute force, SMS pumping, token theft | Argon2-hashed OTP codes, attempt cap then burn; layered Redis token buckets per phone, per IP, and a global circuit breaker; 15-minute access token with rotating refresh and reuse detection | 1 |
| Curious insider | Reads location history or contact details | Field-level access control in the serializer; admin reads audited; KYC fields encrypted at rest | 1, 5, 7 |
| Network attacker | Intercept, replay | TLS everywhere; idempotency keys; no sensitive data in URLs or query strings, including WebSocket auth | 0, 3 |
| Share-link recipient | Holds a URL that was forwarded onward | Single purpose, expiring, revocable; coarse location until `in_progress`; no identity, fare or PIN in the payload | 5 |

## Attacks this design takes seriously that a hackathon build usually does not

**SMS pumping.** An unrated OTP endpoint is a cash machine that bills us and
routes revenue to premium-rate numbers. This is actively exploited, not
theoretical. Three independent layers, because any one of them alone fails:
per-phone, per-IP, and a global circuit breaker that halts sending outright when
system-wide volume crosses a threshold.

**Attacking our own incentive system.** A driver can accept a ride and idle to
farm cancellation compensation. So compensation pays out only when the trace
shows real movement toward the pickup. We modelled the attacker who is a
legitimate user of our own economics, not only the one outside the fence.

**IDOR.** The characteristic vulnerability of ride-hailing APIs. Object-level
authorization is one shared dependency applied to every ride-scoped route, never
a per-handler check, because per-handler checks miss one. Phase 3 adds a test
that enumerates every ride-scoped route and asserts a third-party token gets 404
on each, so the check cannot rot.

**Account enumeration.** `POST /auth/otp/request` returns the same 202 body for
a registered and an unregistered number, and Phase 1 makes it take the same time.

**Log injection.** An inbound `X-Request-ID` that is not a UUID is discarded
rather than echoed, so a client cannot forge lines in the structured logs.

**Phone numbers in logs.** Auth logs are the most-read logs during any
incident, so a plaintext phone column in them is a standing leak that nobody
notices. Every log line that references a number writes a keyed HMAC of it
instead. Keyed rather than a plain hash because the Cameroonian mobile keyspace
is small enough to enumerate exhaustively against an unkeyed digest in seconds.

## Legal constraints as design constraints

Cameroon's Law No. 2024/017, in force since 23 December 2024 with a compliance
deadline of 23 June 2026 that has already passed:

- **Prohibited categories.** Religion, philosophy, trade-union or political
  opinion, racial or ethnic origin, linguistic or regional origin, genetics,
  health and biometrics may not be processed. Consequence: accessibility is
  stored as vehicle capability requirements and never as a medical fact. This
  also rules out face-match driver verification.
- **Cross-border transfer** requires prior authorisation. Consequence: data
  residency is an architectural decision made up front, not a later migration.
- **Breach notification without delay**, plus an annual security report.
  Consequence: `ride_events` and the structured request-correlated logs are
  compliance artifacts, not gold-plating.
- **Fines of 5 to 50 million FCFA** for processing without authorisation.
  Consequence: we say "designed for compliance", never "compliant". We do not
  claim a legal status we do not hold.

On phone-as-identity: SIM registration has been compulsory since the
Prime Ministerial decree of 3 September 2015, requires a CNI, and caps an
individual at three SIMs per network. That makes a phone ban meaningfully
stronger here than in most markets, but enforcement is leaky and the regulator
has found many SIMs registered against one ID. Phone is treated as a strong
signal, never as proof of uniqueness. Passengers are gated on a verified phone
only; hard ID-gating would exclude the many legitimate users who lack a birth
certificate and therefore lack a CNI. Drivers, who are the higher-risk party and
already professionally licensed, carry full KYC.

## Phase 7 hardening, with the evidence

Run `./scripts/security_audit.sh`. It is a script rather than a checklist
because a checklist is a claim and a script is evidence.

**Every endpoint is rate limited, not just the ones somebody remembered.**
Phase 1 limited OTP, Phase 2 places and quotes, Phase 5 the share view. Ride
creation, every state transition, the driver's offer list, messages, SOS and
KYC uploads had no ceiling at all. A middleware floor now covers the whole
surface, keyed by user id with an IP fallback: keying only by IP would put a
whole carrier's NAT pool into one bucket, which here is a large fraction of
the users. The tighter per-endpoint limits stay, because they express things
this one cannot, such as three OTPs per phone per hour.

**Failing open and failing closed are different decisions, and both are
tested.** Losing Redis must not stop somebody reading their ride, so the
general limiter fails open. Losing Redis *must* stop OTP sending, because that
limiter is the only thing between us and an unbounded SMS bill, so that one
fails closed. `scripts/degradation_test.py` kills Redis and asserts both.

**Failing open has to be fast, or it is not failing open.** A limiter that
waits for a socket timeout before allowing the request adds that timeout to
every request, turning a Redis blip into a site-wide latency collapse worse
than the abuse being prevented. A breaker inside `RateLimiter` dials Redis once
per cooldown and short-circuits the rest. This was found by measurement, not
design: the drill showed 6.4 seconds per request while the breaker sat in the
middleware only, because `/places/search` consults its own limiter
independently. One breaker underneath every limit is the only version that
holds.

**Dependency and secret audit.** `pip-audit` reports no known vulnerabilities
in the locked dependencies. `gitleaks` reports no secrets in git history.
`.env` is gitignored and untracked, which the audit asserts rather than
assumes.

One caution worth recording, because it produced a wrong answer that looked
right: **do not run gitleaks through `docker run -v $(pwd):/repo`** on Docker
Desktop with WSL. The bind mount can resolve to the *Windows* working
directory rather than the Linux one. The first scan reported four leaks that
belonged to an entirely unrelated repository, and it looked exactly like a real
finding. The audit script uses a native binary and prints the path and git
remote it is actually scanning.

**Production guards, read out of the code rather than asserted in prose:** API
docs and the OpenAPI schema are withheld in production; the driver simulator
requires DEBUG *and* a non-production environment, so the route does not exist
rather than being guarded inside a handler; the console SMS sender refuses to
run in production; test phone numbers are refused in production; a wildcard
CORS origin and a weak signing secret are both rejected at boot rather than in
review. Unhandled exceptions return a fixed envelope and never their own text,
in every environment.

### Clock skew, and the failure it produced

Access tokens carry `nbf`, and PyJWT enforces it. When a clock moves backward
under a live token, that token's `nbf` lands in the future and PyJWT raises
`ImmatureSignatureError`, which the error map turns into **INVALID_TOKEN**.
That is the same code returned for a bad signature, so the symptom reads as a
forged token rather than as a clock, and it appears on a token that was
working seconds earlier.

This was not hypothetical. During Phase 7 the development host's wall clock
was oscillating by 57 seconds, seven jumps in three minutes, measured against
a monotonic reference. Suites failed intermittently with INVALID_TOKEN, never
reproduced in isolation, and the user row was intact every time, which ruled
out the obvious explanation of something deleting accounts.

`decode_access_token` now allows 30 seconds of leeway on the time claims. RFC
7519 provides for exactly this, two API instances behind a load balancer never
agree on the second, and without it a token minted by one is refused by the
other for as long as they differ. The leeway is small against a 900-second
token, it is bounded by a test, and expiry past it is still refused.

Leeway is the right answer for ordinary skew between machines. It is **not** a
fix for a host whose clock is jumping by a minute, and it is not treated as
one: that host needs its clock repaired.

## Accepted risks

Recorded here rather than fixed, with the mitigation that makes each tolerable
for a 48-hour build. Nothing is skipped silently.

| Risk | Why accepted | Mitigation in place | Real fix |
|---|---|---|---|
| Single-process in-memory WebSocket registry | Horizontal scale is not demonstrable at demo scale and Redis pub/sub costs hours | Isolated behind a `LocationSink` interface, so the swap is one implementation | Redis pub/sub fan-out |
| Console SMS sender | Real gateway credentials are not in hand, and integrating one blind burns hours that Phase 2 needs | `SmsSender` is an interface; the console implementation logs the code in development only | Real gateway behind the same interface |
| No continuous audio or video recording | Deliberately not built. Recording infrastructure without the key management is surveillance, not safety | SOS seals an immutable evidence snapshot that a recording would later attach to | On-device recording, encrypted with a random data key, that key wrapped with a server-held public key, uploaded only when a report is filed, auto-purged, so nobody at the company can casually listen |
| Proximity is not identity | BLE phone-to-phone was evaluated and rejected; a raw broadcast can be relayed or replayed | Ride PIN delivers the same security property today | Short-lived HMAC over `ride_id` plus timestamp under a per-ride key |
| Quick-tunnel hostname is regenerated on restart | No domain was in hand at H0 | Real TLS regardless; the stack stays up for the event | Named tunnel or a VPS with a stable A record |
| KYC files are not stored, only encrypted references | Object storage is a Phase 7 concern, and the KYC state machine works without the file | The reference is AES-GCM encrypted and bound to the driver id; a CNI is kept only as a keyed hash | Encrypted object storage with signed, expiring read URLs |
| Access tokens are not revocable before expiry | A denylist costs a Redis lookup on every request, and the window is bounded at 15 minutes | `get_current_user` reloads the user from the database on every request, so a suspension bites immediately even while the token is still validly signed | `jti` denylist in Redis, keyed by the claim already in the token |
| Roles are granted only by direct database access | Having no self-service escalation path is the point; an admin-granting endpoint is the first thing an attacker looks for | Documented, and the Phase 7 seed script is the supported way to create the first admin | A provisioning tool with its own audit trail |
| The per-IP rate limit trusts one proxy hop | uvicorn runs with `--proxy-headers` behind Caddy, itself behind the tunnel | If the service is ever exposed without that proxy, the per-IP layer becomes decorative; the global circuit breaker exists partly to survive exactly that misconfiguration | Explicit trusted-proxy allow-list rather than a hop count |
| Service area is a bounding box, not a polygon | The served region is two cities and boundary data for a real polygon was not to hand | The box admits some unserved country between Yaounde and Douala. The cost is a ride request nobody can fill, not a safety issue | A polygon per city, checked with `ST_Contains` |
| OSM yielded only 3 tagged carrefours | OSM Cameroon does not tag them, which is precisely the gap Bet 1 exists to fill | Curation attaches the carrefour and bare-name forms people type to the **real OSM node** for that place, so no coordinate is invented. 44 of 63 known names matched; the other 19 stay absent rather than guessed | Survey the missing junctions, or contribute them upstream |
| Landmark positions are OSM node coordinates, not surveyed junction centres | A node tagged for a shop beside a junction sits within a block of it | A landmark is something you navigate *toward*; the driver covers the last 200 m visually. Nothing is presented as a surveyed position | Ground-truth the hundred most popular landmarks |
| Only nodes were extracted from OSM, not ways or areas | A country-wide node-location index exhausted this 5 GB box | A place mapped only as a building polygon is missed. The categories that matter here are nodes by convention, and the run still yielded 5454 landmarks | Extract on a larger machine, or clip the PBF first |
| Mapbox token ships in the browser bundle | I5 says map keys are proxied, but vector tiles sit on the render path and cannot afford an extra hop on a bad network. A Mapbox *public* token is designed to be published | Must be a `pk.` token and never `sk.`, URL-restricted in the Mapbox dashboard before the demo, scoped to styles and tiles only. Geocoding and routing do **not** use Mapbox: those are the gazetteer and OSRM, server-side, so no key is needed for them | Proxy tiles through the API, or self-host a style |
| The PIN is stored in plaintext alongside its hash | The passenger has to read it aloud at pickup and must still see it after an app restart, a lost signal or a reinstall | Never serialised for the driver or an admin; that decision lives in one function, `serialize_ride`, rather than in each handler. `ride_flow.py` asserts the driver's payload has `pin: null` | Encrypt the column at rest with the KYC key, decrypting only for the passenger's own read |
| The driver simulator can fabricate GPS for any ride | It is the only way to demonstrate live tracking without two phones, two SIMs and a second person driving on cue | The router is not registered unless `DEBUG` is on **and** the environment is not production, so the path does not exist on a real deployment rather than being guarded inside a handler. A parameterised test asserts both conditions | Strip it from the production image at build time |
| Realtime state is one in-process dictionary | Redis pub/sub adds a dependency, a failure mode and an ordering question to a demo with twenty connections | Behind the `LocationSink` interface, so the swap changes no caller. A second API process today would simply not see the first one's sockets, which is a scaling limit rather than a correctness bug | Redis pub/sub fan-out |
| The plausibility filter is tuned to catch cheap forgery, not a careful attacker | Every threshold that catches a patient attacker also rejects a real driver, and a false rejection takes money from an honest person | Bounds sit well outside anything a car in Yaounde can do, so the common attacks (teleport, impossible speed, replayed timestamps) fail while real journeys pass. Rejected points are kept as evidence rather than discarded | Corroborate the trace against the routed path and against road-network snapping |
| Corridor capacity is a seat count, not a seat map | Which physical seat somebody sits in is not something the server can know or verify, and modelling it would be a fiction that the driver has to correct in the car | `seats_free` is the declared capacity, and legs are counted against it in the same statement that selects the candidate, so a full car cannot be offered a joiner. Seats are held at the ask and released on a decline or a lapse | Driver-confirmed boarding, which is a person pressing a button, not a data model |
| The corridor detour is measured as offset from the driven line, not by re-routing | Re-routing each candidate turn by turn costs one OSRM call per candidate on the booking path, and the answer moves with traffic that we do not model | Twice the sum of the two perpendicular offsets is a real distance the driver has to cover and cannot be gamed by the passenger, because both endpoints are already constrained to within 400 m of the line. The cap is checked before the driver is asked, so a passenger already aboard never pays for a bad match | Re-route the amended itinerary and compare against the committed one |
| The share socket polls the database rather than subscribing | Precision has to be recomputed per frame, and revocation has to bite within seconds rather than at the end of the trip. Subscribing to the tracking registry gives neither | A three-second server-side poll pushed over the socket, with frames sent only when something changed. Still strictly better for the viewer than the HTTP polling it replaces: no repeated TLS handshake and no token re-validation per request | Publish share updates onto the same fan-out that carries driver location, with precision applied per subscriber |
| Mobile money is a stub; settlement is cash | Sandbox onboarding for MTN MoMo and Orange Money silently blocks, and the build plan puts wiring it behind everything else | Cash on completion is the real default here and is a decision rather than a gap: the fare is charged to the ledger at completion, which is what makes the Phase 5 cancellation debt enforceable with no payment rails. The two providers raise rather than returning a plausible-looking decline, so nobody debugs a provider that was never contacted | Real credentials behind the same `PaymentProvider` interface, with signed webhooks |
| The acceptance suite is not reliable back to back on a small box | Every login costs two argon2 hashes at 32 MiB, deliberately, because a four-digit OTP is only safe when the hash is memory-hard. Fifteen suites in sequence on a 5 GB development box queue behind each other, and a suite that passes comfortably alone can hit the API's own fifteen-second timeout | Each suite passes on its own, and the failures move between runs, which is the signature of contention rather than a defect. `ACCEPTANCE_SETTLE_S` spaces the suites out. The harnesses were made idempotent so a rerun is clean, and `ride_flow` now proves its token immediately after login so a stale-session failure names its own cause instead of surfacing three calls later as an unexplained 401 | Run the suites on a machine with headroom, or in CI where each gets a fresh stack. Never weaken the hash or lengthen the timeout to make the suite green: both would be optimising the measurement rather than the system |

## What we would do next, with more time

In priority order: Redis pub/sub for socket fan-out; the HMAC beacon replacing
the PIN; encrypted incident audio as designed above; rewriting location ingest
in Rust, which is the only path where per-message cost matters at ten thousand
concurrent drivers and is already cleanly isolated behind `LocationSink`;
and a formal data-retention schedule with automated purge, which Law 2024/017
makes a requirement rather than an improvement.
