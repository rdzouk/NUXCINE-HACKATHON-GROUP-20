import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';
import CancelRideDialog from '../components/CancelRideDialog';
import MessagePicker from '../components/MessagePicker';
import ShareTrip from '../components/ShareTrip';
import VoiceGuide from '../../shared/components/VoiceGuide';
import { usePassengerRideSocket } from '../hooks/usePassengerRideSocket';
import { getActiveRide } from '../services/rideState';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';
import { raiseSos } from '../services/ridesApi';

export default function DriverEnRoutePage() {
  const navigate = useNavigate();
  const activeRide = getActiveRide();
  const rideId = activeRide?.id ?? null;
  const { ride, status, driverLocation, error } = usePassengerRideSocket(rideId);
  const [cancelling, setCancelling] = useState(false);
  const [sosState, setSosState] = useState('');
  const en = getLocale() === 'en';

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
  const driverName =
    ride?.driver?.first_name ?? (en ? 'Driver' : 'Chauffeur');
  const vehicle = ride?.vehicle
    ? `${ride.vehicle.color} ${ride.vehicle.make} ${ride.vehicle.model} - ${ride.vehicle.plate}`
    : en
      ? 'Vehicle details pending'
      : 'Details du vehicule a venir';

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
          <p className="eyebrow">
            {en ? 'Driver on the way' : 'Chauffeur en route'}
          </p>
          <h1>
            {etaMin
              ? en ? `${etaMin} min away` : `Dans ${etaMin} min`
              : en ? 'Waiting for a live ETA' : "En attente de l'heure d'arrivee"}
          </h1>
        </div>
        <span className="status">
          {en ? 'Pickup' : 'Depart'}:{' '}
          {ride?.pickup?.label ?? (en ? 'Updating' : 'Mise a jour')}
        </span>
      </div>

      <div className="map-panel">
        <MapView center={mapCenter} />
      </div>

      <VoiceGuide announcement={ride?.announcement} locale={ride?.locale ?? 'fr'} />

      <div className="ride-panel">
        <h3>{driverName}</h3>
        <p>{vehicle}</p>

        {/* The PIN is the whole anti-impersonation mechanism, so it is the
            largest thing on this panel rather than a line of body text. It is
            what a stranger at the kerb cannot know. */}
        <p className="eyebrow">{t('ride.pinTitle')}</p>
        <p
          className="pin-display"
          aria-label={
            en
              ? `Your pickup PIN is ${ride?.pin ?? 'not ready'}`
              : `Votre code de prise en charge est ${ride?.pin ?? 'indisponible'}`
          }
        >
          {ride?.pin ?? '----'}
        </p>
        <p className="section-note">{t('ride.pinNote')}</p>
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
          {sosState === 'sent'
            ? en ? 'Emergency alert sent' : 'Alerte envoyee'
            : t('ride.emergency')}
        </button>
        {sosState === 'sent' ? (
          <p className="section-note">
            {en
              ? 'An evidence snapshot has been sealed. It cannot be altered.'
              : "Un instantane de preuve a ete scelle. Il ne peut plus etre modifie."}
          </p>
        ) : null}
        {sosState === 'failed' ? (
          <p className="form-error">
            {en ? 'Could not send. Try again.' : "Envoi impossible. Reessayez."}
          </p>
        ) : null}

        <button
          className="secondary-button"
          type="button"
          onClick={() => setCancelling(true)}
        >
          {t('ride.cancel')}
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
