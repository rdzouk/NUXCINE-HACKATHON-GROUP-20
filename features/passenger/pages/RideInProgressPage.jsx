import { useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import MapView from '../../map/components/MapView';
import { usePassengerRideSocket } from '../hooks/usePassengerRideSocket';
import { getActiveRide } from '../services/rideState';

export default function RideInProgressPage() {
  const navigate = useNavigate();
  const activeRide = getActiveRide();
  const rideId = activeRide?.id ?? null;
  const { ride, status, driverLocation, error } = usePassengerRideSocket(rideId);

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
  const driverName = ride?.driver?.first_name ?? 'Driver';
  const vehicle = ride?.vehicle
    ? `${ride.vehicle.color} ${ride.vehicle.make} ${ride.vehicle.model} - ${ride.vehicle.plate}`
    : 'Vehicle details pending';

  return (
    <main className="app-shell map-shell">
      <MapView center={mapCenter} />

      <div className="ride-panel">
        <p className="eyebrow">Your driver</p>
        <h3>{driverName}</h3>
        <p>{vehicle}</p>
        <p>Heading to {ride?.dropoff?.label ?? 'your destination'}</p>
        <p>Ride status: {status ?? 'in_progress'}</p>
        {error ? <p>{error}</p> : null}

        <button className="sos-button">SOS</button>
      </div>
    </main>
  );
}