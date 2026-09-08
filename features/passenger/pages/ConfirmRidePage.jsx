import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import PageHeader from '../../shared/components/PageHeader';
import { apiFetch } from '../../map/services/apiClient';
import { getLocale } from '../../shared/services/locale';
import { createRide } from '../services/ridesApi';
import {
  clearBookingAttempt,
  clearPendingBooking,
  getBookingAttempt,
  getPendingBooking,
  setActiveRide,
  setBookingAttempt,
} from '../services/rideState';

/**
 * The last screen before a ride exists.
 *
 * **The needs the passenger chose are sent from here.** They were collected on
 * the booking screen, carried this far in `pendingBooking`, and then dropped:
 * `createRide` never sent them, so the picker was a form that did nothing and
 * the driver screen that reads them always rendered empty. The whole
 * accessibility feature was broken in the middle of its own chain.
 *
 * They are shown again before confirming rather than only submitted, because
 * this is a request made of another person and the passenger should see what
 * they are about to ask for.
 */

function createIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function ConfirmRidePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const locale = getLocale();
  const en = locale === 'en';
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [hintMessage, setHintMessage] = useState('');
  const [catalogue, setCatalogue] = useState([]);

  const pendingBooking = useMemo(() => {
    return location.state?.pendingBooking ?? getPendingBooking();
  }, [location.state]);

  const needs = pendingBooking?.needs ?? [];
  const needsNote = pendingBooking?.needsNote ?? '';

  useEffect(() => {
    if (needs.length === 0) return;
    apiFetch('/ride-needs')
      .then((data) => setCatalogue(data.needs ?? []))
      .catch(() => setCatalogue([]));
  }, [needs.length]);

  const chosen = catalogue
    .filter((n) => needs.includes(n.key))
    .map((n) => (en ? n.label_en : n.label_fr));

  const handleConfirmRide = async () => {
    if (!pendingBooking?.quote?.quoteId) {
      setErrorMessage(
        en
          ? 'This quote is missing. Go back and request a new one.'
          : 'Ce tarif est introuvable. Revenez en arriere et demandez-en un nouveau.',
      );
      return;
    }

    const previousAttempt = getBookingAttempt();
    const shouldReuseKey = previousAttempt?.quoteId === pendingBooking.quote.quoteId;
    const idempotencyKey = shouldReuseKey
      ? previousAttempt.idempotencyKey
      : createIdempotencyKey();

    setBookingAttempt({ quoteId: pendingBooking.quote.quoteId, idempotencyKey });
    setLoading(true);
    setErrorMessage('');
    setHintMessage('');

    try {
      const response = await createRide({
        quoteId: pendingBooking.quote.quoteId,
        seats: pendingBooking.seats,
        idempotencyKey,
        rideNeeds: needs,
        needsNote,
      });

      setActiveRide(response.ride);
      clearPendingBooking();
      clearBookingAttempt();
      navigate('/passenger/searching', { state: { rideId: response.ride.id } });
    } catch (error) {
      setErrorMessage(error.message);

      // The hint is the recovery, not a restatement of the error. The API has
      // already said what went wrong, in the right language.
      const hints = {
        QUOTE_ALREADY_USED: en
          ? 'Request a new quote to continue.'
          : 'Demandez un nouveau tarif pour continuer.',
        QUOTE_EXPIRED: en
          ? 'Go back and request a new quote.'
          : 'Revenez en arriere et demandez un nouveau tarif.',
        OUTSTANDING_BALANCE: en
          ? 'Settle what you owe with your driver, then book again.'
          : 'Reglez ce que vous devez avec votre chauffeur, puis reservez a nouveau.',
        NO_DRIVERS_AVAILABLE: en
          ? 'No driver is free nearby right now. Try again shortly.'
          : "Aucun chauffeur n'est libre a proximite. Reessayez dans un instant.",
      };

      setHintMessage(
        hints[error.code] ??
          (en
            ? 'You can retry this booking with the same request key.'
            : 'Vous pouvez reessayer cette reservation avec la meme cle.'),
      );
    } finally {
      setLoading(false);
    }
  };

  if (!pendingBooking) {
    return (
      <main className="app-shell">
        <PageHeader
          title={en ? 'Confirm your ride' : 'Confirmez votre course'}
          fallback="/passenger/book"
        />
        <p className="section-note">
          {en
            ? 'No quote is available. Go back and request one first.'
            : "Aucun tarif disponible. Revenez en arriere et demandez-en un d'abord."}
        </p>
        <button
          className="primary-button"
          onClick={() => navigate('/passenger/book')}
        >
          {en ? 'Back to the map' : 'Retour a la carte'}
        </button>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <PageHeader
        eyebrow={en ? 'Almost there' : 'Presque fini'}
        title={en ? 'Confirm your ride' : 'Confirmez votre course'}
        fallback="/passenger/book"
      />

      <p className="eyebrow">{en ? 'Route' : 'Trajet'}</p>

      <div className="fact-row">
        <span>{en ? 'From' : 'Depart'}</span>
        <strong>
          {pendingBooking.pickup.name ?? pendingBooking.pickup.label ?? '-'}
        </strong>
      </div>
      <div className="fact-row">
        <span>{en ? 'To' : 'Arrivee'}</span>
        <strong>
          {pendingBooking.dropoff.name ?? pendingBooking.dropoff.label ?? '-'}
        </strong>
      </div>
      <div className="fact-row">
        <span>{en ? 'Distance' : 'Distance'}</span>
        <strong>
          {pendingBooking.quote.distanceKm.toFixed(1)} km,{' '}
          {Math.round(pendingBooking.quote.durationMin)} min
        </strong>
      </div>
      <div className="fact-row">
        <span>{en ? 'Seats' : 'Places'}</span>
        <strong>{pendingBooking.seats}</strong>
      </div>
      <div className="fact-row">
        <span>{en ? 'Fare' : 'Tarif'}</span>
        <strong>{pendingBooking.quote.fareXaf.toLocaleString()} FCFA</strong>
      </div>

      {chosen.length > 0 || needsNote ? (
        <>
          <p className="eyebrow">
            {en ? 'You are asking the driver for' : 'Vous demandez au chauffeur'}
          </p>
          <ul className="driver-needs">
            {chosen.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
          {needsNote ? <p className="driver-needs__note">{needsNote}</p> : null}
        </>
      ) : null}

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {hintMessage ? <p className="section-note">{hintMessage}</p> : null}

      <button
        className="primary-button"
        onClick={handleConfirmRide}
        disabled={loading}
      >
        {loading
          ? en ? 'Confirming...' : 'Confirmation...'
          : en ? 'Confirm ride' : 'Confirmer la course'}
      </button>
    </main>
  );
}
