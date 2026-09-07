import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { usePassengerRideSocket } from '../hooks/usePassengerRideSocket';
import { getActiveRide } from '../services/rideState';

export default function SearchingDriverPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeRide = getActiveRide();
  const rideId = location.state?.rideId ?? activeRide?.id ?? null;
  const { status, error } = usePassengerRideSocket(rideId);

  useEffect(() => {
    if (!rideId) {
      navigate('/passenger/book', { replace: true });
      return;
    }

    if (status === 'accepted' || status === 'arriving' || status === 'arrived') {
      navigate('/passenger/driver-enroute', { replace: true });
    }
  }, [navigate, rideId, status]);

  return (
    <main className="app-shell centered">
      <div className="pulse-dot" />
      <h2>Looking for a driver...</h2>
      <p>Ride status: {status ?? 'matching'}</p>
      {error ? <p>{error}</p> : <p>This should update automatically when a driver accepts.</p>}
    </main>
  );
}