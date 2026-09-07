# Frontend and backend integration

Written after merging `feature/map`, `feature/app-pages` and `DEVELOP` into the
backend branch. It records what already lines up, what does not, and the two
questions the frontend left open for the backend owner.

The headline: **the map feature was coded against the frozen contract and
matches it almost exactly.** `apiClient.js` already parses
`{ error: { code, message, details, request_id } }`, sends
`Authorization: Bearer`, and reads `match_type`, `quote_id`,
`corridor_fare_xaf` and `breakdown` under their real names. Freezing the
contract at Phase 0 and handing over `openapi.json` is what bought that.

## What already matches, no change needed

| Frontend call | Backend route | Status |
|---|---|---|
| `searchPlaces(query, near)` | `GET /places/search` | matches |
| `reverseGeocode(lat, lng)` | `GET /places/reverse` | matches |
| `getQuote(pickup, dropoff, seats, mode)` | `POST /rides/quote` | matches |
| error envelope parsing | every route | matches |
| `Authorization: Bearer` from `localStorage` | every authenticated route | matches |

`getQuote` reads `data.fare_xaf` and never recomputes a price, with a comment
citing I2. That is the invariant the whole quote-signing design exists to
protect, and the client honours it.

## Two mismatches to resolve

### 1. WebSocket authentication (their open question)

`features/map/hooks/useDriverLocation.js` says:

> browser WebSocket API doesn't support custom headers directly, coordinate
> with your backend owner on the actual first-frame token handshake

**Answer: use the first-frame handshake. It is already in the contract.**

The browser cannot set headers on a `WebSocket`, and the contract forbids the
token in a query string because query strings land in access logs, proxy logs
and browser history. So the contract specifies both: an `Authorization` header
*or* a first frame of type `auth`. Browsers take the second path.

```js
const ws = new WebSocket(`${import.meta.env.VITE_WS_BASE_URL}/ws/passenger`);
ws.onopen = () => ws.send(JSON.stringify({
  type: 'auth',
  token: localStorage.getItem('access_token'),
}));
```

The server replies with a `ready` frame once the token verifies, and closes the
socket if the first frame is anything else. `AuthFrame` and `ReadyFrame` are
already defined in `app/schemas/ws.py`; Phase 4 implements the handler.

### 2. The `driver_location` frame is nested, not flat

The hook currently reads `msg.lat`, `msg.lng`, `msg.heading`. The contract
nests them, because a location needs its own timestamp and the ride it belongs
to:

```json
{
  "type": "driver_location",
  "ride_id": "...",
  "location": {"lat": 3.87, "lng": 11.51, "heading": 145,
               "updated_at": "2026-09-07T02:31:00Z"},
  "eta_s": 240
}
```

The client change is one line:

```js
if (msg.type === 'driver_location') setPosition(msg.location);
```

Flattening it server-side was considered and rejected. `updated_at` is what
lets the client show a stale-location warning instead of a marker frozen at a
position the driver left four minutes ago, and `ride_id` is what lets one
socket carry more than one ride's updates without ambiguity.

## Mapbox and invariant I5

The frontend renders with Mapbox GL and needs `VITE_MAPBOX_TOKEN` in the
browser. I5 says map keys live server-side and are proxied.

**This is a real tension and it is being accepted deliberately, not overlooked.**
A Mapbox *public* token is designed to be published, and the mitigation is a
URL restriction on the token itself rather than secrecy. Proxying vector tiles
through the API would cost real work and add a hop on exactly the path that has
to stay fast on a bad network.

What must be true for this to stay acceptable:

- the token in `VITE_MAPBOX_TOKEN` is a **public** token (`pk.`), never a secret
  one (`sk.`)
- it carries a URL restriction in the Mapbox dashboard before the demo
- it is scoped to styles and tiles only

Recorded in `THREAT_MODEL.md` as an accepted risk. Geocoding and routing do
**not** go to Mapbox: those are the gazetteer and OSRM, server-side, which is
both the Bet 1 story and the reason no key is needed for them.

