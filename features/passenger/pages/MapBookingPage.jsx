import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';
import PlaceSearch from '../../map/components/PlaceSearch';
import RouteLayer from '../../map/components/RouteLayer';
import EtaPriceCard from '../../map/components/EtaPriceCard';
import { useGeolocation } from '../../map/hooks/useGeolocation';
import { useRoute } from '../../map/hooks/useRoute';
import { clearBookingAttempt, setPendingBooking } from '../services/rideState';

export default function MapBookingPage() {
  const { position } = useGeolocation();
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const { quote, loading, error, fetchQuote } = useRoute();
  const navigate = useNavigate();

  const handleDestination = (place) => {
    setDestination(place);
    const from = origin ?? position;
    if (from) fetchQuote(from, place);
  };

  const handleConfirm = () => {
    if (!quote || !destination) {
      return;
    }

    const pickup = origin ?? position;

    if (!pickup) {
      return;
    }

    const pendingBooking = {
      pickup,
      dropoff: destination,
      quote,
      seats: 1,
      mode: 'exclusive',
    };

    clearBookingAttempt();
    setPendingBooking(pendingBooking);
    navigate('/passenger/confirm', { state: { pendingBooking } });
  };

  return (
    <main className="app-shell map-shell">
      <MapView center={position ?? { lat: 3.848, lng: 11.502 }}>
        <RouteLayer geometry={quote?.geometry} />
      </MapView>

      <div className="booking-panel">
        <PlaceSearch label="Pickup" defaultValue={position} onSelect={setOrigin} />
        <PlaceSearch label="Destination" onSelect={handleDestination} />
        <EtaPriceCard quote={quote} loading={loading} error={error} />

        {quote && (
          <button className="primary-button" onClick={handleConfirm}>
            Confirm ride
          </button>
        )}
      </div>
    </main>
  );
}