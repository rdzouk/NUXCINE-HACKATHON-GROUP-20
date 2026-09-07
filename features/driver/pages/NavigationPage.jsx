import { useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';

export default function NavigationPage() {
  const navigate = useNavigate();

  return (
    <main className="app-shell map-shell">
      <MapView center={{ lat: 3.848, lng: 11.502 }} />
      <div className="ride-panel">
        <p>Heading to pickup: Carrefour Warda</p>
        <button className="primary-button" onClick={() => navigate('/driver/ride')}>
          Arrived at pickup
        </button>
      </div>
    </main>
  );
}