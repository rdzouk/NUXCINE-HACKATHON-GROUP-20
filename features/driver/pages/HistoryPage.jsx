import { useEffect, useState } from 'react';
import DriverNav from '../components/DriverNav';
import PageHeader from '../../shared/components/PageHeader';
import Icon from '../../shared/components/Icon';
import { getLocale } from '../../shared/services/locale';
import { listRides } from '../../passenger/services/ridesApi';

/**
 * The driver's own trips, from the API.
 *
 * `GET /rides` widens its visibility clause for a caller who is a driver, so
 * the same endpoint answers both sides. This screen was rendering two invented
 * rides from a mock context instead.
 */
export default function HistoryPage() {
  const en = getLocale() === 'en';
  const [rides, setRides] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    listRides({ limit: 30 })
      .then((data) => setRides(data.items ?? []))
      .catch((error) => {
        setErrorMessage(error.message);
        setRides([]);
      });
  }, []);

  const dateOf = (ride) => {
    const raw = ride.ended_at ?? ride.created_at;
    if (!raw) return '';
    return new Date(raw).toLocaleDateString(en ? 'en-GB' : 'fr-FR', {
      day: 'numeric',
      month: 'short',
    });
  };

  return (
    <main className="app-shell">
      <PageHeader
        eyebrow={en ? 'History' : 'Historique'}
        title={en ? 'Your trips' : 'Vos courses'}
        fallback="/driver/dashboard"
      />

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

      {rides === null ? (
        <p className="section-note">{en ? 'Loading' : 'Chargement'}</p>
      ) : rides.length === 0 ? (
        <div className="empty-state">
          <Icon name="route" size={26} />
          <p>
            {en
              ? 'No trips yet. Rides you complete appear here.'
              : 'Aucune course pour le moment. Vos courses terminees apparaitront ici.'}
          </p>
        </div>
      ) : (
        <ul className="recent-list">
          {rides.map((ride) => (
            <li key={ride.id}>
              <button type="button" disabled>
                <span className="recent-list__icon">
                  <Icon name="route" />
                </span>
                <span className="recent-list__body">
                  <span className="recent-list__label">
                    {ride.pickup?.label} {en ? 'to' : 'vers'} {ride.dropoff?.label}
                  </span>
                  <span className="recent-list__fare">
                    {dateOf(ride)}, {ride.status}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <DriverNav />
    </main>
  );
}
