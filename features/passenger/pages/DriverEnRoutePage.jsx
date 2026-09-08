import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';
import CancelRideDialog from '../components/CancelRideDialog';
import MessagePicker from '../components/MessagePicker';
import ShareTrip from '../components/ShareTrip';
import { usePassengerRideSocket } from '../hooks/usePassengerRideSocket';
import { getActiveRide } from '../services/rideState';
import { raiseSos } from '../services/ridesApi';

export default function DriverEnRoutePage() {
  const navigate = useNavigate();
  const activeRide = getActiveRide();
  const rideId = activeRide?.id ?? null;
  const { ride, status, driverLocation, error } = usePassengerRideSocket(rideId);
  const [cancelling, setCancelling] = useState(false);
  const [sosState, setSosState] = useState('');

  useEffect(() => {
    if (!rideId) {
      navigate('/passenger/book', { replace: true });
      return;
    }

    if (status === 'in_progress') {
      navigate('/passenger/ride', { replace: true });
    }

    if (status === 'completed') {
      navigate('/passenger/completed', { replace: true });
    }
  }, [navigate, rideId, status]);

  const etaMin = ride?.eta_s ? Math.ceil(ride.eta_s / 60) : null;
  const mapCenter = driverLocation ?? ride?.driver_location ?? ride?.pickup ?? { lat: 3.848, lng: 11.502 };
  const driverName = ride?.driver?.first_name ?? 'Driver';
  const vehicle = ride?.vehicle
    ? `${ride.vehicle.color} ${ride.vehicle.make} ${ride.vehicle.model} - ${ride.vehicle.plate}`
    : 'Vehicle details pending';

  const triggerSos = async () => {
    setSosState('sending');
    try {
      await raiseSos(rideId);
      setSosState('sent');
    } catch {
      setSosState('failed');
    }
  };

  return (
    <main className="app-shell map-shell">
      <div className="app-header">
        <div>
          <p className="eyebrow">Driver on the way</p>
          <h1>{etaMin ? `${etaMin} min away` : 'Waiting for live ETA'}</h1>
        </div>
        <span className="status">Pickup: {ride?.pickup?.label ?? 'Updating pickup'}</span>
      </div>

      <div className="map-panel">
        <MapView center={mapCenter} />
      </div>

      <div className="ride-panel">
        <h3>{driverName}</h3>
        <p>{vehicle}</p>

        {/* The PIN is the whole anti-impersonation mechanism, so it is the
            largest thing on this panel rather than a line of body text. It is
            what a stranger at the kerb cannot know. */}
        <p className="pin-display" aria-label={`Your pickup PIN is ${ride?.pin ?? 'not ready'}`}>
          {ride?.pin ?? '----'}
        </p>
        <p>Read this 4-digit code aloud to your driver. Do not send it.</p>

        <p>Ride status: {status ?? 'matching'}</p>
        {error ? <p className="form-error">{error}</p> : null}
      </div>

      {rideId ? <MessagePicker rideId={rideId} /> : null}
      {rideId ? <ShareTrip rideId={rideId} /> : null}

      <section className="safety-actions">
        <button
          className="sos-button"
          type="button"
          onClick={triggerSos}
          disabled={sosState === 'sending' || sosState === 'sent'}
        >
          {sosState === 'sent' ? 'Emergency alert sent' : 'Emergency'}
        </button>
        {sosState === 'sent' ? (
          <p className="section-note">
            An evidence snapshot has been sealed. It cannot be altered.
          </p>
        ) : null}
        {sosState === 'failed' ? (
          <p className="form-error">Could not send. Try again.</p>
        ) : null}

        <button
          className="secondary-button"
          type="button"
          onClick={() => setCancelling(true)}
        >
          Cancel ride
        </button>
      </section>

      {cancelling ? (
        <CancelRideDialog
          rideId={rideId}
          onDismiss={() => setCancelling(false)}
          onCancelled={() => navigate('/passenger/home', { replace: true })}
        />
      ) : null}
    </main>
  );
}
