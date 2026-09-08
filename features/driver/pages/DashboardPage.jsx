import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import NotificationBell from '../../shared/components/NotificationBell';
import Icon from '../../shared/components/Icon';
import { getLocale } from '../../shared/services/locale';
import { goOffline, goOnline, listDriverOffers } from '../services/driverApi';
import {
  clearActiveOffer,
  getDutyState,
  setActiveOffer,
  setDutyState,
} from '../services/driverState';
import DriverNav from '../components/DriverNav';

// Yaounde city centre. Used only when the browser will not give a position,
// so a driver on a laptop can still be matched during a demo.
const FALLBACK = { lat: 3.8656, lng: 11.5155 };

/**
 * The driver's home screen.
 *
 * **Going online now reaches the server.** It was local state: the button lit
 * up, `driver_presence` was never written, the matcher never saw the driver,
 * and offers never arrived. A driver would have sat on "Available" waiting for
 * work that was never sent to them, with nothing on screen to explain it.
 *
 * Offers are polled rather than pushed. The driver socket exists and carries
 * live location the other way, but a five-second poll is a few lines, cannot
 * silently die, and at demo scale is indistinguishable to the person watching.
 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const locale = getLocale();
  const [online, setOnline] = useState(getDutyState);
  const [offers, setOffers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const en = locale === 'en';

  const loadOffers = useCallback(async () => {
    try {
      const response = await listDriverOffers();
      setOffers(response.offers ?? []);
      setErrorMessage('');
    } catch (error) {
      setErrorMessage(error.message);
    }
  }, []);

  useEffect(() => {
    loadOffers();
    if (!online) return undefined;

    const timer = setInterval(loadOffers, 5000);
    return () => clearInterval(timer);
  }, [loadOffers, online]);

  const toggle = async () => {
    setBusy(true);
    setErrorMessage('');

    try {
      if (online) {
        await goOffline();
        setOnline(false);
        setDutyState(false);
        setOffers([]);
        return;
      }

      // A real position where the browser gives one, the city centre where it
      // refuses. Without a position there is nothing to match against.
      const position = await new Promise((resolve) => {
        if (!navigator.geolocation) return resolve(FALLBACK);
        navigator.geolocation.getCurrentPosition(
          (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
          () => resolve(FALLBACK),
          { timeout: 4000 },
        );
      });

      await goOnline({ ...position, seatsFree: 4 });
      setOnline(true);
      setDutyState(true);
      loadOffers();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const openOffer = (offer) => {
    setActiveOffer(offer);
    navigate('/driver/request', { state: { offer } });
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">{en ? 'Driver' : 'Chauffeur'}</p>
          <h1 className="headline">
            {online ? (en ? 'On duty' : 'En service') : en ? 'Off duty' : 'Hors service'}
          </h1>
        </div>
        <NotificationBell />
      </header>

      <button
        type="button"
        className={online ? 'duty-toggle is-on' : 'duty-toggle'}
        onClick={toggle}
        disabled={busy}
        aria-pressed={online}
      >
        <span className="duty-toggle__dot" />
        <span>
          {busy
            ? en ? 'Working...' : 'Patientez...'
            : online
              ? en ? 'You are visible to passengers' : 'Vous etes visible'
              : en ? 'Go online to receive rides' : 'Passez en ligne pour recevoir des courses'}
        </span>
      </button>

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

      <p className="eyebrow">
        {en ? 'Incoming requests' : 'Demandes entrantes'}
        {offers.length > 0 ? ` (${offers.length})` : ''}
      </p>

      {offers.length === 0 ? (
        <div className="empty-state">
          <Icon name="route" size={26} />
          <p>
            {online
              ? en
                ? 'Nothing yet. New requests appear here as they come in.'
                : 'Rien pour le moment. Les demandes apparaitront ici.'
              : en
                ? 'You are off duty. Go online to receive requests.'
                : 'Vous etes hors service. Passez en ligne pour recevoir des demandes.'}
          </p>
        </div>
      ) : (
        <ul className="offer-list">
          {offers.map((offer) => (
            <li key={offer.id}>
              <button type="button" onClick={() => openOffer(offer)}>
                <span className="offer-list__head">
                  <span className="offer-list__fare">
                    {offer.fare_xaf?.toLocaleString()} FCFA
                  </span>
                  <span className="offer-list__mode">
                    {offer.mode === 'corridor'
                      ? en ? 'Shared' : 'Partage'
                      : en ? 'Exclusive' : 'Prive'}
                  </span>
                </span>

                <span className="offer-list__leg">
                  <Icon name="pin" size={16} />
                  {offer.pickup?.label}
                </span>
                <span className="offer-list__leg">
                  <Icon name="arrow" size={16} />
                  {offer.dropoff?.label}
                </span>

                <span className="offer-list__meta">
                  {Math.round((offer.distance_to_pickup_m ?? 0) / 100) / 10} km{' '}
                  {en ? 'away' : 'du depart'}
                  {offer.accessibility_required?.length
                    ? ` - ${offer.accessibility_required.length} ${en ? 'requirement' : 'exigence'}`
                    : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <DriverNav />
    </main>
  );
}
