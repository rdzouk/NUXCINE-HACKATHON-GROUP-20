export default function EtaPriceCard({ quote, loading, error }) {
  if (loading) return <div className="eta-card">Calculating route...</div>;
  if (error) return <div className="eta-card eta-card--error">{error.message}</div>;
  if (!quote) return null;

  return (
    <div className="eta-card">
      <div className="eta-card__row">
        <span>Distance</span>
        <strong>{quote.distanceKm.toFixed(1)} km</strong>
      </div>
      <div className="eta-card__row">
        <span>Estimated time</span>
        <strong>{Math.round(quote.durationMin)} min</strong>
      </div>
      <div className="eta-card__row">
        <span>Fare</span>
        <strong>{quote.fareXaf.toLocaleString()} FCFA</strong>
      </div>
      {quote.corridorFareXaf && (
        <div className="eta-card__row eta-card__row--corridor">
          <span>Shared ride</span>
          <strong>{quote.corridorFareXaf.toLocaleString()} FCFA/seat</strong>
        </div>
      )}
    </div>
  );
}