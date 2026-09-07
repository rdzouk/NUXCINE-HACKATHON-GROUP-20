import { apiFetch } from './apiClient';
import { decodePolyline } from '../utils/polyline';

// Replaces Mapbox Directions. Fare is computed server-side here — never
// trust or recompute a price on the client (contract invariant I2).
export async function getQuote(pickup, dropoff, seats = 1, mode = 'exclusive') {
  const data = await apiFetch('/rides/quote', {
    method: 'POST',
    body: JSON.stringify({
      pickup: { lat: pickup.lat, lng: pickup.lng, label: pickup.name },
      dropoff: { lat: dropoff.lat, lng: dropoff.lng, label: dropoff.name },
      seats,
      mode,
    }),
  });

  return {
    quoteId: data.quote_id,
    geometry: decodePolyline(data.route_polyline),
    distanceKm: data.distance_m / 1000,
    durationMin: data.duration_s / 60,
    fareXaf: data.fare_xaf,
    corridorFareXaf: data.corridor_fare_xaf ?? null,
    expiresAt: data.expires_at,
    breakdown: data.breakdown,
  };
}