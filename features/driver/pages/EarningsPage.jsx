import { useEffect, useState } from 'react';
import DriverNav from '../components/DriverNav';
import PageHeader from '../../shared/components/PageHeader';
import Icon from '../../shared/components/Icon';
import { getLocale } from '../../shared/services/locale';
import { listRides } from '../../passenger/services/ridesApi';

/**
 * Earnings, summed from the driver's own completed rides.
 *
 * Derived here rather than served by an endpoint, and that is a real
 * limitation worth stating: it can only total the page of rides the API
 * returns, so a busy week would be under-counted. A proper figure needs
 * `GET /driver/earnings` with the aggregation done in Postgres.
 *
 * The alternative was the previous version, which summed two invented rides
 * and presented the result as "this week". A number that is honest about its
 * own scope beats a confident number that is wrong.
 *
 * Only completed rides count. A cancelled one earns a fee through the
 * cancellation ledger, which is a debt owed by the passenger and not revenue
 * collected by the driver, so it does not belong in this total.
 */
const PAGE = 50;

export default function EarningsPage() {
  const en = getLocale() === 'en';
  const [rides, setRides] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    listRides({ limit: PAGE, status: 'completed' })
      .then((data) => setRides(data.items ?? []))
      .catch((error) => {
        setErrorMessage(error.message);
        setRides([]);
      });
  }, []);

  const total = (rides ?? []).reduce(
    (sum, r) => sum + (r.final_fare_xaf ?? r.quoted_fare_xaf ?? 0),
    0,
  );

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
        eyebrow={en ? 'Money' : 'Revenus'}
        title={en ? 'Earnings' : 'Vos gains'}
        fallback="/driver/dashboard"
      />

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

      <p className="eta-block">{total.toLocaleString()} FCFA</p>
      <p className="section-note">
        {en
          ? `Across your last ${rides?.length ?? 0} completed rides. Fares are cash, collected in the car.`
          : `Sur vos ${rides?.length ?? 0} dernieres courses terminees. Les tarifs sont en especes, percus dans le vehicule.`}
      </p>

      <p className="eyebrow">{en ? 'Completed rides' : 'Courses terminees'}</p>

      {rides === null ? (
        <p className="section-note">{en ? 'Loading' : 'Chargement'}</p>
      ) : rides.length === 0 ? (
        <div className="empty-state">
          <Icon name="route" size={26} />
          <p>
            {en
              ? 'Nothing yet. Complete a ride and it appears here.'
              : 'Rien pour le moment. Terminez une course et elle apparaitra ici.'}
          </p>
        </div>
      ) : (
        <ul className="recent-list">
          {rides.map((ride) => (
            <li key={ride.id}>
              <button type="button" disabled>
                <span className="recent-list__body">
                  <span className="recent-list__label">
                    {ride.pickup?.label} {en ? 'to' : 'vers'} {ride.dropoff?.label}
                  </span>
                  <span className="recent-list__fare">{dateOf(ride)}</span>
                </span>
                <span className="recent-list__fare">
                  {(ride.final_fare_xaf ?? ride.quoted_fare_xaf ?? 0).toLocaleString()} FCFA
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
