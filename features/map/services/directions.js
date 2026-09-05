export async function getRoute(origin, destination) {
  const token = import.meta.env.VITE_MAPBOX_TOKEN;
  const url = `https://api.mapbox.com/directions/v5/mapbox/driving/${origin.lng},${origin.lat};${destination.lng},${destination.lat}?geometries=geojson&access_token=${token}`;

  const res = await fetch(url);
  if (!res.ok) throw new Error('Directions request failed');
  const data = await res.json();
  const route = data.routes?.[0];
  if (!route) throw new Error('No route found');

  return {
    geometry: route.geometry,       // GeoJSON for RouteLayer
    distanceKm: route.distance / 1000,
    durationMin: route.duration / 60,
  };
}