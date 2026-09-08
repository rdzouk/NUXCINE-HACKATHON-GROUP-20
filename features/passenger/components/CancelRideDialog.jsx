import { useState } from 'react';
import { cancelRide } from '../services/ridesApi';

/**
 * Cancelling, with the fee stated before it is charged.
 *
 * The amount is not shown up front because it cannot be known up front. A fee
 * applies only once a driver has been assigned and the server's own trace
 * shows they actually moved toward the pickup, so the client would be guessing.
 * It asks, then reports what the server decided and why.
 *
 * That "why" is the point. A charge with no reason attached reads as a
 * platform taking money; "the driver had already driven toward you" reads as
 * the driver being paid for work done, which is what it is.
 */
export default function CancelRideDialog({ rideId, onCancelled, onDismiss }) {
  const [reason, setReason] = useState('changed_mind');
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  const confirm = async () => {
    setSubmitting(true);
    setErrorMessage('');
    try {
      const result = await cancelRide(rideId, reason);
      setOutcome(result);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (outcome) {
    const fee = outcome.fee_xaf ?? 0;

    return (
      <div className="dialog" role="dialog" aria-label="Ride cancelled">
        <h2>Ride cancelled</h2>
        {fee > 0 ? (
          <>
            <p className="dialog__amount">{fee.toLocaleString()} FCFA</p>
            <p>
              {outcome.fee_reason
                ? outcome.fee_reason
                : 'Your driver had already set off toward you.'}
            </p>
            <p className="section-note">
              This is owed to the driver, not to us. Settle it on your next
              trip; until then you cannot book again.
            </p>
          </>
        ) : (
          <p>No fee. Nobody had set off yet.</p>
        )}
        <button className="primary-button" type="button" onClick={onCancelled}>
          Done
        </button>
      </div>
    );
  }

  return (
    <div className="dialog" role="dialog" aria-label="Cancel this ride">
      <h2>Cancel this ride?</h2>
      <p>
        If a driver has already set off toward you, a fee may apply. You will
        see the amount and the reason before this screen closes.
      </p>

      <label htmlFor="cancel-reason">Why are you cancelling?</label>
      <select
        id="cancel-reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      >
        <option value="changed_mind">I no longer need the ride</option>
        <option value="driver_too_far">The driver is too far away</option>
        <option value="waited_too_long">I have waited too long</option>
        <option value="wrong_address">I entered the wrong address</option>
      </select>

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

      <div className="button-row">
        <button
          className="primary-button"
          type="button"
          onClick={confirm}
          disabled={submitting}
        >
          {submitting ? 'Cancelling...' : 'Cancel the ride'}
        </button>
        <button className="secondary-button" type="button" onClick={onDismiss}>
          Keep the ride
        </button>
      </div>
    </div>
  );
}
