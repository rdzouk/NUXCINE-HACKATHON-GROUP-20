import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';
import PlaceSearch from '../../map/components/PlaceSearch';
import RouteLayer from '../../map/components/RouteLayer';
import EtaPriceCard from '../../map/components/EtaPriceCard';
import { useGeolocation } from '../../map/hooks/useGeolocation';
import { useRoute } from '../../map/hooks/useRoute';

export default function MapBookingPage() {
  const { position } = useGeolocation();
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [map, setMap] = useState(null);
  const { quote, loading, error, fetchQuote } = useRoute();
  const navigate = useNavigate();

  const handleDestination = (place) => {
    setDestination(place);
    const from = origin ?? position;
    if (from) fetchQuote(from, place);
  };

  return (
    <main className="app-shell map-shell">
      <MapView center={position ?? { lat: 3.848, lng: 11.502 }} onMapReady={setMap}>
        {() => <RouteLayer map={map} geometry={quote?.geometry} />}
      </MapView>

      <div className="booking-panel">
        <PlaceSearch label="Pickup" defaultValue={position} onSelect={setOrigin} />
        <PlaceSearch label="Destination" onSelect={handleDestination} />
        <EtaPriceCard quote={quote} loading={loading} error={error} />

        {quote && (
          <button className="primary-button" onClick={() => navigate('/passenger/confirm')}>
            Confirm ride
          </button>
        )}
      </div>
    </main>
  );
}