import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMockAuth } from '../../../app/MockAuthContext';
import MapView from '../../map/components/MapView';
import { useDriverLocation } from '../../map/hooks/useDriverLocation';

export default function DriverEnRoutePage() {
  const { ride } = useMockAuth();
  const navigate = useNavigate();
  const driverPosition = useDriverLocation(ride.id); // live once wired to real backend
  const [etaMin, setEtaMin] = useState(6); // mock countdown until wired to real ETA

  useEffect(() => {
    const interval = setInterval(() => {
      setEtaMin((prev) => Math.max(prev - 1, 0));
    }, 5000); // dev-only visual countdown, not a real timer
    return () => clearInterval(interval);
  }, []);

  return (
    <main className="app-shell map-shell">
      <div className="app-header">
        <div>
          <p className="eyebrow">Driver on the way</p>
          <h1>{etaMin} min away</h1>
        </div>
        <span className="status">Pickup: {ride.origin}</span>
      </div>

      <div className="map-panel">
        <MapView center={driverPosition ?? { lat: 3.848, lng: 11.502 }} />
      </div>

      <div className="ride-panel">
        <h3>{ride.driver.name} · ⭐ {ride.driver.rating}</h3>
        <p>{ride.driver.vehicle}</p>
        <div className="button-row">
          <button className="secondary-button">Message driver</button>
          <button className="secondary-button">Call driver</button>
        </div>
        <button className="primary-button" onClick={() => navigate('/passenger/ride')}>
          (Dev) Simulate driver arrived — start ride
        </button>
      </div>
    </main>
  );
}