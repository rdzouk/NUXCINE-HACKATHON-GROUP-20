import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { completeDriverRide, getDriverRide, startDriverRide } from '../services/driverApi';
import { getActiveDriverRide, setActiveDriverRide, setCompletedDriverRide } from '../services/driverState';
import OtpInput from '../../auth/components/OtpInput';
import RideInstructions from '../components/RideInstructions';

export default function RideInProgressPage() {
  const location = useLocation();
  const [pin, setPin] = useState('');
  const [started, setStarted] = useState(() => {
    const ride = getActiveDriverRide();
    return ride?.status === 'in_progress';
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [hintMessage, setHintMessage] = useState('');
  const navigate = useNavigate();
  const fallbackRide = getActiveDriverRide();
  const rideId = location.state?.rideId ?? fallbackRide?.id ?? null;

  const handleStartRide = async () => {
    if (!rideId) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');
    setHintMessage('');

    try {
      const response = await startDriverRide(rideId, pin.trim());
      setActiveDriverRide(response.ride);
      setStarted(true);
    } catch (error) {
      setErrorMessage(error.message);

      if (error.code === 'PIN_MISMATCH') {
        setHintMessage('PIN did not match. Ask the passenger to read the 4-digit PIN again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEndRide = async () => {
    if (!rideId) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const completion = await completeDriverRide(rideId);
      const freshRide = await getDriverRide(rideId);
      setActiveDriverRide(freshRide.ride);
      setCompletedDriverRide({
        ride: completion.ride,
        finalFareXaf: completion.final_fare_xaf,
      });
      navigate('/driver/end', { replace: true, state: { finalFareXaf: completion.final_fare_xaf } });
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="app-shell centered">
      {/* Shown before the trip starts, not after, because most of these have
          to be done before the passenger gets in: the seat moved, the windows
          up, the temperature set. */}
      <RideInstructions ride={fallbackRide} />

      {!started ? (
        <>
          <h2>Enter passenger PIN to start</h2>
          <p className="section-note">
            Ask the passenger to read you their four-digit code.
          </p>
          <OtpInput value={pin} onChange={setPin} length={4} disabled={isSubmitting} />
          <button className="primary-button" onClick={handleStartRide} disabled={isSubmitting || pin.length !== 4 || !rideId}>
            {isSubmitting ? 'Starting...' : 'Start ride'}
          </button>
          {hintMessage ? <p>{hintMessage}</p> : null}
        </>
      ) : (
        <>
          <h2>Ride in progress</h2>
          <p>Heading to destination</p>
          <button className="primary-button" onClick={handleEndRide} disabled={isSubmitting}>
            {isSubmitting ? 'Completing...' : 'End ride'}
          </button>
        </>
      )}
      {errorMessage ? <p>{errorMessage}</p> : null}
    </main>
  );
}