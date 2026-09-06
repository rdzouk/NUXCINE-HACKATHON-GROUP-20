import { estimatePrice } from '../utils/priceEstimate';

export default function EtaPriceCard({ route, loading, error }) {
  if (loading) return <div className="eta-card">Calculating route...</div>;
  if (error) return <div className="eta-card eta-card--error">Couldn't calculate the route. Showing a rough estimate instead.</div>;
  if (!route) return null;

  const price = estimatePrice(route.distanceKm);

  return (
    <div className="eta-card">
      <div className="eta-card__row">
        <span>Distance</span>
        <strong>{route.distanceKm.toFixed(1)} km</strong>
      </div>
      <div className="eta-card__row">
        <span>Estimated time</span>
        <strong>{Math.round(route.durationMin)} min</strong>
      </div>
      <div className="eta-card__row">
        <span>Estimated price</span>
        <strong>{price} FCFA</strong>
      </div>
    </div>
  );
}