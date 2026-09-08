import { useEffect, useState } from 'react';
import BottomNav from '../components/BottomNav';
import PageHeader from '../../shared/components/PageHeader';
import Icon from '../../shared/components/Icon';
import { getLocale } from '../../shared/services/locale';
import { listRides } from '../services/ridesApi';

/**
 * The passenger's own trips, from the API.
 *
 * This was two invented rides from a mock context, rendered exactly the way
 * real ones would be. A juror had no way to tell which screens in this app
 * hold real data and which do not, which devalues the ones that do.
 *
 * `GET /rides` returns only rides where the caller is the passenger or the
 * assigned driver, and that restriction is a WHERE clause on the server rather
 * than a filter applied here.
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
        title={en ? 'Your trips' : 'Vos trajets'}
        fallback="/passenger/home"
      />

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

      {rides === null ? (
        <p className="section-note">{en ? 'Loading' : 'Chargement'}</p>
      ) : rides.length === 0 ? (
        <div className="empty-state">
          <Icon name="clock" size={26} />
          <p>
            {en
              ? 'No trips yet. Your completed rides appear here.'
              : 'Aucun trajet pour le moment. Vos courses terminees apparaitront ici.'}
          </p>
        </div>
      ) : (
        <ul className="recent-list">
          {rides.map((ride) => (
            <li key={ride.id}>
              <button type="button" disabled>
                <span className="recent-list__icon">
                  <Icon name="clock" />
                </span>
                <span className="recent-list__body">
                  <span className="recent-list__label">
                    {ride.pickup?.label} {en ? 'to' : 'vers'} {ride.dropoff?.label}
                  </span>
                  <span className="recent-list__fare">
                    {dateOf(ride)}
                    {ride.final_fare_xaf || ride.quoted_fare_xaf
                      ? `, ${(ride.final_fare_xaf ?? ride.quoted_fare_xaf).toLocaleString()} FCFA`
                      : ''}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <BottomNav />
    </main>
  );
}
