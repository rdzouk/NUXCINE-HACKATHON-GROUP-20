import { apiFetch } from './apiClient';

// Replaces Mapbox Geocoding with the landmark gazetteer. This is the plan's
// actual innovation bet, so this call matters more than it looks.
export async function searchPlaces(query, near) {
  const params = new URLSearchParams({ q: query, limit: '8' });
  if (near) params.set('near', `${near.lat},${near.lng}`);

  const data = await apiFetch(`/places/search?${params.toString()}`);

  return data.results.map((r) => ({
    id: r.id,
    name: r.name,
    lat: r.lat,
    lng: r.lng,
    quartier: r.quartier,
    matchType: r.match_type, // exact_alias | fuzzy_landmark | quartier | street_fallback
  }));
}

export async function reverseGeocode(lat, lng) {
  const params = new URLSearchParams({ lat, lng });
  return apiFetch(`/places/reverse?${params.toString()}`);
}