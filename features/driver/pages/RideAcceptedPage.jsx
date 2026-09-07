import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import { getActiveDriverRide, setActiveDriverRide } from '../services/driverState';

export default function RideAcceptedPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const ride = location.state?.ride ?? getActiveDriverRide();

  useEffect(() => {
    if (location.state?.ride) {
      setActiveDriverRide(location.state.ride);
    }
  }, [location.state]);

  return (
    <main className="app-shell">
      <h1>Ride accepted</h1>
      {ride ? (
        <>
          <p>Pick up passenger at <strong>{ride.pickup.label}</strong></p>
          <p>Passenger: {ride.passenger?.first_name ?? 'Passenger'}</p>
          <button className="primary-button" onClick={() => navigate('/driver/navigate', { state: { rideId: ride.id } })}>
            Start navigation
          </button>
        </>
      ) : (
        <>
          <p>No accepted ride was found.</p>
          <button className="primary-button" onClick={() => navigate('/driver/dashboard')}>
            Back to dashboard
          </button>
        </>
      )}
    </main>
  );
}