import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import SearchBeacon from '../../shared/components/SearchBeacon';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';
import { usePassengerRideSocket } from '../hooks/usePassengerRideSocket';
import { getActiveRide } from '../services/rideState';

export default function SearchingDriverPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeRide = getActiveRide();
  const rideId = location.state?.rideId ?? activeRide?.id ?? null;
  const { status, error } = usePassengerRideSocket(rideId);
  const en = getLocale() === 'en';

  useEffect(() => {
    if (!rideId) {
      navigate('/passenger/book', { replace: true });
      return;
    }

    if (status === 'accepted' || status === 'arriving' || status === 'arrived') {
      navigate('/passenger/driver-enroute', { replace: true });
    }
  }, [navigate, rideId, status]);

  // What the server is actually doing, said plainly. Matching widens in rings
  // and gives up at sixty seconds, so the screen reports which ring it is on
  // rather than showing an unbounded spinner.
  const detail = {
    requested: en ? 'Sending your request' : 'Envoi de votre demande',
    matching: t('ride.findingNote'),
    accepted: en ? 'A driver accepted' : 'Un chauffeur a accepte',
  }[status] ?? t('ride.findingNote');

  return (
    <main className="app-shell centered">
      <SearchBeacon
        label={t('ride.finding')}
        detail={error ? error : detail}
      />
      {error ? null : (
        <p className="section-note">
          {en
            ? 'This updates on its own the moment a driver accepts. You do not need to refresh.'
            : "Cet ecran se met a jour tout seul des qu'un chauffeur accepte. Inutile de rafraichir."}
        </p>
      )}
    </main>
  );
}