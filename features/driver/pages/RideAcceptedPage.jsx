import { useNavigate } from 'react-router-dom';
import { useMockAuth } from '../../../app/MockAuthContext';

export default function RideAcceptedPage() {
  const { ride } = useMockAuth();
  const navigate = useNavigate();

  return (
    <main className="app-shell">
      <h1>Ride accepted</h1>
      <p>Pick up passenger at <strong>{ride.origin}</strong></p>
      <p>Passenger: Aminata · +237 699 000 000</p>
      <button className="primary-button" onClick={() => navigate('/driver/navigate')}>
        Start navigation
      </button>
    </main>
  );
}