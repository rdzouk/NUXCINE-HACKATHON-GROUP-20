import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../../map/components/MapView';
import PlaceSearch from '../../map/components/PlaceSearch';
import RouteLayer from '../../map/components/RouteLayer';
import EtaPriceCard from '../../map/components/EtaPriceCard';
import { useGeolocation } from '../../map/hooks/useGeolocation';
import { useRoute } from '../../map/hooks/useRoute';
import { clearBookingAttempt, setPendingBooking } from '../services/rideState';
import RideNeedsPicker from '../components/RideNeedsPicker';
import { getBalance } from '../services/ridesApi';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';

const MAX_SEATS = 3;

export default function MapBookingPage() {
  const { position } = useGeolocation();
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [mode, setMode] = useState('exclusive');
  const [seats, setSeats] = useState(1);
  const [owed, setOwed] = useState(0);
  const [needs, setNeeds] = useState([]);
  const [needsNote, setNeedsNote] = useState('');
  const { quote, loading, error, fetchQuote } = useRoute();
  const en = getLocale() === 'en';
  const navigate = useNavigate();

  // An outstanding cancellation debt blocks a new booking server-side, so say
  // so before the passenger picks a destination rather than after.
  useEffect(() => {
    getBalance()
      .then((b) => setOwed(b.outstanding_xaf ?? 0))
      .catch(() => setOwed(0));
  }, []);

  const pickup = origin ?? position;

  // Quote whenever both ends exist, in one effect, rather than from each
  // handler.
  //
  // It was per-handler, and each handler only quoted if the *other* end was
  // already set. Choosing the destination before the pickup therefore produced
  // no fare at all: the destination handler saw no pickup and did nothing, and
  // the pickup handler had no quoting in it. That is the ordinary order on a
  // desktop, where location permission is refused and the home screen sends
  // you straight to the destination field, so the main screen of the app
  // showed nothing and said nothing about why.
  //
  // Both prices come from the server on every change. Corridor is priced per
  // seat on the distance actually travelled, so it is not a multiplication of
  // the exclusive fare and cannot be derived here (I2).
  useEffect(() => {
    if (!pickup || !destination) return;
    fetchQuote(pickup, destination, seats, mode);
  }, [
    fetchQuote,
    destination,
    mode,
    seats,
    pickup?.lat,
    pickup?.lng,
  ]);

  const chooseMode = (next) => {
    setMode(next);
    // Exclusive hire is the whole vehicle, so a seat count means nothing.
    setSeats(next === 'exclusive' ? 1 : seats);
  };

  const changeSeats = (delta) => {
    setSeats(Math.min(MAX_SEATS, Math.max(1, seats + delta)));
  };

  const handleConfirm = () => {
    if (!quote || !destination || !pickup) {
      return;
    }

    clearBookingAttempt();
    const pendingBooking = {
      pickup,
      dropoff: destination,
      quote,
      seats,
      mode,
      needs,
      needsNote,
    };
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
            {en
              ? `You owe ${owed.toLocaleString()} FCFA from a previous cancellation. Settle it with your driver before booking again.`
              : `Vous devez ${owed.toLocaleString()} FCFA suite a une annulation. Reglez avec votre chauffeur avant de reserver a nouveau.`}
          </p>
        ) : null}

        <PlaceSearch
          label={t('book.pickup')}
          defaultValue={position}
          near={position}
          onSelect={setOrigin}
        />
        <PlaceSearch
          label={t('book.destination')}
          hint={t('book.tryWarda')}
          near={pickup}
          onSelect={setDestination}
        />

        {!pickup ? (
          <p className="section-note">{t('book.setPickup')}</p>
        ) : null}

        {/* Bet 2. Shared is the transport model that already exists here, so
            it is offered as an equal choice rather than an upsell. */}
        <div
          className="mode-toggle"
          role="group"
          aria-label={en ? 'Ride type' : 'Type de course'}
        >
          <button
            type="button"
            className={mode === 'exclusive' ? 'mode-toggle__option is-selected' : 'mode-toggle__option'}
            aria-pressed={mode === 'exclusive'}
            onClick={() => chooseMode('exclusive')}
          >
            <span className="mode-toggle__name">{t('book.exclusive')}</span>
            <span className="mode-toggle__note">{t('book.exclusiveNote')}</span>
          </button>
          <button
            type="button"
            className={mode === 'corridor' ? 'mode-toggle__option is-selected' : 'mode-toggle__option'}
            aria-pressed={mode === 'corridor'}
            onClick={() => chooseMode('corridor')}
          >
            <span className="mode-toggle__name">{t('book.shared')}</span>
            <span className="mode-toggle__note">{t('book.sharedNote')}</span>
          </button>
        </div>

        {mode === 'corridor' ? (
          <div className="seat-stepper">
            <span id="seats-label">{t('book.seats')}</span>
            <button
              type="button"
              onClick={() => changeSeats(-1)}
              disabled={seats <= 1}
              aria-label={en ? 'One seat fewer' : 'Une place de moins'}
            >
              -
            </button>
            <output aria-labelledby="seats-label">{seats}</output>
            <button
              type="button"
              onClick={() => changeSeats(1)}
              disabled={seats >= MAX_SEATS}
              aria-label={en ? 'One seat more' : 'Une place de plus'}
            >
              +
            </button>
          </div>
        ) : null}

        <RideNeedsPicker
          value={needs}
          note={needsNote}
          onChange={(next, nextNote) => {
            setNeeds(next);
            setNeedsNote(nextNote ?? needsNote);
          }}
        />

        <EtaPriceCard quote={quote} loading={loading} error={error} mode={mode} seats={seats} />

        {quote && (
          <button className="primary-button" onClick={handleConfirm} disabled={owed > 0}>
            {mode === 'corridor'
              ? en
                ? `Book ${seats} seat${seats > 1 ? 's' : ''}`
                : `Reserver ${seats} place${seats > 1 ? 's' : ''}`
              : t('book.confirm')}
          </button>
        )}
      </div>
    </main>
  );
}
