import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';
import { usePassengerRideSocket } from '../hooks/usePassengerRideSocket';
import { getActiveRide } from '../services/rideState';

export default function DriverEnRoutePage() {
  const navigate = useNavigate();
  const activeRide = getActiveRide();
  const rideId = activeRide?.id ?? null;
  const { ride, status, driverLocation, error } = usePassengerRideSocket(rideId);

  useEffect(() => {
    if (!rideId) {
      navigate('/passenger/book', { replace: true });
      return;
    }

    if (status === 'in_progress') {
      navigate('/passenger/ride', { replace: true });
    }

    if (status === 'completed') {
      navigate('/passenger/completed', { replace: true });
    }
  }, [navigate, rideId, status]);

  const etaMin = ride?.eta_s ? Math.ceil(ride.eta_s / 60) : null;
  const mapCenter = driverLocation ?? ride?.driver_location ?? ride?.pickup ?? { lat: 3.848, lng: 11.502 };
  const driverName = ride?.driver?.first_name ?? 'Driver';
  const vehicle = ride?.vehicle
    ? `${ride.vehicle.color} ${ride.vehicle.make} ${ride.vehicle.model} - ${ride.vehicle.plate}`
    : 'Vehicle details pending';

  return (
    <main className="app-shell map-shell">
      <div className="app-header">
        <div>
          <p className="eyebrow">Driver on the way</p>
          <h1>{etaMin ? `${etaMin} min away` : 'Waiting for live ETA'}</h1>
        </div>
        <span className="status">Pickup: {ride?.pickup?.label ?? 'Updating pickup'}</span>
      </div>

      <div className="map-panel">
        <MapView center={mapCenter} />
      </div>

      <div className="ride-panel">
        <h3>{driverName}</h3>
        <p>{vehicle}</p>
        <p><strong>Your pickup PIN:</strong> {ride?.pin ?? 'Waiting for PIN'}</p>
        <p>Read this 4-digit PIN aloud to your driver at pickup.</p>
        <p>Ride status: {status ?? 'matching'}</p>
        {error ? <p>{error}</p> : null}
      </div>
    </main>
  );
}