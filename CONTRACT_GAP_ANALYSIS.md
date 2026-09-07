# VORA — Design ↔ API Contract Gap Analysis

**Source:** `VORA-HACKATHON.zip` — Figma Make export, React 19 + Vite + Tailwind v4, 32 screens.
**Compared against:** `VORA_BACKEND_BUILD_PLAN.md` §5 (data model) and §6 (API contract).
**Status:** must be resolved before the §6 contract freezes at the end of Phase 0.

Screens inventoried: 5 auth · 11 passenger · 10 driver · 6 admin (desktop).

---

## A. HARD CONFLICTS — design and plan disagree. Decide now.

### A1. Password authentication vs phone OTP
**Design:** `screens/auth.tsx` — login has `Phone number` + `Password`; signup has `Full name` + `Phone number` + `Password`.
**Plan:** §6 is phone + OTP. No passwords anywhere. There is no OTP entry screen among the 32.

**Resolution — keep OTP, change the design.** Passwords in this market mean password reset flows, credential stuffing, and a second secret to store. OTP is both the market-correct primitive and the more secure one, and Phase 1 is already built around it.

Design changes needed:
- Remove the password field from login and signup.
- Add one screen: **OTP entry** — 4-digit boxes, resend countdown, "code sent to +237 6XX XXX XXX".
- Signup becomes: name + phone → OTP → done.

### A2. "📞 Call" button vs invariant I3
**Design:** `PassengerDriverEnRouteScreen` has `💬 Message` and `📞 Call` side by side.
**Plan:** I3 — the API never returns a counterparty's phone number, in any response, at any state. A Call button requires exactly that.

**Resolution — keep Message, repurpose Call.** Masked calling through a telco relay is the correct fix and is not achievable in 48 hours. Options, in order of preference:
1. Replace `📞 Call` with `🆘 Safety` (opens the SOS/share sheet). Better use of the space.
2. Keep the button but route it to support, not the driver.
3. Remove it and let Message take full width.

`💬 Message` maps cleanly onto Phase 5.5 canned messages — needs a template picker screen (4 fixed options, no free text).

*Note: `DriverProfileScreen` showing `Phone: +237 699 456 789` is the driver's own number on their own profile. That is fine and stays.*

### A3. Email field
**Design:** `PassengerProfileScreen` shows `Email: aminata.bello@email.cm`.
**Plan:** §5 `users` has no email column.

**Resolution:** add `email TEXT NULL` to `users`, or drop the row from the design. Nullable column is the cheaper option — one line, no design churn.

---

## B. DESIGN SHOWS IT, THE API DOESN'T RETURN IT

Each of these needs either a contract addition in Phase 0 or a design cut.

### B1. Ratings — **add to contract**
Stars appear on 6+ screens. `PassengerRideCompletedScreen` has "Rate your experience with Koffi", a 5-star control, and "Leave a comment". Profiles show "4.8 passenger rating" and drivers show "⭐ 4.9".

§5 has `drivers.rating_avg` but no ratings table, no passenger rating, and §6 has no rating endpoint.

```
ratings
  ride_id      UUID REFERENCES rides
  rater_id     UUID REFERENCES users
  ratee_id     UUID REFERENCES users
  score        SMALLINT NOT NULL CHECK (score BETWEEN 1 AND 5)
  comment      TEXT
  UNIQUE (ride_id, rater_id)          -- one rating per party per ride

users
  + rating_avg NUMERIC(3,2)
  + rides_count INT NOT NULL DEFAULT 0

POST /rides/{id}/rate  { score, comment? }  → 201
```
Only allowed when `status = completed`. Cheap: ~45 minutes total.

### B2. Notifications — **add a minimal contract**
Full `PassengerNotificationsScreen` with 5 items, read/unread state, "Mark all read", and an unread badge showing `3` on the home screen. Entirely absent from §6.

```
GET   /notifications?limit=&cursor=   → { items:[{id,title,body,created_at,read}], unread_count }
POST  /notifications/read             { ids[] | all: true }  → 204
```
Back it with a simple `notifications` table written by ride state transitions. Don't build push — in-app only.

