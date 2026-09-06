export async function searchPlaces(query) {
  const token = import.meta.env.VITE_MAPBOX_TOKEN;
  const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(query)}.json?access_token=${token}&country=cm&limit=5`;

  const res = await fetch(url);
  if (!res.ok) throw new Error('Geocoding request failed');
  const data = await res.json();

  return data.features.map((f) => ({
    id: f.id,
    name: f.place_name,
    lat: f.center[1],
    lng: f.center[0],
  }));
}