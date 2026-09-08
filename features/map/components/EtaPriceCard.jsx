/**
 * The quote, with both prices side by side.
 *
 * Showing exclusive and shared together is the argument, not decoration: a
 * passenger can see that a seat costs less than the vehicle, and a driver
 * carrying three of them earns more than one exclusive fare. Neither number is
 * computed here. Both come from the server, because the client must never be
 * an input to price (I2).
 */
export default function EtaPriceCard({ quote, loading, error, mode = 'exclusive', seats = 1 }) {
  if (loading) return <div className="eta-card">Calculating route...</div>;
  if (error) return <div className="eta-card eta-card--error">{error.message}</div>;
  if (!quote) return null;

  const sharing = mode === 'corridor' && quote.corridorFareXaf;
  const seatTotal = sharing ? quote.corridorFareXaf * seats : null;

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

      <div className={sharing ? 'eta-card__row' : 'eta-card__row eta-card__row--chosen'}>
        <span>Exclusive</span>
        <strong>{quote.fareXaf.toLocaleString()} FCFA</strong>
      </div>

      {quote.corridorFareXaf ? (
        <div className={sharing ? 'eta-card__row eta-card__row--chosen' : 'eta-card__row'}>
          <span>Shared</span>
          <strong>{quote.corridorFareXaf.toLocaleString()} FCFA per seat</strong>
        </div>
      ) : null}

      {sharing && seats > 1 ? (
        <div className="eta-card__row eta-card__row--total">
          <span>{seats} seats</span>
          <strong>{seatTotal.toLocaleString()} FCFA</strong>
        </div>
      ) : null}

      {sharing ? (
        <p className="eta-card__note">
          You pay for the distance you travel. The driver may pick up others
          along the same route, and is asked before anyone joins.
        </p>
      ) : null}
    </div>
  );
}
