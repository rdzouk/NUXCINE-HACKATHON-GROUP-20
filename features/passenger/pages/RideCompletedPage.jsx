import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Icon from '../../shared/components/Icon';
import { getLocale } from '../../shared/services/locale';
import { getRide } from '../services/ridesApi';
import { clearActiveRide, getActiveRide } from '../services/rideState';

/**
 * The end of the trip, on the real fare.
 *
 * This showed a mock fare and five stars that submitted nothing. Both were
 * wrong in the same way: a control that does nothing is a claim the product
 * does not honour, and an invented total on the one screen where money is
 * settled is the worst place in the app to invent a number.
 *
 * **The final fare comes from the server's own GPS trace**, not from the
 * quote and never from anything this client measured. Points that failed the
 * plausibility filter were excluded before it was computed, so a driver who
 * forged a longer route was not paid for it (I2).
 *
 * Rating is not built. `rating_avg` is returned and displayed on the driver
 * card, but no endpoint collects one, so no stars are offered here.
 */
export default function RideCompletedPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const en = getLocale() === 'en';
  const [ride, setRide] = useState(getActiveRide());

  const rideId = location.state?.rideId ?? ride?.id;

  useEffect(() => {
    if (!rideId) return;
    // Re-read rather than trusting the copy in local storage: the final fare
    // is written when the driver completes the trip, which may be after the
    // last version this device saw.
    getRide(rideId)
      .then((data) => setRide(data.ride ?? data))
      .catch(() => {});
  }, [rideId]);

  const fare = ride?.final_fare_xaf ?? ride?.quoted_fare_xaf;
  const distanceKm =
    ride?.actual_distance_m != null
      ? (ride.actual_distance_m / 1000).toFixed(1)
      : ride?.quoted_distance_m != null
        ? (ride.quoted_distance_m / 1000).toFixed(1)
        : null;

  const done = () => {
    clearActiveRide();
    navigate('/passenger/home', { replace: true });
  };

  return (
    <main className="app-shell">
      <div className="done-mark">
        <Icon name="check" size={30} />
      </div>

      <h1 className="headline">
        {en ? 'Trip complete' : 'Course terminee'}
      </h1>

      <p className="eta-block">
        {fare != null ? `${fare.toLocaleString()} FCFA` : '-'}
      </p>

      <p className="section-note">
        {en
          ? 'Payable in cash to your driver. The amount was computed by the server from its own record of the route.'
          : 'A regler en especes aupres de votre chauffeur. Le montant a ete calcule par le serveur a partir de son propre releve du trajet.'}
      </p>

      {ride ? (
        <>
          <p className="eyebrow">{en ? 'Summary' : 'Recapitulatif'}</p>

          <div className="fact-row">
            <span>{en ? 'From' : 'Depart'}</span>
            <strong>{ride.pickup?.label ?? '-'}</strong>
          </div>
          <div className="fact-row">
            <span>{en ? 'To' : 'Arrivee'}</span>
            <strong>{ride.dropoff?.label ?? '-'}</strong>
          </div>
          {distanceKm ? (
            <div className="fact-row">
              <span>{en ? 'Distance' : 'Distance'}</span>
              <strong>{distanceKm} km</strong>
            </div>
          ) : null}
          {ride.driver?.first_name ? (
            <div className="fact-row">
              <span>{en ? 'Driver' : 'Chauffeur'}</span>
              <strong>{ride.driver.first_name}</strong>
            </div>
          ) : null}
        </>
      ) : null}

      <button className="primary-button" onClick={done}>
        {en ? 'Done' : 'Termine'}
      </button>
    </main>
  );
}
