import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { createRide } from '../services/ridesApi';
import {
  clearBookingAttempt,
  clearPendingBooking,
  getBookingAttempt,
  getPendingBooking,
  setActiveRide,
  setBookingAttempt,
} from '../services/rideState';

function createIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function ConfirmRidePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [hintMessage, setHintMessage] = useState('');

  const pendingBooking = useMemo(() => {
    return location.state?.pendingBooking ?? getPendingBooking();
  }, [location.state]);

  const handleConfirmRide = async () => {
    if (!pendingBooking?.quote?.quoteId) {
      setErrorMessage('This quote is missing. Please go back and request a new one.');
      return;
    }

    const previousAttempt = getBookingAttempt();
    const shouldReuseKey = previousAttempt?.quoteId === pendingBooking.quote.quoteId;
    const idempotencyKey = shouldReuseKey ? previousAttempt.idempotencyKey : createIdempotencyKey();

    setBookingAttempt({ quoteId: pendingBooking.quote.quoteId, idempotencyKey });
    setLoading(true);
    setErrorMessage('');
    setHintMessage('');

    try {
      const response = await createRide({
        quoteId: pendingBooking.quote.quoteId,
        seats: pendingBooking.seats,
        idempotencyKey,
      });

      setActiveRide(response.ride);
      clearPendingBooking();
      clearBookingAttempt();
      navigate('/passenger/searching', { state: { rideId: response.ride.id } });
    } catch (error) {
      setErrorMessage(error.message);

      switch (error.code) {
        case 'QUOTE_ALREADY_USED':
          setHintMessage('This quote has already been used. Request a new quote to continue.');
          break;
        case 'QUOTE_EXPIRED':
          setHintMessage('This quote has expired. Go back and request a new quote.');
          break;
        case 'OUTSTANDING_BALANCE':
          setHintMessage('Your account has an outstanding balance that must be settled before booking.');
          break;
        case 'NO_DRIVERS_AVAILABLE':
          setHintMessage('No drivers are currently available nearby. Please try again shortly.');
          break;
        default:
          setHintMessage('You can retry this booking with the same request key.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <h1>Confirm your ride</h1>
      {pendingBooking ? (
        <>
          <div className="ride-summary">
            <p><strong>From:</strong> {pendingBooking.pickup.name ?? pendingBooking.pickup.label ?? 'Pickup point'}</p>
            <p><strong>To:</strong> {pendingBooking.dropoff.name ?? pendingBooking.dropoff.label ?? 'Drop-off point'}</p>
            <p>
              <strong>Distance:</strong> {pendingBooking.quote.distanceKm.toFixed(1)} km
              {' '}·{' '}
              {Math.round(pendingBooking.quote.durationMin)} min
            </p>
            <p><strong>Fare:</strong> {pendingBooking.quote.fareXaf.toLocaleString()} FCFA</p>
          </div>
          {errorMessage ? <p>{errorMessage}</p> : null}
          {hintMessage ? <p>{hintMessage}</p> : null}
          <div className="button-row">
            <button className="secondary-button" onClick={() => navigate('/passenger/book')} disabled={loading}>
              Back
            </button>
            <button className="primary-button" onClick={handleConfirmRide} disabled={loading}>
              {loading ? 'Confirming...' : 'Confirm ride'}
            </button>
          </div>
        </>
      ) : (
        <>
          <p>No quote is available. Please go back and request a quote first.</p>
          <button className="primary-button" onClick={() => navigate('/passenger/book')}>
            Back to map
          </button>
        </>
      )}
    </main>
  );
}