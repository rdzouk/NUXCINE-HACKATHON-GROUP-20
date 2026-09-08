import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import { getActiveDriverRide, setActiveDriverRide } from '../services/driverState';
import { getLocale } from '../../shared/services/locale';

export default function RideAcceptedPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const ride = location.state?.ride ?? getActiveDriverRide();
  const en = getLocale() === 'en';

  useEffect(() => {
    if (location.state?.ride) {
      setActiveDriverRide(location.state.ride);
    }
  }, [location.state]);

  return (
    <main className="app-shell">
      <h1 className="headline">
        {en ? 'Ride accepted' : 'Course acceptee'}
      </h1>
      {ride ? (
        <>
          <div className="fact-row">
            <span>{en ? 'Pick up at' : 'Prise en charge'}</span>
            <strong>{ride.pickup.label}</strong>
          </div>
          <div className="fact-row">
            <span>{en ? 'Passenger' : 'Passager'}</span>
            <strong>
              {ride.passenger?.first_name ?? (en ? 'Passenger' : 'Passager')}
            </strong>
          </div>
          <button
            className="primary-button"
            onClick={() =>
              navigate('/driver/navigate', { state: { rideId: ride.id } })
            }
          >
            {en ? 'Start navigation' : 'Demarrer la navigation'}
          </button>
        </>
      ) : (
        <>
          <p className="section-note">
            {en
              ? 'No accepted ride was found.'
              : 'Aucune course acceptee trouvee.'}
          </p>
          <button
            className="primary-button"
            onClick={() => navigate('/driver/dashboard')}
          >
            {en ? 'Back to the dashboard' : 'Retour au tableau de bord'}
          </button>
        </>
      )}
    </main>
  );
}