### B3. Driver earnings and commission — **add to contract**
`DriverEndRideScreen` shows an explicit breakdown: fare collected 1 200 XAF, VORA commission (15%) −180 XAF, your earnings 1 020 XAF. `DriverDashboardScreen` shows today's stats: 7 rides, 8 400 XAF earned, 4.9 rating.

```
GET /driver/earnings?period=today|week   → { rides_count, gross_xaf, commission_xaf,
                                             net_xaf, rating_avg }
```
Add `commission_xaf` and `driver_net_xaf` to the ride completion response. The 15% rate goes in fare config alongside the per-km rates. `ledger_entries` already supports the double-sided write.

### B4. Human-readable ride reference — **add to schema**
Admin screens show `#VR-2091`, not UUIDs. A passenger cannot read a UUID aloud to support, and a jury will notice UUIDs in a support flow.

```
rides
  + reference TEXT UNIQUE NOT NULL    -- 'VR-2091', from a sequence
```
Return it on every ride response alongside `id`. Ten minutes, disproportionate polish.

### B5. Admin panel — **scope decision required**
Six desktop screens with real table columns:

| Screen | Columns |
|---|---|
| Dashboard | active rides · online drivers · total users; recent activity table |
| Users | name, role, joined, status, action |
| Drivers | name, vehicle, rating, status, action |
| Rides | id, passenger, driver, status, fare |
| Statistics | rides this month, XAF platform revenue, average rating |
| Reports | — |

§6 has zero admin endpoints. This is a second product surface and it is not in the phase budgets.

**Recommendation — build the minimum that Phase 1 and Phase 5 already need, cut the rest:**
```
GET  /admin/drivers?kyc_status=      → list
POST /admin/drivers/{id}/verify      → approve KYC     (Phase 1 already needs this)
POST /admin/drivers/{id}/reject
GET  /admin/rides?status=            → list
GET  /admin/incidents                → list            (Phase 5 already needs this)
GET  /admin/stats                    → the six counters
```
That is roughly 90 minutes because the queries are trivial, and it makes the KYC approval stub from Phase 1 into something real. Users management, reports, and per-user detail views: cut, or leave as static screens.

### B6. Support messaging — **cut or stub**
`PassengerSupportScreen` has phone/email/WhatsApp contact details (static, no backend) plus a free-text "Describe your issue" form.

Static contact info: keep, costs nothing. The form: either `POST /support/messages { body }` writing to a table nobody reads (15 minutes, honest), or make the button show a "we'll be in touch" confirmation. Do not build a ticketing system.

### B7. Promo codes — **cut**
Home screen: "20% off your next ride — code VORA20, expires 30 Sep 2026". Nothing in §5 or §6.

Promo logic is a real subsystem (redemption, per-user limits, expiry, fraud). Zero jury value against the innovation criterion. **Leave it as a static banner** — it looks fine and costs nothing. Do not wire it.

---

## C. THE PLAN HAS IT, NO SCREEN SHOWS IT

**This section matters more than section B.** Every item here is work you are budgeted to build that a jury will never see. Tell Gaetan today.

### C1. Ride PIN — Phase 5.1
No screen shows the 4-digit pickup PIN. Needs:
- **Passenger, driver-en-route screen:** the PIN displayed large, with "Give this code to your driver".
- **Driver, ride-accepted screen:** a 4-digit entry control before "Start ride".

Two small additions. Without them your anti-impersonation feature is invisible.

### C2. Corridor / shared rides — Phase 6.2, and Bet 2
Zero screens. The single biggest differentiator in the plan has no UI at all. Needs:
- **Booking:** a mode toggle (Exclusive / Shared) and a seats stepper (1–3).
- **Quote card:** both prices side by side — "Exclusive 1 200 XAF · Shared 780 XAF".
- **In-progress:** an indicator that another passenger is joining, with driver consent prompt on the driver side.

If this doesn't get designed, cut Phase 6.2 and reclaim three hours — an invisible feature is worth nothing.

### C3. Accessibility — Phase 6.1
Zero screens, and this is explicitly named in the brief as an innovation area. Needs:
- **Profile:** toggles for ramp, boot space, front seat, driver assistance, guide animal, text-only contact.
- **Booking:** an indicator that the search is filtered to capable vehicles, and an empty state for when none are available.

