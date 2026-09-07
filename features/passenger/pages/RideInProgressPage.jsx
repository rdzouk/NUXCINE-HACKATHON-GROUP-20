import { useNavigate } from 'react-router-dom';
import { useMockAuth } from '../../../app/MockAuthContext';
import MapView from '../../map/components/MapView';

export default function RideInProgressPage() {
  const { ride } = useMockAuth();
  const navigate = useNavigate();

  return (
    <main className="app-shell map-shell">
      <MapView center={{ lat: 3.848, lng: 11.502 }} />

      <div className="ride-panel">
        <p className="eyebrow">Your driver</p>
        <h3>{ride.driver.name} · ⭐ {ride.driver.rating}</h3>
        <p>{ride.driver.vehicle}</p>
        <p>Heading to {ride.destination}</p>

        <button className="sos-button">🆘 SOS</button>
        <button className="primary-button" onClick={() => navigate('/passenger/completed')}>
          (Dev) Simulate ride completed
        </button>
      </div>
    </main>
  );
}