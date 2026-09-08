import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';

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
  const en = getLocale() === 'en';

  if (loading) {
    return (
      <div className="eta-card">
        {en ? 'Calculating route...' : 'Calcul de l\'itineraire...'}
      </div>
    );
  }
  if (error) return <div className="eta-card eta-card--error">{error.message}</div>;
  if (!quote) return null;

  const sharing = mode === 'corridor' && quote.corridorFareXaf;
  const seatTotal = sharing ? quote.corridorFareXaf * seats : null;

  return (
    <div className="eta-card">
      <div className="eta-card__row">
        <span>{en ? 'Distance' : 'Distance'}</span>
        <strong>{quote.distanceKm.toFixed(1)} km</strong>
      </div>
      <div className="eta-card__row">
        <span>{en ? 'Estimated time' : 'Duree estimee'}</span>
        <strong>{Math.round(quote.durationMin)} min</strong>
      </div>

      <div className={sharing ? 'eta-card__row' : 'eta-card__row eta-card__row--chosen'}>
        <span>{t('book.exclusive')}</span>
        <strong>{quote.fareXaf.toLocaleString()} FCFA</strong>
      </div>

      {quote.corridorFareXaf ? (
        <div className={sharing ? 'eta-card__row eta-card__row--chosen' : 'eta-card__row'}>
          <span>{t('book.shared')}</span>
          <strong>
            {quote.corridorFareXaf.toLocaleString()} FCFA{' '}
            {en ? 'per seat' : 'par place'}
          </strong>
        </div>
      ) : null}

      {sharing && seats > 1 ? (
        <div className="eta-card__row eta-card__row--total">
          <span>{seats} {en ? 'seats' : 'places'}</span>
          <strong>{seatTotal.toLocaleString()} FCFA</strong>
        </div>
      ) : null}

      {sharing ? (
        <p className="eta-card__note">
          {en
            ? 'You pay for the distance you travel. The driver may pick up one other booking along the same route, and is asked before anyone joins.'
            : "Vous payez la distance que vous parcourez. Le chauffeur peut prendre une autre reservation sur le meme trajet, et on lui demande son accord avant."}
        </p>
      ) : null}
    </div>
  );
}
