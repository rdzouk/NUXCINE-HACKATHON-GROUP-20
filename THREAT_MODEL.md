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

## What we would do next, with more time

In priority order: Redis pub/sub for socket fan-out; the HMAC beacon replacing
the PIN; encrypted incident audio as designed above; rewriting location ingest
in Rust, which is the only path where per-message cost matters at ten thousand
concurrent drivers and is already cleanly isolated behind `LocationSink`;
and a formal data-retention schedule with automated purge, which Law 2024/017
makes a requirement rather than an improvement.
