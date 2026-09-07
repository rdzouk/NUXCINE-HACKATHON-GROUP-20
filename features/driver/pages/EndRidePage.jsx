import { useLocation, useNavigate } from 'react-router-dom';
import { clearActiveDriverRide, clearCompletedDriverRide, getCompletedDriverRide } from '../services/driverState';

export default function EndRidePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const completion = getCompletedDriverRide();
  const finalFareXaf = location.state?.finalFareXaf ?? completion?.finalFareXaf ?? completion?.ride?.final_fare_xaf ?? null;

  const handleBack = () => {
    clearCompletedDriverRide();
    clearActiveDriverRide();
    navigate('/driver/dashboard');
  };

  return (
    <main className="app-shell centered">
      <h1>Ride completed</h1>
      <p>Final fare: {typeof finalFareXaf === 'number' ? `${finalFareXaf.toLocaleString()} FCFA` : 'Unavailable'}</p>
      <button className="primary-button" onClick={handleBack}>
        Back to dashboard
      </button>
    </main>
  );
}