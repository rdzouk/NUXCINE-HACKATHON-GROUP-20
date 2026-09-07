import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';
import { markDriverArrived } from '../services/driverApi';
import { getActiveDriverRide, setActiveDriverRide } from '../services/driverState';

export default function NavigationPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const ride = getActiveDriverRide();
  const rideId = location.state?.rideId ?? ride?.id ?? null;

  const handleArrived = async () => {
    if (!rideId) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const response = await markDriverArrived(rideId);
      setActiveDriverRide(response.ride);
      navigate('/driver/ride', { state: { rideId }, replace: true });
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="app-shell map-shell">
      <MapView center={ride?.pickup ?? { lat: 3.848, lng: 11.502 }} />
      <div className="ride-panel">
        <p>Heading to pickup: {ride?.pickup?.label ?? 'Pickup location pending'}</p>
        <button className="primary-button" onClick={handleArrived} disabled={isSubmitting || !rideId}>
          {isSubmitting ? 'Updating...' : 'Arrived at pickup'}
        </button>
        {errorMessage ? <p>{errorMessage}</p> : null}
      </div>
    </main>
  );
}