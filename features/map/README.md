# VORA Map Feature

This folder is the reusable map toolbox for VORA. It owns Mapbox rendering, user location, place search, route requests, route drawing, driver markers, and the first version of distance/time/price presentation.

The feature is intentionally separate from ride-booking state. `feature/booking` should compose these pieces into the ride flow: searching, requesting, accepted, in progress, and completed.

## What This Branch Provides

The map feature supports the map-related requirements from the hackathon brief:

- Display a Mapbox map centered on a supplied coordinate.
- Track the passenger's browser geolocation.
- Search Cameroon locations with Mapbox Geocoding.
- Request a driving route between two coordinates.
- Return route geometry, distance, and duration.
- Draw a route line on a Mapbox map.
- Display passenger and driver markers.
- Estimate a price in FCFA from route distance.
- Fall back to a straight-line distance estimate when Directions fails.

This branch does not own ride requests, authentication, driver availability, or Supabase setup.

## Folder Structure

```text
features/map/
├── README.md
├── components/
│   ├── DriverMarker.jsx
│   ├── EtaPriceCard.jsx
│   ├── LocationMarker.jsx
│   ├── MapView.jsx
│   ├── PlaceSearch.jsx
│   └── RouteLayer.jsx
├── hooks/
│   ├── useDriverLocation.js
│   ├── useGeolocation.js
│   └── useRoute.js
├── services/
│   ├── directions.js
│   ├── geocoding.js
│   └── mapboxClient.js
└── utils/
    ├── distance.js
    └── priceEstimate.js
```

Import map functionality through the feature folder. Avoid making other feature branches depend on service internals unless the API below is insufficient.

## Running This Branch

The branch includes a small Vite preview shell so the Mapbox setup can be tested independently before it is integrated into booking.

From the repository root:

```bash
npm install
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`.

For a production build:

```bash
npm run build
npm run preview
```

### Environment

Create a local `.env` file at the repository root:

```env
VITE_MAPBOX_TOKEN=your_mapbox_public_token
```

`.env` is ignored by Git. Commit only `.env.example`, which documents the required variable without a secret.

### Required CSS Import

Mapbox's stylesheet is imported once in [main.jsx](../../main.jsx):

```js
import 'mapbox-gl/dist/mapbox-gl.css';
```

Without this import, the map can initialize but render blank or have broken controls and layout.

## Components

### `MapView.jsx`

Creates the Mapbox instance and renders its container.

Props:

- `center`: required object with `{ lat, lng }`.
- `children`: currently rendered inside the map container, but the Mapbox instance is not currently passed to children.

Example:

```jsx
<MapView center={{ lat: 3.848, lng: 11.5021 }} />
```

Important integration note: `MapView` keeps its map instance in a private ref. `LocationMarker`, `RouteLayer`, and `DriverMarker` expect a `map` prop, so those pieces cannot be composed fully until `MapView` exposes the instance through a callback, context, or another agreed API. Resolve this at the feature boundary before booking depends on live markers or routes.

### `LocationMarker.jsx`

Adds or updates the passenger marker and flies to the first known position.

Props:

- `map`: Mapbox map instance.
- `position`: `{ lat, lng }`.

The marker is removed on unmount.

### `PlaceSearch.jsx`

Search input with Mapbox autocomplete results. Use it separately for origin and destination.

Props:

- `label`: visible label and placeholder.
- `defaultValue`: optional location object; its `name` pre-fills the input.
- `onSelect`: receives `{ lat, lng, name }` when a result is selected.

The search starts after three characters and requests up to five Cameroon results.

### `RouteLayer.jsx`

Draws or updates a GeoJSON route line on an existing map instance.

Props:

- `map`: Mapbox map instance.
- `geometry`: GeoJSON geometry returned by `getRoute`.

The source id is `route-source` and the layer id is `route-layer`.

### `DriverMarker.jsx`

Adds or updates the driver's marker on an existing map instance.

Props:

- `map`: Mapbox map instance.
- `position`: `{ lat, lng }`.

The marker is removed on unmount. The current component does not provide driver simulation itself; position data comes from the parent or `useDriverLocation`.

### `EtaPriceCard.jsx`

Displays route distance, estimated duration, and estimated FCFA price.

Props:

- `route`: object returned by `useRoute`.
- `loading`: route request state.
- `error`: route error state.

It renders nothing until a route exists, and shows loading or fallback messaging while those states are active.

## Hooks

### `useGeolocation.js`

Wraps `navigator.geolocation.watchPosition` and returns:

```js
{ position, error }
```

