import { useState, useCallback } from 'react';
import { getRoute } from '../services/directions';
import { haversineKm } from '../utils/distance';

export function useRoute() {
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchRoute = useCallback(async (origin, destination) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getRoute(origin, destination);
      setRoute(result);
    } catch (err) {
      setError(err.message);
      // fallback: straight-line distance, rough duration estimate
      const distanceKm = haversineKm(origin, destination);
      setRoute({ geometry: null, distanceKm, durationMin: distanceKm * 2 });
    } finally {
      setLoading(false);
    }
  }, []);

  return { route, loading, error, fetchRoute };
}