**Framing to give the designers verbatim:** these are *vehicle capability requirements*, never a medical condition or disability status. Label them "Vehicle needs", not "Accessibility needs" or anything implying a diagnosis. That is a legal requirement under Law 2024/017, which prohibits processing health data — not a style preference.

### C4. Landmark search results — Phase 2, and Bet 1
The home screen has a generic "Enter your destination" field and three recent trips. Nothing shows the landmark gazetteer doing its job.

Needs a **search results screen**: query text at top, results showing landmark name, quartier, and distance — "Carrefour Warda · Bastos · 1.2 km". This is where the demo's opening moment lives. Currently there is no screen for it.

### C5. Cancellation fee and outstanding balance — Phase 5.3
No screen shows a cancellation fee, a confirmation dialog warning of one, or an outstanding balance blocking a new booking. The whole trust-economics story is invisible. Needs:
- Cancel confirmation showing the fee and why.
- A blocking banner on Home when a balance is outstanding.

### C6. Public trip-share view — Phase 5.2
`DriverSafetyScreen` has "📤 Share this ride" (good), but there's no screen for what the recipient sees. That's a browser page, not an app screen — you can build it yourself as `tools/share_view.html` in Phase 5, no designer needed.

*Note: share is on the driver's safety screen but §6 scopes it to the passenger. Decide whether drivers can share too — trivial either way.*

---

## D. Accessibility audit of the design system

Measured WCAG contrast ratios from `src/tokens.ts`:

| Pair | Ratio | AA normal | AA large |
|---|---|---|---|
| text `#17212b` on surface | 16.29:1 | PASS | PASS |
| primary `#285e55` on surface | 7.44:1 | PASS | PASS |
| accent `#45756d` on surface | 5.23:1 | PASS | PASS |
| accent on muted `#f3f6f4` | 4.80:1 | PASS | PASS |
| danger `#c0392b` on surface | 5.44:1 | PASS | PASS |
| **placeholder `#17212b55` on surface** | **3.26:1** | **FAIL** | pass |
| **gold `#d4a017` on surface** | **2.38:1** | **FAIL** | FAIL |
| **border `#a2bbb3` on surface** | **2.04:1** | **FAIL** (needs 3:1 for UI components) | — |

The palette is well chosen — every primary text pair passes AA comfortably. Three fixes, each one line in `tokens.ts`:

1. **Placeholder text** (`${C.text}55`, used in the destination search) — darken to `77` opacity or use `C.accent`.
2. **Gold** — unusable for text at this value. Restrict to decorative fills, or darken to roughly `#8a6a0f`.
3. **Border** at 2.04:1 fails the 3:1 requirement for meaningful UI boundaries. Input field borders in particular should darken to about `#7d9a91`.

Other observations for the designers:
- Status is communicated by colored badges. Confirm the badge **text** always states the status ("Online", "Suspended") and never relies on color alone. From the code it does — good.
- Star ratings are emoji/shape only. They need an accessible label ("4.9 out of 5").
- Fonts are Georgia + Arial — system fonts, so no loading cost and no FOUT. Fine, deliberate, and worth saying so if asked.

---

## E. What to do, in order

**Before Phase 0 ends (contract freeze):**
1. Resolve A1, A2, A3 with Gaetan. These change the API shape.
2. Add B1 (ratings), B2 (notifications), B3 (earnings), B4 (reference) to §6 and §5.
3. Decide B5 (admin) scope. Recommend the six-endpoint minimum.
4. Cut B7 (promo). Confirm B6 (support) is a stub.

**Send to Gaetan today — the C-list:**
The five screens that make budgeted work visible: OTP entry, ride PIN (two placements), landmark search results, corridor booking toggle, accessibility toggles in profile, cancellation fee dialog. Order them by the demo script in §8 of the build plan — anything that doesn't appear in the demo can wait.

**Send to the mobile developer:**
`openapi.json` as soon as Phase 0 produces it. The prototype in this zip is a **web** app (`npm run dev`, Vite) and is a design reference, not the deliverable. Confirm who is building the actual mobile app and that they are coding against the contract, not against these screens.

**Repo:**
Commit this prototype under `ui/` or `design/`. Ensure `node_modules/` and `dist/` are gitignored — the zip is clean at 272 KB and should stay that way.
