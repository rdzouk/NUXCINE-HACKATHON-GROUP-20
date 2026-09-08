import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';
import PlaceSearch from '../../map/components/PlaceSearch';
import RouteLayer from '../../map/components/RouteLayer';
import EtaPriceCard from '../../map/components/EtaPriceCard';
import { useGeolocation } from '../../map/hooks/useGeolocation';
import { useRoute } from '../../map/hooks/useRoute';
import { clearBookingAttempt, setPendingBooking } from '../services/rideState';
import { getBalance } from '../services/ridesApi';

const MAX_SEATS = 3;

export default function MapBookingPage() {
  const { position } = useGeolocation();
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [mode, setMode] = useState('exclusive');
  const [seats, setSeats] = useState(1);
  const [owed, setOwed] = useState(0);
  const { quote, loading, error, fetchQuote } = useRoute();
  const navigate = useNavigate();

  // An outstanding cancellation debt blocks a new booking server-side, so say
  // so before the passenger picks a destination rather than after.
  useEffect(() => {
    getBalance()
      .then((b) => setOwed(b.outstanding_xaf ?? 0))
      .catch(() => setOwed(0));
  }, []);

  const pickup = origin ?? position;

  // Re-quote whenever the mode or the seat count changes. The two prices are
  // not a client-side multiplication of one another: corridor is priced per
  // seat on the distance actually travelled, so only the server can say.
  const requote = (nextMode, nextSeats, dropoff = destination) => {
    // Silent when either end is missing, which is correct: the mode toggle is
    // usable before a destination is chosen, and re-quoting nothing is not an
    // error worth reporting.
    if (pickup && dropoff) {
      fetchQuote(pickup, dropoff, nextSeats, nextMode);
    }
  };

  const handleDestination = (place) => {
    setDestination(place);

    // Without a pickup there is nothing to price, and the first version simply
    // did nothing here. On a desktop, or wherever location permission is
    // refused, that looked exactly like a broken app: the destination was
    // chosen and no fare ever appeared, with nothing on screen to say why.
    if (pickup) {
      fetchQuote(pickup, place, seats, mode);
    }
  };

  const chooseMode = (next) => {
    setMode(next);
    // Exclusive hire is the whole vehicle, so a seat count means nothing.
    const nextSeats = next === 'exclusive' ? 1 : seats;
    setSeats(nextSeats);
    requote(next, nextSeats);
  };

  const changeSeats = (delta) => {
    const next = Math.min(MAX_SEATS, Math.max(1, seats + delta));
    setSeats(next);
    requote(mode, next);
  };

  const handleConfirm = () => {
    if (!quote || !destination || !pickup) {
      return;
    }

    clearBookingAttempt();
    const pendingBooking = { pickup, dropoff: destination, quote, seats, mode };
    setPendingBooking(pendingBooking);
    navigate('/passenger/confirm', { state: { pendingBooking } });
  };

  return (
    <main className="app-shell map-shell">
      <MapView center={position ?? { lat: 3.848, lng: 11.502 }}>
        <RouteLayer geometry={quote?.geometry} />
      </MapView>

      <div className="booking-panel">
        {owed > 0 ? (
          <p className="balance-banner">
            You owe {owed.toLocaleString()} FCFA from a previous cancellation.
            Settle it with your driver before booking again.
          </p>
        ) : null}

        <PlaceSearch label="Pickup" defaultValue={position} near={position} onSelect={setOrigin} />
        <PlaceSearch label="Destination" near={pickup} onSelect={handleDestination} />

        {!pickup ? (
          <p className="section-note">
            Set a pickup point first. We could not read your location, so
            search for the carrefour or quartier you are leaving from.
          </p>
        ) : null}

        {/* Bet 2. Shared is the transport model that already exists here, so
            it is offered as an equal choice rather than an upsell. */}
        <div className="mode-toggle" role="group" aria-label="Ride type">
          <button
            type="button"
            className={mode === 'exclusive' ? 'mode-toggle__option is-selected' : 'mode-toggle__option'}
            aria-pressed={mode === 'exclusive'}
            onClick={() => chooseMode('exclusive')}
          >
            <span className="mode-toggle__name">Exclusive</span>
            <span className="mode-toggle__note">The whole vehicle</span>
          </button>
          <button
            type="button"
            className={mode === 'corridor' ? 'mode-toggle__option is-selected' : 'mode-toggle__option'}
            aria-pressed={mode === 'corridor'}
            onClick={() => chooseMode('corridor')}
          >
            <span className="mode-toggle__name">Shared</span>
            <span className="mode-toggle__note">Pay for your seat</span>
          </button>
        </div>

        {mode === 'corridor' ? (
          <div className="seat-stepper">
            <span id="seats-label">Seats</span>
            <button
              type="button"
              onClick={() => changeSeats(-1)}
              disabled={seats <= 1}
              aria-label="One seat fewer"
            >
              -
            </button>
            <output aria-labelledby="seats-label">{seats}</output>
            <button
              type="button"
              onClick={() => changeSeats(1)}
              disabled={seats >= MAX_SEATS}
              aria-label="One seat more"
            >
              +
            </button>
          </div>
        ) : null}

        <EtaPriceCard quote={quote} loading={loading} error={error} mode={mode} seats={seats} />

        {quote && (
          <button className="primary-button" onClick={handleConfirm} disabled={owed > 0}>
            {mode === 'corridor' ? `Book ${seats} seat${seats > 1 ? 's' : ''}` : 'Confirm ride'}
          </button>
        )}
      </div>
    </main>
  );
}