## One `.env`, two halves

Both halves read the repository-root `.env`. That is safe rather than sloppy:
Vite only exposes variables prefixed `VITE_` to the browser bundle, so the JWT
signing key, the database password and the KYC encryption key cannot reach a
client even during `npm run build`.

Keep it that way. A value that needs to reach the browser needs a server-side
proxy, not a rename.

## Structural notes from the merge

Three things worth tidying, none urgent:

**`app/` holds both packages.** `app/` is the Python package, and
`app/DevIndex.jsx`, `app/MockAuthContext.jsx` and `app/NotificationContext.jsx`
landed inside it. Python ignores them and the Docker build copies them
harmlessly, but the collision is confusing and `docker/api.Dockerfile` ships
three React files into the API image. Moving them to `src/app/` would settle it.

**The merge reverted two backend fixes**, both since restored: the half-up
rounding in `round_to_coins` (banker's rounding made a 25 XAF fare round to
zero) and the `.gitignore` entries for `.venv/`, `__pycache__/` and
`osrm-data/`. Without the second, `git status` was offering to commit 223 MB of
OSM data and a full virtualenv.

**`.env.example` was replaced rather than merged**, losing about thirty
documented backend variables. Restored, with the frontend section kept.

## Running both halves

```bash
./scripts/dev_up.sh          # api, postgres, redis, caddy, tunnel
npm install && npm run dev   # vite on :5173
```

`http://localhost:5173` is already in the backend's CORS allow-list. Point the
frontend at the API with `VITE_API_BASE_URL`; for a phone on the same network,
use the tunnel hostname rather than `localhost`.

---

## Phase 4: the WebSocket answer, now implemented

The question in `useDriverLocation.js` is answered and the server side is live.

### Working passenger socket

```js
const ws = new WebSocket(`${import.meta.env.VITE_WS_BASE_URL}/ws/passenger`);

ws.onopen = () => {
  // Browsers cannot set an Authorization header on a WebSocket, and the
  // contract forbids the token in a query string. The first frame is the path.
  ws.send(JSON.stringify({ type: 'auth', token: localStorage.getItem('access_token') }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'ready':
      // Reconnect resumes from here rather than from nothing: the server
      // reports the current ride and its status, so a dropped connection
      // does not blank the screen.
      setRide(msg.ride_id, msg.ride_status);
      break;

    case 'driver_location':
      // Nested, not flat. msg.location.updated_at is what lets you show a
      // "position is 40s old" warning instead of a marker frozen at a place
      // the driver left minutes ago.
      setPosition(msg.location);
      break;

    case 'ride_update':
      setStatus(msg.status);
      break;

    case 'ping':
      ws.send(JSON.stringify({ type: 'pong' }));
      break;

    case 'error':
      // Socket errors reuse the REST error codes, so one error map serves both.
      console.warn(msg.code, msg.message);
      break;
  }
};
```

The server pings every 20 s and drops a socket that misses two, so answering
`ping` with `pong` is required rather than optional.

Close code **1008** means the token was rejected: refresh and reconnect. Any
other close is a network problem and should back off rather than hammer.

### Demonstrating it without a driver

```bash
python scripts/tracking_demo.py
```

Creates a passenger and a driver, books and accepts a ride, starts the
simulator, and prints a passenger token. Paste that into
`tools/tracking_dashboard.html` and the marker moves along the real route.

The simulator is `POST /dev/simulate-driver`, which exists **only** when
`DEBUG` is on and the environment is not production. Do not build a feature
that depends on it.

### What the driver app sends

```js
ws.send(JSON.stringify({
  type: 'location',
  lat, lng, heading,
  accuracy_m,          // omit rather than guess; a wrong value gets rejected
  ts: new Date().toISOString(),
}));
```

At most one frame per two seconds; anything faster is dropped silently. Every
point runs through the plausibility filter, and a rejected one comes back as
`{type: 'location_rejected', reason}` rather than vanishing. Show that to the
driver: it usually means their phone's GPS is struggling, not that they did
anything wrong.
