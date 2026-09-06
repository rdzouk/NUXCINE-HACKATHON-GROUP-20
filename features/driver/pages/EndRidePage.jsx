import { useNavigate } from 'react-router-dom';
import { useMockAuth } from '../../../app/MockAuthContext';

export default function EndRidePage() {
  const { ride } = useMockAuth();
  const navigate = useNavigate();

  return (
    <main className="app-shell centered">
      <h1>Ride completed</h1>
      <p>Fare collected: {ride.fareXaf.toLocaleString()} FCFA</p>
      <p>Commission (15%): {Math.round(ride.fareXaf * 0.15).toLocaleString()} FCFA</p>
      <button className="primary-button" onClick={() => navigate('/driver/dashboard')}>
        Back to dashboard
      </button>
    </main>
  );
}