`position` is either `null` or `{ lat, lng }`. The browser asks the user for location permission. The watcher is cleared on unmount.

### `useRoute.js`

Returns:

```js
{ route, loading, error, fetchRoute }
```

Call `fetchRoute(origin, destination)` with two `{ lat, lng }` objects. A successful route contains:

```js
{
  geometry,
  distanceKm,
  durationMin,
}
```

If Directions fails, the hook computes a haversine distance and rough duration (`distanceKm * 2`) so the caller still receives route data. The error state remains set so the UI can identify that the result is an estimate.

### `useDriverLocation.js`

Keeps driver data delivery independent from this feature:

```js
const position = useDriverLocation(rideId, subscribeFn);
```

`subscribeFn` is called as `subscribeFn(rideId, onPosition)` and should return an unsubscribe function. `feature/driver` can provide a Supabase Realtime adapter without changing this hook.

## Services

### `mapboxClient.js`

The central Mapbox client. It reads `import.meta.env.VITE_MAPBOX_TOKEN` and exports:

- the configured `mapboxgl` client;
- `MAP_DEFAULTS.style`: `mapbox://styles/mapbox/streets-v12`;
- `MAP_DEFAULTS.zoom`: `14`.

### `geocoding.js`

`searchPlaces(query)` calls Mapbox Geocoding with `country=cm` and `limit=5`. It returns normalized locations:

```js
{ id, name, lat, lng }
```

### `directions.js`

`getRoute(origin, destination)` calls Mapbox driving directions with GeoJSON geometry and returns normalized route data:

```js
{ geometry, distanceKm, durationMin }
```

## Utilities

### `distance.js`

`haversineKm(a, b)` returns the straight-line distance in kilometers. It is used by `useRoute` only as a Directions fallback.

### `priceEstimate.js`

`estimatePrice(distanceKm)` currently uses:

```text
base fare: 300 FCFA
rate:      150 FCFA per km
```

The values are MVP defaults and should be changed in this file if the product or local pricing rules change.

## Minimal Integration Shape

A booking screen will eventually need to coordinate the map instance, locations, route, and driver position. The intended data flow is:

```text
useGeolocation -> origin/default origin -> PlaceSearch
PlaceSearch(origin + destination) -> useRoute.fetchRoute
useRoute.route.geometry -> RouteLayer
useRoute.route -> EtaPriceCard
feature/driver subscription -> useDriverLocation -> DriverMarker
```

A conceptual composition after the map-instance API is agreed could look like this:

```jsx
<MapView center={origin ?? fallbackCenter} onMapReady={setMap}>
  <LocationMarker map={map} position={origin} />
  <RouteLayer map={map} geometry={route?.geometry} />
  <DriverMarker map={map} position={driverPosition} />
</MapView>
```

The `onMapReady` prop in this example is not implemented yet. Treat it as the small API decision that must be completed before using these map layers from booking.

## Current Limitations and Handoff Notes

1. **Map instance exposure:** `MapView` creates the instance but does not expose it. Add an agreed `onMapReady` callback or React context before wiring route and marker components into a screen.
2. **Search error state:** `PlaceSearch` currently awaits `searchPlaces` without its own error UI. The parent should catch or provide an error boundary before production use.
3. **Route layer lifecycle:** `RouteLayer` adds a source and layer but does not remove them when the parent unmounts. This is acceptable for the current MVP but should be handled if map instances are reused.
4. **Driver feed:** `useDriverLocation` is ready for an injected subscription, but no real Supabase Realtime adapter exists in this branch.
5. **API security:** the Mapbox browser token is public by design, but restrict its URL origins and scopes in Mapbox settings.
6. **Pricing:** the FCFA estimate is illustrative and is not a final fare calculation.

Resolve these as focused issues or pull requests so the feature remains reusable and branch ownership stays clear.

## Branch Workflow

This work belongs on `feature/map`. Other feature branches should consume the published branch through a pull request rather than editing this folder directly.

Recommended team flow:

1. Build map-specific changes on `feature/map`.
2. Open a pull request from `feature/map` into `DEVELOP`.
3. Run `npm install`, `npm run build`, and the browser smoke test on `DEVELOP` after integration.
4. Merge tested feature branches into `DEVELOP`.
5. Merge `DEVELOP` into `main` only after the complete app is ready for examiner deployment.

Before opening a pull request, confirm:

- no `.env` file or token appears in `git status` or the diff;
- `npm run build` passes;
- the map loads with a valid local token;
- the Mapbox CSS import remains in `main.jsx`;
- any changes to the map-instance API are documented here and communicated to booking/driver contributors.
