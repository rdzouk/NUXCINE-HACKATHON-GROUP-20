import { useNavigate } from 'react-router-dom';
import { useMockAuth } from '../../../app/MockAuthContext';

export default function ConfirmRidePage() {
  const { ride } = useMockAuth();
  const navigate = useNavigate();

  return (
    <main className="app-shell">
      <h1>Confirm your ride</h1>
      <div className="ride-summary">
        <p><strong>From:</strong> {ride.origin}</p>
        <p><strong>To:</strong> {ride.destination}</p>
        <p><strong>Distance:</strong> {ride.distanceKm} km · {ride.durationMin} min</p>
        <p><strong>Fare:</strong> {ride.fareXaf.toLocaleString()} FCFA</p>
      </div>
      <button className="primary-button" onClick={() => navigate('/passenger/searching')}>
        Confirm ride
      </button>
    </main>
  );
}