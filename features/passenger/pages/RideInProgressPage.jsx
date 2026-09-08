import { useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import MapView from '../../map/components/MapView';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';
import { usePassengerRideSocket } from '../hooks/usePassengerRideSocket';
import { getActiveRide } from '../services/rideState';

export default function RideInProgressPage() {
  const navigate = useNavigate();
  const activeRide = getActiveRide();
  const rideId = activeRide?.id ?? null;
  const { ride, status, driverLocation, error } = usePassengerRideSocket(rideId);
  const en = getLocale() === 'en';

  useEffect(() => {
    if (!rideId) {
      navigate('/passenger/book', { replace: true });
      return;
    }

    if (status === 'completed') {
      navigate('/passenger/completed', { replace: true });
    }
  }, [navigate, rideId, status]);

  const mapCenter = driverLocation ?? ride?.driver_location ?? ride?.pickup ?? { lat: 3.848, lng: 11.502 };
  const driverName =
    ride?.driver?.first_name ?? (en ? 'Driver' : 'Chauffeur');
  const vehicle = ride?.vehicle
    ? `${ride.vehicle.color} ${ride.vehicle.make} ${ride.vehicle.model} - ${ride.vehicle.plate}`
    : en
      ? 'Vehicle details pending'
      : 'Details du vehicule a venir';

  return (
    <main className="app-shell map-shell">
      <MapView center={mapCenter} />

      <div className="ride-panel">
        <p className="eyebrow">{en ? 'Your driver' : 'Votre chauffeur'}</p>
        <h3>{driverName}</h3>
        <p>{vehicle}</p>
        <p>
          {en ? 'Heading to' : 'En route vers'}{' '}
          {ride?.dropoff?.label ?? (en ? 'your destination' : 'votre destination')}
        </p>
        {error ? <p className="form-error">{error}</p> : null}

        <button className="sos-button">{t('ride.emergency')}</button>
      </div>
    </main>
  );
}